"""Integration tests for the admin-only, read-only audit log."""


def test_changes_are_recorded_with_before_and_after_values(admin, manager, employee_account):
    manager.put(f"users/{employee_account['id']}", {"job_title": "Audit Check Title"})
    response = admin.get(f"audit?entity_id={employee_account['id']}&action=user.updated")
    assert response.status_code == 200
    changes = [e["details"]["changes"] for e in response.json()["items"]]
    assert any(c.get("job_title", {}).get("to") == "Audit Check Title" for c in changes)


def test_audit_log_is_read_only(admin):
    assert admin.post("audit", {"summary": "fake"}).status_code == 405
    assert admin.put("audit/1", {"summary": "edited"}).status_code == 405
    assert admin.delete("audit/1").status_code == 405


def test_only_admins_can_view_the_audit_log(manager, employee):
    assert manager.get("audit").status_code == 403
    assert employee.get("audit").status_code == 403


def test_bad_filters_are_rejected(admin):
    assert admin.get("audit?from=2026-13-01").status_code == 400
    assert admin.get("audit?page_size=1000").status_code == 400
    assert admin.get("audit?from=2026-05-02&to=2026-05-01").status_code == 400


def test_pagination(admin):
    body = admin.get("audit?page_size=1").json()
    assert len(body["items"]) <= 1 and body["total"] >= 1
