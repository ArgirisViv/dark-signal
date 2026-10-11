import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api import schemas
from app.api.users import advance_adaptive_program, create_adaptive_program
from app.db.base import Base
from app.models.campaign import Campaign
from app.models.event import Event
from app.models.scenario import Scenario
from app.models.tenant import Tenant
from app.models.user import User
from app.services.template_assistant import generate_training_template


def _seed_workspace():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    tenant = Tenant(name="Auto Program Workspace", slug="auto-program-workspace")
    session.add(tenant)
    session.flush()

    admin = User(email="admin@example.com", hashed_password="unused", role="admin", tenant_id=tenant.id)
    learner_a = User(email="a@example.com", hashed_password="unused", role="trainee", tenant_id=tenant.id)
    learner_b = User(email="b@example.com", hashed_password="unused", role="trainee", tenant_id=tenant.id)

    campaign = Campaign(name="Adaptive campaign", tenant_id=tenant.id, status="Draft")
    session.add(campaign)
    session.flush()

    baseline = Scenario(title="Baseline common", difficulty="medium", tenant_id=tenant.id, campaign_id=campaign.id, indicators={"audience": "All Staff"})
    easier = Scenario(title="Adaptive easy", difficulty="easy", tenant_id=tenant.id, campaign_id=campaign.id, indicators={"audience": "All Staff"})
    same = Scenario(title="Adaptive same", difficulty="medium", tenant_id=tenant.id, campaign_id=campaign.id, indicators={"audience": "All Staff"})
    harder = Scenario(title="Adaptive hard", difficulty="hard", tenant_id=tenant.id, campaign_id=campaign.id, indicators={"audience": "All Staff"})
    final = Scenario(title="Final common", difficulty="medium", tenant_id=tenant.id, campaign_id=campaign.id, indicators={"audience": "All Staff"})

    session.add_all([admin, learner_a, learner_b, baseline, easier, same, harder, final])
    session.commit()

    return session, admin, baseline, easier, same, harder, final


def test_adaptive_program_advances_through_all_stages():
    session, admin, baseline, easier, same, harder, final = _seed_workspace()

    create_payload = schemas.AdaptiveProgramCreateRequest(
        name="Quarterly adaptive run",
        campaign_id=baseline.campaign_id,
        baseline_scenario_id=baseline.id,
        final_scenario_id=final.id,
        easier_scenario_id=easier.id,
        same_scenario_id=same.id,
        harder_scenario_id=harder.id,
        adaptive_rounds=2,
    )
    program = create_adaptive_program(create_payload, db=session, current_user=admin)

    first = advance_adaptive_program(program["id"], db=session, current_user=admin)
    second = advance_adaptive_program(program["id"], db=session, current_user=admin)
    third = advance_adaptive_program(program["id"], db=session, current_user=admin)
    fourth = advance_adaptive_program(program["id"], db=session, current_user=admin)
    fifth = advance_adaptive_program(program["id"], db=session, current_user=admin)

    assert first["stage"] == "baseline_sent"
    assert second["stage"] == "adaptive_round_dispatched"
    assert third["stage"] == "adaptive_round_dispatched"
    assert fourth["stage"] == "final_sent"
    assert fifth["stage"] == "completed"

    statuses = [first["program"]["status"], second["program"]["status"], third["program"]["status"], fourth["program"]["status"], fifth["program"]["status"]]
    assert statuses[-1] == "completed"
    assert fifth["program"]["final_evaluation"] is not None
    assert fifth["program"]["baseline_executed_at"] is not None
    assert fifth["program"]["adaptive_executed_at"] is not None
    assert fifth["program"]["final_executed_at"] is not None
    assert fifth["program"]["completed_at"] is not None

    sends = session.query(Event).filter(Event.action == "phishing.mock_sent").count()
    assert sends > 0

    session.close()


def test_adaptive_program_rejects_scenario_from_another_campaign():
    session, admin, baseline, easier, same, harder, final = _seed_workspace()
    other_campaign = Campaign(name="Unrelated campaign", tenant_id=admin.tenant_id, status="Draft")
    session.add(other_campaign)
    session.flush()
    unrelated = Scenario(
        title="Unrelated scenario",
        difficulty="hard",
        tenant_id=admin.tenant_id,
        campaign_id=other_campaign.id,
        indicators={"audience": "All Staff"},
    )
    session.add(unrelated)
    session.commit()

    payload = schemas.AdaptiveProgramCreateRequest(
        name="Invalid mixed campaign run",
        campaign_id=baseline.campaign_id,
        baseline_scenario_id=baseline.id,
        final_scenario_id=final.id,
        easier_scenario_id=easier.id,
        same_scenario_id=same.id,
        harder_scenario_id=unrelated.id,
    )

    with pytest.raises(HTTPException) as error:
        create_adaptive_program(payload, db=session, current_user=admin)

    assert error.value.status_code == 422
    assert "does not belong" in error.value.detail
    session.close()


def test_template_assistant_fallback_generator_is_reported_without_api_key():
    package = generate_training_template(
        language="English",
        organization_category="Finance",
        recipient_role="Analyst",
        topic="Access verification",
        difficulty="medium",
        psychological_technique="urgency",
        template_name="Fallback check",
    )

    assert package.generator in {"rule_based_fallback", "openai_responses_api"}
    assert "training-safe.example" in package.body_text
