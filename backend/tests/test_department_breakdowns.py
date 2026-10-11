import asyncio

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.stats import get_breakdowns
from app.db.base import Base
from app.models.event import Event
from app.models.scenario import Scenario
from app.models.tenant import Tenant
from app.models.training_assignment import TrainingAssignment
from app.models.user import User


def test_department_breakdowns_include_computed_risk_and_training_completion():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    tenant = Tenant(name="Department Workspace", slug="department-workspace")
    session.add(tenant)
    session.flush()
    admin = User(email="admin@example.com", hashed_password="unused", role="admin", tenant_id=tenant.id)
    finance_user = User(email="finance@example.com", hashed_password="unused", department="Finance", tenant_id=tenant.id)
    engineering_user = User(email="engineering@example.com", hashed_password="unused", department="Engineering", tenant_id=tenant.id)
    scenario = Scenario(title="Invoice review", difficulty="medium", tenant_id=tenant.id, indicators={})
    session.add_all([admin, finance_user, engineering_user, scenario])
    session.flush()
    session.add_all([
        Event(tenant_id=tenant.id, user_id=finance_user.id, scenario_id=scenario.id, action="phishing.mock_sent"),
        Event(tenant_id=tenant.id, user_id=finance_user.id, scenario_id=scenario.id, action="click"),
        Event(tenant_id=tenant.id, user_id=engineering_user.id, scenario_id=scenario.id, action="phishing.mock_sent"),
        Event(tenant_id=tenant.id, user_id=engineering_user.id, scenario_id=scenario.id, action="report"),
        TrainingAssignment(tenant_id=tenant.id, user_id=finance_user.id, title="Finance basics", status="Assigned"),
        TrainingAssignment(tenant_id=tenant.id, user_id=engineering_user.id, title="Engineering basics", status="Completed"),
    ])
    session.commit()

    response = asyncio.run(
        get_breakdowns(
            scenario_id=None,
            date_from=None,
            date_to=None,
            db=session,
            current_user=admin,
        )
    )
    departments = {department.name: department for department in response.departments}

    assert departments["Finance"].high_risk_users == 1
    assert departments["Finance"].training_completion_rate == 0.0
    assert departments["Engineering"].high_risk_users == 0
    assert departments["Engineering"].training_completion_rate == 100.0
    session.close()
