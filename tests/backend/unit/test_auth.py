"""Unit tests for password hashing and access token checks."""
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from core import auth
from core.errors import ApiError

SECRET = "unit-test-secret"
USER = {"id": 7, "role": "manager", "name": "Maria"}


@pytest.fixture(autouse=True)
def fixed_secret(monkeypatch):
    monkeypatch.setattr(auth, "_secret", lambda: SECRET)


class FakeRequest:
    def __init__(self, header=None):
        self.headers = {"authorization": header} if header else {}


def auth_error_code(header):
    with pytest.raises(ApiError) as exc:
        auth.authenticate(FakeRequest(header))
    assert exc.value.status == 401
    return exc.value.code


def test_password_hash_round_trip():
    hashed = auth.hash_password("Secret123")
    assert hashed.startswith("pbkdf2_sha256$")
    assert auth.verify_password("Secret123", hashed)
    assert not auth.verify_password("secret123", hashed)


def test_same_password_gets_a_different_salt():
    assert auth.hash_password("Secret123") != auth.hash_password("Secret123")


def test_verify_handles_missing_and_malformed_hashes():
    assert not auth.verify_password("anything", None)
    assert not auth.verify_password("anything", "not-a-real-hash")


def test_access_token_carries_identity_and_15_minute_expiry():
    payload = jwt.decode(auth.issue_access_token(USER), SECRET, algorithms=["HS256"])
    assert payload["sub"] == "7"
    assert payload["role"] == "manager"
    assert payload["type"] == "access"
    assert payload["exp"] - payload["iat"] == 900


def test_missing_header_is_rejected():
    assert auth_error_code(None) == "TOKEN_MISSING"


def test_non_bearer_header_is_rejected():
    assert auth_error_code("Basic abc123") == "TOKEN_MISSING"


def test_garbage_token_is_rejected():
    assert auth_error_code("Bearer not.a.jwt") == "TOKEN_INVALID"


def test_token_signed_with_another_secret_is_rejected():
    future = datetime.now(timezone.utc) + timedelta(minutes=5)
    forged = jwt.encode({"sub": "7", "type": "access", "exp": future}, "attacker-secret", algorithm="HS256")
    assert auth_error_code(f"Bearer {forged}") == "TOKEN_INVALID"


def test_expired_token_is_rejected(monkeypatch):
    monkeypatch.setattr(auth, "ACCESS_TOKEN_TTL", timedelta(seconds=-1))
    assert auth_error_code(f"Bearer {auth.issue_access_token(USER)}") == "TOKEN_EXPIRED"


def test_non_access_token_type_is_rejected():
    future = datetime.now(timezone.utc) + timedelta(minutes=5)
    token = jwt.encode({"sub": "7", "type": "refresh", "exp": future}, SECRET, algorithm="HS256")
    assert auth_error_code(f"Bearer {token}") == "TOKEN_INVALID"
