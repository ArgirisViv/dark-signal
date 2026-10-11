from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api import schemas
from app.api.deps import get_current_user, require_roles
from app.core.rbac import Role
from app.db.session import get_db
from app.models.campaign import Campaign
from app.models.adaptive_program import AdaptiveProgram
from app.models.campaign_recipient_snapshot import CampaignRecipientSnapshot
from app.models.event import Event
from app.models.scenario import Scenario
from app.models.user import User
from app.services.audit import record_event


router = APIRouter(dependencies=[Depends(get_current_user)])


def _load_campaign_for_tenant(db: Session, tenant_id: int, campaign_id: int) -> Campaign:
    campaign = (
        db.query(Campaign)
        .filter(Campaign.id == campaign_id)
        .filter(Campaign.tenant_id == tenant_id)
        .first()
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


def _load_scenarios_for_tenant(db: Session, tenant_id: int, scenario_ids: list[int]) -> list[Scenario]:
    scenarios = (
        db.query(Scenario)
        .filter(Scenario.tenant_id == tenant_id)
        .filter(Scenario.id.in_(scenario_ids))
        .all()
    )
    found_ids = {scenario.id for scenario in scenarios}
    missing = [scenario_id for scenario_id in scenario_ids if scenario_id not in found_ids]
    if missing:
        raise HTTPException(status_code=404, detail=f"Scenario(s) not found: {', '.join(str(item) for item in missing)}")
    return scenarios


def _serialize_campaign(db: Session, campaign: Campaign, include_scenarios: bool = True) -> dict:
    scenario_query = (
        db.query(Scenario)
        .filter(Scenario.campaign_id == campaign.id)
        .filter(Scenario.tenant_id == campaign.tenant_id)
        .order_by(Scenario.id.desc())
    )
    scenarios = scenario_query.all() if include_scenarios else []
    scenario_count = (
        db.query(Scenario.id)
        .filter(Scenario.campaign_id == campaign.id)
        .filter(Scenario.tenant_id == campaign.tenant_id)
        .count()
    )
    return {
        "id": campaign.id,
        "name": campaign.name,
        "description": campaign.description,
        "status": campaign.status,
        "scenario_count": scenario_count,
        "scenarios": scenarios,
    }


@router.get(
    "/",
    response_model=schemas.CampaignListResponse,
    summary="List campaigns",
    description="Return campaigns with their scenario counts and optional embedded scenarios.",
)
def list_campaigns(
    limit: Optional[int] = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None, min_length=1, max_length=120),
    status: Optional[str] = Query(None, min_length=1, max_length=50),
    include_scenarios: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.admin, Role.analyst, Role.viewer)),
):
    query = (
        db.query(Campaign)
        .filter(Campaign.tenant_id == current_user.tenant_id)
        .order_by(Campaign.id.desc())
    )
    campaigns = query.all()

    if search:
        term = search.strip().lower()
        filtered = []
        for campaign in campaigns:
            scenarios = (
                db.query(Scenario)
                .filter(Scenario.campaign_id == campaign.id)
                .filter(Scenario.tenant_id == current_user.tenant_id)
                .all()
            )
            haystack = " ".join(
                [
                    campaign.name,
                    campaign.description or "",
                    " ".join(scenario.title or "" for scenario in scenarios),
                ]
            ).lower()
            if term in haystack:
                filtered.append(campaign)
        campaigns = filtered

    if status:
        status_value = status.strip().lower()
        campaigns = [campaign for campaign in campaigns if (campaign.status or "").lower() == status_value]

    total = len(campaigns)
    if offset:
        campaigns = campaigns[offset:]
    if limit is not None:
        campaigns = campaigns[:limit]

    return {
        "items": [_serialize_campaign(db, campaign, include_scenarios=include_scenarios) for campaign in campaigns],
        "total": total,
        "limit": limit or total,
        "offset": offset,
        "has_more": (offset + (limit or total)) < total,
    }


@router.post(
    "/",
    response_model=schemas.CampaignOut,
    summary="Create campaign",
    description="Create a campaign and optionally attach existing scenarios.",
)
def create_campaign(
    payload: schemas.CampaignCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.admin, Role.analyst)),
):
    campaign = Campaign(
        tenant_id=current_user.tenant_id,
        name=payload.name,
        description=payload.description,
        status=payload.status,
    )
    db.add(campaign)
    db.flush()

    if payload.scenario_ids:
        scenarios = _load_scenarios_for_tenant(db, current_user.tenant_id, payload.scenario_ids)
        for scenario in scenarios:
            scenario.campaign_id = campaign.id

    record_event(
        db,
        action=f"campaign.created:{campaign.id}",
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        campaign_id=campaign.id,
    )
    db.commit()
    db.refresh(campaign)
    return _serialize_campaign(db, campaign, include_scenarios=True)


@router.get(
    "/{campaign_id}",
    response_model=schemas.CampaignOut,
    summary="Get campaign",
    description="Fetch a campaign with its scenarios.",
)
def get_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.admin, Role.analyst, Role.viewer)),
):
    campaign = _load_campaign_for_tenant(db, current_user.tenant_id, campaign_id)
    return _serialize_campaign(db, campaign, include_scenarios=True)


@router.patch(
    "/{campaign_id}",
    response_model=schemas.CampaignOut,
    summary="Update campaign",
    description="Update campaign metadata.",
)
def update_campaign(
    campaign_id: int,
    payload: schemas.CampaignUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.admin, Role.analyst)),
):
    campaign = _load_campaign_for_tenant(db, current_user.tenant_id, campaign_id)
    if payload.name is not None:
        campaign.name = payload.name
    if payload.description is not None:
        campaign.description = payload.description
    if payload.status is not None:
        campaign.status = payload.status
    record_event(
        db,
        action=f"campaign.updated:{campaign.id}",
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        campaign_id=campaign.id,
    )
    db.commit()
    db.refresh(campaign)
    return _serialize_campaign(db, campaign, include_scenarios=True)


@router.post(
    "/{campaign_id}/scenarios",
    response_model=schemas.CampaignOut,
    summary="Attach scenarios to campaign",
    description="Move existing scenarios into the selected campaign.",
)
def attach_campaign_scenarios(
    campaign_id: int,
    payload: schemas.CampaignAttachScenariosRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.admin, Role.analyst)),
):
    campaign = _load_campaign_for_tenant(db, current_user.tenant_id, campaign_id)
    scenarios = _load_scenarios_for_tenant(db, current_user.tenant_id, payload.scenario_ids)
    for scenario in scenarios:
        scenario.campaign_id = campaign.id
    record_event(
        db,
        action=f"campaign.scenarios.attached:{campaign.id}",
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        campaign_id=campaign.id,
    )
    db.commit()
    db.refresh(campaign)
    return _serialize_campaign(db, campaign, include_scenarios=True)


@router.delete(
    "/{campaign_id}",
    summary="Delete campaign",
    description="Delete a campaign together with its scenarios and dependent adaptive configurations.",
)
def delete_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.admin)),
):
    campaign = _load_campaign_for_tenant(db, current_user.tenant_id, campaign_id)
    scenarios = (
        db.query(Scenario)
        .filter(Scenario.campaign_id == campaign.id)
        .filter(Scenario.tenant_id == current_user.tenant_id)
        .all()
    )
    scenario_ids = [scenario.id for scenario in scenarios]

    adaptive_filters = [AdaptiveProgram.campaign_id == campaign.id]
    if scenario_ids:
        adaptive_filters.extend(
            [
                AdaptiveProgram.baseline_scenario_id.in_(scenario_ids),
                AdaptiveProgram.final_scenario_id.in_(scenario_ids),
                AdaptiveProgram.easier_scenario_id.in_(scenario_ids),
                AdaptiveProgram.same_scenario_id.in_(scenario_ids),
                AdaptiveProgram.harder_scenario_id.in_(scenario_ids),
                AdaptiveProgram.targeted_repetition_scenario_id.in_(scenario_ids),
                AdaptiveProgram.slight_easier_scenario_id.in_(scenario_ids),
            ]
        )
    dependent_programs = (
        db.query(AdaptiveProgram)
        .filter(AdaptiveProgram.tenant_id == current_user.tenant_id)
        .filter(or_(*adaptive_filters))
        .all()
    )
    for program in dependent_programs:
        db.delete(program)
    if dependent_programs:
        db.flush()

    # Keep historical audit records, but remove references to resources that
    # are being permanently deleted.
    if scenario_ids:
        db.query(Event).filter(Event.scenario_id.in_(scenario_ids)).update(
            {Event.scenario_id: None},
            synchronize_session=False,
        )
    db.query(Event).filter(Event.campaign_id == campaign.id).update(
        {Event.campaign_id: None},
        synchronize_session=False,
    )
    snapshot_filters = [CampaignRecipientSnapshot.campaign_id == campaign.id]
    if scenario_ids:
        snapshot_filters.append(CampaignRecipientSnapshot.scenario_id.in_(scenario_ids))
    snapshots_deleted = (
        db.query(CampaignRecipientSnapshot)
        .filter(or_(*snapshot_filters))
        .delete(synchronize_session=False)
    )

    for scenario in scenarios:
        db.delete(scenario)
    if scenarios:
        db.flush()

    record_event(
        db,
        action=f"campaign.deleted:{campaign.id}",
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        campaign_id=None,
    )
    db.delete(campaign)
    db.commit()
    return {
        "deleted": True,
        "campaign_id": campaign_id,
        "scenarios_deleted": len(scenarios),
        "recipient_snapshots_deleted": snapshots_deleted,
        "adaptive_programs_deleted": len(dependent_programs),
    }
