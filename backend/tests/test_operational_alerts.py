from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.stats import acknowledge_operational_alert, get_operational_alerts
from app.db.base import Base
from app.models.event import Event
from app.models.scenario import Scenario
from app.models.tenant import Tenant
from app.models.training_assignment import TrainingAssignment
from app.models.training_module import TrainingModule
from app.models.user import User


def test_operational_alerts_include_risk_training_and_scheduled_campaigns():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    tenant = Tenant(name="Alert Workspace", slug="alert-workspace")
    session.add(tenant)
    session.flush()
    admin = User(email="admin@example.com", hashed_password="unused", role="admin", tenant_id=tenant.id)
    learner = User(email="learner@example.com", hashed_password="unused", role="trainee", tenant_id=tenant.id)
    scenario = Scenario(
        title="Payroll review",
        difficulty="medium",
        tenant_id=tenant.id,
        indicators={"status": "Scheduled", "scheduled_for": "2026-07-25"},
    )
    session.add_all([admin, learner, scenario])
    session.flush()
    session.add_all([
        Event(tenant_id=tenant.id, user_id=learner.id, action="click"),
        TrainingAssignment(
            tenant_id=tenant.id,
            user_id=learner.id,
            title="Recognize suspicious links",
            status="Assigned",
        ),
    ])
    session.commit()

    response = get_operational_alerts(db=session, current_user=admin)
    alert_ids = {alert["id"] for alert in response["alerts"]}

    assert alert_ids == {"high-risk-users", "pending-training", "scheduled-campaigns"}
    session.close()


def test_acknowledged_operational_alert_is_removed_from_active_queue():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    tenant = Tenant(name="Acknowledgement Workspace", slug="acknowledgement-workspace")
    session.add(tenant)
    session.flush()
    admin = User(email="admin@example.com", hashed_password="unused", role="admin", tenant_id=tenant.id)
    learner = User(email="learner@example.com", hashed_password="unused", role="trainee", tenant_id=tenant.id)
    session.add_all([admin, learner])
    session.flush()
    session.add(Event(tenant_id=tenant.id, user_id=learner.id, action="click"))
    session.commit()

    acknowledge_operational_alert("high-risk-users", db=session, current_user=admin)
    response = get_operational_alerts(db=session, current_user=admin)

    assert response["alerts"] == []
    session.close()