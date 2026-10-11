from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.scenarios import get_scenario_results
from app.db.base import Base
from app.models.campaign_recipient_snapshot import CampaignRecipientSnapshot
from app.models.event import Event
from app.models.scenario import Scenario
from app.models.tenant import Tenant
from app.models.user import User
from app.services.mock_campaigns import execute_mock_campaign


def test_campaign_recipient_snapshot_is_unchanged_after_user_update():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    tenant = Tenant(name="Snapshot Workspace", slug="snapshot-workspace")
    session.add(tenant)
    session.flush()
    admin = User(email="admin@example.com", hashed_password="unused", role="admin", tenant_id=tenant.id)
    learner = User(
        email="learner@example.com",
        hashed_password="unused",
        full_name="Original Learner",
        department="Finance",
        tenant_id=tenant.id,
    )
    scenario = Scenario(
        title="Invoice review",
        difficulty="medium",
        tenant_id=tenant.id,
        indicators={"audience": "Finance", "status": "Active"},
    )
    session.add_all([admin, learner, scenario])
    session.flush()

    execute_mock_campaign(session, scenario, executed_at=datetime(2026, 7, 21, 9, 0))
    session.commit()
    learner.email = "changed@example.com"
    learner.full_name = "Changed Learner"
    learner.department = "Engineering"
    session.commit()

    results = get_scenario_results(scenario.id, db=session, current_user=admin)

    assert session.query(CampaignRecipientSnapshot).count() == 1
    assert session.query(Event).filter(Event.action == "phishing.mock_sent").count() == 1
    recipients = results["latest_run_recipients"]
    assert len(recipients) == 1
    assert recipients[0]["id"] == 1
    assert recipients[0]["email"] == "learner@example.com"
    assert recipients[0]["full_name"] == "Original Learner"
    assert recipients[0]["department"] == "Finance"
    assert recipients[0]["executed_at"] == datetime(2026, 7, 21, 9, 0)
    assert recipients[0]["interaction_token"]
    assert set(recipients[0]["interaction_urls"]) == {"open", "click", "report"}
    session.close()


def test_campaign_email_body_gets_single_simulation_link_block_after_multiple_runs():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    tenant = Tenant(name="Link Workspace", slug="link-workspace")
    session.add(tenant)
    session.flush()
    learner = User(
        email="learner@example.com",
        hashed_password="unused",
        full_name="Learner",
        department="Finance",
        tenant_id=tenant.id,
    )
    scenario = Scenario(
        title="Credential prompt",
        difficulty="medium",
        tenant_id=tenant.id,
        indicators={
            "audience": "Finance",
            "status": "Active",
            "email_body_text": "Please review the secure message.",
            "email_body_html": "<p>Please review the secure message.</p>",
        },
    )
    session.add_all([learner, scenario])
    session.flush()

    execute_mock_campaign(session, scenario, executed_at=datetime(2026, 7, 21, 9, 0))
    execute_mock_campaign(session, scenario, executed_at=datetime(2026, 7, 22, 9, 0))
    session.commit()
    session.refresh(scenario)

    text_body = scenario.indicators["email_body_text"]
    html_body = scenario.indicators["email_body_html"]
    assert text_body.count("[SIMULATION_LINK_START]") == 1
    assert text_body.count("/simulate/phishing-link?scenario_id=") == 1
    assert html_body.count("<!--SIMULATION_LINK_START-->") == 1
    assert html_body.count("/simulate/phishing-link?scenario_id=") == 2
    assert scenario.indicators["simulation_click_url"].endswith(f"scenario_id={scenario.id}")
    session.close()
