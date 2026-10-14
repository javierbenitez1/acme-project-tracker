"""Integration tests for the risk register: suggestions from live signals, accepting and dismissing
them, scoring, owners, review reminders in the Action Center, role rules, and the audit trail."""
from datetime import date, timedelta

import pytest

TODAY = date.today()


def d(days):
    return str(TODAY + timedelta(days=days))


@pytest.fixture(scope="module")
def setup(admin, manager, manager_account, employee_account, run_id):
    """Build then Launch run right up to the project end date, so the critical path has no buffer."""
    project = admin.post("projects", {"name": f"IT Risks {run_id}", "manager_id": manager_account["id"],
                                      "start_date": d(-5), "end_date": d(40), "budget_planned": 50000,
                                      "status": "active"}).json()
    assert manager.post(f"projects/{project['id']}/members", {"user_ids": [employee_account["id"]]}).status_code == 201
    build = manager.post("milestones", {"project_id": project["id"], "name": "Build",
                                        "start_date": d(0), "end_date": d(20)}).json()
    launch = manager.post("milestones", {"project_id": project["id"], "name": "Launch", "start_date": d(20),
                                         "end_date": d(40), "depends_on": [build["id"]]})
    assert launch.status_code == 201, launch.text
    return {"project": project, "url": f"projects/{project['id']}/risks"}


def register(client, setup):
    response = client.get(setup["url"])
    assert response.status_code == 200, response.text
    return response.json()


def test_live_signals_suggest_risks(manager, setup):
    body = register(manager, setup)
    suggestion = next(s for s in body["suggestions"] if s["source_key"] == "schedule:critical_path_buffer")
    assert "Build, Launch have no buffer" in suggestion["description"]
    assert body["can_manage"] is True and body["risks"] == []
    setup["suggestion"] = suggestion


def test_accepting_a_suggestion_adds_it_once(manager, manager_account, setup):
    s = setup["suggestion"]
    body = {k: s[k] for k in ("title", "description", "category", "likelihood", "impact", "mitigation", "source_key")}
    created = manager.post(setup["url"], {**body, "owner_id": manager_account["id"]})
    assert created.status_code == 201, created.text
    risk = created.json()
    assert (risk["score"], risk["level"], risk["owner_id"]) == (12, "medium", manager_account["id"])
    assert manager.post(setup["url"], body).status_code == 409
    assert "schedule:critical_path_buffer" not in [x["source_key"] for x in register(manager, setup)["suggestions"]]
    setup["risk"] = risk


def test_manual_risks_are_validated_and_scored(manager, setup):
    bad = manager.post(setup["url"], {"title": "x", "category": "weather", "likelihood": 6, "impact": 0})
    assert bad.status_code == 400
    assert {"category", "likelihood", "impact"} <= set(bad.json()["error"]["details"])
    outsider = manager.post(setup["url"], {"title": "Vendor slips", "category": "vendor", "likelihood": 2,
                                           "impact": 3, "owner_id": 1})
    assert outsider.status_code == 400 and "owner_id" in outsider.json()["error"]["details"]
    vendor = manager.post(setup["url"], {"title": "Card reader vendor slips again", "category": "vendor",
                                         "likelihood": 4, "impact": 4, "review_date": d(-1),
                                         "mitigation": "Line up a second supplier."})
    assert vendor.status_code == 201 and vendor.json()["level"] == "high"
    assert vendor.json()["review_overdue"] is True
    budget = manager.post(setup["url"], {"title": "Licence costs rise", "category": "budget",
                                         "likelihood": 2, "impact": 2})
    assert budget.status_code == 201
    setup["vendor"], setup["budget"] = vendor.json(), budget.json()


def test_register_is_sorted_with_a_summary(manager, setup):
    body = register(manager, setup)
    assert [r["id"] for r in body["risks"]][0] == setup["vendor"]["id"]  # highest score first
    assert body["summary"]["active"] == 3 and body["summary"]["high"] == 1 and body["summary"]["reviews_overdue"] == 1


def test_overdue_reviews_raise_an_action_item(manager, setup):
    response = manager.get(f"actions?project_id={setup['project']['id']}")
    assert response.status_code == 200, response.text
    keys = [item["rule_key"] for item in response.json()]
    assert f"risk_review_overdue:{setup['vendor']['id']}" in keys


def test_updating_and_closing_a_risk_is_audited(admin, manager, setup):
    url = f"{setup['url']}/{setup['vendor']['id']}"
    mitigating = manager.put(url, {"status": "mitigating", "likelihood": 2, "review_date": d(14)})
    assert mitigating.status_code == 200, mitigating.text
    assert (mitigating.json()["score"], mitigating.json()["review_overdue"]) == (8, False)
    closed = manager.put(url, {"status": "closed"})
    assert closed.status_code == 200 and closed.json()["closed_at"] is not None
    log = admin.get(f"audit?project_id={setup['project']['id']}&action=risk.updated").json()["items"]
    assert any(entry["details"]["changes"].get("likelihood") == {"from": 4, "to": 2} for entry in log)


def test_employees_can_read_but_not_change_risks_and_never_see_budget_risks(employee, setup):
    body = register(employee, setup)
    ids = [r["id"] for r in body["risks"]]
    assert setup["risk"]["id"] in ids and setup["budget"]["id"] not in ids
    assert body["suggestions"] == [] and body["can_manage"] is False
    assert employee.post(setup["url"], {"title": "x", "category": "other", "likelihood": 1, "impact": 1}).status_code == 403
    assert employee.get("projects/risks").status_code == 200


def test_portfolio_view_lists_active_risks_highest_first(manager, setup):
    body = manager.get("projects/risks").json()
    mine = [r for r in body["risks"] if r["project_id"] == setup["project"]["id"]]
    assert [r["id"] for r in mine] == [setup["risk"]["id"], setup["budget"]["id"]]  # the closed one is gone


def test_dismissed_suggestions_stay_dismissed(admin, manager, manager_account, run_id):
    project = admin.post("projects", {"name": f"IT Risks dismiss {run_id}", "manager_id": manager_account["id"],
                                      "start_date": d(-5), "end_date": d(10), "budget_planned": 1000,
                                      "status": "active"}).json()
    ship = manager.post("milestones", {"project_id": project["id"], "name": "Ship", "start_date": d(0), "end_date": d(10)})
    assert ship.status_code == 201, ship.text
    url = f"projects/{project['id']}/risks"
    dismissed = manager.post(f"{url}/dismiss", {"source_key": "schedule:critical_path_buffer"})
    assert dismissed.status_code == 204, dismissed.text
    body = manager.get(url).json()
    assert "schedule:critical_path_buffer" not in [s["source_key"] for s in body["suggestions"]]
    assert body["risks"] == []
    assert manager.post(f"{url}/dismiss", {"source_key": "schedule:critical_path_buffer"}).status_code == 409


def test_archived_projects_are_read_only(admin, manager, setup):
    assert admin.delete(f"projects/{setup['project']['id']}").status_code == 204
    assert register(manager, setup)["can_manage"] is False
    assert manager.put(f"{setup['url']}/{setup['risk']['id']}", {"status": "closed"}).status_code == 409
