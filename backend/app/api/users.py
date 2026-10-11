from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import List, Optional
import secrets
from app.api import schemas
from app.db.session import get_db
from app.models.user import User
from app.models.event import Event
from app.models.campaign import Campaign
from app.models.scenario import Scenario
from app.models.adaptive_program import AdaptiveProgram
from app.models.alert_acknowledgement import AlertAcknowledgement
from app.models.campaign_recipient_snapshot import CampaignRecipientSnapshot
from app.models.training_assignment import TrainingAssignment
from app.models.training_module import TrainingModule
from app.core.security import get_password_hash
from app.api.deps import get_current_user, require_roles
from app.core.rbac import Role, normalize_role
from app.services.audit import record_event
from app.services.adaptive_training import (
    build_stage_baseline,
    compare_common_campaigns,
    summarize_stage_baseline,
)
from app.services.adaptive_programs import advance_program
from app.services.mock_campaigns import execute_mock_campaign

router = APIRouter(dependencies=[Depends(get_current_user)])

TRAINING_STATUSES = {"Assigned", "In progress", "Completed"}
ACCOUNT_ROLES = {Role.admin.value, Role.analyst.value, Role.viewer.value}


def _validated_account_role(value: Optional[str], default: str = Role.viewer.value) -> str:
    role = normalize_role(value) or default
    if role not in ACCOUNT_ROLES:
        raise HTTPException(status_code=422, detail=f"Unsupported role: {value}")
    return role


def _load_scenario_for_tenant(db: Session, tenant_id: int, scenario_id: int) -> Scenario:
    scenario = (
        db.query(Scenario)
        .filter(Scenario.id == scenario_id)
        .filter(Scenario.tenant_id == tenant_id)
        .first()
    )
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")
    return scenario


def _load_program_for_tenant(db: Session, tenant_id: int, program_id: int) -> AdaptiveProgram:
    program = (
        db.query(AdaptiveProgram)
        .filter(AdaptiveProgram.id == program_id)
        .filter(AdaptiveProgram.tenant_id == tenant_id)
        .first()
    )
    if not program:
        raise HTTPException(status_code=404, detail="Adaptive program not found")
    return program


def _serialize_program(program: AdaptiveProgram) -> dict:
    return {
        "id": program.id,
        "name": program.name,
        "status": program.status,
        "campaign_id": program.campaign_id,
        "baseline_scenario_id": program.baseline_scenario_id,
        "final_scenario_id": program.final_scenario_id,
        "easier_scenario_id": program.easier_scenario_id,
        "same_scenario_id": program.same_scenario_id,
        "harder_scenario_id": program.harder_scenario_id,
        "targeted_repetition_scenario_id": program.targeted_repetition_scenario_id,
        "slight_easier_scenario_id": program.slight_easier_scenario_id,
        "adaptive_rounds": program.adaptive_rounds,
        "adaptive_round_index": program.adaptive_round_index,
        "source_scenario_ids": [int(item) for item in (program.source_scenario_ids or [])],
        "latest_summary": program.latest_summary,
        "latest_campaigns": program.latest_campaigns or [],
        "final_evaluation": program.final_evaluation,
        "baseline_scheduled_at": program.baseline_scheduled_at,
        "adaptive_scheduled_at": program.adaptive_scheduled_at,
        "final_scheduled_at": program.final_scheduled_at,
        "baseline_executed_at": program.baseline_executed_at,
        "adaptive_executed_at": program.adaptive_executed_at,
        "final_executed_at": program.final_executed_at,
        "completed_at": program.completed_at,
        "created_at": program.created_at,
        "updated_at": program.updated_at,
    }


@router.post("/import-csv", summary="Import users parsed from a CSV file")
def import_users_csv(
    payload: schemas.UserCsvImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.admin)),
):
    created = []
    skipped = []
    seen = set()
    for row in payload.users:
        email = str(row.email).strip().lower()
        if email in seen:
            skipped.append({"email": email, "reason": "Duplicate row"})
            continue
        seen.add(email)
        existing = (
            db.query(User)
            .filter(func.lower(User.email) == email)
            .filter(User.tenant_id == current_user.tenant_id)
            .first()
        )
        if existing:
            skipped.append({"email": email, "reason": "User already exists"})
            continue
        user = User(
            email=email,
            hashed_password=get_password_hash(secrets.token_urlsafe(24)),
            role=Role.trainee.value,
            full_name=row.full_name,
            department=row.department,
            risk=row.risk,
            tenant_id=current_user.tenant_id,
        )
        db.add(user)
        db.flush()
        created.append({"id": user.id, "email": user.email})
    record_event(
        db,
        action=f"user.imported:{len(created)}",
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    db.commit()
    return {"created_count": len(created), "skipped_count": len(skipped), "created": created, "skipped": skipped}


@router.get(
    "/training-modules",
    response_model=List[schemas.TrainingModuleOut],
    summary="List training catalog modules",
)
def list_training_modules(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.admin)),
):
    return (
        db.query(TrainingModule)
        .filter(TrainingModule.tenant_id == current_user.tenant_id)
        .order_by(TrainingModule.title.asc())
        .all()
    )


@router.post(
    "/training-modules",
    response_model=schemas.TrainingModuleOut,
    status_code=201,
    summary="Create a training catalog module",
)
def create_training_module(
    payload: schemas.TrainingModuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.admin)),
):
    module = TrainingModule(tenant_id=current_user.tenant_id, **payload.model_dump())
    db.add(module)
    db.commit()
    db.refresh(module)
    return module


@router.get(
    "/{user_id}/risk-profile",
    response_model=schemas.UserRiskProfile,
    summary="Get user learning and risk profile",
)
def get_user_risk_profile(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.admin)),
):
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .filter(User.tenant_id == current_user.tenant_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    events = (
        db.query(Event)
        .filter(Event.user_id == user.id)
        .filter(Event.tenant_id == current_user.tenant_id)
        .order_by(Event.created_at.desc(), Event.id.desc())
        .all()
    )
    exposures = sum(event.action == "phishing.mock_sent" for event in events)
    clicks = sum("click" in (event.action or "").lower() for event in events)
    reports = sum("report" in (event.action or "").lower() for event in events)
    awareness_score = max(0, min(100, 50 + reports * 10 - clicks * 15))
    computed_risk = "High" if clicks >= 2 or (clicks > reports and clicks > 0) else "Medium" if clicks else "Low"
    recent_activity = [
        {
            "id": event.id,
            "action": event.action,
            "scenario_id": event.scenario_id,
            "created_at": event.created_at,
        }
        for event in events[:8]
    ]
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "department": user.department,
        "recorded_risk": user.risk,
        "computed_risk": computed_risk,
        "awareness_score": awareness_score,
        "exposures": exposures,
        "clicks": clicks,
        "reports": reports,
        "last_activity": events[0].created_at if events else None,
        "recent_activity": recent_activity,
    }


@router.get(
    "/{user_id}/risk-trend",
    response_model=List[schemas.UserRiskTrendPoint],
    summary="Get a user's cumulative simulation risk trend",
)
def get_user_risk_trend(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.admin)),
):
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .filter(User.tenant_id == current_user.tenant_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    events = (
        db.query(Event)
        .filter(Event.user_id == user.id)
        .filter(Event.tenant_id == current_user.tenant_id)
        .order_by(Event.created_at.asc(), Event.id.asc())
        .all()
    )
    events_by_date = {}
    for event in events:
        action = (event.action or "").lower()
        if "click" not in action and "report" not in action:
            continue
        event_date = event.created_at.date().isoformat() if event.created_at else "Unknown"
        events_by_date.setdefault(event_date, []).append(action)

    clicks = 0
    reports = 0
    trend = []
    for event_date, actions in events_by_date.items():
        clicks += sum("click" in action for action in actions)
        reports += sum("report" in action for action in actions)
        awareness_score = max(0, min(100, 50 + reports * 10 - clicks * 15))
        computed_risk = "High" if clicks >= 2 or (clicks > reports and clicks > 0) else "Medium" if clicks else "Low"
        trend.append({
            "date": event_date,
            "awareness_score": awareness_score,
            "computed_risk": computed_risk,
            "clicks": clicks,
            "reports": reports,
        })
    return trend


@router.post(
    "/adaptive-programs/baseline",
    summary="Evaluate baseline user readiness for adaptive phishing training",
)
def evaluate_adaptive_baseline(
    payload: schemas.AdaptiveBaselineRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.admin, Role.analyst)),
):
    source_ids = sorted(set(payload.source_scenario_ids))
    for scenario_id in source_ids:
        _load_scenario_for_tenant(db, current_user.tenant_id, scenario_id)

    metrics = build_stage_baseline(
        db,
        tenant_id=current_user.tenant_id,
        source_scenario_ids=source_ids,
    )
    return {
        "source_scenario_ids": source_ids,
        "summary": summarize_stage_baseline(metrics),
        "users": metrics,
    }


@router.post(
    "/adaptive-programs/dispatch",
    summary="Run adaptive user segmentation and dispatch the next campaign stage",
)
def dispatch_adaptive_stage(
    payload: schemas.AdaptiveStageDispatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.admin, Role.analyst)),
):
    source_ids = sorted(set(payload.source_scenario_ids))
    for scenario_id in source_ids:
        _load_scenario_for_tenant(db, current_user.tenant_id, scenario_id)

    stage_scenarios = {
        "easier": _load_scenario_for_tenant(db, current_user.tenant_id, payload.easier_scenario_id),
        "same": _load_scenario_for_tenant(db, current_user.tenant_id, payload.same_scenario_id),
        "harder": _load_scenario_for_tenant(db, current_user.tenant_id, payload.harder_scenario_id),
    }
    if payload.targeted_repetition_scenario_id:
        stage_scenarios["targeted_repetition"] = _load_scenario_for_tenant(
            db,
            current_user.tenant_id,
            payload.targeted_repetition_scenario_id,
        )
    if payload.slight_easier_scenario_id:
        stage_scenarios["slight_easier"] = _load_scenario_for_tenant(
            db,
            current_user.tenant_id,
            payload.slight_easier_scenario_id,
        )

    metrics = build_stage_baseline(
        db,
        tenant_id=current_user.tenant_id,
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
        key = item["recommended_action"]
        grouped_user_ids.setdefault(key, []).append(item["user_id"])

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
        scenario = stage_scenarios.get(route_key)
        if not scenario:
            scenario = stage_scenarios.get("same")
        if action_key == "targeted_repetition" and "targeted_repetition" not in stage_scenarios:
            scenario = stage_scenarios.get("easier") or scenario
        if action_key == "same_or_slightly_easier" and "slight_easier" not in stage_scenarios:
            scenario = stage_scenarios.get("easier") or scenario
        if not scenario:
            continue

        indicators = dict(scenario.indicators or {})
        indicators["user_target_ids"] = sorted(set(user_ids))
        indicators["adaptive_stage"] = payload.stage_label
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

        if payload.assign_training_for_low_readiness and action_key in {"easier", "targeted_repetition"}:
            for user_id in user_ids:
                existing_assignment = (
                    db.query(TrainingAssignment)
                    .filter(TrainingAssignment.tenant_id == current_user.tenant_id)
                    .filter(TrainingAssignment.user_id == user_id)
                    .filter(TrainingAssignment.title == "Phishing signal micro-learning")
                    .filter(TrainingAssignment.status != "Completed")
                    .first()
                )
                if existing_assignment:
                    continue
                assignment = TrainingAssignment(
                    tenant_id=current_user.tenant_id,
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
                    tenant_id=current_user.tenant_id,
                )
                training_assignments_created += 1

    db.commit()

    return {
        "stage_label": payload.stage_label,
        "source_scenario_ids": source_ids,
        "summary": summarize_stage_baseline(metrics),
        "sent_campaigns": sent_campaigns,
        "training_assignments_created": training_assignments_created,
        "users": metrics,
    }


@router.post(
    "/adaptive-programs/final-evaluation",
    summary="Compare common initial and final campaign performance",
)
def evaluate_final_common_campaign(
    payload: schemas.AdaptiveFinalEvaluationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.admin, Role.analyst)),
):
    _load_scenario_for_tenant(db, current_user.tenant_id, payload.baseline_scenario_id)
    _load_scenario_for_tenant(db, current_user.tenant_id, payload.final_scenario_id)
    return compare_common_campaigns(
        db,
        tenant_id=current_user.tenant_id,
        baseline_scenario_id=payload.baseline_scenario_id,
        final_scenario_id=payload.final_scenario_id,
    )


@router.get(
    "/adaptive-programs",
    response_model=List[schemas.AdaptiveProgramOut],
    summary="List saved adaptive programs",
)
def list_adaptive_programs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.admin, Role.analyst)),
):
    programs = (
        db.query(AdaptiveProgram)
        .filter(AdaptiveProgram.tenant_id == current_user.tenant_id)
        .order_by(AdaptiveProgram.updated_at.desc(), AdaptiveProgram.id.desc())
        .all()
    )
    return [_serialize_program(program) for program in programs]


@router.post(
    "/adaptive-programs",
    response_model=schemas.AdaptiveProgramOut,
    status_code=201,
    summary="Create persisted adaptive workflow program",
)
def create_adaptive_program(
    payload: schemas.AdaptiveProgramCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.admin, Role.analyst)),
):
    campaign = (
        db.query(Campaign)
        .filter(Campaign.id == payload.campaign_id)
        .filter(Campaign.tenant_id == current_user.tenant_id)
        .first()
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    scenario_ids = {
        payload.baseline_scenario_id,
        payload.final_scenario_id,
        payload.easier_scenario_id,
        payload.same_scenario_id,
        payload.harder_scenario_id,
    }
    if payload.targeted_repetition_scenario_id:
        scenario_ids.add(payload.targeted_repetition_scenario_id)
    if payload.slight_easier_scenario_id:
        scenario_ids.add(payload.slight_easier_scenario_id)

    for scenario_id in scenario_ids:
        scenario = _load_scenario_for_tenant(db, current_user.tenant_id, scenario_id)
        if scenario.campaign_id != campaign.id:
            raise HTTPException(
                status_code=422,
                detail=f"Scenario {scenario.id} does not belong to campaign {campaign.name}.",
            )

    def utc_naive(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    baseline_scheduled_at = utc_naive(payload.baseline_scheduled_at)
    adaptive_scheduled_at = utc_naive(payload.adaptive_scheduled_at)
    final_scheduled_at = utc_naive(payload.final_scheduled_at)
    scheduled_dates = [item for item in (baseline_scheduled_at, adaptive_scheduled_at, final_scheduled_at) if item]
    if scheduled_dates != sorted(scheduled_dates):
        raise HTTPException(
            status_code=422,
            detail="Stage schedule must follow Stage 1, Stage 2/3, then Stage 4.",
        )

    program = AdaptiveProgram(
        tenant_id=current_user.tenant_id,
        campaign_id=campaign.id,
        name=payload.name.strip(),
        status="created",
        baseline_scenario_id=payload.baseline_scenario_id,
        final_scenario_id=payload.final_scenario_id,
        easier_scenario_id=payload.easier_scenario_id,
        same_scenario_id=payload.same_scenario_id,
        harder_scenario_id=payload.harder_scenario_id,
        targeted_repetition_scenario_id=payload.targeted_repetition_scenario_id,
        slight_easier_scenario_id=payload.slight_easier_scenario_id,
        adaptive_rounds=payload.adaptive_rounds,
        adaptive_round_index=0,
        source_scenario_ids=[payload.baseline_scenario_id],
        baseline_scheduled_at=baseline_scheduled_at,
        adaptive_scheduled_at=adaptive_scheduled_at,
        final_scheduled_at=final_scheduled_at,
    )
    db.add(program)
    db.commit()
    db.refresh(program)
    return _serialize_program(program)


@router.get(
    "/adaptive-programs/{program_id}",
    response_model=schemas.AdaptiveProgramOut,
    summary="Get adaptive program",
)
def get_adaptive_program(
    program_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.admin, Role.analyst)),
):
    program = _load_program_for_tenant(db, current_user.tenant_id, program_id)
    return _serialize_program(program)


@router.post(
    "/adaptive-programs/{program_id}/advance",
    response_model=schemas.AdaptiveProgramAdvanceResponse,
    summary="Advance adaptive program to next automatic stage",
)
def advance_adaptive_program(
    program_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.admin, Role.analyst)),
):
    program = _load_program_for_tenant(db, current_user.tenant_id, program_id)
    try:
        result = advance_program(db, program=program, current_user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    db.commit()
    db.refresh(program)
    return {
        "stage": result.stage,
        "program": _serialize_program(program),
        "payload": result.payload,
    }


@router.get(
    "/{user_id}/training-assignments",
    response_model=List[schemas.TrainingAssignmentOut],
    summary="List a user's training assignments",
)
def list_training_assignments(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.admin)),
):
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .filter(User.tenant_id == current_user.tenant_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return (
        db.query(TrainingAssignment)
        .filter(TrainingAssignment.user_id == user.id)
        .filter(TrainingAssignment.tenant_id == current_user.tenant_id)
        .order_by(TrainingAssignment.created_at.desc(), TrainingAssignment.id.desc())
        .all()
    )


@router.post(
    "/{user_id}/training-assignments",
    response_model=schemas.TrainingAssignmentOut,
    status_code=201,
    summary="Assign training to a user",
)
def create_training_assignment(
    user_id: int,
    payload: schemas.TrainingAssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.admin)),
):
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .filter(User.tenant_id == current_user.tenant_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    module = None
    if payload.module_id is not None:
        module = (
            db.query(TrainingModule)
            .filter(TrainingModule.id == payload.module_id)
            .filter(TrainingModule.tenant_id == current_user.tenant_id)
            .first()
        )
        if not module:
            raise HTTPException(status_code=404, detail="Training module not found")
    if not module and not payload.title:
        raise HTTPException(status_code=422, detail="Choose a training module or provide an assignment title")
    assignment = TrainingAssignment(
        tenant_id=current_user.tenant_id,
        user_id=user.id,
        module_id=module.id if module else None,
        title=module.title if module else payload.title.strip(),
        assignment_type=module.module_type if module else payload.assignment_type.strip(),
    )
    db.add(assignment)
    record_event(
        db,
        action=f"training.assigned:{assignment.title}",
        user_id=user.id,
        tenant_id=current_user.tenant_id,
    )
    db.commit()
    db.refresh(assignment)
    return assignment


@router.patch(
    "/training-assignments/{assignment_id}",
    response_model=schemas.TrainingAssignmentOut,
    summary="Update a training assignment status",
)
def update_training_assignment(
    assignment_id: int,
    payload: schemas.TrainingAssignmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.admin)),
):
    status = payload.status.strip()
    if status not in TRAINING_STATUSES:
        raise HTTPException(status_code=422, detail="Invalid training assignment status")
    assignment = (
        db.query(TrainingAssignment)
        .filter(TrainingAssignment.id == assignment_id)
        .filter(TrainingAssignment.tenant_id == current_user.tenant_id)
        .first()
    )
    if not assignment:
        raise HTTPException(status_code=404, detail="Training assignment not found")
    assignment.status = status
    assignment.completed_at = datetime.utcnow() if status == "Completed" else None
    assignment.completion_score = payload.completion_score if status == "Completed" else None
    record_event(
        db,
        action=f"training.status:{status.lower().replace(' ', '_')}",
        user_id=assignment.user_id,
        tenant_id=current_user.tenant_id,
    )
    db.commit()
    db.refresh(assignment)
    return assignment


@router.get(
    "/",
    response_model=schemas.UserListResponse,
    summary="List users",
    description="Return all users in the system.",
)
def list_users(
    limit: Optional[int] = Query(None, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None, min_length=1, max_length=100),
    role: Optional[str] = Query(None, min_length=1, max_length=50),
    risk: Optional[str] = Query(None, min_length=1, max_length=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.admin)),
):
    role_counts = {
        role_name: count
        for role_name, count in db.query(User.role, func.count(User.id))
        .filter(User.tenant_id == current_user.tenant_id)
        .filter(User.role.in_(sorted(ACCOUNT_ROLES)))
        .group_by(User.role)
        .all()
    }
    query = (
        db.query(
            User,
            func.max(Event.created_at).label("last_activity"),
        )
        .outerjoin(Event, Event.user_id == User.id)
        .filter(User.tenant_id == current_user.tenant_id)
        .filter(User.role.in_(sorted(ACCOUNT_ROLES)))
        .group_by(User.id)
        .order_by(User.id.desc())
    )

    if search:
        like_term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                User.email.ilike(like_term),
                User.full_name.ilike(like_term),
                User.department.ilike(like_term),
            )
        )

    if role:
        query = query.filter(User.role == normalize_role(role))

    if risk:
        query = query.filter(func.lower(User.risk) == risk.strip().lower())

    total = query.count()

    if offset:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    rows = query.all()
    items = [
        {
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "full_name": user.full_name,
            "department": user.department,
            "risk": user.risk,
            "last_activity": last_activity,
        }
        for user, last_activity in rows
    ]
    return {
        "items": items,
        "total": total,
        "limit": limit or total,
        "offset": offset,
        "has_more": (offset + (limit or total)) < total,
        "role_counts": role_counts,
    }


@router.get(
    "/{user_id}",
    response_model=schemas.UserOut,
    summary="Get user by ID",
    description="Return a single user record by numeric ID.",
)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.admin)),
):
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .filter(User.tenant_id == current_user.tenant_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post(
    "/",
    response_model=schemas.UserOut,
    summary="Create user",
    description="Create a new user account.",
)
def create_user(
    payload: schemas.UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.admin)),
):
    normalized_email = str(payload.email).strip().lower()
    existing = (
        db.query(User)
        .filter(func.lower(User.email) == normalized_email)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="User already exists")
    user = User(
        email=normalized_email,
        hashed_password=get_password_hash(payload.password),
        role=_validated_account_role(payload.role),
        full_name=payload.full_name,
        department=None,
        risk=None,
        tenant_id=current_user.tenant_id,
    )
    db.add(user)
    db.flush()
    record_event(
        db,
        action=f"user.created:{user.id}",
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    db.commit()
    db.refresh(user)
    return user


@router.patch(
    "/{user_id}",
    response_model=schemas.UserOut,
    summary="Update user",
    description="Update a user's email or role.",
)
def update_user(
    user_id: int,
    payload: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.admin)),
):
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .filter(User.tenant_id == current_user.tenant_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if payload.email is not None:
        normalized_email = str(payload.email).strip().lower()
        duplicate = (
            db.query(User.id)
            .filter(func.lower(User.email) == normalized_email)
            .filter(User.id != user.id)
            .first()
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="Email address is already in use.")
        user.email = normalized_email
    if payload.role is not None:
        next_role = _validated_account_role(payload.role, user.role)
        if normalize_role(user.role) == Role.admin.value and next_role != Role.admin.value:
            admin_count = (
                db.query(func.count(User.id))
                .filter(User.tenant_id == current_user.tenant_id)
                .filter(func.lower(User.role) == Role.admin.value)
                .scalar()
            )
            if admin_count <= 1:
                raise HTTPException(
                    status_code=409,
                    detail="The final administrator account cannot be demoted.",
                )
        user.role = next_role
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.password:
        user.hashed_password = get_password_hash(payload.password)
    record_event(
        db,
        action=f"user.updated:{user.id}",
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    db.commit()
    db.refresh(user)
    return user


@router.delete(
    "/{user_id}",
    summary="Delete user",
    description="Delete a user by ID.",
)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.admin)),
):
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .filter(User.tenant_id == current_user.tenant_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_user.id:
        raise HTTPException(
            status_code=409,
            detail="You cannot delete the account you are currently signed in with.",
        )

    if normalize_role(user.role) == Role.admin.value:
        admin_count = (
            db.query(func.count(User.id))
            .filter(User.tenant_id == current_user.tenant_id)
            .filter(func.lower(User.role) == Role.admin.value)
            .scalar()
        )
        if admin_count <= 1:
            raise HTTPException(
                status_code=409,
                detail="The last administrator account cannot be deleted.",
            )

    # Preserve historical campaign and audit data without keeping a foreign-key
    # reference to an application account that is about to be removed.
    db.query(Event).filter(Event.user_id == user.id).update(
        {Event.user_id: None},
        synchronize_session=False,
    )
    db.query(CampaignRecipientSnapshot).filter(
        CampaignRecipientSnapshot.user_id == user.id
    ).update(
        {CampaignRecipientSnapshot.user_id: None},
        synchronize_session=False,
    )

    # Account-specific operational records have no meaning after the account is
    # removed and would otherwise prevent PostgreSQL from deleting the user.
    db.query(TrainingAssignment).filter(
        TrainingAssignment.user_id == user.id
    ).delete(synchronize_session=False)
    db.query(AlertAcknowledgement).filter(
        AlertAcknowledgement.acknowledged_by_user_id == user.id
    ).delete(synchronize_session=False)

    record_event(
        db,
        action=f"user.deleted:{user.id}",
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    db.delete(user)
    db.commit()
    return {"deleted": True, "user_id": user_id}
