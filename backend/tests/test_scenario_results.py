from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.scenarios import get_scenario_results
from app.db.base import Base
from app.models.event import Event
from app.models.scenario import Scenario
from app.models.tenant import Tenant
from app.models.user import User


def test_scenario_results_aggregate_only_simulation_behavior():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    tenant = Tenant(name="Results Workspace", slug="results-workspace")
    session.add(tenant)
    session.flush()
    admin = User(email="admin@example.com", hashed_password="unused", role="admin", tenant_id=tenant.id)
    learner = User(email="learner@example.com", hashed_password="unused", role="trainee", tenant_id=tenant.id)
    scenario = Scenario(title="Invoice review", difficulty="medium", tenant_id=tenant.id, indicators={})
    session.add_all([admin, learner, scenario])
    session.flush()
    session.add_all([
        Event(tenant_id=tenant.id, user_id=learner.id, scenario_id=scenario.id, action="phishing.mock_sent"),
        Event(tenant_id=tenant.id, user_id=learner.id, scenario_id=scenario.id, action="click"),
        Event(tenant_id=tenant.id, user_id=learner.id, scenario_id=scenario.id, action="report"),
        Event(tenant_id=tenant.id, user_id=admin.id, scenario_id=scenario.id, action="scenario.created:1"),
    ])
    session.commit()

    results = get_scenario_results(scenario.id, db=session, current_user=admin)

    assert results["deliveries"] == 1
    assert results["unique_recipients"] == 1
    assert results["clicks"] == 1
    assert results["reports"] == 1
    assert results["click_rate"] == 100.0
    assert results["report_rate"] == 100.0
    assert len(results["recent_responses"]) == 3
    session.close()