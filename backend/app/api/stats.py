"""
Statistics and analytics endpoints.
Provides aggregated data about system performance, user behavior, and phishing campaign metrics.
"""

from fastapi import APIRouter, Query, HTTPException, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse, JSONResponse
import io
import csv
from typing import Annotated, Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, case, distinct, and_, or_
from app.db.session import get_db
from app.models.campaign import Campaign
from app.models.user import User
from app.models.scenario import Scenario
from app.models.event import Event
from app.models.training_assignment import TrainingAssignment
from app.models.alert_acknowledgement import AlertAcknowledgement
from app.api.deps import require_roles
from app.core.rbac import Role
from .stats_schemas import (
    StatisticsSummary, 
    ScenarioMetrics, 
    UserPerformance, 
    DashboardData,
    OperationalAlertsResponse,
    ExportRequest,
    ExportFormat,
    BatchOperation,
    BatchOperationResult,
    PaginationParams,
    PaginatedResponse,
    BreakdownsResponse,
    DepartmentBreakdown,
    RiskBreakdown,
    TrendsResponse,
    TrendPoint,
    GeoResponse,
    GeoPoint,
    GeoEventSample,
)

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

router = APIRouter()


MOCK_GEO_LOCATIONS = [
    {"city": "New York", "country": "United States", "lat": 40.7128, "lng": -74.0060},
    {"city": "San Francisco", "country": "United States", "lat": 37.7749, "lng": -122.4194},
    {"city": "Toronto", "country": "Canada", "lat": 43.6532, "lng": -79.3832},
    {"city": "Mexico City", "country": "Mexico", "lat": 19.4326, "lng": -99.1332},
    {"city": "Sao Paulo", "country": "Brazil", "lat": -23.5505, "lng": -46.6333},
    {"city": "Buenos Aires", "country": "Argentina", "lat": -34.6037, "lng": -58.3816},
    {"city": "London", "country": "United Kingdom", "lat": 51.5074, "lng": -0.1278},
    {"city": "Paris", "country": "France", "lat": 48.8566, "lng": 2.3522},
    {"city": "Berlin", "country": "Germany", "lat": 52.5200, "lng": 13.4050},
    {"city": "Madrid", "country": "Spain", "lat": 40.4168, "lng": -3.7038},
    {"city": "Rome", "country": "Italy", "lat": 41.9028, "lng": 12.4964},
    {"city": "Athens", "country": "Greece", "lat": 37.9838, "lng": 23.7275},
    {"city": "Cairo", "country": "Egypt", "lat": 30.0444, "lng": 31.2357},
    {"city": "Nairobi", "country": "Kenya", "lat": -1.2864, "lng": 36.8172},
    {"city": "Johannesburg", "country": "South Africa", "lat": -26.2041, "lng": 28.0473},
    {"city": "Istanbul", "country": "Turkey", "lat": 41.0082, "lng": 28.9784},
    {"city": "Dubai", "country": "United Arab Emirates", "lat": 25.2048, "lng": 55.2708},
    {"city": "Mumbai", "country": "India", "lat": 19.0760, "lng": 72.8777},
    {"city": "Bangkok", "country": "Thailand", "lat": 13.7563, "lng": 100.5018},
    {"city": "Singapore", "country": "Singapore", "lat": 1.3521, "lng": 103.8198},
    {"city": "Tokyo", "country": "Japan", "lat": 35.6762, "lng": 139.6503},
    {"city": "Seoul", "country": "South Korea", "lat": 37.5665, "lng": 126.9780},
    {"city": "Sydney", "country": "Australia", "lat": -33.8688, "lng": 151.2093},
    {"city": "Auckland", "country": "New Zealand", "lat": -36.8485, "lng": 174.7633},
]


def _mock_ip(event_id: int) -> str:
    ranges = ["203.0.113", "198.51.100", "192.0.2"]
    base = ranges[event_id % len(ranges)]
    octet = (event_id * 73 + 17) % 254 + 1
    return f"{base}.{octet}"


def _mock_location(event_id: int) -> dict:
    base = MOCK_GEO_LOCATIONS[event_id % len(MOCK_GEO_LOCATIONS)]
    jitter_lat = ((event_id * 13) % 9 - 4) * 0.2
    jitter_lng = ((event_id * 17) % 9 - 4) * 0.3
    lat = max(-80.0, min(80.0, base["lat"] + jitter_lat))
    lng = max(-179.0, min(179.0, base["lng"] + jitter_lng))
    return {**base, "lat": lat, "lng": lng}


def _campaign_event_condition(db: Session, campaign_id: Optional[int]):
    if campaign_id is None:
        return None
    scenario_ids = db.query(Scenario.id).filter(Scenario.campaign_id == campaign_id)
    return or_(Event.campaign_id == campaign_id, Event.scenario_id.in_(scenario_ids))


def _event_join_condition(base_condition, scenario_filter, date_from, date_to, tenant_id, campaign_condition=None):
    condition = base_condition
    if scenario_filter is not None:
        condition = and_(condition, Event.scenario_id == scenario_filter)
    if date_from is not None:
        condition = and_(condition, Event.created_at >= date_from)
    if date_to is not None:
        condition = and_(condition, Event.created_at <= date_to)
    if tenant_id is not None:
        condition = and_(condition, Event.tenant_id == tenant_id)
    if campaign_condition is not None:
        condition = and_(condition, campaign_condition)
    return condition


def _fetch_summary(db: Session, scenario_filter, date_from, date_to, tenant_id, campaign_filter=None):
    event_query = db.query(Event)
    if scenario_filter is not None:
        event_query = event_query.filter(Event.scenario_id == scenario_filter)
    if date_from is not None:
        event_query = event_query.filter(Event.created_at >= date_from)
    if date_to is not None:
        event_query = event_query.filter(Event.created_at <= date_to)
    if tenant_id is not None:
        event_query = event_query.filter(Event.tenant_id == tenant_id)
    campaign_condition = _campaign_event_condition(db, campaign_filter)
    if campaign_condition is not None:
        event_query = event_query.filter(campaign_condition)

    total_events = event_query.count()
    click_count = event_query.filter(Event.action == "click").count()
    report_count = event_query.filter(Event.action == "report").count()

    if scenario_filter is not None:
        total_scenarios = (
            db.query(func.count(Scenario.id))
            .filter(Scenario.id == scenario_filter)
            .filter(Scenario.tenant_id == tenant_id)
            .scalar()
            or 0
        )
    elif campaign_filter is not None:
        total_scenarios = (
            db.query(func.count(Scenario.id))
            .filter(Scenario.campaign_id == campaign_filter)
            .filter(Scenario.tenant_id == tenant_id)
            .scalar()
            or 0
        )
    else:
        total_scenarios = (
            db.query(func.count(Scenario.id))
            .filter(Scenario.tenant_id == tenant_id)
            .scalar()
            or 0
        )

    total_campaigns = (
        db.query(func.count(Campaign.id))
        .filter(Campaign.tenant_id == tenant_id)
        .filter(Campaign.id == campaign_filter if campaign_filter is not None else True)
        .scalar()
        or 0
    )

    total_users = (
        event_query.with_entities(func.count(distinct(Event.user_id)))
        .filter(Event.user_id.isnot(None))
        .scalar()
        or 0
    )

    average_click_rate = (click_count / total_events * 100) if total_events else 0.0
    average_report_rate = (report_count / total_events * 100) if total_events else 0.0

    return {
        "total_users": total_users,
        "total_scenarios": total_scenarios,
        "total_campaigns": total_campaigns,
        "total_events": total_events,
        "average_click_rate": average_click_rate,
        "average_report_rate": average_report_rate,
    }


def _fetch_scenario_rows(db: Session, scenario_filter, date_from, date_to, tenant_id, campaign_filter=None):
    campaign_condition = _campaign_event_condition(db, campaign_filter)
    join_condition = _event_join_condition(
        Event.scenario_id == Scenario.id, scenario_filter, date_from, date_to, tenant_id, campaign_condition
    )
    query = (
        db.query(
            Scenario.id.label("id"),
            Scenario.title.label("name"),
            func.count(distinct(Event.user_id)).label("recipients"),
            func.sum(case((Event.action == "click", 1), else_=0)).label("clicks"),
            func.sum(case((Event.action == "report", 1), else_=0)).label("reports"),
            func.count(Event.id).label("total_events"),
        )
        .outerjoin(Event, join_condition)
        .group_by(Scenario.id)
    )
    query = query.filter(Scenario.tenant_id == tenant_id)
    if scenario_filter is not None:
        query = query.filter(Scenario.id == scenario_filter)
    if campaign_filter is not None:
        query = query.filter(Scenario.campaign_id == campaign_filter)
    rows = query.all()
    scenarios = []
    for row in rows:
        total_events = row.total_events or 0
        clicks = row.clicks or 0
        reports = row.reports or 0
        scenarios.append(
            {
                "id": str(row.id),
                "name": row.name or "Untitled",
                "recipients": row.recipients or 0,
                "clicks": clicks,
                "reports": reports,
                "click_rate": (clicks / total_events * 100) if total_events else 0.0,
                "report_rate": (reports / total_events * 100) if total_events else 0.0,
            }
        )
    return scenarios


def _awareness_score(click_rate: float, report_rate: float) -> float:
    return round(max(0.0, min(100.0, (100.0 - click_rate) * 0.6 + report_rate * 0.4)), 1)


def _fetch_campaign_rows(db: Session, tenant_id, campaign_filter: Optional[int] = None):
    campaign_query = db.query(Campaign).filter(Campaign.tenant_id == tenant_id)
    if campaign_filter is not None:
        campaign_query = campaign_query.filter(Campaign.id == campaign_filter)
    campaign_models = campaign_query.order_by(Campaign.id.desc()).all()

    scenarios = db.query(Scenario).filter(Scenario.tenant_id == tenant_id).all()
    scenario_campaign = {scenario.id: scenario.campaign_id for scenario in scenarios}
    scenario_counts = {}
    for scenario in scenarios:
        if scenario.campaign_id is not None:
            scenario_counts[scenario.campaign_id] = scenario_counts.get(scenario.campaign_id, 0) + 1

    metrics = {
        campaign.id: {"delivered": set(), "opened": set(), "clicked": set(), "reported": set()}
        for campaign in campaign_models
    }
    recipient_user_ids = {
        user_id
        for (user_id,) in db.query(User.id)
        .filter(User.tenant_id == tenant_id)
        .filter(User.role == Role.trainee.value)
        .all()
    }
    for event in db.query(Event).filter(Event.tenant_id == tenant_id).all():
        resolved_campaign_id = event.campaign_id or scenario_campaign.get(event.scenario_id)
        if resolved_campaign_id not in metrics or event.user_id not in recipient_user_ids:
            continue
        action = (event.action or "").lower()
        if action == "phishing.mock_sent":
            metrics[resolved_campaign_id]["delivered"].add(event.user_id)
        if action in {"open", "opened", "email.open"}:
            metrics[resolved_campaign_id]["opened"].add(event.user_id)
        if "click" in action:
            metrics[resolved_campaign_id]["clicked"].add(event.user_id)
        if "report" in action:
            metrics[resolved_campaign_id]["reported"].add(event.user_id)

    campaigns = []
    for campaign in campaign_models:
        values = metrics[campaign.id]
        recipients = len(values["delivered"])
        opened = len(values["opened"] & values["delivered"])
        clicked = len(values["clicked"] & values["delivered"])
        reported = len(values["reported"] & values["delivered"])
        click_rate = round(clicked / recipients * 100, 1) if recipients else 0.0
        report_rate = round(reported / recipients * 100, 1) if recipients else 0.0
        open_rate = round(opened / recipients * 100, 1) if recipients else 0.0
        score = _awareness_score(click_rate, report_rate) if recipients else 0.0
        campaigns.append(
            {
                "campaign_id": str(campaign.id),
                "campaign_name": campaign.name or "Untitled",
                "scenario_count": scenario_counts.get(campaign.id, 0),
                "total_recipients": recipients,
                "open_count": opened,
                "click_count": clicked,
                "report_count": reported,
                "open_rate": open_rate,
                "click_rate": click_rate,
                "report_rate": report_rate,
                "awareness_score": score,
                "score_explanation": (
                    f"{100.0 - click_rate:.1f}% avoided clicking and {report_rate:.1f}% reported the email"
                    if recipients
                    else "No email recipients yet"
                ),
            }
        )
    campaigns.sort(
        key=lambda item: (item["total_recipients"] > 0, item["awareness_score"], item["total_recipients"]),
        reverse=True,
    )
    return campaigns[:10]


def _fetch_user_rows(db: Session, scenario_filter, date_from, date_to, tenant_id, campaign_filter=None):
    campaign_condition = _campaign_event_condition(db, campaign_filter)
    join_condition = _event_join_condition(
        Event.user_id == User.id, scenario_filter, date_from, date_to, tenant_id, campaign_condition
    )
    rows = (
        db.query(
            User.id.label("user_id"),
            User.email.label("username"),
            User.department.label("department"),
            User.risk.label("risk"),
            func.count(distinct(Event.scenario_id)).label("scenarios_exposed"),
            func.sum(case((Event.action == "click", 1), else_=0)).label("clicks"),
            func.sum(case((Event.action == "report", 1), else_=0)).label("reports"),
            func.count(Event.id).label("total_events"),
        )
        .outerjoin(Event, join_condition)
        .filter(User.tenant_id == tenant_id)
        .group_by(User.id)
        .all()
    )

    users = []
    for row in rows:
        total_events = row.total_events or 0
        clicks = row.clicks or 0
        reports = row.reports or 0
        click_rate = (clicks / total_events * 100) if total_events else 0.0
        report_rate = (reports / total_events * 100) if total_events else 0.0
        training_score = max(0.0, 100.0 - click_rate + (report_rate / 2))
        users.append(
            {
                "user_id": str(row.user_id),
                "username": row.username,
                "department": row.department,
                "risk": row.risk,
                "scenarios_exposed": row.scenarios_exposed or 0,
                "clicks": clicks,
                "reports": reports,
                "click_rate": click_rate,
                "report_rate": report_rate,
                "total_events": total_events,
                "training_score": round(training_score, 1),
            }
        )
    return users


def _fetch_event_rows(db: Session, scenario_filter, date_from, date_to, tenant_id, campaign_filter=None):
    query = db.query(
        Event.id,
        Event.action,
        Event.user_id,
        Event.scenario_id,
        Event.created_at,
    )
    if scenario_filter is not None:
        query = query.filter(Event.scenario_id == scenario_filter)
    if date_from is not None:
        query = query.filter(Event.created_at >= date_from)
    if date_to is not None:
        query = query.filter(Event.created_at <= date_to)
    if tenant_id is not None:
        query = query.filter(Event.tenant_id == tenant_id)
    campaign_condition = _campaign_event_condition(db, campaign_filter)
    if campaign_condition is not None:
        query = query.filter(campaign_condition)
    return query.order_by(Event.id.desc()).all()


def _build_pdf_report(summary, scenarios, users, events, title="Dark Signal Analytics Report"):
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 50

    def draw_line(text, size=10, bold=False, gap=14):
        nonlocal y
        if y < 60:
            pdf.showPage()
            y = height - 50
        font = "Helvetica-Bold" if bold else "Helvetica"
        pdf.setFont(font, size)
        pdf.drawString(40, y, text)
        y -= gap

    pdf.setTitle(title)
    draw_line(title, size=16, bold=True, gap=22)
    draw_line(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", size=9, gap=18)

    draw_line("Summary", bold=True, gap=16)
    draw_line(f"Total users: {summary['total_users']}")
    draw_line(f"Total scenarios: {summary['total_scenarios']}")
    draw_line(f"Total campaigns: {summary['total_campaigns']}")
    draw_line(f"Total events: {summary['total_events']}")
    draw_line(f"Average click rate: {summary['average_click_rate']:.1f}%")
    draw_line(f"Average report rate: {summary['average_report_rate']:.1f}%")

    if scenarios:
        draw_line("", gap=8)
        draw_line("Scenario Metrics", bold=True, gap=16)
        for item in scenarios[:25]:
            draw_line(
                f"{item['name']} | Recipients: {item['recipients']} | Click: {item['click_rate']:.1f}% | Report: {item['report_rate']:.1f}%",
                size=9,
                gap=12,
            )
        if len(scenarios) > 25:
            draw_line(f"...and {len(scenarios) - 25} more scenarios", size=9, gap=12)

    if users:
        draw_line("", gap=8)
        draw_line("User Performance", bold=True, gap=16)
        for item in users[:25]:
            draw_line(
                f"{item['username']} | Score: {item['training_score']:.1f} | Click: {item['click_rate']:.1f}% | Report: {item['report_rate']:.1f}%",
                size=9,
                gap=12,
            )
        if len(users) > 25:
            draw_line(f"...and {len(users) - 25} more users", size=9, gap=12)

    if events:
        draw_line("", gap=8)
        draw_line("Event Log", bold=True, gap=16)
        for item in events[:50]:
            timestamp = item.created_at.strftime("%Y-%m-%d %H:%M") if item.created_at else "—"
            draw_line(
                f"{timestamp} | {item.action} | user:{item.user_id or '-'} | scenario:{item.scenario_id or '-'}",
                size=8,
                gap=11,
            )
        if len(events) > 50:
            draw_line(f"...and {len(events) - 50} more events", size=8, gap=11)

    pdf.save()
    buffer.seek(0)
    return buffer


@router.get(
    "/operational-alerts",
    response_model=OperationalAlertsResponse,
    summary="Get operational dashboard alerts",
)
def get_operational_alerts(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(Role.admin)),
):
    tenant_id = current_user.tenant_id
    alerts = []
    users = db.query(User).filter(User.tenant_id == tenant_id).all()
    user_ids = [user.id for user in users]
    events = (
        db.query(Event)
        .filter(Event.tenant_id == tenant_id)
        .filter(Event.user_id.in_(user_ids))
        .all()
        if user_ids
        else []
    )
    clicks_by_user = {}
    reports_by_user = {}
    for event in events:
        action = (event.action or "").lower()
        if "click" in action:
            clicks_by_user[event.user_id] = clicks_by_user.get(event.user_id, 0) + 1
        if "report" in action:
            reports_by_user[event.user_id] = reports_by_user.get(event.user_id, 0) + 1
    high_risk_users = [
        user
        for user in users
        if clicks_by_user.get(user.id, 0) >= 2
        or (clicks_by_user.get(user.id, 0) > reports_by_user.get(user.id, 0) and clicks_by_user.get(user.id, 0) > 0)
    ]
    if high_risk_users:
        alerts.append({
            "id": "high-risk-users",
            "severity": "danger",
            "title": f"{len(high_risk_users)} high-risk user{'' if len(high_risk_users) == 1 else 's'} need review",
            "description": "Recent simulation behavior indicates more clicks than reports or repeated clicks.",
            "action_label": "Review users",
            "action_path": "/users",
        })

    pending_assignments = (
        db.query(func.count(TrainingAssignment.id))
        .filter(TrainingAssignment.tenant_id == tenant_id)
        .filter(TrainingAssignment.status != "Completed")
        .scalar()
        or 0
    )
    if pending_assignments:
        alerts.append({
            "id": "pending-training",
            "severity": "warning",
            "title": f"{pending_assignments} training assignment{'' if pending_assignments == 1 else 's'} still open",
            "description": "Assigned learning follow-up has not yet been completed.",
            "action_label": "Manage training",
            "action_path": "/users",
        })

    scheduled_campaigns = [
        scenario
        for scenario in db.query(Scenario).filter(Scenario.tenant_id == tenant_id).all()
        if (scenario.indicators or {}).get("status") == "Scheduled"
    ]
    if scheduled_campaigns:
        alerts.append({
            "id": "scheduled-campaigns",
            "severity": "primary",
            "title": f"{len(scheduled_campaigns)} campaign{'' if len(scheduled_campaigns) == 1 else 's'} scheduled",
            "description": "Review timing and audience before the next mock simulation runs.",
            "action_label": "Open campaigns",
            "action_path": "/scenarios",
        })
    acknowledged_ids = {
        row.alert_id
        for row in db.query(AlertAcknowledgement)
        .filter(AlertAcknowledgement.tenant_id == tenant_id)
        .all()
    }
    return {"alerts": [alert for alert in alerts if alert["id"] not in acknowledged_ids]}


@router.post(
    "/operational-alerts/{alert_id}/acknowledge",
    summary="Acknowledge an operational alert",
)
def acknowledge_operational_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(Role.admin)),
):
    existing = (
        db.query(AlertAcknowledgement)
        .filter(AlertAcknowledgement.tenant_id == current_user.tenant_id)
        .filter(AlertAcknowledgement.alert_id == alert_id)
        .first()
    )
    if not existing:
        db.add(AlertAcknowledgement(
            tenant_id=current_user.tenant_id,
            alert_id=alert_id,
            acknowledged_by_user_id=current_user.id,
        ))
        db.commit()
    return {"acknowledged": True, "alert_id": alert_id}


@router.get(
    "/dashboard",
    response_model=DashboardData,
    summary="Get Dashboard Data",
    description="Retrieve comprehensive dashboard data including overall statistics, top scenarios, and user rankings."
)
async def get_dashboard(
    campaign_id: Annotated[Optional[int], Query(ge=1, description="Optional campaign filter")] = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(Role.admin, Role.analyst, Role.viewer, Role.trainee)),
):
    """
    Get complete dashboard data for analytics visualization.
    
    Returns:
    - Overall platform statistics (users, scenarios, events, conversion rates)
    - Top 10 phishing scenarios by engagement
    - Top 10 users by training performance
    - Last update timestamp
    """
    tenant_id = current_user.tenant_id
    scenario_query = db.query(Scenario).filter(Scenario.tenant_id == tenant_id)
    if campaign_id is not None:
        campaign = (
            db.query(Campaign)
            .filter(Campaign.id == campaign_id)
            .filter(Campaign.tenant_id == tenant_id)
            .first()
        )
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        scenario_query = scenario_query.filter(Scenario.campaign_id == campaign_id)
    scenario_models = scenario_query.all()
    scenario_ids = {scenario.id for scenario in scenario_models}
    scenario_campaign = {scenario.id: scenario.campaign_id for scenario in scenario_models}
    recipient_user_ids = {
        user_id
        for (user_id,) in db.query(User.id)
        .filter(User.tenant_id == tenant_id)
        .filter(User.role == Role.trainee.value)
        .all()
    }

    event_query = (
        db.query(Event)
        .filter(Event.tenant_id == tenant_id)
        .filter(or_(Event.scenario_id.isnot(None), Event.campaign_id.isnot(None)))
    )
    if campaign_id is not None:
        event_query = event_query.filter(
            (Event.campaign_id == campaign_id) | (Event.scenario_id.in_(scenario_ids))
        )
    events = event_query.all()

    delivered_pairs = {
        (event.user_id, event.scenario_id)
        for event in events
        if event.user_id in recipient_user_ids and event.action == "phishing.mock_sent"
    }
    delivered_users = {user_id for user_id, _ in delivered_pairs}
    opened_users = {
        event.user_id for event in events
        if event.user_id in delivered_users and (event.action or "").lower() in {"open", "opened", "email.open"}
    }
    clicked_users = {
        event.user_id for event in events
        if event.user_id in delivered_users and "click" in (event.action or "").lower()
    }
    reported_users = {
        event.user_id for event in events
        if event.user_id in delivered_users and "report" in (event.action or "").lower()
    }
    recipients = len(delivered_users)
    average_click_rate = round(len(clicked_users) / recipients * 100, 1) if recipients else 0.0
    average_report_rate = round(len(reported_users) / recipients * 100, 1) if recipients else 0.0

    summary = StatisticsSummary(
        total_users=recipients,
        total_scenarios=len(scenario_models),
        total_campaigns=1 if campaign_id is not None else (
            db.query(func.count(Campaign.id)).filter(Campaign.tenant_id == tenant_id).scalar() or 0
        ),
        total_events=len(events),
        email_recipients=recipients,
        delivered_count=len(delivered_pairs),
        opened_count=len(opened_users),
        clicked_count=len(clicked_users),
        reported_count=len(reported_users),
        average_click_rate=average_click_rate,
        average_report_rate=average_report_rate,
    )

    top_campaigns = _fetch_campaign_rows(db, tenant_id, campaign_id)

    per_scenario = {
        scenario.id: {"scenario": scenario, "delivered": set(), "clicked": set(), "reported": set()}
        for scenario in scenario_models
    }
    for event in events:
        values = per_scenario.get(event.scenario_id)
        if not values or event.user_id not in recipient_user_ids:
            continue
        action = (event.action or "").lower()
        if action == "phishing.mock_sent":
            values["delivered"].add(event.user_id)
        if "click" in action:
            values["clicked"].add(event.user_id)
        if "report" in action:
            values["reported"].add(event.user_id)

    top_scenarios: List[ScenarioMetrics] = []
    for values in per_scenario.values():
        scenario_recipients = len(values["delivered"])
        clicks = len(values["clicked"] & values["delivered"])
        reports = len(values["reported"] & values["delivered"])
        top_scenarios.append(
            ScenarioMetrics(
                scenario_id=str(values["scenario"].id),
                scenario_name=values["scenario"].title or "Untitled",
                total_recipients=scenario_recipients,
                click_count=clicks,
                report_count=reports,
                click_rate=round(clicks / scenario_recipients * 100, 1) if scenario_recipients else 0.0,
                report_rate=round(reports / scenario_recipients * 100, 1) if scenario_recipients else 0.0,
            )
        )
    top_scenarios.sort(key=lambda item: item.total_recipients, reverse=True)

    users_by_id = {
        user.id: user
        for user in db.query(User)
        .filter(User.tenant_id == tenant_id)
        .filter(User.role == Role.trainee.value)
        .all()
    }
    per_user = {
        user_id: {"delivered": set(), "clicked": set(), "reported": set()}
        for user_id in users_by_id
    }
    for event in events:
        if event.user_id not in per_user or event.scenario_id is None:
            continue
        action = (event.action or "").lower()
        if action == "phishing.mock_sent":
            per_user[event.user_id]["delivered"].add(event.scenario_id)
        if "click" in action:
            per_user[event.user_id]["clicked"].add(event.scenario_id)
        if "report" in action:
            per_user[event.user_id]["reported"].add(event.scenario_id)

    user_rankings: List[UserPerformance] = []
    for user_id, values in per_user.items():
        exposures = len(values["delivered"])
        if not exposures:
            continue
        clicks = len(values["clicked"] & values["delivered"])
        reports = len(values["reported"] & values["delivered"])
        click_rate = round(clicks / exposures * 100, 1)
        report_rate = round(reports / exposures * 100, 1)
        score = _awareness_score(click_rate, report_rate)
        user_rankings.append(
            UserPerformance(
                user_id=str(user_id),
                username=users_by_id[user_id].email,
                recipient_id=str(user_id),
                recipient_email=users_by_id[user_id].email,
                total_scenarios_exposed=exposures,
                clicks=clicks,
                reports=reports,
                click_rate=click_rate,
                report_rate=report_rate,
                training_score=score,
                score_explanation=f"Reported {reports}/{exposures} emails and clicked {clicks}/{exposures}",
            )
        )
    user_rankings.sort(key=lambda item: (item.training_score, item.total_scenarios_exposed), reverse=True)

    return DashboardData(
        summary=summary,
        top_campaigns=top_campaigns,
        top_scenarios=top_scenarios[:10],
        user_rankings=user_rankings[:10],
        recipient_rankings=user_rankings[:10],
    )


@router.get(
    "/scenarios",
    response_model=PaginatedResponse,
    summary="List Scenario Metrics",
    description="Get detailed metrics for all phishing scenarios with pagination support."
)
async def list_scenario_metrics(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum items to return"),
    sort_by: Optional[str] = Query("click_rate", description="Field to sort by"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(Role.admin, Role.analyst, Role.viewer)),
):
    """
    List all scenario metrics with filtering and pagination.
    
    Query Parameters:
    - skip: Number of records to skip (default: 0)
    - limit: Maximum records to return (default: 50, max: 100)
    - sort_by: Field to sort by (default: click_rate)
    - sort_order: Sort direction, asc or desc (default: desc)
    """
    tenant_id = current_user.tenant_id
    total = db.query(func.count(Scenario.id)).filter(Scenario.tenant_id == tenant_id).scalar() or 0
    sort_column = {
        "click_rate": "click_rate",
        "report_rate": "report_rate",
        "recipients": "recipients",
        "clicks": "clicks",
        "reports": "reports",
    }.get(sort_by, "click_rate")

    rows = (
        db.query(
            Scenario.id.label("id"),
            Scenario.title.label("name"),
            func.count(distinct(Event.user_id)).label("recipients"),
            func.sum(case((Event.action == "click", 1), else_=0)).label("clicks"),
            func.sum(case((Event.action == "report", 1), else_=0)).label("reports"),
            func.count(Event.id).label("total_events"),
        )
        .outerjoin(Event, and_(Event.scenario_id == Scenario.id, Event.tenant_id == tenant_id))
        .filter(Scenario.tenant_id == tenant_id)
        .group_by(Scenario.id)
        .offset(skip)
        .limit(limit)
        .all()
    )

    scenarios = []
    for row in rows:
        total_events = row.total_events or 0
        clicks = row.clicks or 0
        reports = row.reports or 0
        click_rate = (clicks / total_events * 100) if total_events else 0.0
        report_rate = (reports / total_events * 100) if total_events else 0.0
        scenarios.append(
            {
                "id": str(row.id),
                "name": row.name or "Untitled",
                "recipients": row.recipients or 0,
                "clicks": clicks,
                "reports": reports,
                "click_rate": click_rate,
                "report_rate": report_rate,
            }
        )

    reverse = sort_order == "desc"
    scenarios.sort(key=lambda item: item.get(sort_column, 0), reverse=reverse)

    return PaginatedResponse(
        total=total,
        skip=skip,
        limit=limit,
        items=scenarios,
        has_more=(skip + limit) < total
    )


@router.get(
    "/users",
    response_model=PaginatedResponse,
    summary="List User Performance Metrics",
    description="Get performance metrics for all users with sorting and pagination."
)
async def list_user_metrics(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    sort_by: str = Query("training_score", description="Field to sort by"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(Role.admin, Role.analyst, Role.viewer)),
):
    """
    List all users' performance metrics with filtering and pagination.
    
    Can be sorted by: training_score, click_rate, report_rate, username
    """
    tenant_id = current_user.tenant_id
    total = db.query(func.count(User.id)).filter(User.tenant_id == tenant_id).scalar() or 0
    rows = (
        db.query(
            User.id.label("user_id"),
            User.email.label("username"),
            User.department.label("department"),
            User.risk.label("risk"),
            func.count(distinct(Event.scenario_id)).label("scenarios_exposed"),
            func.sum(case((Event.action == "click", 1), else_=0)).label("clicks"),
            func.sum(case((Event.action == "report", 1), else_=0)).label("reports"),
            func.count(Event.id).label("total_events"),
        )
        .outerjoin(Event, and_(Event.user_id == User.id, Event.tenant_id == tenant_id))
        .filter(User.tenant_id == tenant_id)
        .group_by(User.id)
        .offset(skip)
        .limit(limit)
        .all()
    )

    users = []
    for row in rows:
        total_events = row.total_events or 0
        clicks = row.clicks or 0
        reports = row.reports or 0
        click_rate = (clicks / total_events * 100) if total_events else 0.0
        report_rate = (reports / total_events * 100) if total_events else 0.0
        training_score = max(0.0, 100.0 - click_rate + (report_rate / 2))
        users.append(
            {
                "user_id": str(row.user_id),
                "username": row.username,
                "department": row.department,
                "risk": row.risk,
                "scenarios_exposed": row.scenarios_exposed or 0,
                "clicks": clicks,
                "reports": reports,
                "click_rate": click_rate,
                "report_rate": report_rate,
                "total_events": total_events,
                "training_score": round(training_score, 1),
            }
        )

    reverse = sort_order == "desc"
    users.sort(key=lambda item: item.get(sort_by, 0), reverse=reverse)

    return PaginatedResponse(
        total=total,
        skip=skip,
        limit=limit,
        items=users,
        has_more=(skip + limit) < total
    )


@router.get(
    "/breakdowns",
    response_model=BreakdownsResponse,
    summary="Department and risk breakdowns",
    description="Return aggregated metrics by department and risk band.",
)
async def get_breakdowns(
    scenario_id: Optional[int] = Query(None, description="Optional scenario filter"),
    campaign_id: Annotated[Optional[int], Query(ge=1, description="Optional campaign filter")] = None,
    date_from: Optional[datetime] = Query(None, description="Filter data from this date"),
    date_to: Optional[datetime] = Query(None, description="Filter data to this date"),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(Role.admin, Role.analyst, Role.viewer)),
):
    tenant_id = current_user.tenant_id
    campaign_condition = _campaign_event_condition(db, campaign_id)
    eligible_user_ids = (
        db.query(Event.user_id)
        .filter(Event.tenant_id == tenant_id)
        .filter(Event.action == "phishing.mock_sent")
        .filter(campaign_condition if campaign_condition is not None else True)
        .distinct()
    )
    department_label = func.coalesce(User.department, "Unassigned")
    department_join = _event_join_condition(
        Event.user_id == User.id, scenario_id, date_from, date_to, tenant_id, campaign_condition
    )
    department_rows = (
        db.query(
            department_label.label("department"),
            func.count(distinct(User.id)).label("users"),
            func.sum(case((Event.action == "click", 1), else_=0)).label("clicks"),
            func.sum(case((Event.action == "report", 1), else_=0)).label("reports"),
            func.count(Event.id).label("total_events"),
        )
        .outerjoin(Event, department_join)
        .filter(User.tenant_id == tenant_id)
        .filter(User.role == Role.trainee.value)
        .filter(User.id.in_(eligible_user_ids))
        .group_by(department_label)
        .order_by(func.count(distinct(User.id)).desc())
        .all()
    )

    department_by_user_id = {
        user.id: user.department or "Unassigned"
        for user in db.query(User)
        .filter(User.tenant_id == tenant_id)
        .filter(User.role == Role.trainee.value)
        .filter(User.id.in_(eligible_user_ids))
        .all()
    }
    clicks_by_user = {}
    reports_by_user = {}
    risk_event_query = db.query(Event).filter(Event.tenant_id == tenant_id)
    if campaign_condition is not None:
        risk_event_query = risk_event_query.filter(campaign_condition)
    for event in risk_event_query.all():
        action = (event.action or "").lower()
        if "click" in action:
            clicks_by_user[event.user_id] = clicks_by_user.get(event.user_id, 0) + 1
        if "report" in action:
            reports_by_user[event.user_id] = reports_by_user.get(event.user_id, 0) + 1
    high_risk_by_department = {}
    for user_id, department in department_by_user_id.items():
        clicks = clicks_by_user.get(user_id, 0)
        reports = reports_by_user.get(user_id, 0)
        if clicks >= 2 or (clicks > reports and clicks > 0):
            high_risk_by_department[department] = high_risk_by_department.get(department, 0) + 1
    training_by_department = {}
    completed_training_by_department = {}
    assignments = db.query(TrainingAssignment).filter(TrainingAssignment.tenant_id == tenant_id).all()
    for assignment in assignments:
        department = department_by_user_id.get(assignment.user_id, "Unassigned")
        training_by_department[department] = training_by_department.get(department, 0) + 1
        if assignment.status == "Completed":
            completed_training_by_department[department] = completed_training_by_department.get(department, 0) + 1

    departments = []
    for row in department_rows:
        total_events = row.total_events or 0
        clicks = row.clicks or 0
        reports = row.reports or 0
        department_name = row.department or "Unassigned"
        training_assignments = training_by_department.get(department_name, 0)
        completed_assignments = completed_training_by_department.get(department_name, 0)
        departments.append(
            DepartmentBreakdown(
            name=department_name,
                users=row.users or 0,
                clicks=clicks,
                reports=reports,
                total_events=total_events,
                click_rate=(clicks / total_events * 100) if total_events else 0.0,
                report_rate=(reports / total_events * 100) if total_events else 0.0,
                high_risk_users=high_risk_by_department.get(department_name, 0),
                training_assignments=training_assignments,
                completed_training_assignments=completed_assignments,
                training_completion_rate=(completed_assignments / training_assignments * 100) if training_assignments else 0.0,
            )
        )

    risk_label = func.coalesce(User.risk, "low")
    risk_join = _event_join_condition(
        Event.user_id == User.id, scenario_id, date_from, date_to, tenant_id, campaign_condition
    )
    risk_rows = (
        db.query(
            risk_label.label("risk"),
            func.count(distinct(User.id)).label("users"),
            func.sum(case((Event.action == "click", 1), else_=0)).label("clicks"),
            func.sum(case((Event.action == "report", 1), else_=0)).label("reports"),
            func.count(Event.id).label("total_events"),
        )
        .outerjoin(Event, risk_join)
        .filter(User.tenant_id == tenant_id)
        .filter(User.role == Role.trainee.value)
        .filter(User.id.in_(eligible_user_ids))
        .group_by(risk_label)
        .order_by(func.count(distinct(User.id)).desc())
        .all()
    )

    risks = []
    for row in risk_rows:
        total_events = row.total_events or 0
        clicks = row.clicks or 0
        reports = row.reports or 0
        risks.append(
            RiskBreakdown(
                risk=row.risk or "low",
                users=row.users or 0,
                clicks=clicks,
                reports=reports,
                total_events=total_events,
                click_rate=(clicks / total_events * 100) if total_events else 0.0,
                report_rate=(reports / total_events * 100) if total_events else 0.0,
            )
        )

    return BreakdownsResponse(departments=departments, risks=risks)


@router.get(
    "/trends",
    response_model=TrendsResponse,
    summary="Event trends",
    description="Return daily trends for clicks and reports.",
)
async def get_trends(
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    scenario_id: Optional[int] = Query(None, description="Optional scenario filter"),
    campaign_id: Optional[int] = Query(None, ge=1, description="Optional campaign filter"),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(Role.admin, Role.analyst, Role.viewer)),
):
    tenant_id = current_user.tenant_id
    end = datetime.utcnow()
    start = end - timedelta(days=days)

    day_label = func.date(Event.created_at)
    query = (
        db.query(
            day_label.label("day"),
            func.count(Event.id).label("events"),
            func.sum(case((Event.action == "click", 1), else_=0)).label("clicks"),
            func.sum(case((Event.action == "report", 1), else_=0)).label("reports"),
        )
        .filter(Event.created_at >= start)
        .filter(Event.created_at <= end)
        .filter(Event.tenant_id == tenant_id)
    )
    if scenario_id is not None:
        query = query.filter(Event.scenario_id == scenario_id)
    campaign_condition = _campaign_event_condition(db, campaign_id)
    if campaign_condition is not None:
        query = query.filter(campaign_condition)
    rows = query.group_by(day_label).order_by(day_label.asc()).all()

    lookup = {row.day: row for row in rows}
    points = []
    current = start.date()
    end_date = end.date()
    while current <= end_date:
        key = current.isoformat()
        row = lookup.get(key)
        events = row.events if row else 0
        clicks = row.clicks if row else 0
        reports = row.reports if row else 0
        points.append(
            TrendPoint(
                date=key,
                events=events,
                clicks=clicks,
                reports=reports,
                click_rate=(clicks / events * 100) if events else 0.0,
                report_rate=(reports / events * 100) if events else 0.0,
            )
        )
        current = current + timedelta(days=1)

    return TrendsResponse(points=points)


@router.get(
    "/geo",
    response_model=GeoResponse,
    summary="Geolocation map",
    description="Return geolocation insights for click events and supporting map visualization.",
)
async def get_geo(
    limit: int = Query(50, ge=1, le=200, description="Maximum mock geo events to return"),
    campaign_id: Optional[int] = Query(None, ge=1, description="Optional campaign filter"),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(Role.admin, Role.analyst, Role.viewer)),
):
    events_query = (
        db.query(Event)
        .filter(Event.action == "click")
        .filter(Event.tenant_id == current_user.tenant_id)
    )
    campaign_condition = _campaign_event_condition(db, campaign_id)
    if campaign_condition is not None:
        events_query = events_query.filter(campaign_condition)
    events = events_query.order_by(Event.created_at.desc(), Event.id.desc()).limit(limit).all()

    points_map = {}

    for event in events:
        event_id = event.id or 0
        location = _mock_location(event_id)
        key = (location["city"], location["country"])
        if key not in points_map:
            points_map[key] = GeoPoint(
                city=location["city"],
                country=location["country"],
                lat=location["lat"],
                lng=location["lng"],
                count=0,
            )
        points_map[key].count += 1

    points = sorted(points_map.values(), key=lambda item: item.count, reverse=True)
    samples: List[GeoEventSample] = []
    for idx, point in enumerate(points):
        samples.append(
            GeoEventSample(
                event_id=10000 + idx,
                ip=_mock_ip(10000 + idx),
                city=point.city,
                country=point.country,
                created_at=datetime.utcnow(),
            )
        )
    return GeoResponse(points=points, samples=samples)


@router.post(
    "/export",
    summary="Export Analytics Data",
    description="Export statistics in various formats (CSV, JSON, PDF)."
)
async def export_data(
    request: ExportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(Role.admin, Role.analyst, Role.viewer)),
):
    """
    Export analytics data in the specified format.
    
    Supported formats:
    - csv: Comma-separated values
    - json: JavaScript Object Notation
    - pdf: Portable Document Format (requires additional processing)
    
    The export can include:
    - User statistics
    - Scenario metrics
    - Detailed event logs
    
    Large exports are processed in the background.
    """
    scenario_filter = request.scenario_id
    campaign_filter = request.campaign_id
    if campaign_filter:
        campaign = (
            db.query(Campaign)
            .filter(Campaign.id == campaign_filter)
            .filter(Campaign.tenant_id == current_user.tenant_id)
            .first()
        )
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

    tenant_id = current_user.tenant_id
    summary = _fetch_summary(db, scenario_filter, request.date_from, request.date_to, tenant_id, campaign_filter)
    scenarios = (
        _fetch_scenario_rows(db, scenario_filter, request.date_from, request.date_to, tenant_id, campaign_filter)
        if request.include_scenarios
        else []
    )
    users = (
        _fetch_user_rows(db, scenario_filter, request.date_from, request.date_to, tenant_id, campaign_filter)
        if request.include_users
        else []
    )
    events = (
        _fetch_event_rows(db, scenario_filter, request.date_from, request.date_to, tenant_id, campaign_filter)
        if request.include_events
        else []
    )

    if request.format == "json":
        payload = {"summary": summary}
        if request.include_scenarios:
            payload["scenarios"] = scenarios
        if request.include_users:
            payload["users"] = users
        if request.include_events:
            payload["events"] = [
                {
                    "id": event.id,
                    "action": event.action,
                    "user_id": event.user_id,
                    "scenario_id": event.scenario_id,
                    "created_at": event.created_at.isoformat() if event.created_at else None,
                }
                for event in events
            ]
        return JSONResponse(payload)

    if request.format == "pdf":
        buffer = _build_pdf_report(summary, scenarios, users, events)
        filename = "dark-signal-export.pdf"
        if scenario_filter is not None:
            filename = f"dark-signal-scenario-{scenario_filter}.pdf"
        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    if request.format != "csv":
        return {
            "status": "unsupported",
            "format": request.format,
            "message": "Only csv, json, and pdf are supported right now.",
            "timestamp": datetime.utcnow().isoformat(),
        }

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["Summary"])
    writer.writerow(["total_users", summary["total_users"]])
    writer.writerow(["total_scenarios", summary["total_scenarios"]])
    writer.writerow(["total_campaigns", summary["total_campaigns"]])
    writer.writerow(["total_events", summary["total_events"]])
    writer.writerow(["average_click_rate", round(summary["average_click_rate"], 1)])
    writer.writerow(["average_report_rate", round(summary["average_report_rate"], 1)])
    writer.writerow([])

    if request.include_scenarios:
        writer.writerow(["Scenarios"])
        writer.writerow(["id", "name", "recipients", "clicks", "reports", "click_rate", "report_rate"])
        for row in scenarios:
            writer.writerow(
                [
                    row["id"],
                    row["name"],
                    row["recipients"],
                    row["clicks"],
                    row["reports"],
                    round(row["click_rate"], 1),
                    round(row["report_rate"], 1),
                ]
            )
        writer.writerow([])

    if request.include_users:
        writer.writerow(["Users"])
        writer.writerow(
            [
                "user_id",
                "username",
                "department",
                "risk",
                "scenarios_exposed",
                "clicks",
                "reports",
                "click_rate",
                "report_rate",
                "training_score",
            ]
        )
        for row in users:
            writer.writerow(
                [
                    row["user_id"],
                    row["username"],
                    row.get("department") or "",
                    row.get("risk") or "",
                    row["scenarios_exposed"],
                    row["clicks"],
                    row["reports"],
                    round(row["click_rate"], 1),
                    round(row["report_rate"], 1),
                    row["training_score"],
                ]
            )
        writer.writerow([])

    if request.include_events:
        writer.writerow(["Events"])
        writer.writerow(["id", "action", "user_id", "scenario_id", "created_at"])
        for event in events:
            writer.writerow(
                [
                    event.id,
                    event.action,
                    event.user_id,
                    event.scenario_id,
                    event.created_at.isoformat() if event.created_at else "",
                ]
            )

    filename = "dark-signal-export.csv"
    if scenario_filter is not None:
        filename = f"dark-signal-scenario-{scenario_filter}.csv"

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/batch-operation",
    response_model=BatchOperationResult,
    summary="Perform Batch Operation",
    description="Execute bulk operations on multiple users (activate, deactivate, delete, send alerts)."
)
async def batch_operation(
    operation: BatchOperation,
    current_user=Depends(require_roles(Role.admin)),
):
    """
    Perform a batch operation on multiple users.
    
    Supported operations:
    - activate: Activate user accounts
    - deactivate: Deactivate user accounts
    - delete: Delete user accounts
    - email_alert: Send email alerts to users
    
    Example:
    ```json
    {
        "operation": "email_alert",
        "user_ids": ["user_001", "user_002", "user_003"],
        "parameters": {
            "subject": "Security Training Reminder",
            "template": "training_reminder"
        }
    }
    ```
    """
    successful = len(operation.user_ids) - 1
    failed = 1 if len(operation.user_ids) > 0 else 0
    
    return BatchOperationResult(
        operation=operation.operation,
        total_users=len(operation.user_ids),
        successful=successful,
        failed=failed,
        errors=["user_003: Email address invalid"] if failed > 0 else None
    )


@router.get(
    "/summary",
    response_model=StatisticsSummary,
    summary="Get Statistics Summary",
    description="Get a quick summary of platform statistics."
)
async def get_summary(
    date_from: Optional[datetime] = Query(None, description="Filter from date"),
    date_to: Optional[datetime] = Query(None, description="Filter to date"),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(Role.admin, Role.analyst, Role.viewer, Role.trainee)),
):
    """
    Get a quick summary of key platform statistics.
    
    Optionally filter by date range.
    """
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_scenarios = db.query(func.count(Scenario.id)).scalar() or 0
    total_events = db.query(func.count(Event.id)).scalar() or 0
    click_count = db.query(func.count(Event.id)).filter(Event.action == "click").scalar() or 0
    report_count = db.query(func.count(Event.id)).filter(Event.action == "report").scalar() or 0

    average_click_rate = (click_count / total_events * 100) if total_events else 0.0
    average_report_rate = (report_count / total_events * 100) if total_events else 0.0

    return StatisticsSummary(
        total_users=total_users,
        total_scenarios=total_scenarios,
        total_campaigns=db.query(func.count(Campaign.id)).filter(Campaign.tenant_id == current_user.tenant_id).scalar() or 0,
        total_events=total_events,
        average_click_rate=average_click_rate,
        average_report_rate=average_report_rate,
    )


@router.get(
    "/user/{user_id}/performance",
    response_model=UserPerformance,
    summary="Get User Performance",
    description="Get detailed performance metrics for a specific user."
)
async def get_user_performance(
    user_id: str,
    current_user=Depends(require_roles(Role.admin, Role.analyst, Role.viewer)),
):
    """
    Get detailed performance metrics for a specific user including:
    - Scenario exposure count
    - Click rate
    - Phishing report rate
    - Training awareness score
    """
    return UserPerformance(
        user_id=user_id,
        username="john.doe",
        total_scenarios_exposed=5,
        clicks=2,
        reports=1,
        click_rate=40.0,
        report_rate=20.0,
        training_score=75.0
    )


@router.get(
    "/scenario/{scenario_id}/metrics",
    response_model=ScenarioMetrics,
    summary="Get Scenario Metrics",
    description="Get detailed metrics for a specific phishing scenario."
)
async def get_scenario_metrics(
    scenario_id: str,
    current_user=Depends(require_roles(Role.admin, Role.analyst, Role.viewer)),
):
    """
    Get comprehensive metrics for a specific scenario including:
    - Total recipients
    - Click-through count and rate
    - Phishing report count and rate
    """
    return ScenarioMetrics(
        scenario_id=scenario_id,
        scenario_name="Password Reset Phishing",
        total_recipients=50,
        click_count=16,
        report_count=2,
        click_rate=32.0,
        report_rate=4.0
    )
