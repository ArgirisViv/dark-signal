from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.api import schemas
from app.api.campaigns import delete_campaign
from app.api.scenarios import delete_scenario
from app.api.users import create_adaptive_program
from app.db.base import Base
from app.models.campaign import Campaign
from app.models.campaign_recipient_snapshot import CampaignRecipientSnapshot
from app.models.event import Event
from app.models.adaptive_program import AdaptiveProgram
from app.models.scenario import Scenario
from app.models.tenant import Tenant
from app.models.user import User


def _foreign_key_session():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _seed_workspace(session):
    tenant = Tenant(name="Deletion Workspace", slug="resource-deletion")
    session.add(tenant)
    session.flush()
    admin = User(
        email="admin-resource-delete@example.com",
        hashed_password="unused",
        role="admin",
        tenant_id=tenant.id,
    )
    campaign = Campaign(
        name="Deletion campaign",
        status="Draft",
        tenant_id=tenant.id,
    )
    session.add_all([admin, campaign])
    session.flush()
    return tenant, admin, campaign


def test_scenario_delete_preserves_audit_and_removes_recipient_snapshots():
    session = _foreign_key_session()
    tenant, admin, campaign = _seed_workspace(session)
    scenario = Scenario(
        title="Deletable scenario",
        difficulty="medium",
        tenant_id=tenant.id,
        campaign_id=campaign.id,
        indicators={},
    )
    session.add(scenario)
    session.flush()
    session.add_all(
        [
            Event(
                tenant_id=tenant.id,
                campaign_id=campaign.id,
                scenario_id=scenario.id,
                action="scenario.updated",
            ),
            CampaignRecipientSnapshot(
                tenant_id=tenant.id,
                campaign_id=campaign.id,
                scenario_id=scenario.id,
                email="recipient@example.com",
            ),
        ]
    )
    session.commit()
    scenario_id = scenario.id

    result = delete_scenario(scenario_id, db=session, current_user=admin)

    assert result == {"deleted": True, "scenario_id": scenario_id}
    assert session.get(Scenario, scenario_id) is None
    assert session.query(CampaignRecipientSnapshot).count() == 0
    assert (
        session.query(Event)
        .filter(Event.action == "scenario.updated")
        .one()
        .scenario_id
        is None
    )
    deletion_event = (
        session.query(Event)
        .filter(Event.action == f"scenario.deleted:{scenario_id}")
        .one()
    )
    assert deletion_event.scenario_id is None
    assert deletion_event.campaign_id == campaign.id
    session.close()


def test_scenario_delete_removes_dependent_adaptive_program():
    session = _foreign_key_session()
    tenant, admin, campaign = _seed_workspace(session)
    scenarios = [
        Scenario(
            title=f"Adaptive scenario {index}",
            difficulty="medium",
            tenant_id=tenant.id,
            campaign_id=campaign.id,
            indicators={},
        )
        for index in range(5)
    ]
    session.add_all(scenarios)
    session.commit()
    create_adaptive_program(
        schemas.AdaptiveProgramCreateRequest(
            name="Protected adaptive program",
            campaign_id=campaign.id,
            baseline_scenario_id=scenarios[0].id,
            easier_scenario_id=scenarios[1].id,
            same_scenario_id=scenarios[2].id,
            harder_scenario_id=scenarios[3].id,
            final_scenario_id=scenarios[4].id,
        ),
        db=session,
        current_user=admin,
    )

    result = delete_scenario(scenarios[0].id, db=session, current_user=admin)

    assert result == {
        "deleted": True,
        "scenario_id": scenarios[0].id,
        "adaptive_programs_deleted": 1,
    }
    assert session.get(Scenario, scenarios[0].id) is None
    assert session.query(AdaptiveProgram).count() == 0
    session.close()


def test_campaign_delete_removes_scenarios_and_preserves_audit_history():
    session = _foreign_key_session()
    tenant, admin, campaign = _seed_workspace(session)
    scenarios = [
        Scenario(
            title=f"Campaign scenario {index}",
            difficulty="medium",
            tenant_id=tenant.id,
            campaign_id=campaign.id,
            indicators={},
        )
        for index in range(5)
    ]
    session.add_all(scenarios)
    session.flush()
    scenario = scenarios[0]
    session.add(
        Event(
            tenant_id=tenant.id,
            campaign_id=campaign.id,
            scenario_id=scenario.id,
            action="campaign.updated",
        )
    )
    session.add(
        CampaignRecipientSnapshot(
            tenant_id=tenant.id,
            campaign_id=campaign.id,
            scenario_id=scenario.id,
            email="campaign-recipient@example.com",
        )
    )
    session.commit()
    create_adaptive_program(
        schemas.AdaptiveProgramCreateRequest(
            name="Campaign adaptive program",
            campaign_id=campaign.id,
            baseline_scenario_id=scenarios[0].id,
            easier_scenario_id=scenarios[1].id,
            same_scenario_id=scenarios[2].id,
            harder_scenario_id=scenarios[3].id,
            final_scenario_id=scenarios[4].id,
        ),
        db=session,
        current_user=admin,
    )
    campaign_id = campaign.id
    scenario_ids = [item.id for item in scenarios]

    result = delete_campaign(campaign_id, db=session, current_user=admin)

    assert result == {
        "deleted": True,
        "campaign_id": campaign_id,
        "scenarios_deleted": 5,
        "recipient_snapshots_deleted": 1,
        "adaptive_programs_deleted": 1,
    }
    assert session.get(Campaign, campaign_id) is None
    assert all(session.get(Scenario, scenario_id) is None for scenario_id in scenario_ids)
    assert session.query(CampaignRecipientSnapshot).count() == 0
    assert session.query(AdaptiveProgram).count() == 0
    historical_event = session.query(Event).filter(Event.action == "campaign.updated").one()
    assert historical_event.campaign_id is None
    assert historical_event.scenario_id is None
    assert (
        session.query(Event)
        .filter(Event.action == f"campaign.deleted:{campaign_id}")
        .one()
        .campaign_id
        is None
    )
    session.close()
