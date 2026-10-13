"""Password hashing, short-lived JWT access tokens, and rotating refresh tokens."""
import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from . import db
from .errors import unauthorized

ACCESS_TOKEN_TTL = timedelta(minutes=15)
REFRESH_TOKEN_TTL = timedelta(days=7)
PBKDF2_ITERATIONS = 100_000
# Used when a username does not exist so the response time does not reveal that
_DUMMY_HASH = "pbkdf2_sha256$100000$AAAAAAAAAAAAAAAAAAAAAA==$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
PUBLIC_USER_FIELDS = "id, username, name, email, job_title, role, manager_id, is_active"

REFRESH_ERRORS = {
    "TOKEN_INVALID": "Your session is invalid. Please log in again.",
    "TOKEN_REUSED": "This session was already used. For your security, please log in again.",
    "TOKEN_EXPIRED": "Your session has expired. Please log in again.",
    "ACCOUNT_INACTIVE": "This account has been deactivated. Contact your administrator.",
}

_SECRET = None


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITERATIONS, base64.b64encode(salt).decode(), base64.b64encode(digest).decode())


def verify_password(password, stored):
    try:
        _, iterations, salt_b64, hash_b64 = (stored or _DUMMY_HASH).split("$")
        expected = base64.b64decode(hash_b64)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt_b64), int(iterations))
    except (ValueError, TypeError):
        return False
    return stored is not None and hmac.compare_digest(digest, expected)


def _secret():
    """Signing key generated once and stored in the database, so every service shares it."""
    global _SECRET
    if _SECRET is None:
        with db.transaction() as cur:
            cur.execute("INSERT INTO app_config (key, value) VALUES ('jwt_secret', %s) "
                        "ON CONFLICT (key) DO NOTHING", (secrets.token_hex(32),))
            cur.execute("SELECT value FROM app_config WHERE key = 'jwt_secret'")
            _SECRET = cur.fetchone()["value"]
    return _SECRET


def public_user(user):
    return {k: user[k] for k in PUBLIC_USER_FIELDS.split(", ") if k in user}


def issue_access_token(user):
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user["id"]), "role": user["role"], "name": user["name"],
               "type": "access", "iat": now, "exp": now + ACCESS_TOKEN_TTL}
    return jwt.encode(payload, _secret(), algorithm="HS256")


def _sha256(token):
    return hashlib.sha256(token.encode()).hexdigest()


def issue_refresh_token(cur, user_id):
    token = secrets.token_urlsafe(48)
    cur.execute("INSERT INTO refresh_tokens (user_id, token_hash, expires_at) VALUES (%s, %s, %s)",
                (user_id, _sha256(token), datetime.now(timezone.utc) + REFRESH_TOKEN_TTL))
    return token


def token_payload(user, refresh_token):
    return {
        "access_token": issue_access_token(user),
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "expires_in": int(ACCESS_TOKEN_TTL.total_seconds()),
        "user": public_user(user),
    }


def rotate_refresh_token(cur, token):
    """Returns (user, new_token) on success, or (None, error_code)."""
    cur.execute("SELECT id, user_id, expires_at, revoked_at FROM refresh_tokens WHERE token_hash = %s",
                (_sha256(token),))
    row = cur.fetchone()
    if row is None:
        return None, "TOKEN_INVALID"
    if row["revoked_at"] is not None:
        # An old token was reused, which can mean it was stolen. End every session for this user.
        cur.execute("UPDATE refresh_tokens SET revoked_at = NOW() WHERE user_id = %s AND revoked_at IS NULL",
                    (row["user_id"],))
        return None, "TOKEN_REUSED"
    if row["expires_at"] <= datetime.now(timezone.utc):
        return None, "TOKEN_EXPIRED"
    cur.execute(f"SELECT {PUBLIC_USER_FIELDS} FROM users WHERE id = %s", (row["user_id"],))
    user = cur.fetchone()
    if user is None or not user["is_active"]:
        return None, "ACCOUNT_INACTIVE"
    cur.execute("UPDATE refresh_tokens SET revoked_at = NOW() WHERE id = %s", (row["id"],))
    return user, issue_refresh_token(cur, user["id"])


def revoke_refresh_token(cur, token):
    cur.execute("UPDATE refresh_tokens SET revoked_at = NOW() WHERE token_hash = %s AND revoked_at IS NULL",
                (_sha256(token),))


def authenticate(req):
    """Checks the Bearer token and loads the user fresh from the database,
    so role changes and deactivations take effect immediately."""
    header = req.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise unauthorized("You need to log in to do that.", "TOKEN_MISSING")
    try:
        payload = jwt.decode(header[7:].strip(), _secret(), algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise unauthorized("Your session has expired. Please refresh your token.", "TOKEN_EXPIRED")
    except jwt.InvalidTokenError:
        raise unauthorized("Invalid authentication token.", "TOKEN_INVALID")
    if payload.get("type") != "access":
        raise unauthorized("Invalid authentication token.", "TOKEN_INVALID")
    with db.transaction() as cur:
        cur.execute(f"SELECT {PUBLIC_USER_FIELDS} FROM users WHERE id = %s", (int(payload["sub"]),))
        user = cur.fetchone()
    if user is None or not user["is_active"]:
        raise unauthorized(REFRESH_ERRORS["ACCOUNT_INACTIVE"], "ACCOUNT_INACTIVE")
    return user
