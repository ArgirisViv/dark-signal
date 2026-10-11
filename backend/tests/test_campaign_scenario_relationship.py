from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api import schemas
from app.api.campaigns import create_campaign, get_campaign
from app.api.scenarios import create_scenario
from app.db.base import Base
from app.models.campaign import Campaign
from app.models.campaign_recipient_snapshot import CampaignRecipientSnapshot
from app.models.event import Event
from app.models.scenario import Scenario
from app.models.tenant import Tenant
from app.models.user import User


def test_campaign_can_contain_multiple_scenarios():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    tenant = Tenant(name="Campaign Workspace", slug="campaign-workspace")
    session.add(tenant)
    session.flush()
    admin = User(
        email="admin@example.com",
        hashed_password="unused",
        role="admin",
        tenant_id=tenant.id,
    )
    session.add(admin)
    session.commit()

    campaign = create_campaign(
        schemas.CampaignCreate(
            name="Quarterly awareness",
            description="One campaign with multiple simulations",
            status="Draft",
        ),
        db=session,
        current_user=admin,
    )

    for title in ("Payroll verification", "Shared document"):
        create_scenario(
            schemas.ScenarioCreate(
                title=title,
                difficulty="medium",
                campaign_id=campaign["id"],
                indicators={"status": "Draft"},
            ),
            db=session,
            current_user=admin,
        )

    result = get_campaign(campaign["id"], db=session, current_user=admin)
    assert result["scenario_count"] == 2
    assert {scenario.title for scenario in result["scenarios"]} == {
        "Payroll verification",
        "Shared document",
    }
    assert all(scenario.campaign_id == campaign["id"] for scenario in result["scenarios"])
    session.close()
