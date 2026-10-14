"""Auth service: login, token refresh, logout, current user, change password."""
from core import auth as tokens
from core import security
from core import db
from core.errors import bad_request, unauthorized
from core.http import Router
from core.validation import F, validate

router = Router("auth")


@router.route("POST", "/login", auth=False)
def login(req):
    data = validate(req.json(), {
        "username": F("str", required=True, max_len=50),
        "password": F("str", required=True, max_len=200, strip=False),
    })
    with db.transaction() as cur:
        cur.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(%s)", (data["username"],))
        user = cur.fetchone()
        valid = tokens.verify_password(data["password"], user["password_hash"] if user else None)
        failure = None if valid and user["is_active"] else ("INVALID_CREDENTIALS" if not valid else "ACCOUNT_INACTIVE")
        if user:
            security.record_sign_in(cur, user["id"], failure is None, req.headers)
        if failure is None:
            refresh_token = tokens.issue_refresh_token(cur, user["id"])
    # Raised after the transaction commits, so failed attempts stay in the sign-in history
    if failure == "INVALID_CREDENTIALS":
        raise unauthorized("Incorrect username or password.", "INVALID_CREDENTIALS")
    if failure:
        raise unauthorized(tokens.REFRESH_ERRORS["ACCOUNT_INACTIVE"], "ACCOUNT_INACTIVE")
    return 200, tokens.token_payload(user, refresh_token)


@router.route("POST", "/refresh", auth=False)
def refresh(req):
    data = validate(req.json(), {"refresh_token": F("str", required=True, max_len=200, strip=False)})
    with db.transaction() as cur:
        user, result = tokens.rotate_refresh_token(cur, data["refresh_token"])
    # Raised after the transaction commits, so a reuse lockout is saved
    if user is None:
        raise unauthorized(tokens.REFRESH_ERRORS[result], result)
    return 200, tokens.token_payload(user, result)


@router.route("POST", "/logout", auth=False)
def logout(req):
    data = validate(req.json(), {"refresh_token": F("str", required=True, max_len=200, strip=False)})
    with db.transaction() as cur:
        tokens.revoke_refresh_token(cur, data["refresh_token"])
    return 204, None


@router.route("GET", "/me")
def me(req):
    return 200, tokens.public_user(req.user)


@router.route("POST", "/password")
def change_password(req):
    data = validate(req.json(), {
        "current_password": F("str", required=True, max_len=200, strip=False),
        "new_password": F("password", required=True, max_len=200),
    })
    with db.transaction() as cur:
        cur.execute("SELECT password_hash FROM users WHERE id = %s", (req.user["id"],))
        if not tokens.verify_password(data["current_password"], cur.fetchone()["password_hash"]):
            raise bad_request("Current password is incorrect.", {"current_password": "Incorrect password."})
        cur.execute("UPDATE users SET password_hash = %s, updated_at = NOW() WHERE id = %s",
                    (tokens.hash_password(data["new_password"]), req.user["id"]))
        cur.execute("UPDATE refresh_tokens SET revoked_at = NOW() WHERE user_id = %s AND revoked_at IS NULL",
                    (req.user["id"],))
    return 204, None


security.register(router)  # adds GET /auth/sign-ins


def handler(event, context=None):
    return router.handle(event, context)
