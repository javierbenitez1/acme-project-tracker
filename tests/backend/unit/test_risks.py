"""Unit tests for risk scoring and suggested risks."""
from datetime import date, timedelta

from core.risks import finish, level, suggest, summarize

MONDAY = date(2026, 6, 1)


def day(n):
    return MONDAY + timedelta(days=n)


def node(start, end, status="not_started", name="m"):
    return {"start_date": day(start), "end_date": day(end), "status": status, "name": name}


def project(**overrides):
    base = {"start_date": day(0), "end_date": day(99), "progress": 50, "budget_planned": 0, "budget_spent": 0}
    return {**base, **overrides}


def risk(likelihood, impact, status="open", review=None):
    return {"likelihood": likelihood, "impact": impact, "status": status, "review_date": review}


def keys(found):
    return [item["source_key"] for item in found]


# Scoring

def test_levels_follow_the_five_by_five_matrix():
    assert [level(s) for s in (25, 15, 14, 8, 7, 1)] == ["high", "high", "medium", "medium", "low", "low"]


def test_finish_scores_and_flags_overdue_reviews():
    scored = finish(risk(4, 4, review=day(5)), today=day(10))
    assert (scored["score"], scored["level"], scored["review_overdue"]) == (16, "high", True)
    assert finish(risk(4, 4, "closed", day(5)), today=day(10))["review_overdue"] is False


def test_summary_counts_only_active_risks():
    risks = [finish(r, today=day(10)) for r in (risk(5, 4), risk(2, 4), risk(1, 2, review=day(1)), risk(5, 5, "closed"))]
    assert summarize(risks) == {"active": 3, "high": 1, "medium": 1, "low": 1, "reviews_overdue": 1}


# Suggested risks

def test_no_buffer_on_the_critical_path_is_suggested():
    nodes = {1: node(0, 50, name="Build"), 2: node(50, 99, name="Launch")}
    found = suggest(project(), nodes, [(2, 1)], today=day(49))
    item = found[0]
    assert item["source_key"] == "schedule:critical_path_buffer"
    assert "Build, Launch have no buffer" in item["description"] and item["level"] == "medium"


def test_plenty_of_buffer_is_not_a_risk():
    nodes = {1: node(0, 50)}
    assert keys(suggest(project(), nodes, [], today=day(49))) == []


def test_a_late_forecast_is_suggested():
    found = suggest(project(progress=30), {}, [], today=day(49))
    assert keys(found) == ["schedule:forecast_late"]
    assert found[0]["likelihood"] == 4 and "days after the end date" in found[0]["description"]


def test_spending_ahead_of_plan_is_suggested_until_it_is_already_over():
    on_pace_to_overrun = project(budget_planned=10000, budget_spent=7000)
    assert keys(suggest(on_pace_to_overrun, {}, [], today=day(49))) == ["budget:forecast_over"]
    already_over = project(budget_planned=10000, budget_spent=12000)
    assert keys(suggest(already_over, {}, [], today=day(49))) == []
