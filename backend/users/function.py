"""Users service: admins manage accounts, managers edit their direct reports,
and everyone can edit their own name and email."""
import re

from core import activity, db
from core.auth import hash_password
from core.errors import bad_request, conflict, forbidden, not_found
from core.http import Router
from core.validation import F, validate

router = Router("users")

ROLES = ["admin", "manager", "employee"]
FIELDS = "id, username, name, email, job_title, role, manager_id, is_active, created_at, updated_at"
U_FIELDS = ", ".join("u." + f for f in FIELDS.split(", "))
USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{3,50}$")

CREATE_SCHEMA = {
    "username": F("str", required=True, min_len=3, max_len=50),
    "password": F("password", required=True, max_len=200),
    "name": F("str", required=True, max_len=100),
    "email": F("email", required=True, max_len=255),
    "job_title": F("str", max_len=100, nullable=True),
    "role": F("enum", required=True, choices=ROLES),
    "manager_id": F("int", nullable=True, min=1),
}

UPDATE_SCHEMA = {
    "name": F("str", required=True, max_len=100),
    "email": F("email", required=True, max_len=255),
    "job_title": F("str", max_len=100, nullable=True),
    "role": F("enum", required=True, choices=ROLES),
    "manager_id": F("int", nullable=True, min=1),
    "is_active": F("bool"),
    "password": F("password", max_len=200),
}
MANAGER_EDITABLE = {"name", "email", "job_title"}
SELF_EDITABLE = {"name", "email"}


def _visible_where(me):
    """SQL condition limiting which users the caller is allowed to see."""
    if me["role"] == "admin":
        return "TRUE", []
    if me["role"] == "manager":
        return "((u.is_active AND u.role <> 'admin') OR u.id = %s)", [me["id"]]
    return (
        "(u.id = %s OR u.id = %s"
        " OR u.id IN (SELECT pm2.user_id FROM project_members pm1"
        "             JOIN project_members pm2 ON pm2.project_id = pm1.project_id WHERE pm1.user_id = %s)"
        " OR u.id IN (SELECT p.manager_id FROM projects p"
        "             JOIN project_members pm ON pm.project_id = p.id WHERE pm.user_id = %s))",
        [me["id"], me["manager_id"] or -1, me["id"], me["id"]],
    )


def _load_visible(cur, me, user_id):
    where, params = _visible_where(me)
    cur.execute(
        f"SELECT {U_FIELDS}, m.name AS manager_name FROM users u "
        f"LEFT JOIN users m ON m.id = u.manager_id WHERE u.id = %s AND {where}",
        [user_id, *params])
    user = cur.fetchone()
    if user is None:
        raise not_found("User")
    return user


def _require_manager(cur, manager_id):
    cur.execute("SELECT role, is_active FROM users WHERE id = %s", (manager_id,))
    row = cur.fetchone()
    if row is None or row["role"] != "manager" or not row["is_active"]:
        raise bad_request("Employees must report to an active manager.",
                          {"manager_id": "Choose an active manager."})


def _ensure_no_manager_duties(cur, user_id):
    cur.execute("SELECT COUNT(*) AS n FROM projects WHERE manager_id = %s AND archived_at IS NULL", (user_id,))
    projects = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) AS n FROM users WHERE manager_id = %s AND is_active", (user_id,))
    reports = cur.fetchone()["n"]
    if projects or reports:
        raise conflict(
            f"This manager still has {projects} active project(s) and {reports} direct report(s). "
            "Reassign them first.",
            {"active_projects": projects, "direct_reports": reports})


def _query_int(query, name):
    try:
        return int(query[name])
    except (TypeError, ValueError):
        raise bad_request("Invalid filter.", {name: "Must be a whole number."})


@router.route("GET", "")
def list_users(req):
    """Filters: ?role=employee  ?manager_id=2  ?search=lee  ?status=active|inactive|all"""
    where, params = _visible_where(req.user)
    clauses = [where]
    q = req.query
    if q.get("role"):
        if q["role"] not in ROLES:
            raise bad_request("Invalid filter.", {"role": f"Must be one of: {', '.join(ROLES)}."})
        clauses.append("u.role = %s")
        params.append(q["role"])
    if q.get("manager_id"):
        clauses.append("u.manager_id = %s")
        params.append(_query_int(q, "manager_id"))
    if q.get("search"):
        clauses.append("(u.name ILIKE %s OR u.username ILIKE %s OR u.email ILIKE %s OR u.job_title ILIKE %s)")
        params.extend([f"%{q['search'].strip()}%"] * 4)
    status = q.get("status", "active")
    if status not in ("active", "inactive", "all"):
        raise bad_request("Invalid filter.", {"status": "Must be one of: active, inactive, all."})
    if status != "all":
        clauses.append("u.is_active = %s")
        params.append(status == "active")
    with db.transaction() as cur:
        cur.execute(
            f"SELECT {U_FIELDS}, m.name AS manager_name,"
            " (SELECT COUNT(*) FROM project_members pm JOIN projects p ON p.id = pm.project_id"
            "   WHERE pm.user_id = u.id AND p.archived_at IS NULL) AS active_projects"
            f" FROM users u LEFT JOIN users m ON m.id = u.manager_id"
            f" WHERE {' AND '.join(clauses)} ORDER BY u.name",
            params)
        return 200, cur.fetchall()


@router.route("GET", "/{id}")
def get_user(req):
    with db.transaction() as cur:
        return 200, _load_visible(cur, req.user, req.params["id"])


@router.route("POST", "", roles=["admin"])
def create_user(req):
    data = validate(req.json(), CREATE_SCHEMA)
    if not USERNAME_RE.match(data["username"]):
        raise bad_request("Some fields are invalid.",
                          {"username": "Use 3 to 50 letters, numbers, dots, dashes, or underscores."})
    with db.transaction() as cur:
        if data["role"] == "employee":
            if not data.get("manager_id"):
                raise bad_request("Employees must report to a manager.",
                                  {"manager_id": "Choose the employee's manager."})
            _require_manager(cur, data["manager_id"])
        else:
            data["manager_id"] = None
        cur.execute(
            "INSERT INTO users (username, password_hash, name, email, job_title, role, manager_id) "
            f"VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING {FIELDS}",
            (data["username"], hash_password(data["password"]), data["name"], data["email"],
             data.get("job_title"), data["role"], data["manager_id"]))
        user = cur.fetchone()
        activity.log(cur, req.user["id"], "user.created", "user",
                     f"{req.user['name']} added {user['role']} {user['name']}", entity_id=user["id"],
                     details={"username": user["username"], "role": user["role"],
                              "manager_id": user["manager_id"]})
    return 201, user


def _editable_fields(me, target):
    if me["role"] == "admin":
        return set(UPDATE_SCHEMA)
    if target["id"] == me["id"]:
        return set(SELF_EDITABLE)
    if me["role"] == "manager" and target["manager_id"] == me["id"]:
        return set(MANAGER_EDITABLE)
    return set()


@router.route("PUT", "/{id}")
def update_user(req):
    me, user_id = req.user, req.params["id"]
    body = req.json()
    unknown = set(body) - set(UPDATE_SCHEMA)
    if unknown:
        raise bad_request("Some fields are invalid.", {k: "Unknown field." for k in unknown})
    with db.transaction() as cur:
        target = _load_visible(cur, me, user_id)
        allowed = _editable_fields(me, target)
        if not allowed:
            raise forbidden("You can only edit yourself or your direct reports.")
        blocked = set(body) - allowed
        if blocked:
            raise forbidden(f"You can only update: {', '.join(sorted(allowed))}.")
        data = validate(body, {k: UPDATE_SCHEMA[k] for k in allowed}, partial=True)
        if not data:
            raise bad_request("Nothing to update.")

        revoke = False
        if me["role"] == "admin":
            new_role = data.get("role", target["role"])
            deactivating = data.get("is_active") is False and target["is_active"]
            if user_id == me["id"] and (new_role != "admin" or deactivating):
                raise bad_request("You can't remove your own admin access.")
            if target["role"] == "manager" and (new_role != "manager" or deactivating):
                _ensure_no_manager_duties(cur, user_id)
            if new_role == "employee":
                manager_id = data.get("manager_id", target["manager_id"])
                if not manager_id:
                    raise bad_request("Employees must report to a manager.",
                                      {"manager_id": "Choose the employee's manager."})
                if manager_id == user_id:
                    raise bad_request("Some fields are invalid.", {"manager_id": "A user can't manage themselves."})
                _require_manager(cur, manager_id)
                data["manager_id"] = manager_id
            elif "role" in data or "manager_id" in data:
                data["manager_id"] = None
            revoke = deactivating or "password" in data
            if "password" in data:
                data["password_hash"] = hash_password(data.pop("password"))

        # Column names come only from the whitelisted schema above, never from user input
        assignments = ", ".join(f"{column} = %s" for column in data)
        cur.execute(f"UPDATE users SET {assignments}, updated_at = NOW() WHERE id = %s RETURNING {FIELDS}",
                    [*data.values(), user_id])
        updated = cur.fetchone()
        if revoke:
            cur.execute("UPDATE refresh_tokens SET revoked_at = NOW() WHERE user_id = %s AND revoked_at IS NULL",
                        (user_id,))
        changes = activity.diff(target, updated, [k for k in data if k != "password_hash"])
        if "password_hash" in data:
            changes["password"] = {"from": "********", "to": "reset"}
        changed = ", ".join(sorted(changes)) or "no changes"
        who = (f"{updated['name']} updated their own profile" if user_id == me["id"]
               else f"{me['name']} updated {updated['name']}")
        activity.log(cur, me["id"], "user.updated", "user",
                     f"{who} ({changed})", entity_id=user_id,
                     details={"changes": changes})
    return 200, updated


@router.route("DELETE", "/{id}", roles=["admin"])
def deactivate_user(req):
    """Soft delete: the account is deactivated and logged out everywhere, but its history is kept."""
    user_id = req.params["id"]
    if user_id == req.user["id"]:
        raise bad_request("You can't deactivate your own account.")
    with db.transaction() as cur:
        target = _load_visible(cur, req.user, user_id)
        if not target["is_active"]:
            return 204, None
        if target["role"] == "manager":
            _ensure_no_manager_duties(cur, user_id)
        cur.execute("UPDATE users SET is_active = FALSE, updated_at = NOW() WHERE id = %s", (user_id,))
        cur.execute("UPDATE refresh_tokens SET revoked_at = NOW() WHERE user_id = %s AND revoked_at IS NULL",
                    (user_id,))
        activity.log(cur, req.user["id"], "user.deactivated", "user",
                     f"{req.user['name']} deactivated {target['name']}", entity_id=user_id,
                     details={"changes": {"is_active": {"from": True, "to": False}}})
    return 204, None


def handler(event, context=None):
    return router.handle(event, context)
