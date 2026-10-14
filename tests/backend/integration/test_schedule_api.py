"""Integration tests for the critical path and delivery forecast endpoint."""
from datetime import date, timedelta

import pytest

TODAY = date.today()


def d(days):
    return str(TODAY + timedelta(days=days))


@pytest.fixture(scope="module")
def plan(admin, manager, manager_account, run_id):
    """Design, Build and Launch form the long chain. Docs runs alongside and is short."""
    project = admin.post("projects", {"name": f"IT Schedule {run_id}", "manager_id": manager_account["id"],
                                      "start_date": d(-5), "end_date": d(60), "budget_planned": 10000,
                                      "status": "active"}).json()

    def create(name, start, end, depends_on=None):
        body = {"project_id": project["id"], "name": name, "start_date": d(start), "end_date": d(end)}
        if depends_on:
            body["depends_on"] = depends_on
        response = manager.post("milestones", body)
        assert response.status_code == 201, response.text
        return response.json()["id"]

    design = create("Design", 0, 10)
    build = create("Build", 10, 20, [design])
    launch = create("Launch", 20, 40, [build])
    docs = create("Docs", 0, 5)
    return {"project": project, "design": design, "build": build, "launch": launch, "docs": docs}


def schedule(client, plan):
    response = client.get(f"milestones/schedule?project_id={plan['project']['id']}")
    assert response.status_code == 200, response.text
    return response.json()


def test_the_longest_chain_is_the_critical_path(manager, plan):
    body = schedule(manager, plan)
    assert [m["id"] for m in body["critical_path"]] == [plan["design"], plan["build"], plan["launch"]]
    assert body["buffer_days"] == 20
    assert body["slack"][str(plan["docs"])] == 55


def test_forecast_is_included(manager, plan):
    assert schedule(manager, plan)["forecast"]["status"] in ("not_enough_data", "on_time", "late", "early")


def test_a_delay_on_the_critical_path_uses_up_the_buffer(manager, plan):
    moved = manager.put(f"milestones/{plan['launch']}", {"end_date": d(50), "change_reason": "Extra security review"})
    assert moved.status_code == 200, moved.text
    assert schedule(manager, plan)["buffer_days"] == 10


def test_finished_milestones_leave_the_critical_path(manager, plan):
    assert manager.put(f"milestones/{plan['design']}", {"status": "done"}).status_code == 200
    ids = [m["id"] for m in schedule(manager, plan)["critical_path"]]
    assert plan["design"] not in ids and plan["launch"] in ids


def test_project_is_required_and_hidden_projects_stay_hidden(manager, employee, plan):
    assert manager.get("milestones/schedule").status_code == 400
    assert manager.get("milestones/schedule?project_id=999999").status_code == 404
    assert employee.get(f"milestones/schedule?project_id={plan['project']['id']}").status_code == 404
