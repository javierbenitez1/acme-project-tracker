"""Integration tests for the dashboard and workload heatmap: role-scoped data, my work, upcoming
milestones, recent activity, and weekly hours against a 40-hour capacity.

This module books a full 8-hour day, so it uses its own employee. Sharing one with other modules
would make the 8-hour rule reject their assignments depending on test order."""
from datetime import date, timedelta

import pytest

from conftest import Client, login

TODAY = date.today()


def d(days):
    return str(TODAY + timedelta(days=days))


@pytest.fixture(scope="module")
def worker_account(admin, manager_account, run_id):
    creds = {"username": f"it_dash_{run_id}", "password": "Employee123"}
    response = admin.post("users", {**creds, "name": f"Dashboard Worker {run_id}", "role": "employee",
                                    "email": f"it_dash_{run_id}@acme.test", "job_title": "Developer",
                                    "manager_id": manager_account["id"]})
    assert response.status_code == 201, response.text
    return {**response.json(), **creds}


@pytest.fixture(scope="module")
def worker(worker_account):
    return Client(login(worker_account["username"], worker_account["password"])["access_token"])


@pytest.fixture(scope="module")
def setup(admin, manager, manager_account, worker_account, run_id):
    project = admin.post("projects", {"name": f"IT Dashboard {run_id}", "manager_id": manager_account["id"],
                                      "start_date": d(-5), "end_date": d(60), "budget_planned": 20000,
                                      "status": "active"}).json()
    uid = worker_account["id"]
    assert manager.post(f"projects/{project['id']}/members", {"user_ids": [uid]}).status_code == 201
    build = manager.post("milestones", {"project_id": project["id"], "name": "Build",
                                        "start_date": d(0), "end_date": d(20)}).json()
    review = manager.post("milestones", {"project_id": project["id"], "name": "Review",
                                         "start_date": d(0), "end_date": d(20)}).json()
    soon = manager.post("milestones", {"project_id": project["id"], "name": "Quick win",
                                       "start_date": d(0), "end_date": d(5)}).json()
    assert manager.post(f"milestones/{build['id']}/assignments", {"user_id": uid, "hours_per_day": 6}).status_code == 201
    assert manager.post(f"milestones/{review['id']}/assignments", {"user_id": uid, "hours_per_day": 2}).status_code == 201
    task = manager.post("deliverables", {"milestone_id": soon["id"], "title": "Draft the launch email",
                                         "assignee_id": uid, "due_date": d(3)}).json()
    return {"project": project, "soon": soon, "task": task}


def test_manager_dashboard_has_kpis_projects_and_upcoming_work(manager, setup):
    response = manager.get("dashboard")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["role"] == "manager"
    assert {"active_projects", "on_track", "at_risk", "off_track", "budget_planned"} <= set(body["kpis"])
    card = next(p for p in body["projects"] if p["id"] == setup["project"]["id"])
    assert card["health"] in ("on_track", "at_risk", "off_track") and "risk_reasons" in card
    assert setup["soon"]["id"] in [m["id"] for m in body["upcoming_milestones"]]


def test_employee_dashboard_shows_their_own_work(worker, setup):
    body = worker.get("dashboard").json()
    assert body["role"] == "employee"
    assert setup["task"]["id"] in [w["id"] for w in body["my_work"]]
    assert body["kpis"]["my_open_deliverables"] >= 1
    assert setup["project"]["id"] in [p["id"] for p in body["projects"]]


def test_recent_activity_is_scoped_to_the_viewer(manager, worker, setup):
    manager_feed = manager.get("dashboard").json()["recent_activity"]
    assert any(entry["project_id"] == setup["project"]["id"] for entry in manager_feed)
    worker_feed = worker.get("dashboard").json()["recent_activity"]
    assert all(entry["entity_type"] != "budget_entry" for entry in worker_feed)


def test_workload_shows_a_full_forty_hour_week(manager, setup):
    response = manager.get(f"dashboard/workload?project_id={setup['project']['id']}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["capacity_per_week"] == 40 and len(body["week_starts"]) == 6
    person = body["people"][0]
    assert person["weeks"][1]["hours"] == 40 and person["weeks"][1]["utilization"] == 100
    assert person["peak_daily_hours"] == 8 and person["over_allocated"] is False
    assert {a["milestone"] for a in person["assignments"]} == {"Build", "Review"}


def test_employees_only_see_their_own_workload(worker, worker_account, setup):
    people = worker.get("dashboard/workload").json()["people"]
    assert [p["user_id"] for p in people] == [worker_account["id"]]


def test_workload_filters_are_validated(manager):
    assert manager.get("dashboard/workload?weeks=20").status_code == 400
    assert manager.get("dashboard/workload?project_id=999999").status_code == 404


def test_admin_dashboard_works(admin):
    response = admin.get("dashboard")
    assert response.status_code == 200 and response.json()["role"] == "admin"