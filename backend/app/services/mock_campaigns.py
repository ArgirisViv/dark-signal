from datetime import datetime
from urllib.parse import urlencode
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.scenario import Scenario
from app.models.user import User
from app.models.campaign_recipient_snapshot import CampaignRecipientSnapshot
from app.services.audit import record_event


TEXT_LINK_START = "[SIMULATION_LINK_START]"
TEXT_LINK_END = "[SIMULATION_LINK_END]"
HTML_LINK_START = "<!--SIMULATION_LINK_START-->"
HTML_LINK_END = "<!--SIMULATION_LINK_END-->"


def build_recipient_interaction_urls(*, token: str) -> dict[str, str]:
    base_url = settings.SIMULATION_LINK_BASE_URL.rstrip("/")
    return {
        "open": f"{base_url}/simulate/phishing-open?{urlencode({'token': token})}",
        "click": f"{base_url}/simulate/phishing-link?{urlencode({'token': token})}",
        "report": f"{base_url}/simulate/phishing-report?{urlencode({'token': token})}",
    }


def _replace_link_block(content: str, start_marker: str, end_marker: str, replacement_block: str) -> str:
    if start_marker in content and end_marker in content:
        start = content.index(start_marker)
        end = content.index(end_marker) + len(end_marker)
        return f"{content[:start]}{replacement_block}{content[end:]}".strip()
    return f"{content.rstrip()}\n\n{replacement_block}".strip()


def _inject_simulation_link(indicators: dict, simulation_link: str) -> dict:
    text_block = (
        f"{TEXT_LINK_START}\n"
        "Training simulation link:\n"
        f"{simulation_link}\n"
        f"{TEXT_LINK_END}"
    )
    html_block = (
        f"{HTML_LINK_START}"
        '<p><strong>Training simulation link:</strong> '
        f'<a href="{simulation_link}">{simulation_link}</a></p>'
        f"{HTML_LINK_END}"
    )

    body_text = indicators.get("email_body_text") or ""
    body_html = indicators.get("email_body_html") or ""

    indicators["email_body_text"] = _replace_link_block(body_text, TEXT_LINK_START, TEXT_LINK_END, text_block)
    indicators["email_body_html"] = _replace_link_block(body_html, HTML_LINK_START, HTML_LINK_END, html_block)
    indicators["simulation_click_url"] = simulation_link
    return indicators


def execute_mock_campaign(
    db: Session,
    scenario: Scenario,
    executed_at: datetime | None = None,
) -> tuple[int, str]:
    """Record mock delivery events for a scenario without sending real email."""
    indicators = dict(scenario.indicators or {})
    audience = (indicators.get("audience") or "All Staff").strip() or "All Staff"
    audience_normalized = audience.lower()
    target_user_ids = [
        int(user_id)
        for user_id in (indicators.get("user_target_ids") or [])
        if str(user_id).isdigit()
    ]

    # Application accounts (admin/analyst/viewer) must never become simulation
    # recipients. CSV-imported recipient records use the dedicated trainee role.
    users_query = (
        db.query(User)
        .filter(User.tenant_id == scenario.tenant_id)
        .filter(User.role == "trainee")
    )
    if target_user_ids:
        users_query = users_query.filter(User.id.in_(target_user_ids))
    if audience_normalized != "all staff":
        users_query = users_query.filter(func.lower(User.department) == audience_normalized)
    recipients = users_query.all()

    execution_time = executed_at or datetime.utcnow()
    base_url = settings.SIMULATION_LINK_BASE_URL.rstrip("/")
    simulation_link = f"{base_url}/simulate/phishing-link?{urlencode({'scenario_id': scenario.id})}"
    indicators = _inject_simulation_link(indicators, simulation_link)
    campaign_id = scenario.campaign_id

    for user in recipients:
        interaction_token = uuid4().hex
        db.add(
            CampaignRecipientSnapshot(
                tenant_id=scenario.tenant_id,
                campaign_id=campaign_id,
                scenario_id=scenario.id,
                user_id=user.id,
                email=user.email,
                full_name=user.full_name,
                department=user.department,
                interaction_token=interaction_token,
                executed_at=execution_time,
            )
        )
        record_event(
            db,
            action="phishing.mock_sent",
            user_id=user.id,
            scenario_id=scenario.id,
            campaign_id=campaign_id,
            tenant_id=scenario.tenant_id,
        )

    indicators["last_run"] = execution_time.date().isoformat()
    indicators["status"] = "Completed"
    scenario.indicators = indicators
    return len(recipients), audience
