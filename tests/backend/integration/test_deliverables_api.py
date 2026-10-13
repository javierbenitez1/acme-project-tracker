"""Integration tests for deliverables: assignment rules, employee status updates, blocked reasons,
milestone dependencies, progress roll-up, and record-keeping rules for completed work."""
from datetime import date, timedelta

import pytest

from conftest import Client, login

TODAY = date.today()


def d(days):
    return str(TODAY + timedelta(days=days))


@pytest.fixture(scope="module")
def setup(admin, manager, manager_account, employee_account, run_id):
    project = admin.post("projects", {"name": f"IT Deliverables {run_id}", "manager_id": manager_account["id"],
                                      "start_date": d(-5), "end_date": d(90), "budget_planned": 10000,
                                      "status": "active"}).json()
    added = manager.post(f"projects/{project['id']}/members", {"user_ids": [employee_account["id"]]})
    assert added.status_code == 201, added.text
    first = manager.post("milestones", {"project_id": project["id"], "name": "Discovery",
                                        "start_date": d(0), "end_date": d(10)}).json()
    second = manager.post("milestones", {"project_id": project["id"], "name": "Delivery",
                                         "start_date": d(10), "end_date": d(20), "depends_on": [first["id"]]}).json()
    return {"project": project, "first": first, "second": second}


def add(manager, milestone, title, **extra):
    return manager.post("deliverables", {"milestone_id": milestone["id"], "title": title, **extra})


def test_manager_creates_an_assigned_deliverable(manager, setup, employee_account):
    response = add(manager, setup["first"], "Interview stakeholders",
                   assignee_id=employee_account["id"], due_date=d(5))
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["assignee_id"] == employee_account["id"] and body["status"] == "todo"
    setup["mine"] = body["id"]


def test_assignee_must_be_on_the_team_and_due_date_inside_the_milestone(manager, setup):
    assert add(manager, setup["first"], "Bad assignee", assignee_id=1).status_code == 400
    late = add(manager, setup["first"], "Bad date", due_date=d(15))
    assert late.status_code == 400 and "due_date" in late.json()["error"]["details"]


def test_employee_sees_their_own_work(employee, setup):
    items = employee.get("deliverables?assignee_id=me").json()
    assert setup["mine"] in [i["id"] for i in items]


def test_starting_work_starts_the_milestone(employee, manager, setup):
    response = employee.put(f"deliverables/{setup['mine']}", {"status": "in_progress"})
    assert response.status_code == 200 and response.json()["milestone_started"] is True
    assert manager.get(f"milestones/{setup['first']['id']}").json()["status"] == "in_progress"


def test_employee_can_only_change_status_on_their_own_work(employee, manager, setup):
    assert employee.put(f"deliverables/{setup['mine']}", {"title": "Renamed"}).status_code == 403
    other = add(manager, setup["first"], "Write summary").json()
    setup["other"] = other["id"]
    assert employee.put(f"deliverables/{other['id']}", {"status": "done"}).status_code == 403


def test_blocked_work_needs_a_reason(employee, setup):
    url = f"deliverables/{setup['mine']}"
    missing = employee.put(url, {"status": "blocked"})
    assert missing.status_code == 400 and "status_note" in missing.json()["error"]["details"]
    blocked = employee.put(url, {"status": "blocked", "status_note": "Waiting on client calendar"})
    assert blocked.status_code == 200 and blocked.json()["status_note"] == "Waiting on client calendar"
    resumed = employee.put(url, {"status": "in_progress"})
    assert resumed.status_code == 200 and resumed.json()["status_note"] is None


def test_work_cannot_start_before_milestone_dependencies_finish(manager, employee, setup, employee_account):
    later = add(manager, setup["second"], "Launch checklist", assignee_id=employee_account["id"]).json()
    response = employee.put(f"deliverables/{later['id']}", {"status": "in_progress"})
    assert response.status_code == 409
    assert response.json()["error"]["details"]["waiting_on"] == ["Discovery"]


def test_progress_rolls_up_and_the_milestone_waits_for_open_work(employee, manager, setup):
    assert employee.put(f"deliverables/{setup['mine']}", {"status": "done"}).status_code == 200
    assert manager.get(f"milestones/{setup['first']['id']}").json()["progress"] == 50
    blocked = manager.put(f"milestones/{setup['first']['id']}", {"status": "done"})
    assert blocked.status_code == 409
    assert blocked.json()["error"]["details"]["open_deliverables"] == ["Write summary"]
    finished = manager.put(f"deliverables/{setup['other']}", {"status": "done"})
    assert finished.status_code == 200 and finished.json()["milestone_ready"] is True
    assert manager.put(f"milestones/{setup['first']['id']}", {"status": "done"}).status_code == 200


def test_work_in_a_finished_milestone_is_locked(employee, manager, setup):
    assert employee.put(f"deliverables/{setup['mine']}", {"status": "in_progress"}).status_code == 409
    assert add(manager, setup["first"], "Late addition").status_code == 409


def test_completed_work_is_kept_but_open_work_can_be_removed(manager, setup):
    assert manager.delete(f"deliverables/{setup['mine']}").status_code == 409
    temp = add(manager, setup["second"], "Temporary").json()
    assert manager.delete(f"deliverables/{temp['id']}").status_code == 204
    assert manager.get(f"deliverables/{temp['id']}").status_code == 404


def test_people_outside_the_project_cannot_see_its_work(admin, manager_account, setup, run_id):
    creds = {"username": f"it_out_{run_id}", "password": "Employee123"}
    created = admin.post("users", {**creds, "name": "Outsider", "email": f"it_out_{run_id}@acme.test",
                                   "role": "employee", "manager_id": manager_account["id"]})
    assert created.status_code == 201, created.text
    outsider = Client(login(creds["username"], creds["password"])["access_token"])
    assert outsider.get(f"deliverables/{setup['mine']}").status_code == 404
    assert setup["mine"] not in [i["id"] for i in outsider.get("deliverables").json()]


def test_filter_validation(manager):
    assert manager.get("deliverables?status=finished").status_code == 400
    assert manager.get("deliverables?milestone_id=abc").status_code == 400