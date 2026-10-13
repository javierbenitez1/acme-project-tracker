"""Unit tests for scheduling: cycle detection, automatic rescheduling, and the 8-hour workday."""
from datetime import date, timedelta

from core.scheduling import peak_daily_load, plan_reschedule, would_create_cycle

MONDAY = date(2026, 6, 1)


def day(n):
    return MONDAY + timedelta(days=n)


def node(start, end, status="not_started"):
    return {"start_date": day(start), "end_date": day(end), "status": status, "name": "m"}


# Cycle detection: edges are (milestone, depends_on)

def test_milestone_cannot_depend_on_itself():
    assert would_create_cycle([], 1, 1)


def test_direct_cycle_is_detected():
    assert would_create_cycle([(2, 1)], 1, 2)


def test_indirect_cycle_is_detected():
    assert would_create_cycle([(2, 1), (3, 2)], 1, 3)


def test_valid_dependency_is_allowed():
    assert not would_create_cycle([(2, 1), (3, 2)], 3, 1)


# Rescheduling

CHAIN_EDGES = [(2, 1), (3, 2)]


def chain(**statuses):
    return {1: node(0, 10), 2: node(10, 20, statuses.get("two", "not_started")), 3: node(20, 25)}


def test_delay_cascades_down_the_chain_and_keeps_lengths():
    plan = plan_reschedule(chain(), CHAIN_EDGES, 1, day(0), day(15))
    assert plan == {1: (day(0), day(15)), 2: (day(15), day(25)), 3: (day(25), day(30))}


def test_completed_milestones_never_move():
    assert plan_reschedule(chain(two="done"), CHAIN_EDGES, 1, day(0), day(15)) == {1: (day(0), day(15))}


def test_moving_earlier_does_not_pull_dependents():
    assert plan_reschedule(chain(), CHAIN_EDGES, 1, day(0), day(5)) == {1: (day(0), day(5))}


def test_slack_absorbs_small_delays():
    nodes = {1: node(0, 10), 2: node(18, 20)}
    assert plan_reschedule(nodes, [(2, 1)], 1, day(0), day(15)) == {1: (day(0), day(15))}


def test_milestone_waits_for_its_latest_prerequisite():
    nodes = {1: node(0, 10), 2: node(0, 5), 3: node(10, 12)}
    plan = plan_reschedule(nodes, [(3, 1), (3, 2)], 2, day(0), day(14))
    assert plan == {2: (day(0), day(14)), 3: (day(14), day(16))}


# 8-hour workday

def booking(hours, start, end):
    return {"hours_per_day": hours, "start_date": day(start), "end_date": day(end)}


def test_overlapping_bookings_add_up_on_the_busiest_day():
    assert peak_daily_load([booking(8, 0, 4), booking(2, 3, 10)], day(0), day(10)) == (10.0, day(3))


def test_weekends_are_ignored():
    assert peak_daily_load([booking(8, 5, 6)], day(0), day(6)) == (0.0, None)


def test_no_bookings_means_no_load():
    assert peak_daily_load([], day(0), day(4)) == (0.0, None)
