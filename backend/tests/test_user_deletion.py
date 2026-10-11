import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.users import delete_user
from app.db.base import Base
from app.models.alert_acknowledgement import AlertAcknowledgement
from app.models.campaign_recipient_snapshot import CampaignRecipientSnapshot
from app.models.event import Event
from app.models.scenario import Scenario
from app.models.tenant import Tenant
from app.models.training_assignment import TrainingAssignment
from app.models.user import User


def _session_with_accounts():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    tenant = Tenant(name="Deletion Workspace", slug="deletion-workspace")
    session.add(tenant)
    session.flush()
    admin = User(
        email="admin@example.com",
        hashed_password="unused",
        role="admin",
        tenant_id=tenant.id,
    )
    analyst = User(
        email="analyst@example.com",
        hashed_password="unused",
        role="analyst",
        tenant_id=tenant.id,
    )
    session.add_all([admin, analyst])
    session.commit()
    return session, tenant, admin, analyst


def test_delete_user_cleans_account_relations_and_preserves_history():
    session, tenant, admin, analyst = _session_with_accounts()
    scenario = Scenario(
        title="Deletion scenario",
        difficulty="medium",
        tenant_id=tenant.id,
    )
    session.add(scenario)
    session.flush()
    session.add_all(
        [
            Event(
                tenant_id=tenant.id,
                user_id=analyst.id,
                action="auth.login.success",
            ),
            CampaignRecipientSnapshot(
                tenant_id=tenant.id,
                scenario_id=scenario.id,
                user_id=analyst.id,
                email=analyst.email,
            ),
            TrainingAssignment(
                tenant_id=tenant.id,
                user_id=analyst.id,
                title="Account training",
                assignment_type="Micro-learning",
            ),
            AlertAcknowledgement(
                tenant_id=tenant.id,
                alert_id="test-alert",
                acknowledged_by_user_id=analyst.id,
            ),
        ]
    )
    session.commit()

    result = delete_user(analyst.id, db=session, current_user=admin)

    assert result == {"deleted": True, "user_id": analyst.id}
    assert session.get(User, analyst.id) is None
    assert (
        session.query(Event)
        .filter(Event.action == "auth.login.success")
        .one()
        .user_id
        is None
    )
    assert session.query(CampaignRecipientSnapshot).one().user_id is None
    assert session.query(TrainingAssignment).count() == 0
    assert session.query(AlertAcknowledgement).count() == 0
    assert (
        session.query(Event)
        .filter(Event.action == f"user.deleted:{analyst.id}")
        .one()
        .user_id
        == admin.id
    )
    session.close()


def test_delete_user_rejects_active_account():
    session, _tenant, admin, _analyst = _session_with_accounts()

    with pytest.raises(HTTPException) as error:
        delete_user(admin.id, db=session, current_user=admin)

    assert error.value.status_code == 409
    assert "currently signed in" in error.value.detail
    assert session.get(User, admin.id) is not None
    session.close()

