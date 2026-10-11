from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.event import Event
from app.models.scenario import Scenario
from app.models.tenant import Tenant
from app.models.user import User
from app.services.adaptive_training import build_stage_baseline, compare_common_campaigns
from app.services.mock_campaigns import execute_mock_campaign


def test_build_stage_baseline_classifies_click_report_sequences():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    tenant = Tenant(name="Adaptive Workspace", slug="adaptive-workspace")
    session.add(tenant)
    session.flush()

    user_click = User(email="clicker@example.com", hashed_password="unused", role="trainee", tenant_id=tenant.id)
    user_report = User(email="reporter@example.com", hashed_password="unused", role="trainee", tenant_id=tenant.id)
    user_ignore = User(email="ignore@example.com", hashed_password="unused", role="trainee", tenant_id=tenant.id)
    baseline = Scenario(title="Baseline", difficulty="medium", tenant_id=tenant.id, indicators={"audience": "All Staff"})
    session.add_all([user_click, user_report, user_ignore, baseline])
    session.flush()

    base_time = datetime(2026, 7, 21, 9, 0)
    session.add_all(
        [
            Event(tenant_id=tenant.id, user_id=user_click.id, scenario_id=baseline.id, action="phishing.mock_sent", created_at=base_time),
            Event(tenant_id=tenant.id, user_id=user_click.id, scenario_id=baseline.id, action="click", created_at=base_time + timedelta(minutes=2)),
            Event(tenant_id=tenant.id, user_id=user_click.id, scenario_id=baseline.id, action="report", created_at=base_time + timedelta(minutes=5)),
            Event(tenant_id=tenant.id, user_id=user_report.id, scenario_id=baseline.id, action="phishing.mock_sent", created_at=base_time),
            Event(tenant_id=tenant.id, user_id=user_report.id, scenario_id=baseline.id, action="report", created_at=base_time + timedelta(minutes=3)),
            Event(tenant_id=tenant.id, user_id=user_ignore.id, scenario_id=baseline.id, action="phishing.mock_sent", created_at=base_time),
            Event(tenant_id=tenant.id, user_id=user_click.id, scenario_id=baseline.id, action="click", created_at=base_time + timedelta(minutes=8)),
        ]
    )
    session.commit()

    metrics = build_stage_baseline(session, tenant_id=tenant.id, source_scenario_ids=[baseline.id])
    by_email = {item["user_email"]: item for item in metrics}

    assert by_email["clicker@example.com"]["clicked"] is True
    assert by_email["clicker@example.com"]["reported"] is True
    assert by_email["clicker@example.com"]["click_before_report"] is True
    assert by_email["clicker@example.com"]["recommended_action"] == "targeted_repetition"

    assert by_email["reporter@example.com"]["clicked"] is False
    assert by_email["reporter@example.com"]["reported"] is True
    assert by_email["reporter@example.com"]["recommended_action"] == "harder"

    assert by_email["ignore@example.com"]["clicked"] is False
    assert by_email["ignore@example.com"]["reported"] is False
    assert by_email["ignore@example.com"]["recommended_action"] == "same"
    session.close()


def test_build_stage_baseline_scopes_repeated_clicks_to_source_scenarios_only():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    tenant = Tenant(name="Scoped Workspace", slug="scoped-workspace")
    session.add(tenant)
    session.flush()

    user = User(email="scoped@example.com", hashed_password="unused", role="trainee", tenant_id=tenant.id)
    baseline = Scenario(title="Baseline", difficulty="medium", tenant_id=tenant.id, indicators={"audience": "All Staff"})
    legacy = Scenario(title="Legacy", difficulty="easy", tenant_id=tenant.id, indicators={"audience": "All Staff"})
    session.add_all([user, baseline, legacy])
    session.flush()

    start = datetime(2026, 7, 22, 9, 0)
    session.add_all(
        [
            Event(tenant_id=tenant.id, user_id=user.id, scenario_id=legacy.id, action="click", created_at=start - timedelta(days=3)),
            Event(tenant_id=tenant.id, user_id=user.id, scenario_id=baseline.id, action="phishing.mock_sent", created_at=start),
            Event(tenant_id=tenant.id, user_id=user.id, scenario_id=baseline.id, action="report", created_at=start + timedelta(minutes=4)),
        ]
    )
    session.commit()

    metrics = build_stage_baseline(session, tenant_id=tenant.id, source_scenario_ids=[baseline.id])

    assert metrics[0]["reported"] is True
    assert metrics[0]["repeated_clicks_total"] == 0
    assert metrics[0]["recommended_action"] == "harder"
    session.close()


def test_execute_mock_campaign_respects_user_target_ids_for_adaptive_stage():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    tenant = Tenant(name="Target Workspace", slug="target-workspace")
    session.add(tenant)
    session.flush()

    user_a = User(email="a@example.com", hashed_password="unused", role="trainee", tenant_id=tenant.id)
    user_b = User(email="b@example.com", hashed_password="unused", role="trainee", tenant_id=tenant.id)
    user_c = User(email="c@example.com", hashed_password="unused", role="trainee", tenant_id=tenant.id)
    scenario = Scenario(
        title="Adaptive easy",
        difficulty="easy",
        tenant_id=tenant.id,
        indicators={"audience": "All Staff", "user_target_ids": []},
    )
    session.add_all([user_a, user_b, user_c, scenario])
    session.flush()

    scenario.indicators = {"audience": "All Staff", "user_target_ids": [user_a.id, user_c.id]}
    recipients, _ = execute_mock_campaign(session, scenario, executed_at=datetime(2026, 7, 22, 10, 0))
    session.commit()

    assert recipients == 2
    delivered_user_ids = {
        event.user_id
        for event in session.query(Event)
        .filter(Event.scenario_id == scenario.id)
        .filter(Event.action == "phishing.mock_sent")
        .all()
    }
    assert delivered_user_ids == {user_a.id, user_c.id}
    session.close()


def test_compare_common_campaigns_returns_before_after_delta():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    tenant = Tenant(name="Evaluation Workspace", slug="evaluation-workspace")
    session.add(tenant)
    session.flush()

    user = User(email="learner@example.com", hashed_password="unused", role="trainee", tenant_id=tenant.id)
    baseline = Scenario(title="Baseline", difficulty="medium", tenant_id=tenant.id, indicators={})
    final = Scenario(title="Final", difficulty="medium", tenant_id=tenant.id, indicators={})
    session.add_all([user, baseline, final])
    session.flush()

    start = datetime(2026, 7, 20, 9, 0)
    session.add_all(
        [
            Event(tenant_id=tenant.id, user_id=user.id, scenario_id=baseline.id, action="phishing.mock_sent", created_at=start),
            Event(tenant_id=tenant.id, user_id=user.id, scenario_id=baseline.id, action="click", created_at=start + timedelta(minutes=1)),
            Event(tenant_id=tenant.id, user_id=user.id, scenario_id=final.id, action="phishing.mock_sent", created_at=start + timedelta(days=7)),
            Event(tenant_id=tenant.id, user_id=user.id, scenario_id=final.id, action="report", created_at=start + timedelta(days=7, minutes=2)),
        ]
    )
    session.commit()

    comparison = compare_common_campaigns(
        session,
        tenant_id=tenant.id,
        baseline_scenario_id=baseline.id,
        final_scenario_id=final.id,
    )

    assert comparison["baseline"]["click_rate"] == 100.0
    assert comparison["final"]["click_rate"] == 0.0
    assert comparison["delta"]["click_rate_change"] == -100.0
    assert comparison["delta"]["report_rate_change"] == 100.0
    assert comparison["per_user"][0]["click_improved"] is True
    assert comparison["per_user"][0]["report_improved"] is True
    session.close()
