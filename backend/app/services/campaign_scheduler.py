import asyncio
import logging
from datetime import datetime

from app.db.session import SessionLocal
from app.models.adaptive_program import AdaptiveProgram
from app.models.scenario import Scenario
from app.services.adaptive_programs import advance_program
from app.services.audit import record_event
from app.services.mock_campaigns import execute_mock_campaign

logger = logging.getLogger(__name__)
POLL_INTERVAL_SECONDS = 60


def run_due_mock_campaigns(now: datetime | None = None) -> int:
    """Execute scheduled mock campaigns that are due today or earlier."""
    execution_time = now or datetime.utcnow()
    due_date = execution_time.date().isoformat()
    db = SessionLocal()
    try:
        due_scenarios = [
            scenario
            for scenario in db.query(Scenario).all()
            if (scenario.indicators or {}).get("status") == "Scheduled"
            and (scenario.indicators or {}).get("scheduled_for")
            and (scenario.indicators or {}).get("scheduled_for") <= due_date
        ]
        for scenario in due_scenarios:
            recipients, audience = execute_mock_campaign(db, scenario, executed_at=execution_time)
            record_event(
                db,
                action="scenario.scheduled.executed",
                scenario_id=scenario.id,
                campaign_id=scenario.campaign_id,
                tenant_id=scenario.tenant_id,
            )
            logger.info(
                "Executed scheduled mock campaign id=%s audience=%s recipients=%s",
                scenario.id,
                audience,
                recipients,
            )
        db.commit()
        return len(due_scenarios)
    except Exception:
        db.rollback()
        logger.exception("Failed to execute due mock campaigns")
        return 0
    finally:
        db.close()


def _adaptive_transition_is_due(program: AdaptiveProgram, execution_time: datetime) -> bool:
    if program.status == "created":
        return bool(program.baseline_scheduled_at and program.baseline_scheduled_at <= execution_time)
    if program.status in {"baseline_sent", "adaptive_running"}:
        rounds_remaining = int(program.adaptive_round_index or 0) < max(1, int(program.adaptive_rounds or 1))
        if rounds_remaining:
            return bool(program.adaptive_scheduled_at and program.adaptive_scheduled_at <= execution_time)
        return bool(program.final_scheduled_at and program.final_scheduled_at <= execution_time)
    return program.status == "final_sent"


def run_due_adaptive_programs(now: datetime | None = None) -> int:
    """Advance each scheduled adaptive program by one due transition."""
    execution_time = now or datetime.utcnow()
    db = SessionLocal()
    advanced_count = 0
    try:
        programs = (
            db.query(AdaptiveProgram)
            .filter(AdaptiveProgram.status != "completed")
            .order_by(AdaptiveProgram.id.asc())
            .all()
        )
        for program in programs:
            if not _adaptive_transition_is_due(program, execution_time):
                continue
            result = advance_program(db, program=program, current_user_id=None)
            advanced_count += 1
            logger.info(
                "Advanced scheduled adaptive program id=%s transition=%s status=%s",
                program.id,
                result.stage,
                program.status,
            )
        db.commit()
        return advanced_count
    except Exception:
        db.rollback()
        logger.exception("Failed to advance due adaptive programs")
        return 0
    finally:
        db.close()


async def run_campaign_scheduler() -> None:
    while True:
        run_due_mock_campaigns()
        run_due_adaptive_programs()
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
