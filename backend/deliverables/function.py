"""Deliverables service: concrete pieces of work inside a milestone. Managers plan and assign them;
employees update the status of the work assigned to them."""
from datetime import date

from core import activity, db
from core.errors import bad_request, conflict, forbidden, not_found
from core.http import Router
from core.projects import can_manage, load_project, require_active, require_manager, visible_where
from core.validation import F, query_choice, query_int, validate

router = Router("deliverables")
MANAGERS = ["admin", "manager"]
STATUSES = ["todo", "in_progress", "blocked", "done"]
EMPLOYEE_FIELDS = {"status", "status_note"}

DELIVERABLE_SELECT = """
SELECT d.id, d.milestone_id, m.name AS milestone_name, m.status AS milestone_status,
       m.project_id, p.name AS project_name,
       d.title, d.description, d.assignee_id, u.name AS assignee_name,
       d.status, d.status_note, d.due_date, d.completed_at, d.created_at, d.updated_at
FROM deliverables d
JOIN milestones m ON m.id = d.milestone_id
JOIN projects p ON p.id = m.project_id
LEFT JOIN users u ON u.id = d.assignee_id
"""

CREATE_SCHEMA = {
    "milestone_id": F("int", required=True, min=1),
    "title": F("str", required=True, max_len=200),
    "description": F("str", nullable=True, max_len=5000),
    "assignee_id": F("int", nullable=True, min=1),
    "due_date": F("date", nullable=True),
}
UPDATE_SCHEMA = {
    "title": F("str", required=True, max_len=200),
    "description": F("str", nullable=True, max_len=5000),
    "assignee_id": F("int", nullable=True, min=1),
    "due_date": F("date", nullable=True),
    "status": F("enum", required=True, choices=STATUSES),
    "status_note": F("str", nullable=True, max_len=1000),
}


# ---------- helpers ----------

def _finish(item, today=None):
    today = today or date.today()
    item["is_overdue"] = (item["status"] != "done" and item["due_date"] is not None
                          and item["due_date"] < today)
    return item


def _load(cur, me, deliverable_id):
    cur.execute(f"{DELIVERABLE_SELECT} WHERE d.id = %s", (deliverable_id,))
    item = cur.fetchone()
    if item is None:
        raise not_found("Deliverable")
    project = load_project(cur, me, item["project_id"])  # 404 if the caller can't see the project
    return _finish(item), project


def _milestone(cur, milestone_id):
    cur.execute("SELECT id, project_id, name, status, start_date, end_date FROM milestones WHERE id = %s",
                (milestone_id,))
    return cur.fetchone()


def _waiting_on(cur, milestone_id):
    """Names of milestones this one depends on that aren't done yet."""
    cur.execute("SELECT d.name FROM milestone_dependencies md JOIN milestones d ON d.id = md.depends_on_id"
                " WHERE md.milestone_id = %s AND d.status <> 'done' ORDER BY d.end_date", (milestone_id,))
    return [row["name"] for row in cur.fetchall()]


def _check_assignee(cur, project_id, assignee_id):
    if assignee_id is None:
        return None
    cur.execute("SELECT u.id, u.name, u.role, u.is_active FROM project_members pm"
                " JOIN users u ON u.id = pm.user_id WHERE pm.project_id = %s AND pm.user_id = %s",
                (project_id, assignee_id))
    user = cur.fetchone()
    if user is None:
        raise bad_request("Some fields are invalid.", {"assignee_id": "Add this person to the project team first."})
    if user["role"] != "employee" or not user["is_active"]:
        raise bad_request("Some fields are invalid.", {"assignee_id": "Only active employees can be assigned."})
    return user


def _check_due_date(milestone, due_date):
    if due_date is not None and not (milestone["start_date"] <= due_date <= milestone["end_date"]):
        raise bad_request("Some fields are invalid.",
                          {"due_date": f"Must fall within the milestone "
                                       f"({milestone['start_date']} to {milestone['end_date']})."})


def _log(cur, me, action, item, summary, details=None):
    activity.log(cur, me["id"], action, "deliverable", summary, entity_id=item["id"],
                 project_id=item["project_id"], details=details)


# ---------- routes ----------

@router.route("GET", "")
def list_deliverables(req):
    """Filters: project_id, milestone_id, assignee_id (a number or "me"), status, overdue=true, search,
    include_archived=true"""
    q, me = req.query, req.user
    where, params = visible_where(me)
    clauses = [where]
    if query_choice(q, "include_archived", ["true", "false"], "false") == "false":
        clauses.append("p.archived_at IS NULL")
    for name, column in (("project_id", "m.project_id"), ("milestone_id", "d.milestone_id")):
        value = query_int(q, name)
        if value:
            clauses.append(f"{column} = %s")
            params.append(value)
    if q.get("assignee_id") == "me":
        clauses.append("d.assignee_id = %s")
        params.append(me["id"])
    else:
        assignee_id = query_int(q, "assignee_id")
        if assignee_id:
            clauses.append("d.assignee_id = %s")
            params.append(assignee_id)
    status = query_choice(q, "status", STATUSES)
    if status:
        clauses.append("d.status = %s")
        params.append(status)
    if query_choice(q, "overdue", ["true", "false"]) == "true":
        clauses.append("d.status <> 'done' AND d.due_date < CURRENT_DATE")
    if q.get("search"):
        clauses.append("(d.title ILIKE %s OR d.description ILIKE %s)")
        params.extend([f"%{q['search'].strip()}%"] * 2)
    with db.transaction() as cur:
        cur.execute(f"{DELIVERABLE_SELECT} WHERE {' AND '.join(clauses)} ORDER BY d.due_date NULLS LAST, d.id",
                    params)
        return 200, [_finish(item) for item in cur.fetchall()]


@router.route("GET", "/{id}")
def get_deliverable(req):
    me = req.user
    with db.transaction() as cur:
        item, project = _load(cur, me, req.params["id"])
    item["can_manage"] = can_manage(me, project) and not project["is_archived"]
    item["can_update_status"] = item["can_manage"] or (item["assignee_id"] == me["id"] and not project["is_archived"])
    return 200, item


@router.route("POST", "", roles=MANAGERS)
def create_deliverable(req):
    me = req.user
    data = validate(req.json(), CREATE_SCHEMA)
    with db.transaction() as cur:
        milestone = _milestone(cur, data["milestone_id"])
        if milestone is None:
            raise bad_request("Some fields are invalid.", {"milestone_id": "Milestone not found."})
        project = load_project(cur, me, milestone["project_id"])
        require_manager(me, project, "add deliverables")
        require_active(project)
        if milestone["status"] == "done":
            raise conflict(f"{milestone['name']} is already done. Reopen it before adding work.")
        assignee = _check_assignee(cur, project["id"], data.get("assignee_id"))
        _check_due_date(milestone, data.get("due_date"))
        cur.execute("INSERT INTO deliverables (milestone_id, title, description, assignee_id, due_date, created_by)"
                    " VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                    (milestone["id"], data["title"], data.get("description"), data.get("assignee_id"),
                     data.get("due_date"), me["id"]))
        item, _ = _load(cur, me, cur.fetchone()["id"])
        who = f" for {assignee['name']}" if assignee else ""
        _log(cur, me, "deliverable.created", item, f"{me['name']} added {item['title']} to {milestone['name']}{who}",
             {"assignee_id": item["assignee_id"], "due_date": item["due_date"]})
    return 201, item


@router.route("PUT", "/{id}")
def update_deliverable(req):
    """Managers can change anything. The assigned employee can change only status and status_note."""
    me, deliverable_id = req.user, req.params["id"]
    body = req.json()
    unknown = set(body) - set(UPDATE_SCHEMA)
    if unknown:
        raise bad_request("Some fields are invalid.", {k: "Unknown field." for k in unknown})
    with db.transaction() as cur:
        item, project = _load(cur, me, deliverable_id)
        require_active(project)
        if not can_manage(me, project):
            if item["assignee_id"] != me["id"]:
                raise forbidden("You can only update deliverables assigned to you.")
            if set(body) - EMPLOYEE_FIELDS:
                raise forbidden("You can only update the status of work assigned to you.")
        data = validate(body, UPDATE_SCHEMA, partial=True)
        if not data:
            raise bad_request("Nothing to update.")

        milestone = _milestone(cur, item["milestone_id"])
        if "assignee_id" in data and data["assignee_id"] != item["assignee_id"]:
            _check_assignee(cur, project["id"], data["assignee_id"])
        if "due_date" in data:
            _check_due_date(milestone, data["due_date"])

        new_status = data.get("status", item["status"])
        if new_status != item["status"]:
            if milestone["status"] == "done":
                raise conflict(f"{milestone['name']} is already done. Reopen it before changing its work.")
            if new_status in ("in_progress", "done"):
                waiting = _waiting_on(cur, milestone["id"])
                if waiting:
                    raise conflict(f"Work on {milestone['name']} can't start until its dependencies are done.",
                                   {"waiting_on": waiting})
            if new_status != "blocked" and "status_note" not in data:
                data["status_note"] = None  # the old blocker no longer applies
        if new_status == "blocked" and not data.get("status_note", item["status_note"]):
            raise bad_request("Please say what's blocking this.",
                              {"status_note": "Required when marking work as blocked."})

        # Column names come only from the whitelisted schema, never from user input
        assignments = ", ".join(f"{column} = %s" for column in data)
        cur.execute(f"UPDATE deliverables SET {assignments}, updated_at = NOW() WHERE id = %s",
                    [*data.values(), deliverable_id])
        cur.execute("UPDATE deliverables SET completed_at = CASE WHEN status = 'done'"
                    " THEN COALESCE(completed_at, NOW()) ELSE NULL END WHERE id = %s", (deliverable_id,))

        milestone_started = False
        if new_status in ("in_progress", "done") and milestone["status"] == "not_started":
            cur.execute("UPDATE milestones SET status = 'in_progress', updated_at = NOW() WHERE id = %s",
                        (milestone["id"],))
            activity.log(cur, me["id"], "milestone.started", "milestone",
                         f"{milestone['name']} started when work began on {item['title']}",
                         entity_id=milestone["id"], project_id=item["project_id"])
            milestone_started = True

        updated, _ = _load(cur, me, deliverable_id)
        changes = activity.diff(item, updated, list(data))
        _log(cur, me, "deliverable.updated", updated,
             f"{me['name']} updated {updated['title']} ({', '.join(sorted(changes)) or 'no changes'})",
             {"changes": changes})
        cur.execute("SELECT COUNT(*) FILTER (WHERE status <> 'done') AS open FROM deliverables WHERE milestone_id = %s",
                    (milestone["id"],))
        open_count = cur.fetchone()["open"]
    updated["milestone_started"] = milestone_started
    updated["milestone_ready"] = open_count == 0 and milestone["status"] != "done"
    return 200, updated


@router.route("DELETE", "/{id}", roles=MANAGERS)
def delete_deliverable(req):
    me = req.user
    with db.transaction() as cur:
        item, project = _load(cur, me, req.params["id"])
        require_manager(me, project, "remove deliverables")
        require_active(project)
        if item["status"] == "done":
            raise conflict("Completed deliverables can't be deleted. They're part of the project record.")
        cur.execute("DELETE FROM deliverables WHERE id = %s", (item["id"],))
        _log(cur, me, "deliverable.deleted", item, f"{me['name']} removed {item['title']} from {item['milestone_name']}",
             {"title": item["title"]})
    return 204, None


def handler(event, context=None):
    return router.handle(event, context)