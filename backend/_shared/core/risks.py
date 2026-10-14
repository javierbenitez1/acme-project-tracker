"""Risk register: things that might go wrong on a project, scored by likelihood and impact, each with
an owner, a mitigation plan and a review date. Suggested risks come from live signals (the critical
path, the delivery forecast and the budget forecast), so managers see risks before they turn into
problems. Routes are registered on the projects service: /projects/risks and /projects/{id}/risks."""
from datetime import date

from . import activity, db, metrics, scheduling
from .errors import bad_request, conflict, not_found
from .projects import can_manage, load_project, require_active, require_manager, visible_where
from .validation import F, validate

MANAGERS = ["admin", "manager"]
CATEGORIES = ["schedule", "budget", "resources", "vendor", "technical", "scope", "other"]
STATUSES = ["open", "mitigating", "closed", "occurred"]
ACTIVE = ("open", "mitigating")
BUFFER_WARNING_DAYS = 5

FIELDS = {
    "title": F("str", required=True, max_len=200),
    "description": F("str", nullable=True, max_len=2000),
    "category": F("enum", required=True, choices=CATEGORIES),
    "likelihood": F("int", required=True, min=1, max=5),
    "impact": F("int", required=True, min=1, max=5),
    "owner_id": F("int", nullable=True, min=1),
    "mitigation": F("str", nullable=True, max_len=2000),
    "review_date": F("date", nullable=True),
}
CREATE_SCHEMA = {**FIELDS, "source_key": F("str", max_len=120)}
UPDATE_SCHEMA = {**FIELDS, "status": F("enum", required=True, choices=STATUSES)}

RISK_SELECT = """
SELECT r.id, r.project_id, p.name AS project_name, r.title, r.description, r.category, r.likelihood,
       r.impact, r.status, r.owner_id, o.name AS owner_name, r.mitigation, r.review_date, r.source_key,
       r.created_by, c.name AS created_by_name, r.created_at, r.updated_at, r.closed_at
FROM risks r
JOIN projects p ON p.id = r.project_id
LEFT JOIN users o ON o.id = r.owner_id
LEFT JOIN users c ON c.id = r.created_by
"""


# ---------- scoring and suggestions (pure, unit tested) ----------

def level(score):
    """The usual 5x5 matrix bands: 15 to 25 is high, 8 to 14 is medium, 1 to 7 is low."""
    if score >= 15:
        return "high"
    if score >= 8:
        return "medium"
    return "low"


def finish(risk, today=None):
    today = today or date.today()
    risk["score"] = risk["likelihood"] * risk["impact"]
    risk["level"] = level(risk["score"])
    risk["review_overdue"] = (risk["status"] in ACTIVE and risk["review_date"] is not None
                              and risk["review_date"] < today)
    return risk


def summarize(risks):
    active = [r for r in risks if r["status"] in ACTIVE]
    return {"active": len(active),
            "high": sum(1 for r in active if r["level"] == "high"),
            "medium": sum(1 for r in active if r["level"] == "medium"),
            "low": sum(1 for r in active if r["level"] == "low"),
            "reviews_overdue": sum(1 for r in active if r["review_overdue"])}


def _days(count):
    return f"{count} day" if count == 1 else f"{count} days"


def _when(day):
    return f"{day:%b} {day.day}"


def suggest(project, nodes, edges, today=None):
    """Proposes risks from live signals. No database access, so every rule is unit tested."""
    today = today or date.today()
    found = []

    path = scheduling.critical_path(nodes, edges, project["end_date"])
    if path["critical"] and path["buffer_days"] <= BUFFER_WARNING_DAYS:
        names = [nodes[nid]["name"] for nid in path["critical"]]
        buffer = "no buffer" if path["buffer_days"] <= 0 else f"only {_days(path['buffer_days'])} of buffer"
        found.append({
            "source_key": "schedule:critical_path_buffer", "category": "schedule",
            "title": "Little or no schedule buffer on the critical path",
            "description": f"{', '.join(names)} {'has' if len(names) == 1 else 'have'} {buffer} before the "
                           "project end date, so any slip there moves the end date.",
            "likelihood": 3, "impact": 4,
            "mitigation": "Build in buffer before the end date, or split critical work so parts can run in parallel.",
        })

    forecast = scheduling.delivery_forecast(project["progress"], project["start_date"], project["end_date"], today)
    if forecast["status"] == "late":
        found.append({
            "source_key": "schedule:forecast_late", "category": "schedule",
            "title": "Delivery is forecast to finish late",
            "description": f"At the current pace the work finishes around {_when(forecast['projected_end'])}, "
                           f"{_days(forecast['days_late'])} after the end date.",
            "likelihood": 4 if forecast["days_late"] > 14 else 3, "impact": 4,
            "mitigation": "Re-plan the remaining milestones, add people to the critical path, or agree a new "
                          "end date with stakeholders early.",
        })

    planned, spent = float(project["budget_planned"] or 0), float(project["budget_spent"] or 0)
    budget = metrics.budget_forecast(planned, spent, project["start_date"], project["end_date"], today)
    if budget["status"] == "over" and 0 < spent <= planned:
        found.append({
            "source_key": "budget:forecast_over", "category": "budget",
            "title": "Spending is on pace to overrun the budget",
            "description": f"At the current burn rate the project would spend about ${budget['projected_total']:,.0f} "
                           f"against a ${planned:,.0f} budget.",
            "likelihood": 4, "impact": 3,
            "mitigation": "Review upcoming spending, defer lower-value scope, or request a budget change with a reason.",
        })

    for item in found:
        item["score"] = item["likelihood"] * item["impact"]
        item["level"] = level(item["score"])
    return found


# ---------- database helpers ----------

def _graph(cur, project_id):
    cur.execute("SELECT id, name, status, start_date, end_date FROM milestones WHERE project_id = %s", (project_id,))
    nodes = {row["id"]: row for row in cur.fetchall()}
    cur.execute("SELECT md.milestone_id, md.depends_on_id FROM milestone_dependencies md"
                " JOIN milestones m ON m.id = md.milestone_id WHERE m.project_id = %s", (project_id,))
    return nodes, [(row["milestone_id"], row["depends_on_id"]) for row in cur.fetchall()]


def _open_suggestions(cur, project):
    nodes, edges = _graph(cur, project["id"])
    cur.execute("SELECT source_key FROM risks WHERE project_id = %s AND source_key IS NOT NULL", (project["id"],))
    taken = {row["source_key"] for row in cur.fetchall()}
    return [s for s in suggest(project, nodes, edges) if s["source_key"] not in taken]


def _suggestion(cur, project, source_key):
    for item in _open_suggestions(cur, project):
        if item["source_key"] == source_key:
            return item
    raise conflict("That suggestion no longer applies or was already handled. Refresh to see the current ones.")


def _hide_budget(me):
    """Employees don't see financial data, so budget risks are left out for them."""
    return me["role"] == "employee"


def _load(cur, me, project_id, risk_id):
    project = load_project(cur, me, project_id)  # 404 if the caller can't see the project
    cur.execute(f"{RISK_SELECT} WHERE r.id = %s AND r.project_id = %s AND r.status <> 'dismissed'",
                (risk_id, project["id"]))
    risk = cur.fetchone()
    if risk is None or (_hide_budget(me) and risk["category"] == "budget"):
        raise not_found("Risk")
    return finish(risk), project


def _for_write(cur, me, project_id):
    project = load_project(cur, me, project_id)
    require_manager(me, project, "manage its risks")
    require_active(project)
    return project


def _check_owner(cur, project, owner_id):
    if owner_id is None:
        return
    cur.execute("SELECT 1 FROM project_members WHERE project_id = %s AND user_id = %s", (project["id"], owner_id))
    if cur.fetchone() is None:
        raise bad_request("Some fields are invalid.", {"owner_id": "Choose someone on this project's team."})


def _log(cur, me, action, risk, summary, details=None):
    activity.log(cur, me["id"], action, "risk", summary, entity_id=risk["id"], project_id=risk["project_id"],
                 details=details)


# ---------- routes ----------

def register(router):
    """Adds the risk register routes to the projects service's router."""

    @router.route("GET", "/risks")
    def portfolio_risks(req):
        """Every active risk on projects the caller can see, highest score first."""
        me = req.user
        where, params = visible_where(me)
        clauses = [where, "p.archived_at IS NULL", "r.status IN ('open', 'mitigating')"]
        if _hide_budget(me):
            clauses.append("r.category <> 'budget'")
        with db.transaction() as cur:
            cur.execute(f"{RISK_SELECT} WHERE {' AND '.join(clauses)}", params)
            risks = [finish(r) for r in cur.fetchall()]
        risks.sort(key=lambda r: (-r["score"], r["review_date"] or date.max, r["id"]))
        return 200, {"risks": risks, "summary": summarize(risks)}

    @router.route("GET", "/{id}/risks")
    def project_risks(req):
        me = req.user
        with db.transaction() as cur:
            project = load_project(cur, me, req.params["id"])
            clauses, params = ["r.project_id = %s", "r.status <> 'dismissed'"], [project["id"]]
            if _hide_budget(me):
                clauses.append("r.category <> 'budget'")
            cur.execute(f"{RISK_SELECT} WHERE {' AND '.join(clauses)}", params)
            risks = [finish(r) for r in cur.fetchall()]
            manage = can_manage(me, project) and not project["is_archived"]
            suggestions = _open_suggestions(cur, project) if manage else []
        risks.sort(key=lambda r: (r["status"] not in ACTIVE, -r["score"], r["id"]))
        return 200, {"project_id": project["id"], "risks": risks, "suggestions": suggestions,
                     "summary": summarize(risks), "can_manage": manage}

    @router.route("POST", "/{id}/risks", roles=MANAGERS)
    def create_risk(req):
        me = req.user
        data = validate(req.json(), CREATE_SCHEMA)
        with db.transaction() as cur:
            project = _for_write(cur, me, req.params["id"])
            _check_owner(cur, project, data.get("owner_id"))
            source_key = data.get("source_key")
            if source_key:
                _suggestion(cur, project, source_key)
            cur.execute(
                "INSERT INTO risks (project_id, title, description, category, likelihood, impact, owner_id,"
                " mitigation, review_date, source_key, created_by)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                (project["id"], data["title"], data.get("description"), data["category"], data["likelihood"],
                 data["impact"], data.get("owner_id"), data.get("mitigation"), data.get("review_date"),
                 source_key, me["id"]))
            risk, _ = _load(cur, me, project["id"], cur.fetchone()["id"])
            _log(cur, me, "risk.created", risk, f"{me['name']} added the risk \"{risk['title']}\" to {project['name']}",
                 {"likelihood": risk["likelihood"], "impact": risk["impact"], "score": risk["score"],
                  "suggested": bool(source_key)})
        return 201, risk

    @router.route("POST", "/{id}/risks/dismiss", roles=MANAGERS)
    def dismiss_suggestion(req):
        """Records that a suggested risk was looked at and doesn't apply, so it isn't suggested again."""
        me = req.user
        data = validate(req.json(), {"source_key": F("str", required=True, max_len=120)})
        with db.transaction() as cur:
            project = _for_write(cur, me, req.params["id"])
            item = _suggestion(cur, project, data["source_key"])
            cur.execute(
                "INSERT INTO risks (project_id, title, description, category, likelihood, impact, mitigation,"
                " source_key, status, created_by, closed_at)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'dismissed', %s, NOW()) RETURNING id, project_id",
                (project["id"], item["title"], item["description"], item["category"], item["likelihood"],
                 item["impact"], item["mitigation"], item["source_key"], me["id"]))
            row = cur.fetchone()
            _log(cur, me, "risk.dismissed", row,
                 f"{me['name']} dismissed the suggested risk \"{item['title']}\" on {project['name']}",
                 {"source_key": item["source_key"]})
        return 204, None

    @router.route("PUT", "/{id}/risks/{risk_id}", roles=MANAGERS)
    def update_risk(req):
        me = req.user
        data = validate(req.json(), UPDATE_SCHEMA, partial=True)
        if not data:
            raise bad_request("Nothing to update.")
        with db.transaction() as cur:
            project = _for_write(cur, me, req.params["id"])
            risk, _ = _load(cur, me, project["id"], req.params["risk_id"])
            if "owner_id" in data:
                _check_owner(cur, project, data["owner_id"])
            # Column names come only from the whitelisted schema, never from user input
            assignments = ", ".join(f"{column} = %s" for column in data)
            cur.execute(f"UPDATE risks SET {assignments}, updated_at = NOW() WHERE id = %s", [*data.values(), risk["id"]])
            cur.execute("UPDATE risks SET closed_at = CASE WHEN status IN ('closed', 'occurred')"
                        " THEN COALESCE(closed_at, NOW()) ELSE NULL END WHERE id = %s", (risk["id"],))
            updated, _ = _load(cur, me, project["id"], risk["id"])
            changes = activity.diff(risk, updated, list(data))
            _log(cur, me, "risk.updated", updated,
                 f"{me['name']} updated the risk \"{updated['title']}\" ({', '.join(sorted(changes)) or 'no changes'})",
                 {"changes": changes})
        return 200, updated