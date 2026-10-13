"""Integration tests for budgets: recording spending, validation, the over-budget warning and health
change, the consumed-versus-planned summary, corrections, and who can see financial data."""
from datetime import date, timedelta

import pytest

TODAY = date.today()


def d(days):
    return str(TODAY + timedelta(days=days))


@pytest.fixture(scope="module")
def project(admin, manager_account, run_id):
    response = admin.post("projects", {"name": f"IT Budgets {run_id}", "manager_id": manager_account["id"],
                                       "start_date": d(-30), "end_date": d(30), "budget_planned": 10000,
                                       "status": "active"})
    assert response.status_code == 201, response.text
    return response.json()


def spend(client, project, amount, category="labor", **extra):
    return client.post("budgets", {"project_id": project["id"], "amount": amount, "category": category, **extra})


def test_manager_records_spending(manager, project):
    response = spend(manager, project, 4000, entry_date=d(-10), description="Sprint 1 labor")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["amount"] == 4000 and body["warning"] is None
    project["entry_id"] = body["id"]


@pytest.mark.parametrize("amount, category, extra, field", [
    (0, "labor", {}, "amount"),
    (100, "snacks", {}, "category"),
    (100, "labor", {"entry_date": d(5)}, "entry_date"),
    (100, "labor", {"entry_date": d(-60)}, "entry_date"),
])
def test_invalid_spending_is_rejected(manager, project, amount, category, extra, field):
    response = spend(manager, project, amount, category, **extra)
    assert response.status_code == 400 and field in response.json()["error"]["details"]


def test_employees_cannot_see_financial_data(employee, project):
    assert employee.get(f"budgets?project_id={project['id']}").status_code == 403
    assert employee.get(f"budgets/summary?project_id={project['id']}").status_code == 403


def test_summary_shows_consumed_versus_planned(manager, project):
    response = manager.get(f"budgets/summary?project_id={project['id']}")
    assert response.status_code == 200, response.text
    summary = response.json()
    assert (summary["planned"], summary["spent"], summary["remaining"]) == (10000, 4000, 6000)
    assert summary["by_category"][0]["category"] == "labor"
    assert summary["monthly"][-1]["cumulative"] == 4000
    assert summary["forecast"]["status"] in ("under", "on_track", "over")


def test_summary_requires_a_project(manager):
    assert manager.get("budgets/summary").status_code == 400


def test_going_over_budget_warns_and_changes_project_health(manager, project):
    response = spend(manager, project, 7000, "contractors")
    assert response.status_code == 201 and "over budget" in response.json()["warning"]
    health = manager.get(f"projects/{project['id']}").json()
    assert health["health"] == "off_track"
    assert any(reason.startswith("Over budget") for reason in health["risk_reasons"])


def test_corrections_and_removals_update_the_totals(manager, project):
    corrected = manager.put(f"budgets/{project['entry_id']}", {"amount": 3000})
    assert corrected.status_code == 200 and corrected.json()["amount"] == 3000
    assert manager.get(f"budgets/summary?project_id={project['id']}").json()["spent"] == 10000
    assert manager.delete(f"budgets/{project['entry_id']}").status_code == 204
    assert manager.get(f"budgets/summary?project_id={project['id']}").json()["spent"] == 7000
    assert manager.get(f"budgets/{project['entry_id']}").status_code == 404


def test_removed_entries_stay_in_the_audit_log(admin, project):
    entries = admin.get(f"audit?project_id={project['id']}&action=budget.entry_removed").json()["items"]
    assert entries and entries[0]["details"]["amount"] == 3000


def test_filters_are_validated(manager):
    assert manager.get("budgets?category=snacks").status_code == 400
    assert manager.get("budgets?from=2026-05-02&to=2026-05-01").status_code == 400


def test_archived_projects_are_read_only(admin, manager, project):
    assert admin.delete(f"projects/{project['id']}").status_code == 204
    assert spend(manager, project, 50).status_code == 409