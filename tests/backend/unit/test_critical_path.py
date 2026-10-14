"""Unit tests for critical path analysis and the delivery forecast."""
from datetime import date, timedelta

import pytest

from core.scheduling import critical_path, delivery_forecast

MONDAY = date(2026, 6, 1)


def day(n):
    return MONDAY + timedelta(days=n)


def node(start, end, status="not_started"):
    return {"start_date": day(start), "end_date": day(end), "status": status, "name": "m"}


# Critical path: edges are (milestone, depends_on)

def test_a_simple_chain_is_entirely_critical():
    nodes = {1: node(0, 10), 2: node(10, 20), 3: node(20, 30)}
    result = critical_path(nodes, [(2, 1), (3, 2)], day(40))
    assert result == {"slack": {1: 10, 2: 10, 3: 10}, "critical": [1, 2, 3], "buffer_days": 10}


def test_a_short_side_branch_has_slack():
    nodes = {1: node(0, 10), 2: node(10, 30), 3: node(10, 15), 4: node(30, 35)}
    result = critical_path(nodes, [(2, 1), (3, 1), (4, 2), (4, 3)], day(35))
    assert result["critical"] == [1, 2, 4]
    assert result["slack"][3] == 15 and result["buffer_days"] == 0


def test_a_gap_before_the_next_milestone_counts_as_slack():
    nodes = {1: node(0, 10), 2: node(15, 20)}
    result = critical_path(nodes, [(2, 1)], day(20))
    assert result["slack"] == {1: 5, 2: 0} and result["critical"] == [2]


def test_completed_milestones_are_left_out():
    nodes = {1: node(0, 10, "done"), 2: node(10, 20)}
    result = critical_path(nodes, [(2, 1)], day(25))
    assert result == {"slack": {2: 5}, "critical": [2], "buffer_days": 5}


def test_nothing_open_means_no_critical_path():
    assert critical_path({1: node(0, 10, "done")}, [], day(20)) == {"slack": {}, "critical": [], "buffer_days": None}


def test_cycles_are_reported():
    with pytest.raises(ValueError):
        critical_path({1: node(0, 5), 2: node(5, 10)}, [(1, 2), (2, 1)], day(20))


# Delivery forecast (a 100-day project)

END = day(99)


def test_on_pace_finishes_on_time():
    forecast = delivery_forecast(50, day(0), END, today=day(49))
    assert forecast == {"status": "on_time", "projected_end": END, "days_late": 0}


def test_slow_progress_is_forecast_late():
    forecast = delivery_forecast(40, day(0), END, today=day(49))
    assert forecast["status"] == "late" and forecast["days_late"] == 25


def test_fast_progress_is_forecast_early():
    assert delivery_forecast(80, day(0), END, today=day(49))["status"] == "early"


def test_too_early_or_no_progress_means_no_forecast():
    assert delivery_forecast(30, day(0), END, today=day(3))["status"] == "not_enough_data"
    assert delivery_forecast(0, day(0), END, today=day(60))["status"] == "not_enough_data"


def test_finished_work_needs_no_forecast():
    assert delivery_forecast(100, day(0), END, today=day(60))["status"] == "complete"
