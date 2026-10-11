from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.campaign_recipient_snapshot import CampaignRecipientSnapshot
from app.models.event import Event
from app.models.scenario import Scenario
from app.models.tenant import Tenant
from app.models.user import User
from app.services.mock_campaigns import execute_mock_campaign


def test_simulated_click_feedback_page_logs_event_and_returns_training_content():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestingSessionLocal() as db:
            tenant = Tenant(name="Feedback Workspace", slug="feedback-workspace")
            db.add(tenant)
            db.flush()

            user = User(email="learner@example.com", hashed_password="unused", role="trainee", tenant_id=tenant.id)
            scenario = Scenario(
                title="Urgent payroll verification",
                difficulty="medium",
                tenant_id=tenant.id,
                indicators={
                    "sender_name": "HR Payroll Team",
                    "sender_email": "hr-payroll@external-payroll-alerts.com",
                    "claimed_domain": "company.com",
                    "link_url": "http://payroll-verify-login.example.net",
                    "urgency_phrase": "Respond in 10 minutes to avoid suspension.",
                    "credential_request": "Share your password and one-time code.",
                },
            )
            db.add_all([user, scenario])
            db.commit()
            db.refresh(user)
            db.refresh(scenario)

        client = TestClient(app)
        response = client.get(f"/simulate/phishing-link?scenario_id={scenario.id}&user_id={user.id}")

        assert response.status_code == 200
        assert "This was a simulated phishing message" in response.text
        assert "What to notice next time" in response.text

        with TestingSessionLocal() as db:
            click_events = (
                db.query(Event)
                .filter(Event.scenario_id == scenario.id)
                .filter(Event.user_id == user.id)
                .filter(Event.action == "click")
                .all()
            )
            assert len(click_events) == 1
    finally:
        app.dependency_overrides.clear()


def test_simulated_click_feedback_preview_mode_does_not_log_event():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestingSessionLocal() as db:
            tenant = Tenant(name="Preview Workspace", slug="preview-workspace")
            db.add(tenant)
            db.flush()

            scenario = Scenario(
                title="Preview only",
                difficulty="medium",
                tenant_id=tenant.id,
                indicators={"sender_email": "preview@example.com"},
            )
            db.add(scenario)
            db.commit()
            db.refresh(scenario)

        client = TestClient(app)
        response = client.get(f"/simulate/phishing-link?scenario_id={scenario.id}&preview=1")

        assert response.status_code == 200
        assert "Preview mode (no event logged)" in response.text

        with TestingSessionLocal() as db:
            click_events = (
                db.query(Event)
                .filter(Event.scenario_id == scenario.id)
                .filter(Event.action == "click")
                .all()
            )
            assert len(click_events) == 0
    finally:
        app.dependency_overrides.clear()


def test_simulated_interaction_token_logs_open_click_and_report_for_snapshot_user():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestingSessionLocal() as db:
            tenant = Tenant(name="Token Workspace", slug="token-workspace")
            db.add(tenant)
            db.flush()

            user = User(email="recipient@example.com", hashed_password="unused", role="trainee", tenant_id=tenant.id)
            scenario = Scenario(title="Tokenized campaign", difficulty="medium", tenant_id=tenant.id, indicators={"audience": "All Staff"})
            db.add_all([user, scenario])
            db.flush()

            execute_mock_campaign(db, scenario)
            db.commit()

            snapshot = db.query(CampaignRecipientSnapshot).filter(CampaignRecipientSnapshot.scenario_id == scenario.id).first()
            assert snapshot is not None
            assert snapshot.interaction_token
            scenario_id = scenario.id
            user_id = user.id
            interaction_token = snapshot.interaction_token

        client = TestClient(app)
        open_response = client.get(f"/simulate/phishing-open?token={interaction_token}")
        click_response = client.get(f"/simulate/phishing-link?token={interaction_token}")
        report_response = client.get(f"/simulate/phishing-report?token={interaction_token}")

        assert open_response.status_code == 204
        assert click_response.status_code == 200
        assert report_response.status_code == 200

        with TestingSessionLocal() as db:
            actions = [
                event.action
                for event in db.query(Event)
                .filter(Event.scenario_id == scenario_id)
                .filter(Event.user_id == user_id)
                .order_by(Event.id.asc())
                .all()
            ]
            assert "phishing.mock_sent" in actions
            assert "email.open" in actions
            assert "click" in actions
            assert "report" in actions
    finally:
        app.dependency_overrides.clear()
