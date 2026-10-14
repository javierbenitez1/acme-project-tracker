"""Integration tests for the weekly status report: RAG ratings with reasons, the summary, and who can see it."""
from datetime import date, timedelta

import pytest

TODAY = date.today()


def d(days):
    return str(TODAY + timedelta(days=days))


@pytest.fixture(scope="module")
def project(admin, manager, manager_account, run_id):
    created = admin.post("projects", {"name": f"IT Report {run_id}", "manager_id": manager_account["id"],
                                      "start_date": d(-20), "end_date": d(20), "budget_planned": 10000,
                                      "status": "active"}).json()
    build = manager.post("milestones", {"project_id": created["id"], "name": "Build",
                                        "start_date": d(-20), "end_date": d(10)}).json()
    assert manager.post("milestones", {"project_id": created["id"], "name": "Launch", "start_date": d(10),
                                       "end_date": d(20), "depends_on": [build["id"]]}).status_code == 201
    return created


def test_manager_gets_a_rag_report_with_reasons(manager, project):
    response = manager.get(f"projects/{project['id']}/report")
    assert response.status_code == 200, response.text
    body = response.json()
    for area in ("overall", "schedule", "budget", "risks"):
        assert body["rag"][area]["status"] in ("green", "amber", "red") and body["rag"][area]["reason"]
    assert body["summary"].startswith(project["name"])
    assert [m["name"] for m in body["milestones"]] == ["Build", "Launch"]
    assert all(m["critical"] for m in body["milestones"])


def test_admins_can_read_it_and_employees_cannot(admin, employee, project):
    assert admin.get(f"projects/{project['id']}/report").status_code == 200
    assert employee.get(f"projects/{project['id']}/report").status_code == 403