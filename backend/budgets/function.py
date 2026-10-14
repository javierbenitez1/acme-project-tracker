"""Budgets service: spending entries against a project's planned budget, plus a summary showing
consumed versus planned, spending by category and month, and an end-of-project forecast."""
from datetime import date

from core import activity, db
from core.errors import bad_request, not_found
from core.http import Router
from core.metrics import budget_forecast
from core.projects import load_project, require_active, require_manager, visible_where
from core.validation import F, query_choice, query_date, query_int, validate

router = Router("budgets")
MANAGERS = ["admin", "manager"]  # employees can't see financial data
CATEGORIES = ["labor", "contractors", "software", "hardware", "travel", "training", "other"]

ENTRY_SELECT = """
SELECT b.id, b.project_id, p.name AS project_name, b.amount, b.category, b.description, b.entry_date,
       b.created_by, u.name AS created_by_name, b.created_at
FROM budget_entries b
JOIN projects p ON p.id = b.project_id
LEFT JOIN users u ON u.id = b.created_by
"""

FIELDS = {
    "amount": F("number", required=True, min=0.01, max=999_999_999),
    "category": F("enum", required=True, choices=CATEGORIES),
    "description": F("str", nullable=True, max_len=500),
    "entry_date": F("date"),
}
CREATE_SCHEMA = {"project_id": F("int", required=True, min=1), **FIELDS}


def _load(cur, me, entry_id):
    cur.execute(f"{ENTRY_SELECT} WHERE b.id = %s", (entry_id,))
    entry = cur.fetchone()
    if entry is None:
        raise not_found("Budget entry")
    project = load_project(cur, me, entry["project_id"])  # 404 if the caller can't see the project
    return entry, project


def _check_date(project, entry_date):
    if entry_date > date.today():
        raise bad_request("Some fields are invalid.", {"entry_date": "Spending can't be recorded in the future."})
    if entry_date < project["start_date"]:
        raise bad_request("Some fields are invalid.",
                          {"entry_date": f"Must be on or after the project start ({project['start_date']})."})


def _over_budget_warning(cur, project):
    cur.execute("SELECT COALESCE(SUM(amount), 0) AS spent FROM budget_entries WHERE project_id = %s",
                (project["id"],))
    spent = cur.fetchone()["spent"]
    planned = project["budget_planned"]
    if planned > 0 and spent > planned:
        return f"{project['name']} is now over budget by ${spent - planned:,.2f}."
    return None


def _log(cur, me, action, entry, summary, details=None):
    activity.log(cur, me["id"], action, "budget_entry", summary, entity_id=entry["id"],
                 project_id=entry["project_id"], details=details)


@router.route("GET", "", roles=MANAGERS)
def list_entries(req):
    """Filters: project_id, category, from, to"""
    q = req.query
    where, params = visible_where(req.user)
    clauses = [where]
    project_id = query_int(q, "project_id")
    if project_id:
        clauses.append("b.project_id = %s")
        params.append(project_id)
    category = query_choice(q, "category", CATEGORIES)
    if category:
        clauses.append("b.category = %s")
        params.append(category)
    start, end = query_date(q, "from"), query_date(q, "to")
    if start and end and end < start:
        raise bad_request("Invalid filter.", {"to": "Must be on or after the from date."})
    if start:
        clauses.append("b.entry_date >= %s")
        params.append(start)
    if end:
        clauses.append("b.entry_date <= %s")
        params.append(end)
    with db.transaction() as cur:
        cur.execute(f"{ENTRY_SELECT} WHERE {' AND '.join(clauses)} ORDER BY b.entry_date DESC, b.id DESC", params)
        return 200, cur.fetchall()


@router.route("GET", "/summary", roles=MANAGERS)
def budget_summary(req):
    """Consumed versus planned for one project: totals, by category, by month, and a forecast."""
    project_id = query_int(req.query, "project_id")
    if not project_id:
        raise bad_request("Invalid filter.", {"project_id": "Required."})
    with db.transaction() as cur:
        project = load_project(cur, req.user, project_id)
        cur.execute("SELECT category, SUM(amount) AS amount, COUNT(*) AS entries FROM budget_entries"
                    " WHERE project_id = %s GROUP BY category ORDER BY SUM(amount) DESC", (project_id,))
        by_category = cur.fetchall()
        cur.execute("SELECT to_char(date_trunc('month', entry_date), 'YYYY-MM') AS month, SUM(amount) AS amount"
                    " FROM budget_entries WHERE project_id = %s GROUP BY 1 ORDER BY 1", (project_id,))
        monthly = cur.fetchall()
    planned, spent = float(project["budget_planned"]), float(project["budget_spent"])
    running = 0.0
    for month in monthly:
        running += float(month["amount"])
        month["cumulative"] = round(running, 2)
    for category in by_category:
        category["pct_of_spent"] = round(100 * float(category["amount"]) / spent) if spent else 0
    return 200, {
        "project_id": project["id"], "project_name": project["name"],
        "planned": planned, "spent": spent, "remaining": round(planned - spent, 2),
        "used_pct": project["budget_used_pct"], "progress": project["progress"],
        "by_category": by_category, "monthly": monthly,
        "forecast": budget_forecast(planned, spent, project["start_date"], project["end_date"]),
    }


@router.route("GET", "/{id}", roles=MANAGERS)
def get_entry(req):
    with db.transaction() as cur:
        entry, _ = _load(cur, req.user, req.params["id"])
    return 200, entry


@router.route("POST", "", roles=MANAGERS)
def create_entry(req):
    me = req.user
    data = validate(req.json(), CREATE_SCHEMA)
    entry_date = data.get("entry_date") or date.today()
    with db.transaction() as cur:
        project = load_project(cur, me, data["project_id"])
        require_manager(me, project, "record spending")
        require_active(project)
        _check_date(project, entry_date)
        cur.execute("INSERT INTO budget_entries (project_id, amount, category, description, entry_date, created_by)"
                    " VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                    (project["id"], data["amount"], data["category"], data.get("description"), entry_date, me["id"]))
        entry, _ = _load(cur, me, cur.fetchone()["id"])
        _log(cur, me, "budget.entry_added", entry,
             f"{me['name']} recorded ${entry['amount']:,.2f} of {entry['category']} spending on {project['name']}",
             {"amount": entry["amount"], "category": entry["category"], "entry_date": entry["entry_date"]})
        entry["warning"] = _over_budget_warning(cur, project)
    return 201, entry


@router.route("PUT", "/{id}", roles=MANAGERS)
def update_entry(req):
    me = req.user
    data = validate(req.json(), FIELDS, partial=True)
    if not data:
        raise bad_request("Nothing to update.")
    with db.transaction() as cur:
        entry, project = _load(cur, me, req.params["id"])
        require_manager(me, project, "change its spending")
        require_active(project)
        if data.get("entry_date"):
            _check_date(project, data["entry_date"])
        # Column names come only from the whitelisted schema, never from user input
        assignments = ", ".join(f"{column} = %s" for column in data)
        cur.execute(f"UPDATE budget_entries SET {assignments} WHERE id = %s", [*data.values(), entry["id"]])
        updated, _ = _load(cur, me, entry["id"])
        changes = activity.diff(entry, updated, list(data))
        _log(cur, me, "budget.entry_updated", updated,
             f"{me['name']} corrected a spending entry on {project['name']} ({', '.join(sorted(changes)) or 'no changes'})",
             {"changes": changes})
        updated["warning"] = _over_budget_warning(cur, project)
    return 200, updated


@router.route("DELETE", "/{id}", roles=MANAGERS)
def delete_entry(req):
    me = req.user
    with db.transaction() as cur:
        entry, project = _load(cur, me, req.params["id"])
        require_manager(me, project, "change its spending")
        require_active(project)
        cur.execute("DELETE FROM budget_entries WHERE id = %s", (entry["id"],))
        # The full entry is kept in the audit log, so nothing is truly lost
        _log(cur, me, "budget.entry_removed", entry,
             f"{me['name']} removed a ${entry['amount']:,.2f} {entry['category']} entry from {project['name']}",
             {"amount": entry["amount"], "category": entry["category"], "entry_date": entry["entry_date"],
              "description": entry["description"]})
    return 204, None


def handler(event, context=None):
    return router.handle(event, context)s