from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.api.deps import require_roles
from app.core.rbac import Role
from app.db.session import get_db
from app.models.user import User
from app.models.scenario import Scenario
from app.models.event import Event

router = APIRouter(dependencies=[Depends(require_roles(Role.admin, Role.analyst, Role.viewer))])


@router.get("/summary")
def analytics_summary(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(Role.admin, Role.analyst, Role.viewer)),
):
    tenant_id = current_user.tenant_id
    total_users = db.query(func.count(User.id)).filter(User.tenant_id == tenant_id).scalar() or 0
    total_scenarios = db.query(func.count(Scenario.id)).filter(Scenario.tenant_id == tenant_id).scalar() or 0
    total_events = db.query(func.count(Event.id)).filter(Event.tenant_id == tenant_id).scalar() or 0
    click_count = (
        db.query(func.count(Event.id))
        .filter(Event.tenant_id == tenant_id)
        .filter(Event.action == "click")
        .scalar()
        or 0
    )
    report_count = (
        db.query(func.count(Event.id))
        .filter(Event.tenant_id == tenant_id)
        .filter(Event.action == "report")
        .scalar()
        or 0
    )

    click_rate = (click_count / total_events * 100) if total_events else 0.0
    report_rate = (report_count / total_events * 100) if total_events else 0.0

    return {
        "total_users": total_users,
        "total_scenarios": total_scenarios,
        "total_events": total_events,
        "click_rate": round(click_rate, 1),
        "report_rate": round(report_rate, 1),
    }
