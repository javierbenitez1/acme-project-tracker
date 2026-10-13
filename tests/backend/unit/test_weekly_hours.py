"""Unit tests for weekly booked hours used by the workload heatmap."""
from datetime import date, timedelta

from core.scheduling import weekly_hours

MONDAY = date(2026, 6, 1)


def booking(hours, start, end):
    return {"hours_per_day": hours, "start_date": MONDAY + timedelta(days=start),
            "end_date": MONDAY + timedelta(days=end)}


def test_full_week_at_eight_hours_is_forty():
    assert weekly_hours([booking(8, 0, 13)], MONDAY) == 40.0


def test_partial_week_counts_only_overlapping_weekdays():
    assert weekly_hours([booking(8, 2, 3)], MONDAY) == 16.0  # Wednesday and Thursday


def test_weekends_do_not_count():
    assert weekly_hours([booking(8, 5, 6)], MONDAY) == 0.0


def test_overlapping_bookings_add_up():
    assert weekly_hours([booking(6, 0, 4), booking(4, 0, 4)], MONDAY) == 50.0