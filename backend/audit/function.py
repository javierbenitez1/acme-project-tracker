"""Audit service (admin only): a read-only, filterable history of every change in the system.
There are deliberately no create, update, or delete routes, so the trail can't be altered."""
from datetime import date, timedelta

from core import db
from core.errors import bad_request, not_found
from core.http import Router

router = Router("audit")
ADMIN = ["admin"]

SELECT = (
    "SELECT a.id, a.action, a.entity_type, a.entity_id, a.project_id, a.summary, a.details, a.created_at,"
    " a.actor_id, u.name AS actor_name, u.role AS actor_role, p.name AS project_name"
    " FROM activity_log a"
    " LEFT JOIN users u ON u.id = a.actor_id"
    " LEFT JOIN projects p ON p.id = a.project_id"
)


def _int(query, name, default=None, lo=1, hi=None):
    if query.get(name) in (None, ""):
        return default
    try:
        value = int(query[name])
    except ValueError:
        raise bad_request("Invalid filter.", {name: "Must be a whole number."})
    if value < lo or (hi is not None and value > hi):
        limit = f"between {lo} and {hi}" if hi is not None else f"at least {lo}"
        raise bad_request("Invalid filter.", {name: f"Must be {limit}."})
    return value


def _date(query, name):
    if not query.get(name):
        return None
    try:
        return date.fromisoformat(query[name])
    except ValueError:
        raise bad_request("Invalid filter.", {name: "Must be a date in YYYY-MM-DD format."})


@router.route("GET", "", roles=ADMIN)
def list_audit(req):
    """Filters: actor_id, project_id, entity_id, action, entity_type, from, to, search, page, page_size"""
    q = req.query
    clauses, params = [], []
    for name in ("actor_id", "project_id", "entity_id"):
        value = _int(q, name)
        if value is not None:
            clauses.append(f"a.{name} = %s")
            params.append(value)
    for name in ("action", "entity_type"):
        if q.get(name):
            clauses.append(f"a.{name} = %s")
            params.append(q[name].strip())
    start, end = _date(q, "from"), _date(q, "to")
    if start and end and end < start:
        raise bad_request("Invalid filter.", {"to": "Must be on or after the from date."})
    if start:
        clauses.append("a.created_at >= %s")
        params.append(start)
    if end:
        clauses.append("a.created_at < %s")
        params.append(end + timedelta(days=1))
    if q.get("search"):
        clauses.append("a.summary ILIKE %s")
        params.append(f"%{q['search'].strip()}%")
    page = _int(q, "page", 1)
    page_size = _int(q, "page_size", 50, hi=200)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with db.transaction() as cur:
        cur.execute(f"SELECT COUNT(*) AS n FROM activity_log a{where}", params)
        total = cur.fetchone()["n"]
        cur.execute(f"{SELECT}{where} ORDER BY a.created_at DESC, a.id DESC LIMIT %s OFFSET %s",
                    [*params, page_size, (page - 1) * page_size])
        items = cur.fetchall()
        cur.execute("SELECT DISTINCT action FROM activity_log ORDER BY action")
        actions = [row["action"] for row in cur.fetchall()]
    return 200, {"items": items, "page": page, "page_size": page_size, "total": total,
                 "available_actions": actions}


@router.route("GET", "/{id}", roles=ADMIN)
def get_audit_entry(req):
    with db.transaction() as cur:
        cur.execute(f"{SELECT} WHERE a.id = %s", (req.params["id"],))
        entry = cur.fetchone()
    if entry is None:
        raise not_found("Audit entry")
    return 200, entry


def handler(event, context=None):
    return router.handle(event, context)
