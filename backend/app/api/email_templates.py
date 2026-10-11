from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from app.api import schemas
from app.api.deps import require_roles
from app.core.rbac import Role
from app.db.session import get_db
from app.models.email_template import EmailTemplate
from app.services.email_templates import (
    DEFAULT_EMAIL_TEMPLATES,
    create_custom_template,
    get_or_create_template,
    reset_template,
)
from app.services.template_assistant import (
    AssistantConfigurationError,
    AssistantGenerationError,
    generate_training_template,
    get_assistant_status,
)
from app.services.html_sanitizer import sanitize_email_html

router = APIRouter()


def _assert_known_key(key: str) -> None:
    if key not in DEFAULT_EMAIL_TEMPLATES:
        raise HTTPException(status_code=404, detail="Unknown email template key")


@router.get(
    "/",
    response_model=List[schemas.EmailTemplateOut],
    summary="List email templates",
    description="Return all email templates available for editing.",
)
def list_templates(
    approval_status: str | None = Query(None, pattern="^(draft|approved|rejected)$"),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(Role.admin, Role.analyst, Role.viewer)),
):
    for key in DEFAULT_EMAIL_TEMPLATES.keys():
        get_or_create_template(db, key)
    query = db.query(EmailTemplate)
    if approval_status:
        query = query.filter(EmailTemplate.approval_status == approval_status)
    return query.order_by(EmailTemplate.key.asc()).all()


@router.get(
    "/assistant/status",
    response_model=schemas.AssistantStatusResponse,
    summary="Get the OpenAI assistant configuration status",
    description="Report whether the backend has an OpenAI key without exposing the key itself.",
)
def get_template_assistant_status(
    current_user=Depends(require_roles(Role.admin)),
):
    return get_assistant_status()


@router.get(
    "/{key}",
    response_model=schemas.EmailTemplateOut,
    summary="Get email template",
    description="Fetch a single email template by key.",
)
def get_template(
    key: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(Role.admin, Role.analyst, Role.viewer)),
):
    template = db.query(EmailTemplate).filter(EmailTemplate.key == key).first()
    if template:
        return template
    _assert_known_key(key)
    return get_or_create_template(db, key)


@router.put(
    "/{key}",
    response_model=schemas.EmailTemplateOut,
    summary="Update email template",
    description="Update an email template subject/body for a given key.",
)
def update_template(
    key: str,
    payload: schemas.EmailTemplateUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(Role.admin)),
):
    template = db.query(EmailTemplate).filter(EmailTemplate.key == key).first()
    if not template:
        _assert_known_key(key)
        template = get_or_create_template(db, key)
    if payload.name is not None:
        template.name = payload.name
    if payload.subject is not None:
        template.subject = payload.subject
    if payload.body_text is not None:
        template.body_text = payload.body_text
    if payload.body_html is not None:
        template.body_html = sanitize_email_html(payload.body_html)
    for field in ("difficulty", "category", "topic", "psychological_technique"):
        value = getattr(payload, field)
        if value is not None:
            setattr(template, field, value)
    db.commit()
    db.refresh(template)
    return template


@router.post(
    "/",
    response_model=schemas.EmailTemplateOut,
    summary="Create custom email template",
    description="Create a custom email template from the templates page.",
)
def create_template(
    payload: schemas.EmailTemplateCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(Role.admin)),
):
    return create_custom_template(
        db,
        key=payload.key,
        name=payload.name,
        subject=payload.subject,
        body_text=payload.body_text,
        body_html=payload.body_html,
        difficulty=payload.difficulty,
        category=payload.category,
        topic=payload.topic,
        psychological_technique=payload.psychological_technique,
    )


@router.post(
    "/assistant/generate-draft",
    response_model=schemas.AssistantTemplateResponse,
    summary="Generate phishing training template draft with assistant",
    description="Generate a safe training draft template and store it as draft pending admin approval.",
)
def generate_template_draft(
    payload: schemas.AssistantTemplateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(Role.admin)),
):
    try:
        generated = generate_training_template(
            language=payload.language,
            organization_category=payload.organization_category,
            recipient_role=payload.recipient_role,
            topic=payload.topic,
            difficulty=payload.difficulty,
            psychological_technique=payload.psychological_technique,
            template_name=payload.template_name,
            require_llm=True,
        )
    except AssistantConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AssistantGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    draft_template = create_custom_template(
        db,
        key=f"{generated.key_seed}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        name=generated.name,
        subject=generated.subject,
        body_text=generated.body_text,
        body_html=generated.body_html,
        approval_status="draft",
        origin="llm_assistant",
        assistant_metadata={
            "generator": generated.generator,
            "provider": generated.provider,
            "model": generated.model,
            "request_id": generated.request_id,
            "language": payload.language,
            "organization_category": payload.organization_category,
            "recipient_role": payload.recipient_role,
            "topic": payload.topic,
            "difficulty": payload.difficulty,
            "psychological_technique": payload.psychological_technique,
            "suspicious_points": generated.suspicious_points,
            "alternative_variant": {
                "difficulty": generated.alternative_variant.difficulty,
                "subject": generated.alternative_variant.subject,
                "body_text": generated.alternative_variant.body_text,
                "body_html": generated.alternative_variant.body_html,
            },
            "safety_notes": generated.safety_notes,
        },
        difficulty=payload.difficulty.lower(),
        category=payload.organization_category,
        topic=payload.topic,
        psychological_technique=payload.psychological_technique,
    )

    return {
        "template": draft_template,
        "suspicious_points": generated.suspicious_points,
        "alternative_variant": {
            "difficulty": generated.alternative_variant.difficulty,
            "subject": generated.alternative_variant.subject,
            "body_text": generated.alternative_variant.body_text,
            "body_html": generated.alternative_variant.body_html,
        },
        "safety_notes": generated.safety_notes,
        "generator": generated.generator,
        "provider": generated.provider,
        "model": generated.model,
        "request_id": generated.request_id,
    }


@router.post(
    "/{key}/approve",
    response_model=schemas.EmailTemplateOut,
    summary="Approve template draft",
    description="Approve a draft template for campaign usage.",
)
def approve_template(
    key: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(Role.admin)),
):
    template = db.query(EmailTemplate).filter(EmailTemplate.key == key).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    template.approval_status = "approved"
    template.approved_by = current_user.email
    template.approved_at = datetime.utcnow()
    db.commit()
    db.refresh(template)
    return template


@router.post(
    "/{key}/reset",
    response_model=schemas.EmailTemplateOut,
    summary="Reset email template",
    description="Reset an email template to default content.",
)
def reset_template_to_default(
    key: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(Role.admin)),
):
    _assert_known_key(key)
    return reset_template(db, key)
