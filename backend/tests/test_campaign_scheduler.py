from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.event import Event
from app.models.scenario import Scenario
from app.models.tenant import Tenant
from app.models.user import User
from app.services import campaign_scheduler


def test_due_mock_campaign_is_completed_once(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    monkeypatch.setattr(campaign_scheduler, "SessionLocal", session_factory)

    session = session_factory()
    tenant = Tenant(name="Test Workspace", slug="test-workspace")
    session.add(tenant)
    session.flush()
    session.add(User(email="learner@example.com", hashed_password="unused", tenant_id=tenant.id))
    scenario = Scenario(
        title="Scheduled training",
        difficulty="medium",
        tenant_id=tenant.id,
        indicators={"status": "Scheduled", "scheduled_for": "2026-07-20", "audience": "All Staff"},
    )
    session.add(scenario)
    session.commit()
    scenario_id = scenario.id
    session.close()

    assert campaign_scheduler.run_due_mock_campaigns(datetime(2026, 7, 21)) == 1
    assert campaign_scheduler.run_due_mock_campaigns(datetime(2026, 7, 21)) == 0

    session = session_factory()
    saved_scenario = session.get(Scenario, scenario_id)
    assert saved_scenario.indicators["status"] == "Completed"
    assert saved_scenario.indicators["last_run"] == "2026-07-21"
    assert session.query(Event).filter(Event.action == "phishing.mock_sent").count() == 1
    session.close()