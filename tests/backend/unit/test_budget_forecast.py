"""Unit tests for the end-of-project budget forecast."""
from datetime import date, timedelta

from core.metrics import budget_forecast

START = date(2026, 1, 1)
END = START + timedelta(days=99)  # a 100-day project


def on_day(n):
    return START + timedelta(days=n - 1)


def test_too_early_to_forecast():
    assert budget_forecast(10000, 500, START, END, on_day(5))["status"] == "not_enough_data"


def test_no_spending_means_no_forecast():
    assert budget_forecast(10000, 0, START, END, on_day(50))["status"] == "not_enough_data"


def test_spending_on_pace_is_on_track():
    forecast = budget_forecast(10000, 5000, START, END, on_day(50))
    assert forecast == {"projected_total": 10000.0, "projected_variance": 0.0, "daily_burn": 100.0,
                        "status": "on_track"}


def test_fast_spending_is_forecast_over_budget():
    forecast = budget_forecast(10000, 7000, START, END, on_day(50))
    assert forecast["status"] == "over" and forecast["projected_variance"] == 4000.0


def test_slow_spending_is_forecast_under_budget():
    assert budget_forecast(10000, 2000, START, END, on_day(50))["status"] == "under"


def test_finished_project_projects_its_actual_spend():
    assert budget_forecast(10000, 9000, START, END, on_day(150))["projected_total"] == 9000.0