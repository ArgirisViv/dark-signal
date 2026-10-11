from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.users import get_user_risk_profile
from app.db.base import Base
from app.models.event import Event
from app.models.scenario import Scenario
from app.models.tenant import Tenant
from app.models.user import User


def test_user_risk_profile_uses_simulation_events():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    tenant = Tenant(name="Test Workspace", slug="risk-profile-workspace")
    session.add(tenant)
    session.flush()
    admin = User(email="admin@example.com", hashed_password="unused", role="admin", tenant_id=tenant.id)
    learner = User(email="learner@example.com", hashed_password="unused", role="trainee", risk="Low", tenant_id=tenant.id)
    session.add_all([admin, learner])
    session.flush()
    session.add_all([
        Event(user_id=learner.id, tenant_id=tenant.id, action="phishing.mock_sent"),
        Event(user_id=learner.id, tenant_id=tenant.id, action="click"),
        Event(user_id=learner.id, tenant_id=tenant.id, action="report"),
    ])
    session.commit()

    profile = get_user_risk_profile(learner.id, db=session, current_user=admin)

    assert profile["exposures"] == 1
    assert profile["clicks"] == 1
    assert profile["reports"] == 1
    assert profile["awareness_score"] == 45
    assert profile["computed_risk"] == "Medium"
    session.close()