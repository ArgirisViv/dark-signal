from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.users import get_user_risk_trend
from app.db.base import Base
from app.models.event import Event
from app.models.scenario import Scenario
from app.models.tenant import Tenant
from app.models.user import User


def test_user_risk_trend_is_cumulative_and_chronological():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    tenant = Tenant(name="Trend Workspace", slug="trend-workspace")
    session.add(tenant)
    session.flush()
    admin = User(email="admin@example.com", hashed_password="unused", role="admin", tenant_id=tenant.id)
    learner = User(email="learner@example.com", hashed_password="unused", role="trainee", tenant_id=tenant.id)
    session.add_all([admin, learner])
    session.flush()
    session.add_all([
        Event(tenant_id=tenant.id, user_id=learner.id, action="click", created_at=datetime(2026, 7, 20, 9, 0)),
        Event(tenant_id=tenant.id, user_id=learner.id, action="report", created_at=datetime(2026, 7, 21, 9, 0)),
    ])
    session.commit()

    trend = get_user_risk_trend(learner.id, db=session, current_user=admin)

    assert trend == [
        {"date": "2026-07-20", "awareness_score": 35, "computed_risk": "High", "clicks": 1, "reports": 0},
        {"date": "2026-07-21", "awareness_score": 45, "computed_risk": "Medium", "clicks": 1, "reports": 1},
    ]
    session.close()