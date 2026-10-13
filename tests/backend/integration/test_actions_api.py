"""Integration tests for the Action Center: rules raise items for real problems, close them when fixed,
and reopen them if the problem returns. Manual items follow role rules, and every resolution is
recorded for admins."""
from datetime import date, timedelta

import pytest

TODAY = date.today()


def d(days):
    return str(TODAY + timedelta(days=days))


@pytest.fixture(scope="module")
def setup(admin, manager, manager_account, employee_account, run_id):
    project = admin.post("projects", {"name": f"IT Actions {run_id}", "manager_id": manager_account["id"],
                                      "start_date": d(-20), "end_date": d(30), "budget_planned": 1000,
                                      "status": "active"}).json()
    added = manager.post(f"projects/{project['id']}/members", {"user_ids": [employee_account["id"]]})
    assert added.status_code == 201, added.text
    late = manager.post("milestones", {"project_id": project["id"], "name": "Kickoff",
                                       "start_date": d(-20), "end_date": d(-1)}).json()
    ready = manager.post("milestones", {"project_id": project["id"], "name": "Build",
                                        "start_date": d(0), "end_date": d(10)}).json()
    task = manager.post("deliverables", {"milestone_id": ready["id"], "title": "Set up CI",
                                         "assignee_id": employee_account["id"]}).json()
    return {"project": project, "late": late, "ready": ready, "task": task}


def items(client, setup, status="active"):
    response = client.get(f"actions?project_id={setup['project']['id']}&status={status}")
    assert response.status_code == 200, response.text
    return {item["rule_key"] or item["title"]: item for item in response.json()}


def test_rules_raise_items_for_real_problems(manager, setup):
    found = items(manager, setup)
    assert found[f"milestone_overdue:{setup['late']['id']}"]["priority"] == "high"
    assert f"milestone_ready_to_start:{setup['ready']['id']}" in found


def test_blocked_work_and_overspending_raise_items(employee, manager, setup):
    project_id = setup["project"]["id"]
    blocked = employee.put(f"deliverables/{setup['task']['id']}",
                           {"status": "blocked", "status_note": "Waiting on cloud access"})
    assert blocked.status_code == 200, blocked.text
    spent = manager.post("budgets", {"project_id": project_id, "amount": 1500, "category": "software"})
    assert spent.status_code == 201, spent.text
    found = items(manager, setup)
    assert "Waiting on cloud access" in found[f"deliverable_blocked:{setup['task']['id']}"]["description"]
    assert found[f"project_over_budget:{project_id}"]["priority"] == "critical"
    assert list(found.values())[0]["priority"] == "critical"  # most urgent first


def test_fixing_a_problem_closes_its_item_and_a_relapse_reopens_it(manager, setup):
    project_id = setup["project"]["id"]
    raised = manager.put(f"projects/{project_id}", {"budget_planned": 2000, "change_reason": "Approved extra licenses"})
    assert raised.status_code == 200, raised.text
    closed = items(manager, setup, "all")[f"project_over_budget:{project_id}"]
    assert closed["status"] == "done" and closed["resolution_note"].startswith("Resolved automatically")
    assert manager.post("budgets", {"project_id": project_id, "amount": 1000, "category": "software"}).status_code == 201
    assert items(manager, setup)[f"project_over_budget:{project_id}"]["status"] == "open"


def test_system_items_close_themselves_but_can_be_dismissed_with_a_note(manager, setup, manager_account):
    item = items(manager, setup)[f"milestone_ready_to_start:{setup['ready']['id']}"]
    url = f"actions/{item['id']}"
    assert manager.put(url, {"status": "done"}).status_code == 409
    assert manager.put(url, {"title": "Edited"}).status_code == 403
    assert manager.put(url, {"status": "dismissed"}).status_code == 400
    dismissed = manager.put(url, {"status": "dismissed", "resolution_note": "Starting next sprint instead"})
    assert dismissed.status_code == 200
    assert dismissed.json()["resolved_by_name"] == manager_account["name"]
    assert manager.delete(url).status_code == 409


def test_manager_assigns_an_item_and_the_employee_resolves_it(admin, manager, employee, setup, employee_account):
    project_id = setup["project"]["id"]
    created = manager.post("actions", {"title": "Prepare the client demo", "priority": "high", "due_date": d(3),
                                       "assignee_id": employee_account["id"], "project_id": project_id})
    assert created.status_code == 201, created.text
    action_id = created.json()["id"]
    assert action_id in [i["id"] for i in employee.get("actions?assignee_id=me").json()]
    assert employee.put(f"actions/{action_id}", {"priority": "low"}).status_code == 403
    assert employee.put(f"actions/{action_id}", {"status": "done"}).status_code == 400
    done = employee.put(f"actions/{action_id}", {"status": "done", "resolution_note": "Demo deck shared with the client"})
    assert done.status_code == 200 and done.json()["status"] == "done"
    audit = admin.get(f"audit?project_id={project_id}&action=action.resolved").json()["items"]
    assert any("Demo deck shared" in entry["summary"] for entry in audit)


def test_employees_only_see_their_own_items(employee, setup, employee_account):
    found = items(employee, setup, "all")
    assert found and all(i["assignee_id"] == employee_account["id"] for i in found.values())
    assert f"project_over_budget:{setup['project']['id']}" not in found


def test_manual_item_rules(manager, employee, setup, manager_account):
    project_id = setup["project"]["id"]
    assert employee.post("actions", {"title": "Nope"}).status_code == 403
    assert manager.post("actions", {"title": "x", "assignee_id": 1, "project_id": project_id}).status_code == 400
    assert manager.post("actions", {"title": "x", "due_date": d(-1)}).status_code == 400
    assert manager.post("actions", {"title": "x", "priority": "urgent"}).status_code == 400
    reminder = manager.post("actions", {"title": "Temporary reminder"})
    assert reminder.status_code == 201 and reminder.json()["assignee_id"] == manager_account["id"]
    assert manager.delete(f"actions/{reminder.json()['id']}").status_code == 204


def test_summary_and_filter_validation(manager):
    summary = manager.get("actions/summary").json()
    assert summary["open_total"] >= 1 and set(summary["by_priority"]) == {"critical", "high", "medium", "low"}
    assert manager.get("actions?status=finished").status_code == 400
    assert manager.get("actions?assignee_id=5").status_code == 400


def test_archiving_a_project_clears_its_items(admin, manager, setup):
    assert admin.delete(f"projects/{setup['project']['id']}").status_code == 204
    assert items(manager, setup) == {}