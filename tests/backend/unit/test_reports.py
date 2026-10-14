"""Unit tests for the weekly status report's RAG ratings and summary."""
from datetime import date, timedelta

from core.reports import rate_budget, rate_overall, rate_risks, rate_schedule, summary

TODAY = date(2026, 10, 14)


def project(**overrides):
    base = {"name": "Branch Kiosk Rollout", "status": "active", "progress": 56, "time_elapsed_pct": 60,
            "days_remaining": 11, "milestones_overdue": 0, "milestones_blocked": 0, "budget_planned": 100000,
            "budget_spent": 50000, "budget_used_pct": 50, "end_date": TODAY + timedelta(days=11)}
    return {**base, **overrides}


ON_TIME = {"status": "on_time", "projected_end": TODAY, "days_late": 0}


def late(days):
    return {"status": "late", "projected_end": TODAY + timedelta(days=days), "days_late": days}


def test_schedule_rating():
    assert rate_schedule(project(), ON_TIME)["status"] == "green"
    assert rate_schedule(project(), late(7)) == {"status": "amber", "reason": "Forecast to finish 7 days late"}
    assert rate_schedule(project(), late(46))["status"] == "red"
    assert rate_schedule(project(milestones_overdue=2), ON_TIME)["reason"] == "2 overdue milestones"
    assert rate_schedule(project(days_remaining=-3), ON_TIME)["reason"] == "Past its end date by 3 days"
    assert rate_schedule(project(progress=40, time_elapsed_pct=60), {"status": "not_enough_data"})["status"] == "amber"
    assert rate_schedule(project(status="completed"), late(46))["status"] == "green"


def test_budget_rating():
    assert rate_budget(project(), {"status": "on_track"})["status"] == "green"
    assert rate_budget(project(budget_spent=120000), {})["reason"] == "Over budget by $20,000"
    assert rate_budget(project(), {"status": "over", "projected_total": 104000})["status"] == "amber"
    assert rate_budget(project(), {"status": "over", "projected_total": 130000})["status"] == "red"
    assert rate_budget(project(budget_used_pct=80, progress=50), {"status": "on_track"})["status"] == "amber"
    assert rate_budget(project(budget_planned=0, budget_spent=0), {})["reason"] == "No budget set"


def test_risk_rating():
    assert rate_risks([{"level": "high"}, {"level": "medium"}]) == {"status": "red", "reason": "1 high risk open"}
    assert rate_risks([{"level": "medium"}, {"level": "medium"}])["reason"] == "2 medium risks open"
    assert rate_risks([])["reason"] == "No open risks logged"


def test_overall_is_the_worst_area_and_names_it():
    green, amber = {"status": "green", "reason": ""}, {"status": "amber", "reason": ""}
    assert rate_overall(green, green, green) == {"status": "green", "reason": "All areas on track"}
    assert rate_overall(amber, green, amber) == {"status": "amber", "reason": "Driven by schedule and risks"}


def test_summary_reads_like_a_status_update():
    text = summary(project(), {"status": "amber"}, late(46), ["Install at branches", "Go-live review"], 0, 1, 2)
    assert text.startswith("Branch Kiosk Rollout is amber overall. It is 56% complete with 60% of the time used")
    assert "46 days after its Oct 25 end date" in text
    assert "The critical path (Install at branches, Go-live review) has no buffer." in text
    assert text.endswith("1 open risk and 2 items need attention.")