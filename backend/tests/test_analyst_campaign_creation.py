from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import campaigns, email_templates, scenarios
from app.core.security import create_access_token, get_password_hash
from app.db.base import Base
from app.db.session import get_db
from app.models.tenant import Tenant
from app.models.user import User


def test_analyst_can_load_templates_and_create_campaign_with_scenario():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)

    seed = session_factory()
    tenant = Tenant(name="Analyst Workspace", slug="analyst-workspace")
    seed.add(tenant)
    seed.flush()
    analyst = User(
        email="analyst@example.com",
        hashed_password=get_password_hash("SecurePass123!"),
        role="analyst",
        tenant_id=tenant.id,
    )
    seed.add(analyst)
    seed.commit()
    seed.refresh(analyst)

    app = FastAPI()
    app.include_router(email_templates.router, prefix="/email-templates")
    app.include_router(campaigns.router, prefix="/campaigns")
    app.include_router(scenarios.router, prefix="/scenarios")

    def override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    token = create_access_token(
        {"sub": analyst.email, "role": analyst.role, "tenant_id": analyst.tenant_id}
    )
    headers = {"Authorization": f"Bearer {token}"}

    templates_response = client.get(
        "/email-templates/",
        params={"approval_status": "approved"},
        headers=headers,
    )
    assert templates_response.status_code == 200
    assert templates_response.json()

    campaign_response = client.post(
        "/campaigns/",
        json={
            "name": "Analyst campaign",
            "description": "Created through the analyst workflow",
            "status": "Draft",
            "scenario_ids": [],
        },
        headers=headers,
    )
    assert campaign_response.status_code == 200
    campaign_id = campaign_response.json()["id"]

    scenario_response = client.post(
        "/scenarios/",
        json={
            "title": "Analyst scenario",
            "difficulty": "medium",
            "campaign_id": campaign_id,
            "indicators": {
                "status": "Draft",
                "email_template_key": templates_response.json()[0]["key"],
            },
        },
        headers=headers,
    )
    assert scenario_response.status_code == 200
    assert scenario_response.json()["campaign_id"] == campaign_id
    seed.close()
