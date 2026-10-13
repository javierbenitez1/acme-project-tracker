"""Action Center: a to-do queue of what needs attention. System items are created and closed
automatically by the rules in core/actions.py; managers and admins can also add their own.
Closing any item requires a note, and every resolution is written to the audit log."""
from datetime import date

from core import actions, activity, db
from core.errors import bad_request, conflict, forbidden, not_found
from core.http import Router
from core.projects import load_project, require_active, require_manager
from core.validation import F, query_choice, query_int, validate

router = Router("actions")
MANAGERS = ["admin", "manager"]
PRIORITIES = ["critical", "high", "medium", "low"]
STATUSES = ["open", "in_progress", "done", "dismissed"]
CLOSED = ("done", "dismissed")
STATUS_FIELDS = {"status", "resolution_note"}

ACTION_SELECT = """
SELECT a.id, a.title, a.description, a.priority, a.status, a.source, a.rule_key,
       a.assignee_id, u.name AS assignee_name, a.project_id, p.name AS project_name,
       a.entity_type, a.entity_id, a.due_date, a.created_by, c.name AS created_by_name,
       a.resolved_by, r.name AS resolved_by_name, a.resolved_at, a.resolution_note, a.created_at, a.updated_at
FROM action_items a
LEFT JOIN users u ON u.id = a.assignee_id
LEFT JOIN projects p ON p.id = a.project_id
LEFT JOIN users c ON c.id = a.created_by
LEFT JOIN users r ON r.id = a.resolved_by
"""
ORDER = (" ORDER BY CASE a.priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,"
         " a.due_date NULLS LAST, a.created_at DESC")

CREATE_SCHEMA = {
    "title": F("str", required=True, max_len=200),
    "description": F("str", nullable=True, max_len=2000),
    "priority": F("enum", choices=PRIORITIES),
    "assignee_id": F("int", min=1),
    "project_id": F("int", min=1),
    "due_date": F("date", nullable=True),
}
UPDATE_SCHEMA = {
    "title": F("str", required=True, max_len=200),
    "description": F("str", nullable=True, max_len=2000),
    "priority": F("enum", required=True, choices=PRIORITIES),
    "assignee_id": F("int", required=True, min=1),
    "due_date": F("date", nullable=True),
    "status": F("enum", required=True, choices=STATUSES),
    "resolution_note": F("str", nullable=True, max_len=1000),
}


def _visible_where(me):
    """Admins see everything, managers see items on their projects or that they created or own,
    employees see items assigned to them."""
    if me["role"] == "admin":
        return "TRUE", []
    if me["role"] == "manager":
        return "(a.assignee_id = %s OR a.created_by = %s OR p.manager_id = %s)", [me["id"]] * 3
    return "a.assignee_id = %s", [me["id"]]


def _load(cur, me, action_id):
    where, params = _visible_where(me)
    cur.execute(f"{ACTION_SELECT} WHERE a.id = %s AND {where}", [action_id, *params])
    item = cur.fetchone()
    if item is None:
        raise not_found("Action item")
    return item


def _manages_item(cur, me, item):
    """Admins, the manager of the item's project, and whoever created a manual item can manage it."""
    if me["role"] == "admin":
        return True
    if item["source"] == "manual" and item["created_by"] == me["id"]:
        return True
    if item["project_id"]:
        cur.execute("SELECT manager_id FROM projects WHERE id = %s", (item["project_id"],))
        row = cur.fetchone()
        return row is not None and row["manager_id"] == me["id"]
    return False


def _check_assignee(cur, me, assignee_id, project_id):
    cur.execute("SELECT id, name, is_active, manager_id FROM users WHERE id = %s", (assignee_id,))
    user = cur.fetchone()
    if user is None or not user["is_active"]:
        raise bad_request("Some fields are invalid.", {"assignee_id": "Must be an active user."})
    if project_id:
        cur.execute("SELECT 1 FROM project_members WHERE project_id = %s AND user_id = %s", (project_id, assignee_id))
        if cur.fetchone() is None:
            raise bad_request("Some fields are invalid.", {"assignee_id": "Must be on the project team."})
    elif me["role"] != "admin" and assignee_id != me["id"] and user["manager_id"] != me["id"]:
        raise bad_request("Some fields are invalid.",
                          {"assignee_id": "Without a project, you can assign yourself or your direct reports."})
    return user


@router.route("GET", "")
def list_actions(req):
    """Filters: status=active|open|in_progress|done|dismissed|all (default active), priority, project_id,
    source=system|manual, assignee_id=me"""
    q, me = req.query, req.user
    where, params = _visible_where(me)
    clauses = [where]
    status = query_choice(q, "status", ["active", "all", *STATUSES], "active")
    if status == "active":
        clauses.append("a.status IN ('open', 'in_progress')")
    elif status != "all":
        clauses.append("a.status = %s")
        params.append(status)
    priority = query_choice(q, "priority", PRIORITIES)
    if priority:
        clauses.append("a.priority = %s")
        params.append(priority)
    project_id = query_int(q, "project_id")
    if project_id:
        clauses.append("a.project_id = %s")
        params.append(project_id)
    source = query_choice(q, "source", ["system", "manual"])
    if source:
        clauses.append("a.source = %s")
        params.append(source)
    if q.get("assignee_id") == "me":
        clauses.append("a.assignee_id = %s")
        params.append(me["id"])
    elif q.get("assignee_id"):
        raise bad_request("Invalid filter.", {"assignee_id": 'Use "me" to see items assigned to you.'})
    with db.transaction() as cur:
        actions.sync(cur)
        cur.execute(f"{ACTION_SELECT} WHERE {' AND '.join(clauses)}{ORDER}", params)
        return 200, cur.fetchall()


@router.route("GET", "/summary")
def action_summary(req):
    """Counts for the navigation badge and dashboard."""
    me = req.user
    where, params = _visible_where(me)
    active = "a.status IN ('open', 'in_progress')"
    with db.transaction() as cur:
        actions.sync(cur)
        cur.execute(
            f"SELECT COUNT(*) FILTER (WHERE {active}) AS open_total,"
            + "".join(f" COUNT(*) FILTER (WHERE {active} AND a.priority = '{p}') AS {p}," for p in PRIORITIES)
            + f" COUNT(*) FILTER (WHERE {active} AND a.assignee_id = %s) AS assigned_to_me,"
            " COUNT(*) FILTER (WHERE a.status = 'done' AND a.resolved_at >= NOW() - INTERVAL '7 days')"
            "   AS resolved_this_week"
            f" FROM action_items a LEFT JOIN projects p ON p.id = a.project_id WHERE {where}",
            [me["id"], *params])
        row = cur.fetchone()
    return 200, {"open_total": row["open_total"], "by_priority": {p: row[p] for p in PRIORITIES},
                 "assigned_to_me": row["assigned_to_me"], "resolved_this_week": row["resolved_this_week"]}


@router.route("GET", "/{id}")
def get_action(req):
    with db.transaction() as cur:
        item = _load(cur, req.user, req.params["id"])
        item["can_manage"] = _manages_item(cur, req.user, item)
    return 200, item


@router.route("POST", "", roles=MANAGERS)
def create_action(req):
    me = req.user
    data = validate(req.json(), CREATE_SCHEMA)
    if data.get("due_date") and data["due_date"] < date.today():
        raise bad_request("Some fields are invalid.", {"due_date": "Can't be in the past."})
    project_id = data.get("project_id")
    assignee_id = data.get("assignee_id", me["id"])
    with db.transaction() as cur:
        if project_id:
            project = load_project(cur, me, project_id)
            require_manager(me, project, "add action items to it")
            require_active(project)
        assignee = _check_assignee(cur, me, assignee_id, project_id)
        cur.execute("INSERT INTO action_items (title, description, priority, source, assignee_id, project_id,"
                    " due_date, created_by) VALUES (%s, %s, %s, 'manual', %s, %s, %s, %s) RETURNING id",
                    (data["title"], data.get("description"), data.get("priority", "medium"), assignee_id,
                     project_id, data.get("due_date"), me["id"]))
        item = _load(cur, me, cur.fetchone()["id"])
        activity.log(cur, me["id"], "action.created", "action_item",
                     f"{me['name']} asked {assignee['name']} to: {item['title']}", entity_id=item["id"],
                     project_id=project_id, details={"priority": item["priority"], "due_date": item["due_date"]})
    return 201, item


@router.route("PUT", "/{id}")
def update_action(req):
    me = req.user
    body = req.json()
    unknown = set(body) - set(UPDATE_SCHEMA)
    if unknown:
        raise bad_request("Some fields are invalid.", {k: "Unknown field." for k in unknown})
    with db.transaction() as cur:
        item = _load(cur, me, req.params["id"])
        manages = _manages_item(cur, me, item)
        is_assignee = item["assignee_id"] == me["id"]
        if item["source"] == "system":
            if not (manages or is_assignee):
                raise forbidden("You can only update action items assigned to you.")
            if set(body) - STATUS_FIELDS:
                raise forbidden("System items are kept up to date automatically. You can only change their status.")
        elif not manages:
            if not is_assignee:
                raise forbidden("You can only update action items assigned to you.")
            if set(body) - STATUS_FIELDS:
                raise forbidden("You can only update the status of items assigned to you.")
        data = validate(body, UPDATE_SCHEMA, partial=True)
        if not data:
            raise bad_request("Nothing to update.")

        new_status = data.get("status", item["status"])
        if item["source"] == "system" and new_status == "done" and item["status"] != "done":
            raise conflict("This item closes automatically once the problem is fixed. "
                           "Dismiss it with a note if it doesn't need action.")
        if "assignee_id" in data and data["assignee_id"] != item["assignee_id"]:
            _check_assignee(cur, me, data["assignee_id"], item["project_id"])
        if data.get("due_date") and data["due_date"] < date.today() and data["due_date"] != item["due_date"]:
            raise bad_request("Some fields are invalid.", {"due_date": "Can't be in the past."})
        closing = new_status in CLOSED and new_status != item["status"]
        if closing and not data.get("resolution_note"):
            raise bad_request("Please add a short note about what was done.",
                              {"resolution_note": "Required when closing an item."})

        extra, extra_params = "", []
        if new_status != item["status"]:
            if new_status in CLOSED:
                extra, extra_params = ", resolved_by = %s, resolved_at = NOW()", [me["id"]]
            else:
                extra = ", resolved_by = NULL, resolved_at = NULL"
                data.setdefault("resolution_note", None)
        # Column names come only from the whitelisted schema, never from user input
        assignments = ", ".join(f"{column} = %s" for column in data)
        cur.execute(f"UPDATE action_items SET {assignments}{extra}, updated_at = NOW() WHERE id = %s",
                    [*data.values(), *extra_params, item["id"]])
        updated = _load(cur, me, item["id"])

        if closing:
            verb = "completed" if new_status == "done" else "dismissed"
            action = "action.resolved" if new_status == "done" else "action.dismissed"
            summary = f"{me['name']} {verb} {item['title']}: {data['resolution_note']}"
        else:
            action, summary = "action.updated", f"{me['name']} updated {item['title']}"
        activity.log(cur, me["id"], action, "action_item", summary, entity_id=item["id"],
                     project_id=item["project_id"], details={"changes": activity.diff(item, updated, list(data))})
    return 200, updated


@router.route("DELETE", "/{id}", roles=MANAGERS)
def delete_action(req):
    me = req.user
    with db.transaction() as cur:
        item = _load(cur, me, req.params["id"])
        if item["source"] == "system":
            raise conflict("System items can't be deleted. Dismiss it with a note instead.")
        if not _manages_item(cur, me, item):
            raise forbidden("Only the person who created this item or an admin can delete it.")
        cur.execute("DELETE FROM action_items WHERE id = %s", (item["id"],))
        activity.log(cur, me["id"], "action.deleted", "action_item", f"{me['name']} deleted {item['title']}",
                     entity_id=item["id"], project_id=item["project_id"], details={"title": item["title"]})
    return 204, None


def handler(event, context=None):
    return router.handle(event, context)