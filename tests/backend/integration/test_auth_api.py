"""Integration tests for login, sessions, and token refresh."""
import requests

from conftest import ADMIN, API, Client, login


def test_login_returns_tokens_and_safe_user_fields():
    body = login(*ADMIN)
    assert body["token_type"] == "Bearer" and body["expires_in"] == 900
    assert body["user"]["role"] == "admin"
    assert "password_hash" not in body["user"]


def test_wrong_password_and_unknown_user_get_the_same_error():
    wrong = requests.post(f"{API}/auth/login", json={"username": "admin", "password": "Wrong1234"}, timeout=60)
    unknown = requests.post(f"{API}/auth/login", json={"username": "nobody_here", "password": "Wrong1234"}, timeout=60)
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_login_validation_lists_missing_fields():
    response = requests.post(f"{API}/auth/login", json={}, timeout=60)
    assert response.status_code == 400
    assert set(response.json()["error"]["details"]) == {"username", "password"}


def test_protected_route_requires_a_token():
    response = Client().get("auth/me")
    assert response.status_code == 401 and response.json()["error"]["code"] == "TOKEN_MISSING"


def test_me_returns_the_logged_in_user(admin):
    response = admin.get("auth/me")
    assert response.status_code == 200 and response.json()["username"] == "admin"


def test_refresh_rotates_tokens_and_detects_reuse(employee_account):
    first = login(employee_account["username"], employee_account["password"])
    rotated = requests.post(f"{API}/auth/refresh", json={"refresh_token": first["refresh_token"]}, timeout=60)
    assert rotated.status_code == 200
    assert rotated.json()["refresh_token"] != first["refresh_token"]

    reused = requests.post(f"{API}/auth/refresh", json={"refresh_token": first["refresh_token"]}, timeout=60)
    assert reused.status_code == 401 and reused.json()["error"]["code"] == "TOKEN_REUSED"

    # Reuse ends every session, so the newer token is dead too
    newer = requests.post(f"{API}/auth/refresh", json={"refresh_token": rotated.json()["refresh_token"]}, timeout=60)
    assert newer.status_code == 401


def test_logout_revokes_the_refresh_token(employee_account):
    session = login(employee_account["username"], employee_account["password"])
    out = requests.post(f"{API}/auth/logout", json={"refresh_token": session["refresh_token"]}, timeout=60)
    assert out.status_code == 204
    again = requests.post(f"{API}/auth/refresh", json={"refresh_token": session["refresh_token"]}, timeout=60)
    assert again.status_code == 401
