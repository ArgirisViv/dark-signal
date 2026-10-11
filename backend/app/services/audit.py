from typing import Optional
from sqlalchemy.orm import Session
from app.models.event import Event


def record_event(
    db: Session,
    action: str,
    user_id: Optional[int] = None,
    scenario_id: Optional[int] = None,
    campaign_id: Optional[int] = None,
    tenant_id: Optional[int] = None,
) -> Event:
    event = Event(
        user_id=user_id,
        scenario_id=scenario_id,
        campaign_id=campaign_id,
        action=action,
        tenant_id=tenant_id,
    )
    db.add(event)
    return event
