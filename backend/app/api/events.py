from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import date, datetime, time
from typing import List, Optional
from app.api.deps import get_current_user, require_roles
from app.core.rbac import Role
from app.api import schemas
from app.db.session import get_db
from app.models.event import Event
from app.models.user import User
from app.models.scenario import Scenario
from app.models.campaign import Campaign
from app.services.audit import record_event
from app.api.websocket import broadcast_analytics_update, broadcast_event

router = APIRouter(dependencies=[Depends(get_current_user)])

@router.post("/")
async def register_event(
    event: schemas.EventCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(Role.admin, Role.analyst, Role.trainee)),
):
    user_id = event.user_id or current_user.id
    audit_event = record_event(
        db,
        action=event.action,
        user_id=user_id,
        scenario_id=event.scenario_id,
        campaign_id=event.campaign_id,
        tenant_id=current_user.tenant_id,
    )
    db.commit()
    db.refresh(audit_event)
    await broadcast_event(
        "event_recorded",
        {"event_id": audit_event.id, "action": audit_event.action},
        current_user.tenant_id,
    )
    await broadcast_analytics_update({"refresh": True}, current_user.tenant_id)
    return audit_event


@router.get("/", response_model=List[schemas.EventOut])
def list_events(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    action_type: Optional[str] = Query(None, pattern="^(simulation|scenario|user|training)$"),
    user: Optional[str] = Query(None, min_length=1, max_length=120),
    campaign: Optional[str] = Query(None, min_length=1, max_length=120),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(Role.admin, Role.analyst, Role.viewer)),
):
    query = (
        db.query(
            Event.id,
            Event.action,
            Event.user_id,
            User.email.label("user_email"),
            Event.campaign_id,
            Event.scenario_id,
            Scenario.title.label("scenario_title"),
            Campaign.name.label("campaign_name"),
            Event.created_at,
        )
        .outerjoin(User, Event.user_id == User.id)
        .outerjoin(Scenario, Event.scenario_id == Scenario.id)
        .outerjoin(Campaign, Event.campaign_id == Campaign.id)
        .filter(Event.tenant_id == current_user.tenant_id)
    )
    if action_type == "simulation":
        query = query.filter(Event.action.in_(["phishing.mock_sent", "open", "email.open", "click", "report"]))
    elif action_type:
        query = query.filter(Event.action.like(f"{action_type}.%"))
    if user:
        query = query.filter(User.email.ilike(f"%{user.strip()}%"))
    if campaign:
        term = campaign.strip()
        query = query.filter((Campaign.name.ilike(f"%{term}%")) | (Scenario.title.ilike(f"%{term}%")))
    if date_from:
        query = query.filter(Event.created_at >= datetime.combine(date_from, time.min))
    if date_to:
        query = query.filter(Event.created_at <= datetime.combine(date_to, time.max))
    rows = query.order_by(Event.created_at.desc(), Event.id.desc()).offset(offset).limit(limit).all()
    return [
        {
            "id": row.id,
            "action": row.action,
            "user_id": row.user_id,
            "user_email": row.user_email,
            "campaign_id": row.campaign_id,
            "campaign_name": row.campaign_name,
            "scenario_id": row.scenario_id,
            "scenario_title": row.scenario_title,
            "created_at": row.created_at,
        }
        for row in rows
    ]
