"""Integration tests for user management and role-based permissions."""
import requests

from conftest import API


def test_admin_can_search_and_filter(admin, employee_account):
    response = admin.get(f"users?role=employee&search={employee_account['username']}")
    assert response.status_code == 200
    assert [u["id"] for u in response.json()] == [employee_account["id"]]


def test_create_reports_every_invalid_field(admin):
    response = admin.post("users", {"username": "x", "role": "employee", "email": "bad"})
    assert response.status_code == 400
    assert {"username", "password", "name", "email"} <= set(response.json()["error"]["details"])


def test_duplicate_username_returns_409(admin, manager_account):
    response = admin.post("users", {"username": manager_account["username"], "password": "Manager123",
                                    "name": "Dup", "email": "dup_unique_1@acme.test", "role": "manager"})
    assert response.status_code == 409
    assert "username" in response.json()["error"]["details"]


def test_employee_must_report_to_an_active_manager(admin, run_id):
    response = admin.post("users", {"username": f"it_bad_{run_id}", "password": "Employee123", "name": "Bad",
                                    "email": f"it_bad_{run_id}@acme.test", "role": "employee", "manager_id": 1})
    assert response.status_code == 400
    assert "manager_id" in response.json()["error"]["details"]


def test_manager_can_edit_a_direct_report(manager, employee_account):
    response = manager.put(f"users/{employee_account['id']}", {"job_title": "Senior QA Engineer"})
    assert response.status_code == 200 and response.json()["job_title"] == "Senior QA Engineer"


def test_manager_cannot_escalate_privileges(manager, employee_account):
    assert manager.put(f"users/{employee_account['id']}", {"role": "admin"}).status_code == 403


def test_manager_cannot_create_users(manager):
    assert manager.post("users", {"username": "nope"}).status_code == 403


def test_employee_can_only_edit_own_name_and_email(employee, employee_account):
    assert employee.put(f"users/{employee_account['id']}", {"name": "Renamed Employee"}).status_code == 200
    assert employee.put(f"users/{employee_account['id']}", {"job_title": "CTO"}).status_code == 403


def test_employee_cannot_see_unrelated_users(employee):
    assert employee.get("users/1").status_code == 404


def test_unknown_fields_are_rejected(admin, employee_account):
    assert admin.put(f"users/{employee_account['id']}", {"salary": 1}).status_code == 400


def test_missing_and_malformed_ids_return_404(admin):
    assert admin.get("users/999999").status_code == 404
    assert admin.get("users/abc").status_code == 404


def test_deactivate_blocks_login_and_reactivate_restores_it(admin, manager_account, run_id):
    created = admin.post("users", {"username": f"it_tmp_{run_id}", "password": "Employee123", "name": "Temp",
                                   "email": f"it_tmp_{run_id}@acme.test", "role": "employee",
                                   "manager_id": manager_account["id"]}).json()
    assert admin.delete(f"users/{created['id']}").status_code == 204
    assert admin.get(f"users/{created['id']}").json()["is_active"] is False

    blocked = requests.post(f"{API}/auth/login", json={"username": created["username"], "password": "Employee123"},
                            timeout=60)
    assert blocked.status_code == 401 and blocked.json()["error"]["code"] == "ACCOUNT_INACTIVE"

    assert admin.put(f"users/{created['id']}", {"is_active": True}).status_code == 200


def test_manager_with_direct_reports_cannot_be_deactivated(admin, manager_account, employee_account):
    response = admin.delete(f"users/{manager_account['id']}")
    assert response.status_code == 409 and response.json()["error"]["details"]["direct_reports"] >= 1


def test_admin_cannot_deactivate_themselves(admin):
    me = admin.get("auth/me").json()
    assert admin.delete(f"users/{me['id']}").status_code == 400
