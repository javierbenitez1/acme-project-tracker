"""Unit tests for sign-in history: readable devices, masked addresses, and the summary shown at sign-in."""
from datetime import datetime, timedelta, timezone

from core.security import client_address, describe_device, lock_until, locked_message, mask_ip, summarize

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)


def event(id_, succeeded, minutes_ago):
    return {"id": id_, "succeeded": succeeded, "created_at": NOW - timedelta(minutes=minutes_ago)}


def test_devices_are_described_in_plain_words():
    firefox = "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0"
    chrome_mac = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/129.0 Safari/537.36"
    iphone = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1"
    edge = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129.0 Safari/537.36 Edg/129.0"
    assert describe_device(firefox) == "Firefox on Linux"
    assert describe_device(chrome_mac) == "Chrome on macOS"
    assert describe_device(iphone) == "Safari on iPhone"
    assert describe_device(edge) == "Edge on Windows"
    assert describe_device(None) == "Unknown device"


def test_addresses_are_masked_before_storing():
    assert mask_ip("203.0.113.45") == "203.0.113.x"
    assert mask_ip("2001:db8:85a3::8a2e:370:7334") == "2001:0db8:85a3::/48"
    assert mask_ip("not an address") is None and mask_ip(None) is None


def test_the_original_client_is_first_in_x_forwarded_for():
    assert client_address({"x-forwarded-for": "198.51.100.7, 130.176.1.1"}) == "198.51.100.7"
    assert client_address({}) is None


def test_summary_finds_the_previous_sign_in_and_failures_since():
    events = [event(5, True, 0), event(4, False, 30), event(3, False, 31), event(2, True, 600), event(1, False, 900)]
    result = summarize(events)
    assert result["current"]["id"] == 5 and result["previous"]["id"] == 2
    assert result["failed_since_previous"] == 2


def test_first_ever_sign_in_has_no_previous():
    result = summarize([event(1, True, 0)])
    assert result["previous"] is None and result["failed_since_previous"] == 0


# Lockout

def attempts(*results, start_minutes_ago=30, step=1):
    """results: True for success, False for failure, "blocked" for an attempt refused during a lock."""
    return [{"succeeded": r is True, "blocked": r == "blocked",
             "created_at": NOW - timedelta(minutes=start_minutes_ago - i * step)} for i, r in enumerate(results)]


def test_five_failures_in_a_row_lock_the_account_for_15_minutes():
    events = attempts(False, False, False, False, False, start_minutes_ago=5)
    assert lock_until(events, NOW) == events[-1]["created_at"] + timedelta(minutes=15)
    assert lock_until(events[:4], NOW) is None


def test_a_success_resets_the_count():
    assert lock_until(attempts(False, False, False, True, False, False), NOW) is None


def test_the_lock_ends_and_refused_attempts_do_not_extend_it():
    events = attempts(False, False, False, False, False, "blocked", "blocked", start_minutes_ago=40)
    assert lock_until(events, NOW) is None  # the lock started 36 minutes ago, so it has ended


def test_failures_after_a_lock_start_counting_again():
    events = attempts(False, False, False, False, False, start_minutes_ago=60) + attempts(False, start_minutes_ago=2)
    assert lock_until(events, NOW) is None


def test_the_locked_message_counts_down_in_minutes():
    assert "locked for 15 more minutes" in locked_message(NOW + timedelta(minutes=14, seconds=30), NOW)
    assert "locked for 1 more minute." in locked_message(NOW + timedelta(seconds=20), NOW)