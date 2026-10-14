"""Projects service: admins create, reassign, archive, and restore projects; managers run their own
projects (team, dates, budget, completion); employees see the projects they're on."""
from core import activity, db
from core.errors import bad_request, conflict, forbidden, not_found
from core.http import Router
from core.metrics import HEALTH_ORDER, enrich
from core.projects import (PROJECT_SELECT, can_manage, fetch_project, load_project, require_active,
                           require_manager, visible_where)
from core.validation import F, validate

router = Router("projects")

EDITABLE_STATUSES = ["planning", "active", "on_hold"]
ALL_STATUSES = EDITABLE_STATUSES + ["completed"]
MAX_BUDGET = 999_999_999_999

FIELDS = {
    "name": F("str", required=True, max_len=150),
    "description": F("str", nullable=True, max_len=5000),
    "department": F("str", nullable=True, max_len=100),
    "manager_id": F("int", required=True, min=1),
    "start_date": F("date", required=True),
    "end_date": F("date", required=True),
    "budget_planned": F("number", min=0, max=MAX_BUDGET),
}
CREATE_SCHEMA = {**FIELDS, "status": F("enum", choices=["planning", "active"])}
UPDATE_SCHEMA = {
    **FIELDS,
    "budget_planned": F("number", required=True, min=0, max=MAX_BUDGET),
    "status": F("enum", required=True, choices=EDITABLE_STATUSES),
    "change_reason": F("str", max_len=1000),
}
REASON_SCHEMA = {"reason": F("str", max_len=1000)}

SORTS = {
    "end_date": lambda p: (p["end_date"], p["name"].lower()),
    "start_date": lambda p: (p["start_date"], p["name"].lower()),
    "name": lambda p: p["name"].lower(),
    "progress": lambda p: (p["progress"], p["name"].lower()),
    "health": lambda p: (HEALTH_ORDER[p["health"]], p["end_date"]),
}


def _choice(query, name, choices, default=None):
    value = query.get(name, default)
    if value is not None and value not in choices:
        raise bad_request("Invalid filter.", {name: f"Must be one of: {', '.join(choices)}."})
    return value


def _require_active_manager(cur, manager_id):
    cur.execute("SELECT role, is_active FROM users WHERE id = %s", (manager_id,))
    row = cur.fetchone()
    if row is None or row["role"] != "manager" or not row["is_active"]:
        raise bad_request("Some fields are invalid.", {"manager_id": "Must be an active manager."})


def _members(cur, project_id):
    cur.execute(
        "SELECT u.id, u.name, u.email, u.job_title, u.role, u.is_active, pm.added_at,"
        " (u.id = p.manager_id) AS is_manager"
        " FROM project_members pm"
        " JOIN users u ON u.id = pm.user_id"
        " JOIN projects p ON p.id = pm.project_id"
        " WHERE pm.project_id = %s ORDER BY is_manager DESC, u.name",
        (project_id,))
    return cur.fetchall()


@router.route("GET", "")
def list_projects(req):
    """Filters: archived=false|true|all, status, health, at_risk=true, manager_id, department, search, sort"""
    q = req.query
    where, params = visible_where(req.user)
    clauses = [where]
    archived = _choice(q, "archived", ["false", "true", "all"], "false")
    if archived == "false":
        clauses.append("p.archived_at IS NULL")
    elif archived == "true":
        clauses.append("p.archived_at IS NOT NULL")
    status = _choice(q, "status", ALL_STATUSES)
    if status:
        clauses.append("p.status = %s")
        params.append(status)
    if q.get("manager_id"):
        try:
            params.append(int(q["manager_id"]))
        except ValueError:
            raise bad_request("Invalid filter.", {"manager_id": "Must be a whole number."})
        clauses.append("p.manager_id = %s")
    if q.get("department"):
        clauses.append("p.department ILIKE %s")
        params.append(q["department"].strip())
    if q.get("search"):
        clauses.append("(p.name ILIKE %s OR p.description ILIKE %s OR mgr.name ILIKE %s)")
        params.extend([f"%{q['search'].strip()}%"] * 3)
    health = _choice(q, "health", list(HEALTH_ORDER))
    at_risk = _choice(q, "at_risk", ["true", "false"])
    sort = _choice(q, "sort", list(SORTS), "end_date")

    with db.transaction() as cur:
        cur.execute(f"{PROJECT_SELECT} WHERE {' AND '.join(clauses)}", params)
        projects = [enrich(p) for p in cur.fetchall()]
    if health:
        projects = [p for p in projects if p["health"] == health]
    if at_risk == "true":
        projects = [p for p in projects if p["health"] in ("at_risk", "off_track")]
    projects.sort(key=SORTS[sort])
    return 200, projects


@router.route("GET", "/{id}")
def get_project(req):
    project_id = req.params["id"]
    with db.transaction() as cur:
        project = load_project(cur, req.user, project_id)
        project["members"] = _members(cur, project_id)
        cur.execute(
            "SELECT dc.id, dc.entity_type, dc.entity_id, dc.old_start, dc.old_end, dc.new_start, dc.new_end,"
            " dc.reason, dc.changed_at, u.name AS changed_by_name"
            " FROM date_changes dc LEFT JOIN users u ON u.id = dc.changed_by"
            " WHERE dc.project_id = %s ORDER BY dc.changed_at DESC",
            (project_id,))
        project["date_changes"] = cur.fetchall()
        cur.execute(
            "SELECT bc.id, bc.old_amount, bc.new_amount, bc.reason, bc.changed_at, u.name AS changed_by_name"
            " FROM budget_changes bc LEFT JOIN users u ON u.id = bc.changed_by"
            " WHERE bc.project_id = %s ORDER BY bc.changed_at DESC",
            (project_id,))
        project["budget_changes"] = cur.fetchall()
        project["archived_by_name"] = None
        if project["archived_by"]:
            cur.execute("SELECT name FROM users WHERE id = %s", (project["archived_by"],))
            project["archived_by_name"] = cur.fetchone()["name"]
        project["can_manage"] = can_manage(req.user, project)
    return 200, project


@router.route("POST", "", roles=["admin"])
def create_project(req):
    data = validate(req.json(), CREATE_SCHEMA)
    if data["end_date"] < data["start_date"]:
        raise bad_request("Some fields are invalid.", {"end_date": "Must be on or after the start date."})
    with db.transaction() as cur:
        _require_active_manager(cur, data["manager_id"])
        cur.execute(
            "INSERT INTO projects (name, description, department, manager_id, start_date, end_date,"
            " budget_planned, status, created_by) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (data["name"], data.get("description"), data.get("department"), data["manager_id"],
             data["start_date"], data["end_date"], data.get("budget_planned", 0),
             data.get("status", "planning"), req.user["id"]))
        project_id = cur.fetchone()["id"]
        # The manager is always part of their own project team
        cur.execute("INSERT INTO project_members (project_id, user_id, added_by) VALUES (%s, %s, %s)",
                    (project_id, data["manager_id"], req.user["id"]))
        project = fetch_project(cur, project_id)
        activity.log(cur, req.user["id"], "project.created", "project",
                     f"{req.user['name']} created project {project['name']} for {project['manager_name']}",
                     entity_id=project_id, project_id=project_id,
                     details={"manager_id": project["manager_id"], "start_date": project["start_date"],
                              "end_date": project["end_date"], "budget_planned": project["budget_planned"]})
    return 201, project


@router.route("PUT", "/{id}", roles=["admin", "manager"])
def update_project(req):
    me, project_id = req.user, req.params["id"]
    body = req.json()
    unknown = set(body) - set(UPDATE_SCHEMA)
    if unknown:
        raise bad_request("Some fields are invalid.", {k: "Unknown field." for k in unknown})
    with db.transaction() as cur:
        project = load_project(cur, me, project_id)
        require_manager(me, project)
        require_active(project)
        if me["role"] != "admin" and "manager_id" in body:
            raise forbidden("Only an admin can reassign a project to a different manager.")
        data = validate(body, UPDATE_SCHEMA, partial=True)
        reason = data.pop("change_reason", None)
        if not data:
            raise bad_request("Nothing to update.")

        new_start = data.get("start_date", project["start_date"])
        new_end = data.get("end_date", project["end_date"])
        if new_end < new_start:
            raise bad_request("Some fields are invalid.", {"end_date": "Must be on or after the start date."})
        dates_changed = (new_start, new_end) != (project["start_date"], project["end_date"])
        budget_changed = "budget_planned" in data and data["budget_planned"] != project["budget_planned"]
        if (dates_changed or budget_changed) and not reason:
            raise bad_request("Please explain why the dates or budget are changing.",
                              {"change_reason": "Required when changing dates or budget."})

        if dates_changed:
            cur.execute("SELECT name FROM milestones WHERE project_id = %s AND (start_date < %s OR end_date > %s)"
                        " ORDER BY start_date", (project_id, new_start, new_end))
            outside = [row["name"] for row in cur.fetchall()]
            if outside:
                raise conflict("Some milestones fall outside the new project dates. Adjust them first.",
                               {"milestones": outside})
            cur.execute(
                "INSERT INTO date_changes (entity_type, entity_id, project_id, old_start, old_end, new_start,"
                " new_end, reason, changed_by) VALUES ('project', %s, %s, %s, %s, %s, %s, %s, %s)",
                (project_id, project_id, project["start_date"], project["end_date"], new_start, new_end,
                 reason, me["id"]))
        if budget_changed:
            cur.execute("INSERT INTO budget_changes (project_id, old_amount, new_amount, reason, changed_by)"
                        " VALUES (%s, %s, %s, %s, %s)",
                        (project_id, project["budget_planned"], data["budget_planned"], reason, me["id"]))
        if data.get("manager_id", project["manager_id"]) != project["manager_id"]:
            _require_active_manager(cur, data["manager_id"])
            cur.execute("DELETE FROM project_members WHERE project_id = %s AND user_id = %s",
                        (project_id, project["manager_id"]))
            cur.execute("INSERT INTO project_members (project_id, user_id, added_by) VALUES (%s, %s, %s)"
                        " ON CONFLICT DO NOTHING", (project_id, data["manager_id"], me["id"]))

        # Column names come only from the whitelisted schema, never from user input
        assignments = ", ".join(f"{column} = %s" for column in data)
        cur.execute(f"UPDATE projects SET {assignments}, updated_at = NOW() WHERE id = %s",
                    [*data.values(), project_id])
        updated = fetch_project(cur, project_id)
        changes = activity.diff(project, updated, list(data))
        details = {"changes": changes, **({"reason": reason} if reason else {})}
        activity.log(cur, me["id"], "project.updated", "project",
                     f"{me['name']} updated {updated['name']} ({', '.join(sorted(changes)) or 'no changes'})",
                     entity_id=project_id, project_id=project_id, details=details)
    return 200, updated


@router.route("DELETE", "/{id}")
def archive_project(req):
    """DELETE never removes data. It archives the project (admin only), and an admin can restore it."""
    me, project_id = req.user, req.params["id"]
    if me["role"] != "admin":
        raise forbidden("Projects can't be deleted. Only an admin can archive a project.")
    data = validate(req.json(), REASON_SCHEMA)
    with db.transaction() as cur:
        project = load_project(cur, me, project_id)
        if project["archived_at"] is None:
            cur.execute("UPDATE projects SET archived_at = NOW(), archived_by = %s, archive_reason = %s,"
                        " updated_at = NOW() WHERE id = %s", (me["id"], data.get("reason"), project_id))
            activity.log(cur, me["id"], "project.archived", "project",
                         f"{me['name']} archived {project['name']}", entity_id=project_id, project_id=project_id,
                         details={"reason": data.get("reason")} if data.get("reason") else None)
    return 204, None


@router.route("POST", "/{id}/restore", roles=["admin"])
def restore_project(req):
    me, project_id = req.user, req.params["id"]
    data = validate(req.json(), REASON_SCHEMA)
    with db.transaction() as cur:
        project = load_project(cur, me, project_id)
        if project["archived_at"] is None:
            raise conflict("This project isn't archived.")
        cur.execute("UPDATE projects SET archived_at = NULL, archived_by = NULL, archive_reason = NULL,"
                    " status = CASE WHEN status = 'completed' THEN 'active' ELSE status END, updated_at = NOW()"
                    " WHERE id = %s", (project_id,))
        restored = fetch_project(cur, project_id)
        activity.log(cur, me["id"], "project.restored", "project", f"{me['name']} restored {project['name']}",
                     entity_id=project_id, project_id=project_id,
                     details={"reason": data.get("reason")} if data.get("reason") else None)
    return 200, restored


@router.route("POST", "/{id}/complete", roles=["admin", "manager"])
def complete_project(req):
    """Marks a project done and archives it, but only once every milestone is done."""
    me, project_id = req.user, req.params["id"]
    data = validate(req.json(), REASON_SCHEMA)
    with db.transaction() as cur:
        project = load_project(cur, me, project_id)
        require_manager(me, project, "complete it")
        require_active(project)
        if project["milestone_count"] == 0:
            raise conflict("Add at least one milestone before completing this project.")
        cur.execute("SELECT name FROM milestones WHERE project_id = %s AND status <> 'done' ORDER BY end_date",
                    (project_id,))
        open_milestones = [row["name"] for row in cur.fetchall()]
        if open_milestones:
            raise conflict(f"{len(open_milestones)} milestone(s) are still open.",
                           {"open_milestones": open_milestones})
        cur.execute("UPDATE projects SET status = 'completed', archived_at = NOW(), archived_by = %s,"
                    " archive_reason = %s, updated_at = NOW() WHERE id = %s",
                    (me["id"], data.get("reason") or "Completed: all milestones done", project_id))
        completed = fetch_project(cur, project_id)
        activity.log(cur, me["id"], "project.completed", "project",
                     f"{me['name']} marked {project['name']} complete", entity_id=project_id, project_id=project_id)
    return 200, completed


@router.route("GET", "/{id}/members")
def list_members(req):
    with db.transaction() as cur:
        load_project(cur, req.user, req.params["id"])
        return 200, _members(cur, req.params["id"])


@router.route("POST", "/{id}/members", roles=["admin", "manager"])
def add_members(req):
    me, project_id = req.user, req.params["id"]
    data = validate(req.json(), {"user_ids": F("ids", required=True, max_len=50)})
    with db.transaction() as cur:
        project = load_project(cur, me, project_id)
        require_manager(me, project, "change its team")
        require_active(project)
        cur.execute("SELECT id, name, role, is_active FROM users WHERE id = ANY(%s)", (data["user_ids"],))
        found = {row["id"]: row for row in cur.fetchall()}
        problems = {}
        for user_id in data["user_ids"]:
            user = found.get(user_id)
            if user is None:
                problems[str(user_id)] = "User not found."
            elif not user["is_active"]:
                problems[str(user_id)] = f"{user['name']} is deactivated."
            elif user["role"] != "employee":
                problems[str(user_id)] = f"{user['name']} is not an employee."
        if problems:
            raise bad_request("Some users can't be added to this project.", {"user_ids": problems})
        added = []
        for user_id in data["user_ids"]:
            cur.execute("INSERT INTO project_members (project_id, user_id, added_by) VALUES (%s, %s, %s)"
                        " ON CONFLICT DO NOTHING RETURNING user_id", (project_id, user_id, me["id"]))
            if cur.fetchone():
                added.append(found[user_id]["name"])
        if added:
            activity.log(cur, me["id"], "project.members_added", "project",
                         f"{me['name']} added {', '.join(added)} to {project['name']}",
                         entity_id=project_id, project_id=project_id, details={"added": added})
        return 201, _members(cur, project_id)


@router.route("DELETE", "/{id}/members/{user_id}", roles=["admin", "manager"])
def remove_member(req):
    me, project_id, user_id = req.user, req.params["id"], req.params["user_id"]
    with db.transaction() as cur:
        project = load_project(cur, me, project_id)
        require_manager(me, project, "change its team")
        require_active(project)
        if user_id == project["manager_id"]:
            raise bad_request("The project manager can't be removed from their own project.")
        cur.execute("SELECT u.name FROM project_members pm JOIN users u ON u.id = pm.user_id"
                    " WHERE pm.project_id = %s AND pm.user_id = %s", (project_id, user_id))
        member = cur.fetchone()
        if member is None:
            raise not_found("Team member")
        cur.execute(
            "SELECT"
            " (SELECT COUNT(*) FROM milestone_assignments ma JOIN milestones m ON m.id = ma.milestone_id"
            "   WHERE m.project_id = %s AND ma.user_id = %s AND m.status <> 'done') AS assignments,"
            " (SELECT COUNT(*) FROM deliverables d JOIN milestones m ON m.id = d.milestone_id"
            "   WHERE m.project_id = %s AND d.assignee_id = %s AND d.status <> 'done') AS deliverables",
            (project_id, user_id, project_id, user_id))
        work = cur.fetchone()
        if work["assignments"] or work["deliverables"]:
            raise conflict(
                f"{member['name']} still has {work['assignments']} milestone assignment(s) and "
                f"{work['deliverables']} open deliverable(s) on this project. Reassign them first.",
                dict(work))
        cur.execute("DELETE FROM project_members WHERE project_id = %s AND user_id = %s", (project_id, user_id))
        activity.log(cur, me["id"], "project.member_removed", "project",
                     f"{me['name']} removed {member['name']} from {project['name']}",
                     entity_id=project_id, project_id=project_id)
    return 204, None


from core import risks as risk_register  # noqa: E402 (adds the /projects/risks routes to this router)

risk_register.register(router)


def handler(event, context=None):
    return router.handle(event, context)
