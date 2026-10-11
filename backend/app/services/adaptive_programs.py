from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.adaptive_program import AdaptiveProgram
from app.models.scenario import Scenario
from app.models.training_assignment import TrainingAssignment
from app.services.adaptive_training import build_stage_baseline, compare_common_campaigns, summarize_stage_baseline
from app.services.audit import record_event
from app.services.mock_campaigns import execute_mock_campaign


@dataclass
class AdaptiveProgramAdvanceResult:
    stage: str
    program: AdaptiveProgram
    payload: dict[str, Any]


def _load_tenant_scenario(db: Session, tenant_id: int, scenario_id: int) -> Scenario:
    scenario = (
        db.query(Scenario)
        .filter(Scenario.id == scenario_id)
        .filter(Scenario.tenant_id == tenant_id)
        .first()
    )
    if not scenario:
        raise ValueError(f"Scenario {scenario_id} not found for tenant")
    return scenario


def _dispatch_round(db: Session, program: AdaptiveProgram, tenant_id: int) -> dict[str, Any]:
    source_ids = [int(item) for item in (program.source_scenario_ids or []) if int(item) > 0]
    if not source_ids:
        source_ids = [program.baseline_scenario_id]

    stage_scenarios = {
        "easier": _load_tenant_scenario(db, tenant_id, program.easier_scenario_id),
        "same": _load_tenant_scenario(db, tenant_id, program.same_scenario_id),
        "harder": _load_tenant_scenario(db, tenant_id, program.harder_scenario_id),
    }
    if program.targeted_repetition_scenario_id:
        stage_scenarios["targeted_repetition"] = _load_tenant_scenario(
            db,
            tenant_id,
            program.targeted_repetition_scenario_id,
        )
    if program.slight_easier_scenario_id:
        stage_scenarios["slight_easier"] = _load_tenant_scenario(
            db,
            tenant_id,
            program.slight_easier_scenario_id,
        )

    metrics = build_stage_baseline(
        db,
        tenant_id=tenant_id,
        source_scenario_ids=source_ids,
    )

    grouped_user_ids = {
        "easier": [],
        "same": [],
        "harder": [],
        "targeted_repetition": [],
        "same_or_slightly_easier": [],
    }
    for item in metrics:
        grouped_user_ids.setdefault(item["recommended_action"], []).append(item["user_id"])

    routing = {
        "easier": "easier",
        "same": "same",
        "harder": "harder",
        "targeted_repetition": "targeted_repetition",
        "same_or_slightly_easier": "slight_easier",
    }

    sent_campaigns = []
    training_assignments_created = 0

    for action_key, user_ids in grouped_user_ids.items():
        if not user_ids:
            continue

        route_key = routing.get(action_key, "same")
        scenario = stage_scenarios.get(route_key) or stage_scenarios.get("same")
        if action_key == "targeted_repetition" and "targeted_repetition" not in stage_scenarios:
            scenario = stage_scenarios.get("easier") or scenario
        if action_key == "same_or_slightly_easier" and "slight_easier" not in stage_scenarios:
            scenario = stage_scenarios.get("easier") or scenario
        if not scenario:
            continue

        indicators = dict(scenario.indicators or {})
        indicators["user_target_ids"] = sorted(set(user_ids))
        indicators["adaptive_program_id"] = program.id
        indicators["adaptive_round"] = program.adaptive_round_index + 1
        indicators["adaptive_source_scenario_ids"] = source_ids
        scenario.indicators = indicators

        recipients, audience = execute_mock_campaign(db, scenario)
        sent_campaigns.append(
            {
                "recommended_action": action_key,
                "scenario_id": scenario.id,
                "recipients": recipients,
                "audience": audience,
            }
        )

        if action_key in {"easier", "targeted_repetition"}:
            for user_id in user_ids:
                existing_assignment = (
                    db.query(TrainingAssignment)
                    .filter(TrainingAssignment.tenant_id == tenant_id)
                    .filter(TrainingAssignment.user_id == user_id)
                    .filter(TrainingAssignment.title == "Phishing signal micro-learning")
                    .filter(TrainingAssignment.status != "Completed")
                    .first()
                )
                if existing_assignment:
                    continue
                assignment = TrainingAssignment(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    title="Phishing signal micro-learning",
                    assignment_type="Adaptive coaching",
                    status="Assigned",
                )
                db.add(assignment)
                record_event(
                    db,
                    action="training.assigned:adaptive_micro_learning",
                    user_id=user_id,
                    tenant_id=tenant_id,
                )
                training_assignments_created += 1

    next_source_ids = sorted(
        {
            int(campaign["scenario_id"])
            for campaign in sent_campaigns
            if campaign.get("scenario_id")
        }
    )

    payload = {
        "source_scenario_ids": source_ids,
        "summary": summarize_stage_baseline(metrics),
        "users": metrics,
        "sent_campaigns": sent_campaigns,
        "training_assignments_created": training_assignments_created,
        "next_source_scenario_ids": next_source_ids,
    }
    return payload


def advance_program(db: Session, *, program: AdaptiveProgram, current_user_id: int | None) -> AdaptiveProgramAdvanceResult:
    tenant_id = program.tenant_id

    if program.status == "created":
        baseline = _load_tenant_scenario(db, tenant_id, program.baseline_scenario_id)
        indicators = dict(baseline.indicators or {})
        indicators["adaptive_program_id"] = program.id
        indicators["adaptive_stage"] = "baseline"
        baseline.indicators = indicators
        recipients, audience = execute_mock_campaign(db, baseline)

        program.status = "baseline_sent"
        program.baseline_executed_at = datetime.utcnow()
        program.source_scenario_ids = [program.baseline_scenario_id]
        program.latest_campaigns = [
            {
                "stage": "baseline",
                "scenario_id": baseline.id,
                "recipients": recipients,
                "audience": audience,
            }
        ]

        record_event(
            db,
            action="adaptive_program.baseline_sent",
            user_id=current_user_id,
            scenario_id=baseline.id,
            tenant_id=tenant_id,
        )
        return AdaptiveProgramAdvanceResult(
            stage="baseline_sent",
            program=program,
            payload={
                "scenario_id": baseline.id,
                "recipients": recipients,
                "audience": audience,
            },
        )

    if program.status in {"baseline_sent", "adaptive_running"}:
        if program.adaptive_round_index < max(1, int(program.adaptive_rounds or 1)):
            dispatch_payload = _dispatch_round(db, program, tenant_id)
            program.adaptive_round_index = int(program.adaptive_round_index or 0) + 1
            program.status = "adaptive_running"
            if program.adaptive_executed_at is None:
                program.adaptive_executed_at = datetime.utcnow()
            program.source_scenario_ids = dispatch_payload["next_source_scenario_ids"] or program.source_scenario_ids
            program.latest_summary = dispatch_payload["summary"]
            program.latest_campaigns = dispatch_payload["sent_campaigns"]

            record_event(
                db,
                action="adaptive_program.round_dispatched",
                user_id=current_user_id,
                tenant_id=tenant_id,
            )
            return AdaptiveProgramAdvanceResult(
                stage="adaptive_round_dispatched",
                program=program,
                payload=dispatch_payload,
            )

        final_scenario = _load_tenant_scenario(db, tenant_id, program.final_scenario_id)
        indicators = dict(final_scenario.indicators or {})
        indicators["adaptive_program_id"] = program.id
        indicators["adaptive_stage"] = "final_common"
        final_scenario.indicators = indicators
        recipients, audience = execute_mock_campaign(db, final_scenario)
        program.status = "final_sent"
        program.final_executed_at = datetime.utcnow()
        program.latest_campaigns = [
            {
                "stage": "final_common",
                "scenario_id": final_scenario.id,
                "recipients": recipients,
                "audience": audience,
            }
        ]

        record_event(
            db,
            action="adaptive_program.final_sent",
            user_id=current_user_id,
            scenario_id=final_scenario.id,
            tenant_id=tenant_id,
        )
        return AdaptiveProgramAdvanceResult(
            stage="final_sent",
            program=program,
            payload={
                "scenario_id": final_scenario.id,
                "recipients": recipients,
                "audience": audience,
            },
        )

    if program.status == "final_sent":
        evaluation = compare_common_campaigns(
            db,
            tenant_id=tenant_id,
            baseline_scenario_id=program.baseline_scenario_id,
            final_scenario_id=program.final_scenario_id,
        )
        program.status = "completed"
        program.completed_at = datetime.utcnow()
        program.final_evaluation = evaluation

        record_event(
            db,
            action="adaptive_program.completed",
            user_id=current_user_id,
            tenant_id=tenant_id,
        )
        return AdaptiveProgramAdvanceResult(
            stage="completed",
            program=program,
            payload=evaluation,
        )

    return AdaptiveProgramAdvanceResult(
        stage="noop",
        program=program,
        payload={
            "message": "Program is already completed.",
        },
    )
