"""Integration tests for Ask Throughline: answers come from live data, respect each role's access,
and follow the conversation's project. This module books a full day, so it uses its own employee."""
from datetime import date, timedelta

import pytest

from conftest import Client, login

TODAY = date.today()


def d(days):
    return str(TODAY + timedelta(days=days))


@pytest.fixture(scope="module")
def helper_account(admin, manager_account, run_id):
    creds = {"username": f"it_ask_{run_id}", "password": "Employee123"}
    response = admin.post("users", {**creds, "name": f"Quinn Askwith{run_id}", "role": "employee",
                                    "email": f"it_ask_{run_id}@acme.test", "job_title": "Analyst",
                                    "manager_id": manager_account["id"]})
    assert response.status_code == 201, response.text
    return {**response.json(), **creds}


@pytest.fixture(scope="module")
def helper(helper_account):
    return Client(login(helper_account["username"], helper_account["password"])["access_token"])


@pytest.fixture(scope="module")
def setup(admin, manager, manager_account, helper_account, run_id):
    project = admin.post("projects", {"name": f"Zephyr Upgrade {run_id}", "manager_id": manager_account["id"],
                                      "start_date": d(-10), "end_date": d(30), "budget_planned": 40000,
                                      "status": "active"}).json()
    uid = helper_account["id"]
    assert manager.post(f"projects/{project['id']}/members", {"user_ids": [uid]}).status_code == 201
    late = manager.post("milestones", {"project_id": project["id"], "name": "Kickoff workshop",
                                       "start_date": d(-10), "end_date": d(-1)}).json()
    build = manager.post("milestones", {"project_id": project["id"], "name": "Build the gateway",
                                        "start_date": d(0), "end_date": d(20)}).json()
    assert manager.post(f"milestones/{build['id']}/assignments", {"user_id": uid, "hours_per_day": 8}).status_code == 201
    task = manager.post("deliverables", {"milestone_id": build["id"], "title": "Wire up the gateway",
                                         "assignee_id": uid, "due_date": d(3)}).json()
    return {"project": project, "late": late, "task": task}


def ask(client, question, project_id=None):
    body = {"question": question}
    if project_id:
        body["project_id"] = project_id
    response = client.post("dashboard/ask", body)
    assert response.status_code == 200, response.text
    return response.json()


def test_greeting_offers_suggestions(manager, setup):
    reply = ask(manager, "hi")
    assert reply["intent"] == "greeting" and len(reply["follow_ups"]) >= 3


def test_status_of_a_project_named_in_the_question(manager, setup):
    reply = ask(manager, "How is the zephyr project doing?")
    assert reply["intent"] == "status" and reply["project_id"] == setup["project"]["id"]
    assert setup["project"]["name"] in reply["text"] and "Next milestone" in reply["text"]
    assert any(link["to"] == f"/projects/{setup['project']['id']}" for link in reply["links"])


def test_overdue_and_due_soon_come_from_live_data(manager, setup):
    assert "Kickoff workshop" in ask(manager, "What's overdue on zephyr?")["text"]
    assert "Wire up the gateway" in ask(manager, "What's due this week?", setup["project"]["id"])["text"]


def test_blocked_work_includes_the_reason(manager, helper, setup):
    blocked = helper.put(f"deliverables/{setup['task']['id']}", {"status": "blocked", "status_note": "Waiting on firewall rules"})
    assert blocked.status_code == 200, blocked.text
    reply = ask(manager, "What's blocking zephyr?")
    assert reply["intent"] == "blocked" and "Waiting on firewall rules" in reply["text"]


def test_workload_finds_fully_booked_people(manager, helper_account, setup):
    reply = ask(manager, "Who's overbooked?")
    assert reply["intent"] == "workload" and helper_account["name"] in reply["text"]
    assert "8 hours" in ask(manager, f"Is {helper_account['name'].split()[0]} free?")["text"]


def test_follow_ups_keep_the_project_from_the_conversation(manager, setup):
    reply = ask(manager, "What are the risks?", setup["project"]["id"])
    assert reply["intent"] == "risks" and reply["project_id"] == setup["project"]["id"]


def test_help_questions_explain_the_app(manager, setup):
    reply = ask(manager, "How do I reschedule a milestone?")
    assert reply["intent"] == "help" and "Milestones" in reply["text"] and reply["links"]


def test_employees_get_their_own_work_and_no_budget(helper, setup):
    assert "Wire up the gateway" in ask(helper, "What should I work on?")["text"]
    assert "only visible to managers" in ask(helper, "How's the budget on zephyr?")["text"]


def test_questions_are_validated(manager, setup):
    assert manager.post("dashboard/ask", {"question": ""}).status_code == 400
    assert manager.post("dashboard/ask", {"question": "x" * 501}).status_code == 400


def test_follow_ups_never_repeat_the_question(manager, setup):
    reply = ask(manager, "Which projects are at risk?")
    assert "Which projects are at risk?" not in reply["follow_ups"]
