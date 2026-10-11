from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api import schemas
from app.api.users import (
    create_training_assignment,
    list_training_assignments,
    update_training_assignment,
)
from app.db.base import Base
from app.models.event import Event
from app.models.scenario import Scenario
from app.models.tenant import Tenant
from app.models.training_assignment import TrainingAssignment
from app.models.user import User


def test_training_assignment_lifecycle_is_scoped_to_the_user_and_tenant():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    tenant = Tenant(name="Training Workspace", slug="training-workspace")
    session.add(tenant)
    session.flush()
    admin = User(email="admin@example.com", hashed_password="unused", role="admin", tenant_id=tenant.id)
    learner = User(email="learner@example.com", hashed_password="unused", role="trainee", tenant_id=tenant.id)
    session.add_all([admin, learner])
    session.commit()

    assignment = create_training_assignment(
        learner.id,
        schemas.TrainingAssignmentCreate(title="Recognize credential prompts"),
        db=session,
        current_user=admin,
    )
    assert assignment.status == "Assigned"
    assignments = list_training_assignments(learner.id, db=session, current_user=admin)
    updated = update_training_assignment(
        assignment.id,
        schemas.TrainingAssignmentUpdate(status="Completed"),
        db=session,
        current_user=admin,
    )

    assert len(assignments) == 1
    assert assignments[0].title == "Recognize credential prompts"
    assert updated.status == "Completed"
    assert updated.completed_at is not None
    session.close()