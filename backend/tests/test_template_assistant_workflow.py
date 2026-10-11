import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fastapi import HTTPException

from app.api import schemas
from app.api import email_templates as email_templates_api
from app.api.email_templates import approve_template, generate_template_draft
from app.core.config import settings
from app.api.scenarios import send_mock_phishing
from app.db.base import Base
from app.models.email_template import EmailTemplate
from app.models.scenario import Scenario
from app.models.tenant import Tenant
from app.models.user import User
from app.services import template_assistant
from app.services.template_assistant import AssistantConfigurationError, generate_training_template


def test_template_assistant_generates_safe_training_content():
    package = generate_training_template(
        language="English",
        organization_category="Healthcare",
        recipient_role="Nurse",
        topic="Credentials refresh",
        difficulty="hard",
        psychological_technique="authority",
        template_name="Authority draft",
    )

    assert "training-safe.example" in package.body_text
    assert package.suspicious_points
    assert len(package.suspicious_points) >= 3
    assert package.alternative_variant.difficulty in {"medium", "hard"}


def test_real_assistant_uses_openai_responses_api_and_reports_model(monkeypatch):
    recorded = {}
    model_output = {
        "subject": "Quarterly account review",
        "body_text": "Review https://untrusted.example/login",
        "body_html": (
            '<p onclick="steal()">Review <a href="https://untrusted.example/login">this update</a>.</p>'
            "<script>alert('unsafe')</script>"
        ),
        "suspicious_points": ["Unexpected sender", "Urgent request", "Unfamiliar link"],
        "alternative_variant": {
            "difficulty": "hard",
            "subject": "Account review reminder",
            "body_text": "Review https://untrusted.example/alternative",
            "body_html": '<a href="https://untrusted.example/alternative">Review</a>',
        },
        "safety_notes": ["Fictional exercise", "Training-only domain"],
    }

    class FakeResponse:
        status_code = 200
        headers = {"x-request-id": "req_test"}

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "id": "resp_test",
                "model": "gpt-5.6-2026-07-01",
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": json.dumps(model_output)}],
                    }
                ],
            }

    class FakeClient:
        def __init__(self, *, timeout):
            recorded["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, endpoint, *, headers, json):
            recorded.update(endpoint=endpoint, headers=headers, payload=json)
            return FakeResponse()

    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-project-key")
    monkeypatch.setattr(settings, "OPENAI_MODEL", "gpt-5.6")
    monkeypatch.setattr(template_assistant.httpx, "Client", FakeClient)

    package = generate_training_template(
        language="English",
        organization_category="Finance",
        recipient_role="Analyst",
        topic="Access verification",
        difficulty="medium",
        psychological_technique="urgency",
        require_llm=True,
    )

    assert recorded["endpoint"].endswith("/responses")
    assert recorded["payload"]["text"]["format"]["type"] == "json_schema"
    assert recorded["payload"]["store"] is False
    assert package.generator == "openai_responses_api"
    assert package.provider == "openai"
    assert package.model == "gpt-5.6-2026-07-01"
    assert package.request_id == "req_test"
    assert "untrusted.example" not in package.body_text
    assert "training-safe.example" in package.body_text
    assert "onclick" not in package.body_html
    assert "<script" not in package.body_html
    assert "alert(" not in package.body_html


def test_real_assistant_requires_backend_api_key(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)

    with pytest.raises(AssistantConfigurationError):
        generate_training_template(
            language="English",
            organization_category="Finance",
            recipient_role="Analyst",
            topic="Access verification",
            difficulty="medium",
            psychological_technique="urgency",
            require_llm=True,
        )


def test_generate_draft_and_approve_flow_changes_status(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    tenant = Tenant(name="Assistant Workspace", slug="assistant-workspace")
    session.add(tenant)
    session.flush()
    admin = User(
        email="admin@example.com",
        hashed_password="unused",
        role="admin",
        tenant_id=tenant.id,
    )
    session.add(admin)
    session.commit()

    payload = schemas.AssistantTemplateRequest(
        language="English",
        organization_category="Finance",
        recipient_role="Analyst",
        topic="Quarterly access review",
        difficulty="medium",
        psychological_technique="urgency",
        template_name="Quarterly review draft",
    )

    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)
    safe_package = generate_training_template(
        language=payload.language,
        organization_category=payload.organization_category,
        recipient_role=payload.recipient_role,
        topic=payload.topic,
        difficulty=payload.difficulty,
        psychological_technique=payload.psychological_technique,
        template_name=payload.template_name,
    )
    monkeypatch.setattr(
        email_templates_api,
        "generate_training_template",
        lambda **kwargs: safe_package,
    )

    generated = generate_template_draft(payload, db=session, current_user=admin)
    template = generated["template"]
    assert template.approval_status == "draft"
    assert template.origin == "llm_assistant"

    approved = approve_template(template.key, db=session, current_user=admin)
    assert approved.approval_status == "approved"
    assert approved.approved_by == "admin@example.com"
    assert approved.approved_at is not None
    session.close()


def test_send_mock_blocks_unapproved_template_usage():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    tenant = Tenant(name="Approval Workspace", slug="approval-workspace")
    session.add(tenant)
    session.flush()

    admin = User(email="admin@example.com", hashed_password="unused", role="admin", tenant_id=tenant.id)
    learner = User(email="learner@example.com", hashed_password="unused", role="trainee", tenant_id=tenant.id)
    draft_template = EmailTemplate(
        key="assistant_draft_template",
        name="Assistant Draft",
        subject="Draft subject",
        body_text="Draft body",
        body_html="<p>Draft body</p>",
        approval_status="draft",
        origin="llm_assistant",
    )
    scenario = Scenario(
        title="Draft template scenario",
        difficulty="medium",
        tenant_id=tenant.id,
        indicators={"email_template_key": draft_template.key, "audience": "All Staff", "status": "Active"},
    )
    session.add_all([admin, learner, draft_template, scenario])
    session.commit()

    try:
        send_mock_phishing(scenario.id, db=session, current_user=admin)
        assert False, "Expected HTTPException for draft template"
    except HTTPException as exc:
        assert exc.status_code == 409
        assert "must be approved" in str(exc.detail)

    session.close()
