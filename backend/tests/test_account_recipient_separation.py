from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api import schemas
from app.api.campaigns import create_campaign
from app.api.scenarios import create_scenario
from app.api.users import list_users
from app.db.base import Base
from app.models.scenario import Scenario
from app.models.tenant import Tenant
from app.models.user import User
from app.services.mock_campaigns import execute_mock_campaign


def test_application_accounts_are_not_campaign_recipients():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    tenant = Tenant(name="Role Workspace", slug="role-workspace")
    session.add(tenant)
    session.flush()
    session.add_all(
        [
            User(email="admin@example.com", hashed_password="unused", role="admin", tenant_id=tenant.id),
            User(email="analyst@example.com", hashed_password="unused", role="analyst", tenant_id=tenant.id),
            User(email="viewer@example.com", hashed_password="unused", role="viewer", tenant_id=tenant.id),
            User(email="recipient@example.com", hashed_password="unused", role="trainee", tenant_id=tenant.id),
        ]
    )
    scenario = Scenario(
        title="Recipient isolation",
        difficulty="medium",
        tenant_id=tenant.id,
        indicators={"audience": "All Staff"},
    )
    session.add(scenario)
    session.flush()

    recipients, _ = execute_mock_campaign(session, scenario)
    session.commit()

    assert recipients == 1
    session.close()


def test_user_directory_lists_only_application_accounts():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    tenant = Tenant(name="Directory Workspace", slug="directory-workspace")
    session.add(tenant)
    session.flush()
    admin = User(email="admin@example.com", hashed_password="unused", role="admin", tenant_id=tenant.id)
    session.add_all(
        [
            admin,
            User(email="analyst@example.com", hashed_password="unused", role="analyst", tenant_id=tenant.id),
            User(email="viewer@example.com", hashed_password="unused", role="viewer", tenant_id=tenant.id),
            User(email="recipient@example.com", hashed_password="unused", role="trainee", tenant_id=tenant.id),
        ]
    )
    session.commit()

    result = list_users(
        limit=None,
        offset=0,
        search=None,
        role=None,
        risk=None,
        db=session,
        current_user=admin,
    )

    assert result["total"] == 3
    assert {item["role"] for item in result["items"]} == {"admin", "analyst", "viewer"}
    assert result["role_counts"] == {"admin": 1, "analyst": 1, "viewer": 1}
    session.close()


def test_analyst_can_create_campaign_and_scenario():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    tenant = Tenant(name="Analyst Workspace", slug="analyst-workspace")
    session.add(tenant)
    session.flush()
    analyst = User(email="analyst@example.com", hashed_password="unused", role="analyst", tenant_id=tenant.id)
    session.add(analyst)
    session.commit()

    campaign = create_campaign(
        schemas.CampaignCreate(name="Analyst campaign", status="Draft"),
        db=session,
        current_user=analyst,
    )
    scenario = create_scenario(
        schemas.ScenarioCreate(
            title="Analyst scenario",
            difficulty="medium",
            campaign_id=campaign["id"],
            indicators={"status": "Draft"},
        ),
        db=session,
        current_user=analyst,
    )

    assert scenario.campaign_id == campaign["id"]
    session.close()
