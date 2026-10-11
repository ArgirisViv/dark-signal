from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
from app.db.session import get_db
from app.models.campaign import Campaign
from app.models.scenario import Scenario
from app.models.event import Event
from app.models.campaign_recipient_snapshot import CampaignRecipientSnapshot
from app.models.email_template import EmailTemplate
from app.models.adaptive_program import AdaptiveProgram
from app.api import schemas
from app.api.deps import get_current_user, require_roles
from app.core.rbac import Role
from app.models.user import User
from app.services.audit import record_event
from app.services.mock_campaigns import build_recipient_interaction_urls, execute_mock_campaign

router = APIRouter(dependencies=[Depends(get_current_user)])

@router.get(
    "/",
    response_model=schemas.ScenarioListResponse,
    summary="List phishing scenarios",
    description="Return available phishing scenario templates and metadata.",
)
def list_scenarios(
    limit: Optional[int] = Query(None, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None, min_length=1, max_length=100),
    status: Optional[str] = Query(None, min_length=1, max_length=50),
    campaign_id: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.admin, Role.analyst, Role.viewer)),
):
    query = (
        db.query(Scenario)
        .filter(Scenario.tenant_id == current_user.tenant_id)
        .order_by(Scenario.id.desc())
    )
    if campaign_id is not None:
        rows = query.filter(Scenario.campaign_id == campaign_id).all()
    else:
        rows = query.all()

    if search:
        term = search.strip().lower()
        filtered = []
        for scenario in rows:
            indicators = scenario.indicators or {}
            campaign_name = None
            if scenario.campaign_id:
                campaign_name = (
                    db.query(Campaign.name)
                    .filter(Campaign.id == scenario.campaign_id)
                    .filter(Campaign.tenant_id == current_user.tenant_id)
                    .scalar()
                )
            candidates = [
                scenario.title,
                indicators.get("template"),
                indicators.get("audience"),
                campaign_name,
            ]
            haystack = " ".join([value for value in candidates if value]).lower()
            if term in haystack:
                filtered.append(scenario)
        rows = filtered

    if status:
        status_value = status.strip().lower()
        rows = [
            scenario
            for scenario in rows
            if (scenario.indicators or {}).get("status", "").lower() == status_value
        ]

    total = len(rows)
    if offset:
        rows = rows[offset:]
    if limit is not None:
        rows = rows[:limit]
    return {
        "items": rows,
        "total": total,
        "limit": limit or total,
        "offset": offset,
        "has_more": (offset + (limit or total)) < total,
    }


@router.post(
    "/",
    response_model=schemas.ScenarioOut,
    summary="Create scenario",
    description="Create a new phishing scenario.",
)
def create_scenario(
    payload: schemas.ScenarioCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.admin, Role.analyst)),
):
    campaign_id = payload.campaign_id
    if campaign_id is None:
        campaign = Campaign(
            tenant_id=current_user.tenant_id,
            name=payload.title,
            description="Auto-created campaign for a new scenario.",
            status=(payload.indicators or {}).get("status") or "Draft",
        )
        db.add(campaign)
        db.flush()
        campaign_id = campaign.id
    else:
        campaign = (
            db.query(Campaign)
            .filter(Campaign.id == campaign_id)
            .filter(Campaign.tenant_id == current_user.tenant_id)
            .first()
        )
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
    scenario = Scenario(
        title=payload.title,
        difficulty=payload.difficulty,
        indicators=payload.indicators,
        campaign_id=campaign_id,
        tenant_id=current_user.tenant_id,
    )
    db.add(scenario)
    db.flush()
    record_event(
        db,
        action=f"scenario.created:{scenario.id}",
        user_id=current_user.id,
        scenario_id=scenario.id,
        campaign_id=campaign_id,
        tenant_id=current_user.tenant_id,
    )
    db.commit()
    db.refresh(scenario)
    return scenario


@router.get(
    "/{scenario_id}",
    response_model=schemas.ScenarioOut,
    summary="Get scenario",
    description="Fetch a scenario by ID.",
)
def get_scenario(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.admin, Role.analyst, Role.viewer)),
):
    scenario = (
        db.query(Scenario)
        .filter(Scenario.id == scenario_id)
        .filter(Scenario.tenant_id == current_user.tenant_id)
        .first()
    )
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return scenario


@router.get(
    "/{scenario_id}/results",
    response_model=schemas.ScenarioResults,
    summary="Get results for a mock campaign",
)
def get_scenario_results(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.admin, Role.analyst, Role.viewer)),
):
    scenario = (
        db.query(Scenario)
        .filter(Scenario.id == scenario_id)
        .filter(Scenario.tenant_id == current_user.tenant_id)
        .first()
    )
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    campaign = None
    if scenario.campaign_id is not None:
        campaign = (
            db.query(Campaign)
            .filter(Campaign.id == scenario.campaign_id)
            .filter(Campaign.tenant_id == current_user.tenant_id)
            .first()
        )

    recipient_user_ids = {
        user_id
        for (user_id,) in db.query(User.id)
        .filter(User.tenant_id == current_user.tenant_id)
        .filter(User.role == Role.trainee.value)
        .all()
    }
    event_rows = (
        db.query(Event)
        .filter(Event.scenario_id == scenario.id)
        .filter(Event.tenant_id == current_user.tenant_id)
        .filter(Event.user_id.in_(recipient_user_ids))
        .order_by(Event.created_at.desc(), Event.id.desc())
        .all()
    )
    deliveries = sum(event.action == "phishing.mock_sent" for event in event_rows)
    opens = sum((event.action or "").lower() in {"open", "email.open"} for event in event_rows)
    clicks = sum("click" in (event.action or "").lower() for event in event_rows)
    reports = sum("report" in (event.action or "").lower() for event in event_rows)
    unique_recipients = len({event.user_id for event in event_rows if event.action == "phishing.mock_sent" and event.user_id})
    relevant_events = [
        event
        for event in event_rows
        if event.action == "phishing.mock_sent"
        or (event.action or "").lower() in {"open", "email.open"}
        or "click" in (event.action or "").lower()
        or "report" in (event.action or "").lower()
    ]
    user_ids = {event.user_id for event in relevant_events if event.user_id}
    users = db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else []
    emails_by_user_id = {user.id: user.email for user in users}
    latest_snapshot_time = (
        db.query(CampaignRecipientSnapshot.executed_at)
        .filter(CampaignRecipientSnapshot.scenario_id == scenario.id)
        .filter(CampaignRecipientSnapshot.tenant_id == current_user.tenant_id)
        .order_by(CampaignRecipientSnapshot.executed_at.desc())
        .first()
    )
    latest_run_recipients = []
    if latest_snapshot_time:
        snapshots = (
            db.query(CampaignRecipientSnapshot)
            .filter(CampaignRecipientSnapshot.scenario_id == scenario.id)
            .filter(CampaignRecipientSnapshot.tenant_id == current_user.tenant_id)
            .filter(CampaignRecipientSnapshot.executed_at == latest_snapshot_time[0])
            .order_by(CampaignRecipientSnapshot.email.asc())
            .all()
        )
        latest_run_recipients = [
            {
                "id": snapshot.id,
                "email": snapshot.email,
                "full_name": snapshot.full_name,
                "department": snapshot.department,
                "interaction_token": snapshot.interaction_token,
                "interaction_urls": build_recipient_interaction_urls(token=snapshot.interaction_token)
                if snapshot.interaction_token
                else {},
                "executed_at": snapshot.executed_at,
            }
            for snapshot in snapshots
        ]

    return {
        "scenario_id": scenario.id,
        "scenario_title": scenario.title or "Untitled scenario",
        "campaign_id": campaign.id if campaign else scenario.campaign_id,
        "campaign_name": campaign.name if campaign else None,
        "deliveries": deliveries,
        "unique_recipients": unique_recipients,
        "opens": opens,
        "clicks": clicks,
        "reports": reports,
        "open_rate": round(opens / deliveries * 100, 1) if deliveries else 0.0,
        "click_rate": round(clicks / deliveries * 100, 1) if deliveries else 0.0,
        "report_rate": round(reports / deliveries * 100, 1) if deliveries else 0.0,
        "latest_run_recipients": latest_run_recipients,
        "recent_responses": [
            {
                "id": event.id,
                "action": event.action,
                "user_email": emails_by_user_id.get(event.user_id),
                "created_at": event.created_at,
            }
            for event in relevant_events[:12]
        ],
    }


@router.patch(
    "/{scenario_id}",
    response_model=schemas.ScenarioOut,
    summary="Update scenario",
    description="Update scenario fields and metadata.",
)
def update_scenario(
    scenario_id: int,
    payload: schemas.ScenarioUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.admin, Role.analyst)),
):
    scenario = (
        db.query(Scenario)
        .filter(Scenario.id == scenario_id)
        .filter(Scenario.tenant_id == current_user.tenant_id)
        .first()
    )
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    if payload.title is not None:
        scenario.title = payload.title
    if payload.difficulty is not None:
        scenario.difficulty = payload.difficulty
    if payload.indicators is not None:
        scenario.indicators = payload.indicators
    if payload.campaign_id is not None:
        campaign = (
            db.query(Campaign)
            .filter(Campaign.id == payload.campaign_id)
            .filter(Campaign.tenant_id == current_user.tenant_id)
            .first()
        )
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        scenario.campaign_id = campaign.id
    record_event(
        db,
        action=f"scenario.updated:{scenario.id}",
        user_id=current_user.id,
        scenario_id=scenario.id,
        campaign_id=scenario.campaign_id,
        tenant_id=current_user.tenant_id,
    )
    db.commit()
    db.refresh(scenario)
    return scenario


@router.delete(
    "/{scenario_id}",
    summary="Delete scenario",
    description="Delete a scenario by ID.",
)
def delete_scenario(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.admin, Role.analyst)),
):
    scenario = (
        db.query(Scenario)
        .filter(Scenario.id == scenario_id)
        .filter(Scenario.tenant_id == current_user.tenant_id)
        .first()
    )
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    referenced_programs = (
        db.query(AdaptiveProgram)
        .filter(AdaptiveProgram.tenant_id == current_user.tenant_id)
        .filter(
            or_(
                AdaptiveProgram.baseline_scenario_id == scenario.id,
                AdaptiveProgram.final_scenario_id == scenario.id,
                AdaptiveProgram.easier_scenario_id == scenario.id,
                AdaptiveProgram.same_scenario_id == scenario.id,
                AdaptiveProgram.harder_scenario_id == scenario.id,
                AdaptiveProgram.targeted_repetition_scenario_id == scenario.id,
                AdaptiveProgram.slight_easier_scenario_id == scenario.id,
            )
        )
        .all()
    )

    # An adaptive program cannot remain valid when one of its required
    # scenarios is removed. Delete the dependent saved configuration first so
    # the explicit scenario deletion can complete without leaving broken
    # foreign-key references behind.
    for program in referenced_programs:
        db.delete(program)
    if referenced_programs:
        db.flush()

    # Preserve audit history without retaining a foreign-key reference to the
    # scenario. Recipient snapshots belong to the deleted scenario and are
    # removed with it.
    db.query(Event).filter(Event.scenario_id == scenario.id).update(
        {Event.scenario_id: None},
        synchronize_session=False,
    )
    db.query(CampaignRecipientSnapshot).filter(
        CampaignRecipientSnapshot.scenario_id == scenario.id
    ).delete(synchronize_session=False)

    record_event(
        db,
        action=f"scenario.deleted:{scenario.id}",
        user_id=current_user.id,
        scenario_id=None,
        campaign_id=scenario.campaign_id,
        tenant_id=current_user.tenant_id,
    )
    db.delete(scenario)
    db.commit()
    result = {"deleted": True, "scenario_id": scenario_id}
    if referenced_programs:
        result["adaptive_programs_deleted"] = len(referenced_programs)
    return result


@router.post(
    "/{scenario_id}/send-mock",
    response_model=schemas.MockPhishingSendResponse,
    summary="Send mock phishing emails",
    description="Simulate a phishing email send by logging mock delivery events without sending real emails.",
)
def send_mock_phishing(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.admin, Role.analyst)),
):
    scenario = (
        db.query(Scenario)
        .filter(Scenario.id == scenario_id)
        .filter(Scenario.tenant_id == current_user.tenant_id)
        .first()
    )
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    template_key = (scenario.indicators or {}).get("email_template_key")
    if template_key:
        template = db.query(EmailTemplate).filter(EmailTemplate.key == template_key).first()
        if template and template.approval_status != "approved":
            raise HTTPException(
                status_code=409,
                detail="Selected email template is still draft and must be approved before campaign send.",
            )

    recipients, audience = execute_mock_campaign(db, scenario)
    db.commit()
    db.refresh(scenario)

    return {
        "message": f"Mock phishing campaign completed for {recipients} users.",
        "scenario": scenario,
        "recipients": recipients,
        "audience": audience,
    }
