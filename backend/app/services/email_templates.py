import re
import json
from datetime import datetime
from typing import Dict, Optional
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.email_template import EmailTemplate
from app.services.html_sanitizer import sanitize_email_html


DEFAULT_EMAIL_TEMPLATES: Dict[str, Dict[str, Optional[str]]] = {
  "account_notice": {
    "name": "Account verification notice",
    "subject": "Action required: verify your account access",
    "body_text": "This is a simulated security-awareness message for {{scenario_title}}.\n\nA training notice asks recipients to verify account access.\nAudience: {{audience}}\n\nNo real link or credential collection is used.\n\n- {{app_name}}",
    "body_html": "<h2>Account verification notice</h2><p>This is a simulated security-awareness message for <strong>{{scenario_title}}</strong>.</p><p>A training notice asks recipients to verify account access.</p><p><strong>Audience:</strong> {{audience}}</p><p>No real link or credential collection is used.</p><p>- {{app_name}}</p>",
  },
  "invoice_review": {
    "name": "Invoice review request",
    "subject": "Invoice review requested before payment processing",
    "body_text": "This is a simulated security-awareness message for {{scenario_title}}.\n\nA mock supplier requests an invoice review before payment processing.\nAudience: {{audience}}\n\nNo payment action is performed.\n\n- {{app_name}}",
    "body_html": "<h2>Invoice review request</h2><p>This is a simulated security-awareness message for <strong>{{scenario_title}}</strong>.</p><p>A mock supplier requests an invoice review before payment processing.</p><p><strong>Audience:</strong> {{audience}}</p><p>No payment action is performed.</p><p>- {{app_name}}</p>",
  },
  "shared_document": {
    "name": "Shared document alert",
    "subject": "A document was shared with you for review",
    "body_text": "This is a simulated security-awareness message for {{scenario_title}}.\n\nA mock notification claims a document requires review.\nAudience: {{audience}}\n\nNo document is opened and no external action is performed.\n\n- {{app_name}}",
    "body_html": "<h2>Shared document alert</h2><p>This is a simulated security-awareness message for <strong>{{scenario_title}}</strong>.</p><p>A mock notification claims a document requires review.</p><p><strong>Audience:</strong> {{audience}}</p><p>No document is opened and no external action is performed.</p><p>- {{app_name}}</p>",
  },
  "delivery_notice": {
    "name": "Delivery notification",
    "subject": "Delivery update: confirmation needed",
    "body_text": "This is a simulated security-awareness message for {{scenario_title}}.\n\nA mock courier notification asks the recipient to confirm a delivery update.\nAudience: {{audience}}\n\nNo delivery service is contacted.\n\n- {{app_name}}",
    "body_html": "<h2>Delivery notification</h2><p>This is a simulated security-awareness message for <strong>{{scenario_title}}</strong>.</p><p>A mock courier notification asks the recipient to confirm a delivery update.</p><p><strong>Audience:</strong> {{audience}}</p><p>No delivery service is contacted.</p><p>- {{app_name}}</p>",
  },
  "payroll_update": {
    "name": "Payroll update request",
    "subject": "Payroll update required before Friday",
    "body_text": "This is a simulated security-awareness message for {{scenario_title}}.\n\nA mock payroll notice asks the recipient to review updated payment details.\nAudience: {{audience}}\n\nNo payroll system is accessed.\n\n- {{app_name}}",
    "body_html": "<h2>Payroll update request</h2><p>This is a simulated security-awareness message for <strong>{{scenario_title}}</strong>.</p><p>A mock payroll notice asks the recipient to review updated payment details.</p><p><strong>Audience:</strong> {{audience}}</p><p>No payroll system is accessed.</p><p>- {{app_name}}</p>",
  },
  "security_policy_reminder": {
    "name": "Security policy reminder",
    "subject": "Security policy reminder: review now",
    "body_text": "This is a simulated security-awareness message for {{scenario_title}}.\n\nA mock IT reminder prompts the recipient to review the latest security policy.\nAudience: {{audience}}\n\nNo policy portal is opened.\n\n- {{app_name}}",
    "body_html": "<h2>Security policy reminder</h2><p>This is a simulated security-awareness message for <strong>{{scenario_title}}</strong>.</p><p>A mock IT reminder prompts the recipient to review the latest security policy.</p><p><strong>Audience:</strong> {{audience}}</p><p>No policy portal is opened.</p><p>- {{app_name}}</p>",
  },
  "cloud_storage_alert": {
    "name": "Cloud storage alert",
    "subject": "Cloud storage quota alert: action required",
    "body_text": "This is a simulated security-awareness message for {{scenario_title}}.\n\nA mock cloud provider alert asks the recipient to confirm storage usage.\nAudience: {{audience}}\n\nNo cloud account is changed.\n\n- {{app_name}}",
    "body_html": "<h2>Cloud storage alert</h2><p>This is a simulated security-awareness message for <strong>{{scenario_title}}</strong>.</p><p>A mock cloud provider alert asks the recipient to confirm storage usage.</p><p><strong>Audience:</strong> {{audience}}</p><p>No cloud account is changed.</p><p>- {{app_name}}</p>",
  },
  "benefits_enrollment": {
    "name": "Benefits enrollment reminder",
    "subject": "Benefits enrollment closes soon",
    "body_text": "This is a simulated security-awareness message for {{scenario_title}}.\n\nA mock HR reminder encourages the recipient to review benefits enrollment before the deadline.\nAudience: {{audience}}\n\nNo enrollment portal is accessed.\n\n- {{app_name}}",
    "body_html": "<h2>Benefits enrollment reminder</h2><p>This is a simulated security-awareness message for <strong>{{scenario_title}}</strong>.</p><p>A mock HR reminder encourages the recipient to review benefits enrollment before the deadline.</p><p><strong>Audience:</strong> {{audience}}</p><p>No enrollment portal is accessed.</p><p>- {{app_name}}</p>",
  },
  "travel_reimbursement": {
    "name": "Travel reimbursement notice",
    "subject": "Travel reimbursement request needs review",
    "body_text": "This is a simulated security-awareness message for {{scenario_title}}.\n\nA mock finance notice asks the recipient to verify travel reimbursement details.\nAudience: {{audience}}\n\nNo reimbursement claim is submitted.\n\n- {{app_name}}",
    "body_html": "<h2>Travel reimbursement notice</h2><p>This is a simulated security-awareness message for <strong>{{scenario_title}}</strong>.</p><p>A mock finance notice asks the recipient to verify travel reimbursement details.</p><p><strong>Audience:</strong> {{audience}}</p><p>No reimbursement claim is submitted.</p><p>- {{app_name}}</p>",
  },
  "shared_drive_access": {
    "name": "Shared drive access request",
    "subject": "Shared drive access request pending",
    "body_text": "This is a simulated security-awareness message for {{scenario_title}}.\n\nA mock collaboration request asks the recipient to confirm shared drive access.\nAudience: {{audience}}\n\nNo shared drive permissions are changed.\n\n- {{app_name}}",
    "body_html": "<h2>Shared drive access request</h2><p>This is a simulated security-awareness message for <strong>{{scenario_title}}</strong>.</p><p>A mock collaboration request asks the recipient to confirm shared drive access.</p><p><strong>Audience:</strong> {{audience}}</p><p>No shared drive permissions are changed.</p><p>- {{app_name}}</p>",
  },
    "password_reset": {
        "name": "Password reset",
        "subject": "Reset your {{app_name}} password",
        "body_text": "\n".join(
            [
                "We received a request to reset your {{app_name}} password.",
                "",
                "Reset link: {{reset_url}}",
                "",
                "This link is valid for {{expires_minutes}} minutes.",
                "If you did not request this, you can ignore this email.",
                "",
                "Thank you,",
                "The {{app_name}} Team",
            ]
        ),
        "body_html": """
        <html>
          <body style="font-family: 'Segoe UI', Arial, sans-serif; background:#0b1220; padding:32px;">
            <table style="max-width:600px; width:100%; margin:0 auto; background:#0f172a; border-radius:16px; padding:28px; border:1px solid #1e293b;">
              <tr>
                <td style="padding-bottom:18px;">
                  <h1 style="margin:0; font-size:22px; color:#e2e8f0; letter-spacing:0.3px;">{{app_name}}</h1>
                  <p style="margin:6px 0 0; color:#94a3b8; font-size:13px;">Security Awareness Platform</p>
                </td>
              </tr>
              <tr>
                <td>
                  <h2 style="margin:0 0 12px; color:#f8fafc; font-size:20px;">Reset your password</h2>
                  <p style="margin:0 0 16px; color:#cbd5f5; font-size:14px;">
                    We received a request to reset your password. Click the button below to continue.
                  </p>
                  <p style="margin:0 0 20px;">
                    <a href="{{reset_url}}" style="display:inline-block; padding:12px 20px; background:#38bdf8; color:#0b1220; text-decoration:none; border-radius:10px; font-weight:700;">
                      Reset password
                    </a>
                  </p>
                  <p style="margin:0 0 8px; color:#94a3b8; font-size:12px;">If the button doesn't work, use this link:</p>
                  <p style="margin:0 0 16px; color:#60a5fa; word-break:break-all; font-size:12px;">{{reset_url}}</p>
                  <p style="margin:0 0 10px; color:#94a3b8; font-size:12px;">This link is valid for {{expires_minutes}} minutes.</p>
                  <p style="margin:0; color:#94a3b8; font-size:12px;">
                    If you did not request this, you can ignore this email.
                  </p>
                </td>
              </tr>
              <tr>
                <td style="padding-top:20px; border-top:1px solid #1e293b;">
                  <p style="margin:0; color:#64748b; font-size:12px;">
                    Thank you,<br />The {{app_name}} Team
                  </p>
                </td>
              </tr>
            </table>
          </body>
        </html>
        """,
    },
    "mock_phishing": {
        "name": "Mock phishing",
        "subject": "Security awareness test: {{scenario_title}}",
        "body_text": "\n".join(
            [
                "This is a simulated phishing email for training purposes only.",
                "",
                "Scenario: {{scenario_title}}",
                "Audience: {{audience}}",
                "",
                "No real email is sent. This template is editable from the app.",
                "",
                "— {{app_name}}",
            ]
        ),
        "body_html": """
        <html>
          <body style="font-family: 'Segoe UI', Arial, sans-serif; background:#0b1220; padding:32px;">
            <table style="max-width:600px; width:100%; margin:0 auto; background:#0f172a; border-radius:16px; padding:28px; border:1px solid #1e293b;">
              <tr>
                <td style="padding-bottom:18px;">
                  <h1 style="margin:0; font-size:22px; color:#e2e8f0; letter-spacing:0.3px;">{{app_name}}</h1>
                  <p style="margin:6px 0 0; color:#94a3b8; font-size:13px;">Mock Email Preview</p>
                </td>
              </tr>
              <tr>
                <td>
                  <h2 style="margin:0 0 12px; color:#f8fafc; font-size:20px;">Security awareness test</h2>
                  <p style="margin:0 0 16px; color:#cbd5f5; font-size:14px;">
                    This is a simulated phishing email for training purposes only.
                  </p>
                  <p style="margin:0 0 8px; color:#94a3b8; font-size:12px;">Scenario: <strong>{{scenario_title}}</strong></p>
                  <p style="margin:0 0 16px; color:#94a3b8; font-size:12px;">Audience: {{audience}}</p>
                  <p style="margin:0; color:#94a3b8; font-size:12px;">
                    No real email is sent. This template is editable from the app.
                  </p>
                </td>
              </tr>
              <tr>
                <td style="padding-top:20px; border-top:1px solid #1e293b;">
                  <p style="margin:0; color:#64748b; font-size:12px;">
                    — {{app_name}}
                  </p>
                </td>
              </tr>
            </table>
          </body>
        </html>
        """,
    },
}

DEFAULT_TEMPLATE_METADATA = {
    "account_notice": ("easy", "Security", "Account verification", "urgency"),
    "invoice_review": ("medium", "Finance", "Invoice fraud", "authority"),
    "shared_document": ("easy", "Collaboration", "Shared documents", "curiosity"),
    "delivery_notice": ("easy", "Operations", "Delivery notification", "urgency"),
    "payroll_update": ("hard", "Finance", "Payroll change", "authority"),
    "security_policy_reminder": ("medium", "IT", "Security policy", "authority"),
    "cloud_storage_alert": ("medium", "IT", "Cloud storage", "fear"),
    "benefits_enrollment": ("medium", "HR", "Benefits enrollment", "urgency"),
    "travel_reimbursement": ("hard", "Finance", "Expense reimbursement", "reward"),
    "shared_drive_access": ("hard", "Collaboration", "Shared drive access", "curiosity"),
    "mock_phishing": ("easy", "Training", "Phishing fundamentals", "urgency"),
    "password_reset": ("medium", "Security", "Password reset", "urgency"),
}


def get_default_template(key: str) -> Dict[str, Optional[str]]:
    if key not in DEFAULT_EMAIL_TEMPLATES:
        raise KeyError(f"Unknown email template key: {key}")
    return DEFAULT_EMAIL_TEMPLATES[key]


def render_template(content: Optional[str], context: Dict[str, str]) -> Optional[str]:
    if content is None:
        return None
    rendered = content
    for key, value in context.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", str(value))
    return rendered


def get_or_create_template(db: Session, key: str) -> EmailTemplate:
    template = db.query(EmailTemplate).filter(EmailTemplate.key == key).first()
    if template:
        difficulty, category, topic, technique = DEFAULT_TEMPLATE_METADATA.get(
            key, ("medium", "General", "Security awareness", "urgency")
        )
        if template.origin == "system" and template.category in {None, "General"}:
            template.difficulty = difficulty
            template.category = category
            template.topic = topic
            template.psychological_technique = technique
            db.commit()
            db.refresh(template)
        return template
    defaults = get_default_template(key)
    difficulty, category, topic, technique = DEFAULT_TEMPLATE_METADATA.get(
        key, ("medium", "General", "Security awareness", "urgency")
    )
    template = EmailTemplate(
        key=key,
        name=defaults["name"] or key,
        subject=defaults["subject"] or f"Message from {settings.APP_NAME}",
        body_text=defaults.get("body_text"),
        body_html=defaults.get("body_html"),
      approval_status="approved",
      origin="system",
      difficulty=difficulty,
      category=category,
      topic=topic,
      psychological_technique=technique,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def create_custom_template(
    db: Session,
    key: str,
    name: str,
    subject: str,
    body_text: Optional[str] = None,
    body_html: Optional[str] = None,
  approval_status: str = "approved",
  approved_by: Optional[str] = None,
  origin: str = "manual",
  assistant_metadata: Optional[dict] = None,
  difficulty: str = "medium",
  category: str = "General",
  topic: str = "Security awareness",
  psychological_technique: str = "urgency",
) -> EmailTemplate:
    normalized_key = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_") or "custom_template"
    existing = db.query(EmailTemplate).filter(EmailTemplate.key == normalized_key).first()
    if existing:
        return existing

    template = EmailTemplate(
        key=normalized_key,
        name=name or "Custom template",
        subject=subject or f"Message from {settings.APP_NAME}",
        body_text=body_text,
        body_html=sanitize_email_html(body_html),
      approval_status=approval_status,
      approved_by=approved_by,
      approved_at=datetime.utcnow() if approval_status == "approved" else None,
      origin=origin,
      assistant_metadata=json.dumps(assistant_metadata, ensure_ascii=True) if assistant_metadata is not None else None,
      difficulty=difficulty,
      category=category,
      topic=topic,
      psychological_technique=psychological_technique,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def reset_template(db: Session, key: str) -> EmailTemplate:
    defaults = get_default_template(key)
    template = get_or_create_template(db, key)
    template.name = defaults["name"] or template.name
    template.subject = defaults["subject"] or template.subject
    template.body_text = defaults.get("body_text")
    template.body_html = defaults.get("body_html")
    template.approval_status = "approved"
    template.origin = "system"
    template.assistant_metadata = None
    template.approved_at = datetime.utcnow()
    db.commit()
    db.refresh(template)
    return template
