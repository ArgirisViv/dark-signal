import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import auth, schemas
from app.api.users import update_user
from app.core.security import create_access_token, get_password_hash
from app.db.base import Base
from app.db.session import get_db
from app.models.tenant import Tenant
from app.models.user import User


def _account_app():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    tenant = Tenant(name="Security Workspace", slug="security-workspace")
    session.add(tenant)
    session.flush()
    admin = User(
        email="admin@example.com",
        hashed_password=get_password_hash("SecurePass123!"),
        role="admin",
        tenant_id=tenant.id,
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)

    app = FastAPI()
    app.include_router(auth.router, prefix="/auth")

    def override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    return TestClient(app), session, admin


def test_registration_requires_admin_and_uses_admin_tenant():
    client, session, admin = _account_app()
    payload = {
        "email": "analyst@example.com",
        "password": "SecurePass123!",
        "role": "analyst",
        "full_name": "Test Analyst",
    }

    assert client.post("/auth/register", json=payload).status_code == 401

    token = create_access_token(
        {"sub": admin.email, "role": admin.role, "tenant_id": admin.tenant_id}
    )
    response = client.post(
        "/auth/register",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    created = session.query(User).filter(User.email == "analyst@example.com").one()
    assert created.tenant_id == admin.tenant_id
    session.close()


def test_password_schemas_reject_short_passwords():
    with pytest.raises(ValidationError):
        schemas.UserCreate(email="viewer@example.com", password="short", role="viewer")
    with pytest.raises(ValidationError):
        schemas.ResetPasswordRequest(token="token", password="short")


def test_duplicate_email_and_final_admin_demotion_return_conflicts():
    _client, session, admin = _account_app()
    viewer = User(
        email="viewer@example.com",
        hashed_password=get_password_hash("SecurePass123!"),
        role="viewer",
        tenant_id=admin.tenant_id,
    )
    session.add(viewer)
    session.commit()

    with pytest.raises(HTTPException) as duplicate_error:
        update_user(
            viewer.id,
            schemas.UserUpdate(email="ADMIN@example.com"),
            db=session,
            current_user=admin,
        )
    assert duplicate_error.value.status_code == 409

    with pytest.raises(HTTPException) as demotion_error:
        update_user(
            admin.id,
            schemas.UserUpdate(role="viewer"),
            db=session,
            current_user=admin,
        )
    assert demotion_error.value.status_code == 409
    session.close()
