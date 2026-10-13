"""Integration tests for projects: creation, visibility, team, edits with reasons, archive, restore, complete."""
from datetime import date, timedelta

import pytest

TODAY = date.today()


def make_project(admin, manager_account, run_id, suffix):
    body = {"name": f"IT Project {run_id} {suffix}", "description": "Integration test project",
            "department": "QA", "manager_id": manager_account["id"],
            "start_date": str(TODAY - timedelta(days=5)), "end_date": str(TODAY + timedelta(days=60)),
            "budget_planned": 50000, "status": "active"}
    response = admin.post("projects", body)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture(scope="module")
def project(admin, manager_account, run_id):
    return make_project(admin, manager_account, run_id, "main")


def test_admin_creates_project_with_manager_on_the_team(admin, project, manager_account):
    assert project["manager_id"] == manager_account["id"]
    assert project["health"] == "on_track" and project["progress"] == 0
    members = admin.get(f"projects/{project['id']}/members").json()
    assert [m["id"] for m in members] == [manager_account["id"]] and members[0]["is_manager"]


def test_end_date_must_follow_start_date(admin, manager_account):
    response = admin.post("projects", {"name": "Bad dates", "manager_id": manager_account["id"],
                                       "start_date": "2026-05-10", "end_date": "2026-05-01"})
    assert response.status_code == 400 and "end_date" in response.json()["error"]["details"]


def test_project_manager_must_be_a_manager(admin, employee_account):
    response = admin.post("projects", {"name": "Bad manager", "manager_id": employee_account["id"],
                                       "start_date": "2026-05-01", "end_date": "2026-05-10"})
    assert response.status_code == 400 and "manager_id" in response.json()["error"]["details"]


def test_managers_cannot_create_projects(manager, manager_account):
    response = manager.post("projects", {"name": "Nope", "manager_id": manager_account["id"],
                                         "start_date": "2026-05-01", "end_date": "2026-05-10"})
    assert response.status_code == 403


def test_manager_sees_their_own_project(manager, project):
    assert project["id"] in [p["id"] for p in manager.get("projects").json()]


def test_team_membership_controls_employee_access(manager, employee, project, employee_account):
    assert employee.get(f"projects/{project['id']}").status_code == 404
    added = manager.post(f"projects/{project['id']}/members", {"user_ids": [employee_account["id"]]})
    assert added.status_code == 201
    assert employee_account["id"] in [m["id"] for m in added.json()]
    assert employee.get(f"projects/{project['id']}").status_code == 200
    assert employee.post(f"projects/{project['id']}/members",
                         {"user_ids": [employee_account["id"]]}).status_code == 403


def test_only_active_employees_can_join(manager, project):
    response = manager.post(f"projects/{project['id']}/members", {"user_ids": [1, 999999]})
    assert response.status_code == 400
    assert set(response.json()["error"]["details"]["user_ids"]) == {"1", "999999"}


def test_date_change_requires_a_reason_and_is_recorded(manager, project):
    new_end = str(TODAY + timedelta(days=75))
    missing = manager.put(f"projects/{project['id']}", {"end_date": new_end})
    assert missing.status_code == 400 and "change_reason" in missing.json()["error"]["details"]
    changed = manager.put(f"projects/{project['id']}", {"end_date": new_end, "change_reason": "Vendor delay"})
    assert changed.status_code == 200 and changed.json()["end_date"] == new_end
    history = manager.get(f"projects/{project['id']}").json()["date_changes"]
    assert history[0]["reason"] == "Vendor delay" and history[0]["new_end"] == new_end


def test_budget_change_is_recorded(manager, project):
    response = manager.put(f"projects/{project['id']}", {"budget_planned": 65000, "change_reason": "Added a contractor"})
    assert response.status_code == 200 and response.json()["budget_planned"] == 65000
    latest = manager.get(f"projects/{project['id']}").json()["budget_changes"][0]
    assert latest["new_amount"] == 65000 and latest["reason"] == "Added a contractor"


def test_manager_cannot_reassign_complete_or_send_unknown_fields(manager, project):
    assert manager.put(f"projects/{project['id']}", {"manager_id": 1}).status_code == 403
    assert manager.put(f"projects/{project['id']}", {"status": "completed"}).status_code == 400
    assert manager.put(f"projects/{project['id']}", {"owner": "someone"}).status_code == 400


def test_employees_cannot_edit_projects(employee, project):
    assert employee.put(f"projects/{project['id']}", {"description": "hacked"}).status_code == 403


def test_search_and_filter_validation(admin, project):
    found = admin.get(f"projects?search={project['name']}").json()
    assert project["id"] in [p["id"] for p in found]
    assert admin.get("projects?archived=maybe").status_code == 400
    assert admin.get("projects?sort=bogus").status_code == 400


def test_archive_is_admin_only_read_only_and_restorable(admin, manager, manager_account, run_id):
    temp = make_project(admin, manager_account, run_id, "archive")
    assert manager.delete(f"projects/{temp['id']}").status_code == 403
    assert admin.request("DELETE", f"projects/{temp['id']}", {"reason": "Client cancelled"}).status_code == 204
    assert temp["id"] not in [p["id"] for p in admin.get("projects").json()]
    assert temp["id"] in [p["id"] for p in admin.get("projects?archived=true").json()]
    assert manager.put(f"projects/{temp['id']}", {"description": "edit"}).status_code == 409
    assert manager.post(f"projects/{temp['id']}/restore").status_code == 403
    restored = admin.post(f"projects/{temp['id']}/restore")
    assert restored.status_code == 200 and restored.json()["is_archived"] is False


def test_complete_requires_milestones(manager, project):
    assert manager.post(f"projects/{project['id']}/complete").status_code == 409


def test_project_manager_cannot_be_removed(manager, project, manager_account):
    assert manager.delete(f"projects/{project['id']}/members/{manager_account['id']}").status_code == 400


def test_member_can_be_removed(admin, manager, manager_account, employee_account, run_id):
    temp = make_project(admin, manager_account, run_id, "members")
    manager.post(f"projects/{temp['id']}/members", {"user_ids": [employee_account["id"]]})
    assert manager.delete(f"projects/{temp['id']}/members/{employee_account['id']}").status_code == 204
    assert employee_account["id"] not in [m["id"] for m in manager.get(f"projects/{temp['id']}/members").json()]


def test_manager_with_active_projects_cannot_be_deactivated(admin, manager_account, project):
    response = admin.delete(f"users/{manager_account['id']}")
    assert response.status_code == 409 and response.json()["error"]["details"]["active_projects"] >= 1
