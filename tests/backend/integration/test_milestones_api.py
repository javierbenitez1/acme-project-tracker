"""Integration tests for milestones, run as one story in order: dependencies, cycle prevention,
rescheduling with reasons and automatic shifting, the 8-hour workday, status rules, and completion."""
from datetime import date, timedelta

import pytest

TODAY = date.today()


def d(days):
    return str(TODAY + timedelta(days=days))


@pytest.fixture(scope="module")
def setup(admin, manager, manager_account, employee_account, run_id):
    project = admin.post("projects", {"name": f"IT Milestones {run_id}", "manager_id": manager_account["id"],
                                      "start_date": d(-5), "end_date": d(90), "budget_planned": 10000,
                                      "status": "active"}).json()
    added = manager.post(f"projects/{project['id']}/members", {"user_ids": [employee_account["id"]]})
    assert added.status_code == 201, added.text
    return {"project": project}


def create(manager, setup, name, start, end, **extra):
    return manager.post("milestones", {"project_id": setup["project"]["id"], "name": name,
                                       "start_date": start, "end_date": end, **extra})


def test_create_milestone(manager, setup):
    response = create(manager, setup, "Design", d(0), d(10))
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["progress"] == 0 and body["can_start"] is True and body["status"] == "not_started"
    setup["a"] = body["id"]


def test_milestone_must_fit_inside_the_project(manager, setup):
    response = create(manager, setup, "Too late", d(80), d(120))
    assert response.status_code == 400 and "end_date" in response.json()["error"]["details"]


def test_dependent_cannot_start_before_its_prerequisite_ends(manager, setup):
    early = create(manager, setup, "Build", d(5), d(20), depends_on=[setup["a"]])
    assert early.status_code == 400 and "start_date" in early.json()["error"]["details"]
    ok = create(manager, setup, "Build", d(10), d(20), depends_on=[setup["a"]])
    assert ok.status_code == 201, ok.text
    body = ok.json()
    assert body["can_start"] is False and [b["id"] for b in body["blocked_by"]] == [setup["a"]]
    setup["b"] = body["id"]


def test_blocked_milestone_cannot_start(manager, setup):
    response = manager.put(f"milestones/{setup['b']}", {"status": "in_progress"})
    assert response.status_code == 409 and response.json()["error"]["details"]["waiting_on"] == ["Design"]


def test_circular_dependencies_are_rejected(manager, setup):
    response = manager.post(f"milestones/{setup['a']}/dependencies", {"depends_on_id": setup["b"]})
    assert response.status_code == 409 and "circular" in response.json()["error"]["message"]


def test_reschedule_requires_a_reason_and_can_shift_dependents(manager, setup):
    url = f"milestones/{setup['a']}"
    assert manager.put(url, {"end_date": d(15)}).status_code == 400
    blocked = manager.put(url, {"end_date": d(15), "change_reason": "Client feedback round"})
    assert blocked.status_code == 409
    assert blocked.json()["error"]["details"]["shifted"][0]["id"] == setup["b"]
    preview = manager.put(url, {"end_date": d(15), "change_reason": "Client feedback round", "dry_run": True})
    assert preview.status_code == 200 and preview.json()["shifted"][0]["new_start"] == d(15)
    moved = manager.put(url, {"end_date": d(15), "change_reason": "Client feedback round", "shift_dependents": True})
    assert moved.status_code == 200 and moved.json()["end_date"] == d(15)
    build = manager.get(f"milestones/{setup['b']}").json()
    assert (build["start_date"], build["end_date"]) == (d(15), d(25))
    assert any("Client feedback round" in c["reason"] for c in build["date_changes"])


def test_eight_hour_workday_is_enforced(manager, setup, employee_account):
    setup["c"] = create(manager, setup, "Research", d(1), d(8)).json()["id"]
    uid = employee_account["id"]
    assert manager.post(f"milestones/{setup['a']}/assignments", {"user_id": uid}).status_code == 201
    over = manager.post(f"milestones/{setup['c']}/assignments", {"user_id": uid, "hours_per_day": 4})
    assert over.status_code == 409 and over.json()["error"]["details"]["available_hours"] == 0
    assert manager.put(f"milestones/{setup['a']}/assignments/{uid}", {"hours_per_day": 4}).status_code == 200
    assert manager.post(f"milestones/{setup['c']}/assignments", {"user_id": uid, "hours_per_day": 4}).status_code == 201
    assert manager.put(f"milestones/{setup['c']}/assignments/{uid}", {"hours_per_day": 5}).status_code == 409


def test_only_project_team_employees_can_be_assigned(manager, setup):
    response = manager.post(f"milestones/{setup['a']}/assignments", {"user_id": 1})
    assert response.status_code == 400 and "user_id" in response.json()["error"]["details"]


def test_assigned_member_cannot_be_removed_from_the_project(manager, setup, employee_account):
    response = manager.delete(f"projects/{setup['project']['id']}/members/{employee_account['id']}")
    assert response.status_code == 409


def test_employees_can_view_but_not_change_milestones(employee, setup):
    assert employee.get(f"milestones/{setup['a']}").status_code == 200
    assert employee.put(f"milestones/{setup['a']}", {"name": "x"}).status_code == 403
    assert employee.post("milestones", {"project_id": setup["project"]["id"], "name": "x",
                                        "start_date": d(1), "end_date": d(2)}).status_code == 403


def test_list_and_filters(manager, setup):
    items = manager.get(f"milestones?project_id={setup['project']['id']}").json()
    assert {setup["a"], setup["b"], setup["c"]} <= {m["id"] for m in items}
    assert manager.get("milestones?status=finished").status_code == 400


def test_delete_an_unstarted_milestone(manager, setup):
    temp = create(manager, setup, "Temporary", d(30), d(31)).json()
    assert manager.delete(f"milestones/{temp['id']}").status_code == 204
    assert manager.get(f"milestones/{temp['id']}").status_code == 404


def test_finishing_unblocks_dependents_and_reopening_is_guarded(manager, setup):
    assert manager.put(f"milestones/{setup['a']}", {"status": "done"}).status_code == 200
    assert manager.put(f"milestones/{setup['b']}", {"status": "in_progress"}).status_code == 200
    assert manager.put(f"milestones/{setup['a']}", {"status": "in_progress"}).status_code == 409
    assert manager.delete(f"milestones/{setup['a']}").status_code == 409


def test_project_completes_once_every_milestone_is_done(manager, setup):
    project_id = setup["project"]["id"]
    assert manager.post(f"projects/{project_id}/complete").status_code == 409
    for key in ("b", "c"):
        assert manager.put(f"milestones/{setup[key]}", {"status": "done"}).status_code == 200
    done = manager.post(f"projects/{project_id}/complete")
    assert done.status_code == 200
    assert done.json()["status"] == "completed" and done.json()["is_archived"] is True
    assert manager.put(f"milestones/{setup['a']}", {"name": "Edited"}).status_code == 409
