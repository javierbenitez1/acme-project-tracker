"""Unit tests for project health scoring."""
from datetime import date, timedelta

from core.metrics import enrich, project_health

TODAY = date(2026, 6, 1)


def project(**overrides):
    base = {"start_date": TODAY - timedelta(days=10), "end_date": TODAY + timedelta(days=89), "progress": 20,
            "budget_planned": 10000, "budget_spent": 1000, "milestones_overdue": 0, "milestones_blocked": 0,
            "status": "active", "archived_at": None}
    return {**base, **overrides}


def health(**overrides):
    return project_health(project(**overrides), TODAY)


def test_healthy_project_is_on_track():
    h = health()
    assert h["health"] == "on_track" and h["risk_reasons"] == []
    assert (h["time_elapsed_pct"], h["days_remaining"], h["budget_used_pct"]) == (11, 89, 10)


def test_past_end_date_is_off_track():
    h = health(start_date=TODAY - timedelta(days=60), end_date=TODAY - timedelta(days=3), progress=95)
    assert h["health"] == "off_track" and "Past its end date by 3 day(s)" in h["risk_reasons"]


def test_over_budget_is_off_track():
    h = health(budget_spent=12500)
    assert h["health"] == "off_track" and "Over budget by $2,500" in h["risk_reasons"]


def test_overdue_milestones_are_off_track():
    assert health(milestones_overdue=2)["health"] == "off_track"


def test_spending_with_no_budget_is_off_track():
    assert health(budget_planned=0, budget_spent=10)["health"] == "off_track"


def test_behind_schedule_is_at_risk():
    h = health(start_date=TODAY - timedelta(days=50), end_date=TODAY + timedelta(days=49))
    assert h["health"] == "at_risk" and h["risk_reasons"][0].startswith("Behind schedule")


def test_spending_ahead_of_progress_is_at_risk():
    h = health(budget_spent=6000)
    assert h["health"] == "at_risk" and h["risk_reasons"][0].startswith("Spending ahead")


def test_blocked_milestone_is_at_risk():
    assert health(milestones_blocked=1)["health"] == "at_risk"


def test_ending_soon_with_low_progress_is_at_risk():
    h = health(start_date=TODAY - timedelta(days=93), end_date=TODAY + timedelta(days=6), progress=85)
    assert h["health"] == "at_risk" and "Ends in 6 day(s) at 85% complete" in h["risk_reasons"]


def test_project_that_has_not_started_uses_no_time():
    h = health(start_date=TODAY + timedelta(days=10), end_date=TODAY + timedelta(days=40), progress=0)
    assert h["time_elapsed_pct"] == 0 and h["health"] == "on_track"


def test_completed_project_has_no_risks():
    h = health(status="completed", end_date=TODAY - timedelta(days=1), budget_spent=99999)
    assert h["health"] == "completed" and h["risk_reasons"] == []


def test_archived_project_is_labeled_archived():
    assert health(archived_at="2026-05-01T00:00:00")["health"] == "archived"


def test_enrich_adds_health_fields_and_archive_flag():
    enriched = enrich(project(), TODAY)
    assert enriched["is_archived"] is False and enriched["health"] == "on_track"
