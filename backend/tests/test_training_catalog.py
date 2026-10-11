from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api import schemas
from app.api.users import create_training_assignment, create_training_module, update_training_assignment
from app.db.base import Base
from app.models.event import Event
from app.models.scenario import Scenario
from app.models.tenant import Tenant
from app.models.training_assignment import TrainingAssignment
from app.models.training_module import TrainingModule
from app.models.user import User


def test_catalog_module_can_be_assigned_and_completed_with_score():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    tenant = Tenant(name="Catalog Workspace", slug="catalog-workspace")
    session.add(tenant)
    session.flush()
    admin = User(email="admin@example.com", hashed_password="unused", role="admin", tenant_id=tenant.id)
    learner = User(email="learner@example.com", hashed_password="unused", role="trainee", tenant_id=tenant.id)
    session.add_all([admin, learner])
    session.commit()

    module = create_training_module(
        schemas.TrainingModuleCreate(title="Spot suspicious links", estimated_minutes=12, required_score=85),
        db=session,
        current_user=admin,
    )
    assignment = create_training_assignment(
        learner.id,
        schemas.TrainingAssignmentCreate(module_id=module.id),
        db=session,
        current_user=admin,
    )
    completed = update_training_assignment(
        assignment.id,
        schemas.TrainingAssignmentUpdate(status="Completed", completion_score=92),
        db=session,
        current_user=admin,
    )

    assert assignment.module_id == module.id
    assert assignment.title == "Spot suspicious links"
    assert completed.completion_score == 92
    assert completed.completed_at is not None
    session.close()