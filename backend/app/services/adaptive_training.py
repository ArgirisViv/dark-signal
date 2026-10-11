from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.event import Event
from app.models.user import User


def _is_click(action: str | None) -> bool:
    return "click" in (action or "").lower()


def _is_report(action: str | None) -> bool:
    return "report" in (action or "").lower()


def _is_open(action: str | None) -> bool:
    normalized = (action or "").lower()
    return normalized == "open" or normalized == "email.open"


def _seconds_between(start: datetime | None, end: datetime | None) -> float | None:
    if not start or not end:
        return None
    return round((end - start).total_seconds(), 2)


def classify_user_behavior(
    clicked: bool,
    reported: bool,
    click_before_report: bool,
    repeated_clicks_total: int,
) -> tuple[str, str, str]:
    """Return readiness band, machine action key, and human guidance."""
    if repeated_clicks_total >= 2 and clicked:
        return (
            "Increased educational risk",
            "targeted_repetition",
            "Targeted repetition with easier scenario and mandatory micro-learning",
        )
    if reported and not clicked:
        return (
            "High readiness",
            "harder",
            "Assign a harder scenario",
        )
    if clicked and reported:
        if click_before_report:
            return (
                "Partial recognition",
                "same_or_slightly_easier",
                "Assign same or slightly easier scenario",
            )
        return (
            "Moderate readiness",
            "same",
            "Assign same level scenario",
        )
    if clicked:
        return (
            "Low readiness",
            "easier",
            "Assign easier scenario and short training",
        )
    return (
        "Moderate/uncertain readiness",
        "same",
        "Assign same level scenario and verify active recognition",
    )


def build_stage_baseline(
    db: Session,
    *,
    tenant_id: int,
    source_scenario_ids: list[int],
) -> list[dict[str, Any]]:
    """Build per-user baseline metrics from one or more source scenarios."""
    source_ids = [item for item in source_scenario_ids if item]
    if not source_ids:
        return []

    users = (
        db.query(User)
        .filter(User.tenant_id == tenant_id)
        .filter(User.role == "trainee")
        .order_by(User.id.asc())
        .all()
    )
    if not users:
        return []

    events = (
        db.query(Event)
        .filter(Event.tenant_id == tenant_id)
        .filter(Event.scenario_id.in_(source_ids))
        .order_by(Event.created_at.asc(), Event.id.asc())
        .all()
    )

    click_totals = Counter(
        event.user_id
        for event in db.query(Event)
        .filter(Event.tenant_id == tenant_id)
        .filter(Event.scenario_id.in_(source_ids))
        .all()
        if _is_click(event.action)
    )

    metrics: list[dict[str, Any]] = []
    for user in users:
        user_events = [event for event in events if event.user_id == user.id]
        sent_events = [event for event in user_events if event.action == "phishing.mock_sent"]
        latest_sent = sent_events[-1] if sent_events else None

        opened = False
        clicked = False
        reported = False
        first_open_at = None
        first_click_at = None
        first_report_at = None
        source_scenario_id = latest_sent.scenario_id if latest_sent else None

        if latest_sent:
            interactions = [
                event
                for event in user_events
                if event.scenario_id == latest_sent.scenario_id
                and event.created_at
                and latest_sent.created_at
                and event.created_at >= latest_sent.created_at
            ]
            for event in interactions:
                if _is_open(event.action) and not opened:
                    opened = True
                    first_open_at = event.created_at
                if _is_click(event.action) and not clicked:
                    clicked = True
                    first_click_at = event.created_at
                if _is_report(event.action) and not reported:
                    reported = True
                    first_report_at = event.created_at

        click_before_report = bool(
            first_click_at and first_report_at and first_click_at < first_report_at
        )
        readiness, action_key, guidance = classify_user_behavior(
            clicked=clicked,
            reported=reported,
            click_before_report=click_before_report,
            repeated_clicks_total=click_totals.get(user.id, 0),
        )
        metrics.append(
            {
                "user_id": user.id,
                "user_email": user.email,
                "source_scenario_id": source_scenario_id,
                "opened": opened,
                "clicked": clicked,
                "reported": reported,
                "time_to_click_seconds": _seconds_between(latest_sent.created_at if latest_sent else None, first_click_at),
                "time_to_report_seconds": _seconds_between(latest_sent.created_at if latest_sent else None, first_report_at),
                "click_before_report": click_before_report,
                "repeated_clicks_total": click_totals.get(user.id, 0),
                "readiness": readiness,
                "recommended_action": action_key,
                "next_step": guidance,
            }
        )

    return metrics


def summarize_stage_baseline(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    if not metrics:
        return {
            "users": 0,
            "opened": 0,
            "clicked": 0,
            "reported": 0,
            "click_before_report": 0,
            "avg_time_to_click_seconds": None,
            "avg_time_to_report_seconds": None,
            "action_distribution": {},
        }

    opened = sum(1 for item in metrics if item["opened"])
    clicked = sum(1 for item in metrics if item["clicked"])
    reported = sum(1 for item in metrics if item["reported"])
    click_before_report = sum(1 for item in metrics if item["click_before_report"])
    time_to_click = [item["time_to_click_seconds"] for item in metrics if item["time_to_click_seconds"] is not None]
    time_to_report = [item["time_to_report_seconds"] for item in metrics if item["time_to_report_seconds"] is not None]
    action_distribution = Counter(item["recommended_action"] for item in metrics)

    return {
        "users": len(metrics),
        "opened": opened,
        "clicked": clicked,
        "reported": reported,
        "click_before_report": click_before_report,
        "avg_time_to_click_seconds": round(sum(time_to_click) / len(time_to_click), 2) if time_to_click else None,
        "avg_time_to_report_seconds": round(sum(time_to_report) / len(time_to_report), 2) if time_to_report else None,
        "action_distribution": dict(action_distribution),
    }


def compare_common_campaigns(
    db: Session,
    *,
    tenant_id: int,
    baseline_scenario_id: int,
    final_scenario_id: int,
) -> dict[str, Any]:
    baseline = build_stage_baseline(db, tenant_id=tenant_id, source_scenario_ids=[baseline_scenario_id])
    final = build_stage_baseline(db, tenant_id=tenant_id, source_scenario_ids=[final_scenario_id])
    baseline_by_user = {item["user_id"]: item for item in baseline}
    final_by_user = {item["user_id"]: item for item in final}

    all_user_ids = sorted(set(baseline_by_user.keys()) | set(final_by_user.keys()))
    per_user = []
    for user_id in all_user_ids:
        base = baseline_by_user.get(user_id, {})
        end = final_by_user.get(user_id, {})
        per_user.append(
            {
                "user_id": user_id,
                "user_email": end.get("user_email") or base.get("user_email"),
                "baseline_clicked": bool(base.get("clicked")),
                "baseline_reported": bool(base.get("reported")),
                "final_clicked": bool(end.get("clicked")),
                "final_reported": bool(end.get("reported")),
                "click_improved": bool(base.get("clicked")) and not bool(end.get("clicked")),
                "report_improved": (not bool(base.get("reported"))) and bool(end.get("reported")),
            }
        )

    baseline_summary = summarize_stage_baseline(baseline)
    final_summary = summarize_stage_baseline(final)
    baseline_users = baseline_summary["users"] or 1
    final_users = final_summary["users"] or 1

    baseline_click_rate = round(baseline_summary["clicked"] / baseline_users * 100, 1)
    final_click_rate = round(final_summary["clicked"] / final_users * 100, 1)
    baseline_report_rate = round(baseline_summary["reported"] / baseline_users * 100, 1)
    final_report_rate = round(final_summary["reported"] / final_users * 100, 1)

    return {
        "baseline": {
            "scenario_id": baseline_scenario_id,
            **baseline_summary,
            "click_rate": baseline_click_rate,
            "report_rate": baseline_report_rate,
        },
        "final": {
            "scenario_id": final_scenario_id,
            **final_summary,
            "click_rate": final_click_rate,
            "report_rate": final_report_rate,
        },
        "delta": {
            "click_rate_change": round(final_click_rate - baseline_click_rate, 1),
            "report_rate_change": round(final_report_rate - baseline_report_rate, 1),
        },
        "per_user": per_user,
    }
