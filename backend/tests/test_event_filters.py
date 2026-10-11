from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.events import list_events
from app.db.base import Base
from app.models.event import Event
from app.models.scenario import Scenario
from app.models.tenant import Tenant
from app.models.user import User


def test_event_filters_combine_action_user_campaign_and_date():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    tenant = Tenant(name="Audit Workspace", slug="audit-workspace")
    session.add(tenant)
    session.flush()
    admin = User(email="admin@example.com", hashed_password="unused", role="admin", tenant_id=tenant.id)
    learner = User(email="learner@example.com", hashed_password="unused", role="trainee", tenant_id=tenant.id)
    scenario = Scenario(title="Invoice review", difficulty="medium", tenant_id=tenant.id, indicators={})
    session.add_all([admin, learner, scenario])
    session.flush()
    session.add_all([
        Event(tenant_id=tenant.id, user_id=learner.id, scenario_id=scenario.id, action="click", created_at=datetime(2026, 7, 20, 10, 0)),
        Event(tenant_id=tenant.id, user_id=learner.id, scenario_id=scenario.id, action="phishing.mock_sent", created_at=datetime(2026, 7, 21, 10, 0)),
        Event(tenant_id=tenant.id, user_id=admin.id, scenario_id=scenario.id, action="scenario.updated:1", created_at=datetime(2026, 7, 20, 11, 0)),
    ])
    session.commit()

    events = list_events(
        limit=50,
        offset=0,
        action_type="simulation",
        user="learner",
        campaign="invoice",
        date_from=date(2026, 7, 20),
        date_to=date(2026, 7, 20),
        db=session,
        current_user=admin,
    )

    assert len(events) == 1
    assert events[0]["action"] == "click"
    assert events[0]["user_email"] == "learner@example.com"
    session.close()