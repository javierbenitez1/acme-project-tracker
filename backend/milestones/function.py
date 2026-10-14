"""Milestones service: scheduled phases inside a project, with dependencies, team assignments that
respect an 8-hour workday, and rescheduling that records a reason and can shift later milestones."""
from datetime import date
from decimal import Decimal

from core import activity, db, scheduling
from core.errors import bad_request, conflict, not_found
from core.http import Router
from core.projects import can_manage, load_project, require_active, require_manager, visible_where
from core.validation import F, query_choice, query_int, validate

router = Router("milestones")
MANAGERS = ["admin", "manager"]
STATUSES = ["not_started", "in_progress", "blocked", "done"]

MILESTONE_SELECT = """
SELECT m.id, m.project_id, p.name AS project_name, m.name, m.description, m.start_date, m.end_date,
       m.status, m.completed_at, m.created_at, m.updated_at,
       COALESCE(dc.total, 0) AS deliverables_total, COALESCE(dc.done, 0) AS deliverables_done,
       CASE WHEN m.status = 'done' THEN 100
            WHEN dc.total > 0 THEN ROUND(100.0 * dc.done / dc.total)
            ELSE 0 END AS progress,
       COALESCE((SELECT json_agg(json_build_object('id', d.id, 'name', d.name, 'status', d.status,
                                                   'end_date', d.end_date) ORDER BY d.end_date)
                 FROM milestone_dependencies md JOIN milestones d ON d.id = md.depends_on_id
                 WHERE md.milestone_id = m.id), '[]'::json) AS dependencies,
       COALESCE((SELECT json_agg(json_build_object('user_id', u.id, 'name', u.name,
                                                   'hours_per_day', ma.hours_per_day) ORDER BY u.name)
                 FROM milestone_assignments ma JOIN users u ON u.id = ma.user_id
                 WHERE ma.milestone_id = m.id), '[]'::json) AS assignees
FROM milestones m
JOIN projects p ON p.id = m.project_id
LEFT JOIN LATERAL (SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE status = 'done') AS done
                   FROM deliverables WHERE milestone_id = m.id) dc ON TRUE
"""

CREATE_SCHEMA = {
    "project_id": F("int", required=True, min=1),
    "name": F("str", required=True, max_len=150),
    "description": F("str", nullable=True, max_len=5000),
    "start_date": F("date", required=True),
    "end_date": F("date", required=True),
    "depends_on": F("ids", max_len=20),
}
UPDATE_SCHEMA = {
    "name": F("str", required=True, max_len=150),
    "description": F("str", nullable=True, max_len=5000),
    "status": F("enum", required=True, choices=STATUSES),
    "start_date": F("date", required=True),
    "end_date": F("date", required=True),
    "change_reason": F("str", max_len=1000),
    "shift_dependents": F("bool"),
    "dry_run": F("bool"),
}
ASSIGN_SCHEMA = {"user_id": F("int", required=True, min=1), "hours_per_day": F("number", min=0.5, max=8)}
HOURS_SCHEMA = {"hours_per_day": F("number", required=True, min=0.5, max=8)}


# ---------- helpers ----------

def _finish(milestone, today=None):
    today = today or date.today()
    milestone["progress"] = int(milestone["progress"] or 0)
    milestone["depends_on"] = [d["id"] for d in milestone["dependencies"]]
    milestone["blocked_by"] = [d for d in milestone["dependencies"] if d["status"] != "done"]
    milestone["can_start"] = not milestone["blocked_by"]
    milestone["is_overdue"] = milestone["status"] != "done" and milestone["end_date"] < today
    return milestone


def _load(cur, me, milestone_id):
    cur.execute(f"{MILESTONE_SELECT} WHERE m.id = %s", (milestone_id,))
    milestone = cur.fetchone()
    if milestone is None:
        raise not_found("Milestone")
    project = load_project(cur, me, milestone["project_id"])  # 404 if the caller can't see the project
    return _finish(milestone), project


def _for_write(cur, me, milestone_id, action="change its milestones"):
    milestone, project = _load(cur, me, milestone_id)
    require_manager(me, project, action)
    require_active(project)
    return milestone, project


def _graph(cur, project_id):
    cur.execute("SELECT id, name, status, start_date, end_date FROM milestones WHERE project_id = %s",
                (project_id,))
    nodes = {row["id"]: row for row in cur.fetchall()}
    cur.execute("SELECT md.milestone_id, md.depends_on_id FROM milestone_dependencies md"
                " JOIN milestones m ON m.id = md.milestone_id WHERE m.project_id = %s", (project_id,))
    edges = [(row["milestone_id"], row["depends_on_id"]) for row in cur.fetchall()]
    return nodes, edges


def _within_project(project, start, end):
    errors = {}
    if start < project["start_date"]:
        errors["start_date"] = f"Must be on or after the project start ({project['start_date']})."
    if end > project["end_date"]:
        errors["end_date"] = f"Must be on or before the project end ({project['end_date']}). Extend the project first."
    if end < start:
        errors["end_date"] = "Must be on or after the start date."
    if errors:
        raise bad_request("Some fields are invalid.", errors)


def _log(cur, me, action, milestone, summary, details=None):
    activity.log(cur, me["id"], action, "milestone", summary, entity_id=milestone["id"],
                 project_id=milestone["project_id"], details=details)


def _record_date_change(cur, me, project_id, milestone_id, old, new, reason):
    cur.execute(
        "INSERT INTO date_changes (entity_type, entity_id, project_id, old_start, old_end, new_start, new_end,"
        " reason, changed_by) VALUES ('milestone', %s, %s, %s, %s, %s, %s, %s, %s)",
        (milestone_id, project_id, old[0], old[1], new[0], new[1], reason, me["id"]))


def _overlapping(cur, user_id, start, end, exclude_milestone_id):
    """The user's other open assignments whose dates overlap start to end."""
    cur.execute(
        "SELECT m.id, m.name, p.name AS project_name, m.start_date, m.end_date, ma.hours_per_day"
        " FROM milestone_assignments ma"
        " JOIN milestones m ON m.id = ma.milestone_id"
        " JOIN projects p ON p.id = m.project_id"
        " WHERE ma.user_id = %s AND m.id <> %s AND m.status <> 'done' AND p.archived_at IS NULL"
        "   AND m.start_date <= %s AND m.end_date >= %s ORDER BY m.start_date",
        (user_id, exclude_milestone_id, end, start))
    return cur.fetchall()


def _check_capacity(cur, user, milestone, hours):
    """Enforces the 8-hour workday across every overlapping milestone the person is on."""
    cur.execute("SELECT id FROM users WHERE id = %s FOR UPDATE", (user["id"],))  # serializes concurrent bookings
    others = _overlapping(cur, user["id"], milestone["start_date"], milestone["end_date"], milestone["id"])
    peak, day = scheduling.peak_daily_load(others, milestone["start_date"], milestone["end_date"])
    if peak + float(hours) > scheduling.WORKDAY_HOURS:
        available = max(scheduling.WORKDAY_HOURS - peak, 0)
        raise conflict(
            f"{user['name']} only has {available:g} hour(s) a day free on {day:%b} {day.day} "
            f"({peak:g} of {scheduling.WORKDAY_HOURS:g} already booked).",
            {"available_hours": available, "requested_hours": float(hours), "busiest_day": day,
             "booked_on": [{"milestone": o["name"], "project": o["project_name"],
                            "hours_per_day": o["hours_per_day"], "start_date": o["start_date"],
                            "end_date": o["end_date"]} for o in others]})


def _overload_warnings(cur, milestone_ids):
    """After dates move, flags anyone now booked over 8 hours a day (reported, not blocked)."""
    cur.execute(
        "SELECT ma.user_id, u.name, ma.hours_per_day, m.id, m.name AS milestone_name, m.start_date, m.end_date"
        " FROM milestone_assignments ma JOIN users u ON u.id = ma.user_id"
        " JOIN milestones m ON m.id = ma.milestone_id WHERE ma.milestone_id = ANY(%s)", (list(milestone_ids),))
    warnings = []
    for row in cur.fetchall():
        others = _overlapping(cur, row["user_id"], row["start_date"], row["end_date"], row["id"])
        peak, day = scheduling.peak_daily_load(others, row["start_date"], row["end_date"])
        total = peak + float(row["hours_per_day"])
        if total > scheduling.WORKDAY_HOURS:
            warnings.append(f"{row['name']} is now booked {total:g}h on {day:%b} {day.day} because of {row['milestone_name']}.")
    return warnings


# ---------- milestones ----------

@router.route("GET", "")
def list_milestones(req):
    """Filters: project_id, status, assignee_id, overdue=true, include_archived=true"""
    q = req.query
    where, params = visible_where(req.user)
    clauses = [where]
    if query_choice(q, "include_archived", ["true", "false"], "false") == "false":
        clauses.append("p.archived_at IS NULL")
    project_id = query_int(q, "project_id")
    if project_id:
        clauses.append("m.project_id = %s")
        params.append(project_id)
    status = query_choice(q, "status", STATUSES)
    if status:
        clauses.append("m.status = %s")
        params.append(status)
    assignee_id = query_int(q, "assignee_id")
    if assignee_id:
        clauses.append("EXISTS (SELECT 1 FROM milestone_assignments ma"
                       " WHERE ma.milestone_id = m.id AND ma.user_id = %s)")
        params.append(assignee_id)
    if query_choice(q, "overdue", ["true", "false"]) == "true":
        clauses.append("m.status <> 'done' AND m.end_date < CURRENT_DATE")
    with db.transaction() as cur:
        cur.execute(f"{MILESTONE_SELECT} WHERE {' AND '.join(clauses)} ORDER BY m.start_date, m.id", params)
        return 200, [_finish(m) for m in cur.fetchall()]


@router.route("GET", "/{id}")
def get_milestone(req):
    with db.transaction() as cur:
        milestone, project = _load(cur, req.user, req.params["id"])
        cur.execute("SELECT m2.id, m2.name, m2.status, m2.start_date, m2.end_date FROM milestone_dependencies md"
                    " JOIN milestones m2 ON m2.id = md.milestone_id WHERE md.depends_on_id = %s"
                    " ORDER BY m2.start_date", (milestone["id"],))
        milestone["dependents"] = cur.fetchall()
        cur.execute("SELECT dc.old_start, dc.old_end, dc.new_start, dc.new_end, dc.reason, dc.changed_at,"
                    " u.name AS changed_by_name FROM date_changes dc LEFT JOIN users u ON u.id = dc.changed_by"
                    " WHERE dc.entity_type = 'milestone' AND dc.entity_id = %s ORDER BY dc.changed_at DESC",
                    (milestone["id"],))
        milestone["date_changes"] = cur.fetchall()
        milestone["can_manage"] = can_manage(req.user, project) and not project["is_archived"]
    return 200, milestone


@router.route("POST", "", roles=MANAGERS)
def create_milestone(req):
    me = req.user
    data = validate(req.json(), CREATE_SCHEMA)
    with db.transaction() as cur:
        project = load_project(cur, me, data["project_id"])
        require_manager(me, project, "add milestones")
        require_active(project)
        _within_project(project, data["start_date"], data["end_date"])
        depends_on = data.get("depends_on") or []
        if depends_on:
            cur.execute("SELECT id, name, end_date, project_id FROM milestones WHERE id = ANY(%s)", (depends_on,))
            found = {row["id"]: row for row in cur.fetchall()}
            problems = {str(i): "Milestone not found in this project." for i in depends_on
                        if i not in found or found[i]["project_id"] != project["id"]}
            if problems:
                raise bad_request("Some dependencies are invalid.", {"depends_on": problems})
            latest = max(found.values(), key=lambda row: row["end_date"])
            if data["start_date"] < latest["end_date"]:
                raise bad_request("Some fields are invalid.",
                                  {"start_date": f"Must be on or after {latest['name']} ends ({latest['end_date']})."})
        cur.execute("INSERT INTO milestones (project_id, name, description, start_date, end_date)"
                    " VALUES (%s, %s, %s, %s, %s) RETURNING id",
                    (project["id"], data["name"], data.get("description"), data["start_date"], data["end_date"]))
        milestone_id = cur.fetchone()["id"]
        for prerequisite in depends_on:
            cur.execute("INSERT INTO milestone_dependencies (milestone_id, depends_on_id) VALUES (%s, %s)",
                        (milestone_id, prerequisite))
        milestone, _ = _load(cur, me, milestone_id)
        _log(cur, me, "milestone.created", milestone,
             f"{me['name']} added milestone {milestone['name']} to {project['name']}",
             {"start_date": milestone["start_date"], "end_date": milestone["end_date"], "depends_on": depends_on})
    return 201, milestone


@router.route("PUT", "/{id}", roles=MANAGERS)
def update_milestone(req):
    me, milestone_id = req.user, req.params["id"]
    data = validate(req.json(), UPDATE_SCHEMA, partial=True)
    reason = data.pop("change_reason", None)
    shift = data.pop("shift_dependents", False)
    dry_run = data.pop("dry_run", False)
    if not data:
        raise bad_request("Nothing to update.")
    with db.transaction() as cur:
        milestone, project = _for_write(cur, me, milestone_id)
        new_start = data.get("start_date", milestone["start_date"])
        new_end = data.get("end_date", milestone["end_date"])
        dates_changed = (new_start, new_end) != (milestone["start_date"], milestone["end_date"])
        shifted, preview, nodes = {}, [], {}

        if dates_changed:
            if not reason:
                raise bad_request("Please explain why the dates are changing.",
                                  {"change_reason": "Required when changing dates."})
            _within_project(project, new_start, new_end)
            nodes, edges = _graph(cur, project["id"])
            prerequisites = [nodes[p] for (m, p) in edges if m == milestone_id]
            if prerequisites:
                latest = max(prerequisites, key=lambda n: n["end_date"])
                if new_start < latest["end_date"]:
                    raise bad_request("Some fields are invalid.",
                                      {"start_date": f"Must be on or after {latest['name']} ends ({latest['end_date']})."})
            plan = scheduling.plan_reschedule(nodes, edges, milestone_id, new_start, new_end)
            shifted = {k: v for k, v in plan.items() if k != milestone_id}
            preview = [{"id": k, "name": nodes[k]["name"], "old_start": nodes[k]["start_date"],
                        "old_end": nodes[k]["end_date"], "new_start": s, "new_end": e}
                       for k, (s, e) in sorted(shifted.items(), key=lambda kv: kv[1][0])]
            overflow = [p["name"] for p in preview if p["new_end"] > project["end_date"]]
            if dry_run:
                return 200, {"dry_run": True, "shifted": preview, "overflows_project": overflow}
            if overflow:
                raise conflict("Moving this milestone would push others past the project end date. "
                               "Extend the project first.",
                               {"milestones": overflow, "project_end": project["end_date"]})
            if shifted and not shift:
                raise conflict(f"{len(shifted)} later milestone(s) depend on this one and would start too early. "
                               "Send shift_dependents: true to move them automatically.", {"shifted": preview})
        elif dry_run:
            return 200, {"dry_run": True, "shifted": [], "overflows_project": []}

        new_status = data.get("status", milestone["status"])
        if new_status != milestone["status"]:
            if new_status in ("in_progress", "done") and milestone["blocked_by"]:
                raise conflict(f"{milestone['name']} can't start until its dependencies are done.",
                               {"waiting_on": [d["name"] for d in milestone["blocked_by"]]})
            if new_status == "done":
                cur.execute("SELECT title FROM deliverables WHERE milestone_id = %s AND status <> 'done' ORDER BY id",
                            (milestone_id,))
                open_items = [row["title"] for row in cur.fetchall()]
                if open_items:
                    raise conflict(f"{len(open_items)} deliverable(s) are still open.",
                                   {"open_deliverables": open_items})
            if milestone["status"] == "done":
                cur.execute("SELECT m2.name FROM milestone_dependencies md JOIN milestones m2 ON m2.id = md.milestone_id"
                            " WHERE md.depends_on_id = %s AND m2.status IN ('in_progress', 'done')", (milestone_id,))
                started = [row["name"] for row in cur.fetchall()]
                if started:
                    raise conflict("Later milestones have already started based on this one.",
                                   {"dependents": started})

        # Column names come only from the whitelisted schema, never from user input
        assignments = ", ".join(f"{column} = %s" for column in data)
        cur.execute(f"UPDATE milestones SET {assignments}, updated_at = NOW() WHERE id = %s",
                    [*data.values(), milestone_id])
        cur.execute("UPDATE milestones SET completed_at = CASE WHEN status = 'done'"
                    " THEN COALESCE(completed_at, NOW()) ELSE NULL END WHERE id = %s", (milestone_id,))
        if dates_changed:
            _record_date_change(cur, me, project["id"], milestone_id,
                                (milestone["start_date"], milestone["end_date"]), (new_start, new_end), reason)
            for other_id, (start, end) in shifted.items():
                cur.execute("UPDATE milestones SET start_date = %s, end_date = %s, updated_at = NOW() WHERE id = %s",
                            (start, end, other_id))
                _record_date_change(cur, me, project["id"], other_id,
                                    (nodes[other_id]["start_date"], nodes[other_id]["end_date"]), (start, end),
                                    f"Shifted automatically because {milestone['name']} moved: {reason}")

        updated, _ = _load(cur, me, milestone_id)
        changes = activity.diff(milestone, updated, list(data))
        details = {"changes": changes}
        if reason:
            details["reason"] = reason
        if preview:
            details["shifted"] = [p["name"] for p in preview]
        _log(cur, me, "milestone.updated", updated,
             f"{me['name']} updated {updated['name']} ({', '.join(sorted(changes)) or 'no changes'})", details)
        updated["shifted"] = preview
        updated["warnings"] = _overload_warnings(cur, [milestone_id, *shifted]) if dates_changed else []
    return 200, updated


@router.route("DELETE", "/{id}", roles=MANAGERS)
def delete_milestone(req):
    me = req.user
    with db.transaction() as cur:
        milestone, _ = _for_write(cur, me, req.params["id"])
        if milestone["status"] == "done":
            raise conflict("Completed milestones can't be deleted. They're part of the project record.")
        if milestone["deliverables_done"]:
            raise conflict("This milestone has completed deliverables, so it can't be deleted.")
        cur.execute("SELECT m2.name FROM milestone_dependencies md JOIN milestones m2 ON m2.id = md.milestone_id"
                    " WHERE md.depends_on_id = %s", (milestone["id"],))
        unlinked = [row["name"] for row in cur.fetchall()]
        cur.execute("DELETE FROM milestones WHERE id = %s", (milestone["id"],))
        _log(cur, me, "milestone.deleted", milestone, f"{me['name']} deleted milestone {milestone['name']}",
             {"name": milestone["name"], "unlinked_dependents": unlinked})
    return 204, None


# ---------- dependencies ----------

@router.route("POST", "/{id}/dependencies", roles=MANAGERS)
def add_dependency(req):
    me, milestone_id = req.user, req.params["id"]
    data = validate(req.json(), {"depends_on_id": F("int", required=True, min=1)})
    with db.transaction() as cur:
        milestone, project = _for_write(cur, me, milestone_id)
        prerequisite_id = data["depends_on_id"]
        nodes, edges = _graph(cur, project["id"])
        if prerequisite_id not in nodes:
            raise bad_request("Some fields are invalid.", {"depends_on_id": "Must be a milestone in the same project."})
        if (milestone_id, prerequisite_id) in edges:
            raise conflict("That dependency already exists.")
        prerequisite = nodes[prerequisite_id]
        if scheduling.would_create_cycle(edges, milestone_id, prerequisite_id):
            raise conflict(f"That would create a circular chain: {prerequisite['name']} already depends on "
                           f"{milestone['name']}.")
        if milestone["status"] in ("in_progress", "done") and prerequisite["status"] != "done":
            raise conflict(f"{milestone['name']} has already started, so it can't wait on {prerequisite['name']}.")
        if milestone["start_date"] < prerequisite["end_date"]:
            raise conflict(f"{milestone['name']} starts before {prerequisite['name']} ends "
                           f"({prerequisite['end_date']}). Move it to start on or after that date first.",
                           {"required_start": prerequisite["end_date"]})
        cur.execute("INSERT INTO milestone_dependencies (milestone_id, depends_on_id) VALUES (%s, %s)",
                    (milestone_id, prerequisite_id))
        updated, _ = _load(cur, me, milestone_id)
        _log(cur, me, "milestone.dependency_added", updated,
             f"{me['name']} made {milestone['name']} depend on {prerequisite['name']}")
    return 201, updated


@router.route("DELETE", "/{id}/dependencies/{depends_on_id}", roles=MANAGERS)
def remove_dependency(req):
    me = req.user
    with db.transaction() as cur:
        milestone, _ = _for_write(cur, me, req.params["id"])
        cur.execute("DELETE FROM milestone_dependencies WHERE milestone_id = %s AND depends_on_id = %s",
                    (milestone["id"], req.params["depends_on_id"]))
        if cur.rowcount == 0:
            raise not_found("Dependency")
        _log(cur, me, "milestone.dependency_removed", milestone,
             f"{me['name']} removed a dependency from {milestone['name']}",
             {"depends_on_id": req.params["depends_on_id"]})
    return 204, None


# ---------- assignments (8-hour workday) ----------

@router.route("POST", "/{id}/assignments", roles=MANAGERS)
def assign_person(req):
    me = req.user
    data = validate(req.json(), ASSIGN_SCHEMA)
    hours = data.get("hours_per_day") or Decimal("8")
    with db.transaction() as cur:
        milestone, project = _for_write(cur, me, req.params["id"], "assign people")
        if milestone["status"] == "done":
            raise conflict("This milestone is already done.")
        cur.execute("SELECT u.id, u.name, u.role, u.is_active FROM project_members pm"
                    " JOIN users u ON u.id = pm.user_id WHERE pm.project_id = %s AND pm.user_id = %s",
                    (project["id"], data["user_id"]))
        user = cur.fetchone()
        if user is None:
            raise bad_request("Some fields are invalid.", {"user_id": "Add this person to the project team first."})
        if user["role"] != "employee" or not user["is_active"]:
            raise bad_request("Some fields are invalid.", {"user_id": "Only active employees can be assigned."})
        cur.execute("SELECT 1 FROM milestone_assignments WHERE milestone_id = %s AND user_id = %s",
                    (milestone["id"], user["id"]))
        if cur.fetchone():
            raise conflict(f"{user['name']} is already assigned. Update their hours instead.")
        _check_capacity(cur, user, milestone, hours)
        cur.execute("INSERT INTO milestone_assignments (milestone_id, user_id, hours_per_day, assigned_by)"
                    " VALUES (%s, %s, %s, %s)", (milestone["id"], user["id"], hours, me["id"]))
        updated, _ = _load(cur, me, milestone["id"])
        _log(cur, me, "milestone.assigned", updated,
             f"{me['name']} assigned {user['name']} to {milestone['name']} ({hours:g}h/day)",
             {"user_id": user["id"], "hours_per_day": hours})
    return 201, updated


@router.route("PUT", "/{id}/assignments/{user_id}", roles=MANAGERS)
def update_assignment(req):
    me = req.user
    data = validate(req.json(), HOURS_SCHEMA)
    with db.transaction() as cur:
        milestone, _ = _for_write(cur, me, req.params["id"], "assign people")
        cur.execute("SELECT u.id, u.name, ma.hours_per_day FROM milestone_assignments ma"
                    " JOIN users u ON u.id = ma.user_id WHERE ma.milestone_id = %s AND ma.user_id = %s",
                    (milestone["id"], req.params["user_id"]))
        user = cur.fetchone()
        if user is None:
            raise not_found("Assignment")
        _check_capacity(cur, user, milestone, data["hours_per_day"])
        cur.execute("UPDATE milestone_assignments SET hours_per_day = %s WHERE milestone_id = %s AND user_id = %s",
                    (data["hours_per_day"], milestone["id"], user["id"]))
        updated, _ = _load(cur, me, milestone["id"])
        _log(cur, me, "milestone.assignment_updated", updated,
             f"{me['name']} changed {user['name']}'s hours on {milestone['name']} to {data['hours_per_day']:g}h/day",
             {"changes": {"hours_per_day": {"from": user["hours_per_day"], "to": data["hours_per_day"]}}})
    return 200, updated


@router.route("DELETE", "/{id}/assignments/{user_id}", roles=MANAGERS)
def unassign_person(req):
    me = req.user
    with db.transaction() as cur:
        milestone, _ = _for_write(cur, me, req.params["id"], "assign people")
        cur.execute("DELETE FROM milestone_assignments WHERE milestone_id = %s AND user_id = %s RETURNING user_id",
                    (milestone["id"], req.params["user_id"]))
        if cur.fetchone() is None:
            raise not_found("Assignment")
        _log(cur, me, "milestone.unassigned", milestone,
             f"{me['name']} removed someone from {milestone['name']}", {"user_id": req.params["user_id"]})
    return 204, None


def handler(event, context=None):
    return router.handle(event, context)