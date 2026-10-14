"""Integration tests for sign-in history: successes and failures are recorded, and people see the
sign-in before this one plus any failed attempts in between."""
import requests

from conftest import API, Client, login


def attempt(username, password):
    return requests.post(f"{API}/auth/login", json={"username": username, "password": password}, timeout=60)


def test_sign_in_history_reports_failed_attempts_since_last_visit(admin, manager_account, run_id):
    creds = {"username": f"it_sec_{run_id}", "password": "Secure1234"}
    created = admin.post("users", {**creds, "name": f"Sam Secure{run_id}", "role": "employee",
                                   "email": f"it_sec_{run_id}@acme.test", "manager_id": manager_account["id"]})
    assert created.status_code == 201, created.text
    login(creds["username"], creds["password"])
    assert attempt(creds["username"], "wrong-password-1").status_code == 401
    assert attempt(creds["username"], "wrong-password-2").status_code == 401
    me = Client(login(creds["username"], creds["password"])["access_token"])
    body = me.get("auth/sign-ins").json()
    assert body["current"]["succeeded"] and body["previous"]["succeeded"]
    assert body["failed_since_previous"] == 2
    assert len(body["recent"]) == 4 and {"device", "ip_masked", "created_at"} <= set(body["recent"][0])


def test_sign_in_history_needs_a_session():
    assert requests.get(f"{API}/auth/sign-ins", timeout=60).status_code == 401


def test_five_failed_attempts_lock_the_account(admin, manager_account, run_id):
    creds = {"username": f"it_lock_{run_id}", "password": "Locked1234"}
    created = admin.post("users", {**creds, "name": f"Lee Lockwood{run_id}", "role": "employee",
                                   "email": f"it_lock_{run_id}@acme.test", "manager_id": manager_account["id"]})
    assert created.status_code == 201, created.text
    for _ in range(4):
        assert attempt(creds["username"], "not-the-password-1").status_code == 401
    fifth = attempt(creds["username"], "not-the-password-1")
    assert fifth.status_code == 423 and fifth.json()["error"]["code"] == "ACCOUNT_LOCKED"
    assert attempt(creds["username"], creds["password"]).status_code == 423  # even the right password


def test_the_health_check_is_public():
    response = requests.get(f"{API}/auth/health", timeout=60)
    assert response.status_code == 200 and response.json()["status"] == "ok"
