"""Unit tests for the audit trail helpers."""
from core import activity


class FakeCursor:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params):
        self.calls.append((sql, params))


def test_diff_only_reports_changed_fields():
    before = {"name": "Jordan", "email": "j@acme.com", "job_title": "Engineer"}
    after = {"name": "Jordan", "email": "j@acme.com", "job_title": "Senior Engineer"}
    assert activity.diff(before, after, ["name", "email", "job_title"]) == {
        "job_title": {"from": "Engineer", "to": "Senior Engineer"}}


def test_log_writes_one_row_with_details():
    cur = FakeCursor()
    activity.log(cur, 1, "user.updated", "user", "Admin updated Jordan", entity_id=3,
                 details={"changes": {"name": {"from": "A", "to": "B"}}})
    sql, params = cur.calls[0]
    assert "INSERT INTO activity_log" in sql
    assert params[:6] == (1, "user.updated", "user", 3, None, "Admin updated Jordan")
    assert params[6] is not None


def test_log_without_details_stores_null():
    cur = FakeCursor()
    activity.log(cur, 1, "user.created", "user", "Admin added Jordan")
    assert cur.calls[0][1][6] is None
