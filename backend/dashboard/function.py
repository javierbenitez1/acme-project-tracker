"""Dashboard service: one call that powers the home screen for each role, plus the team workload
heatmap used to spot over-allocated people."""
from datetime import date, timedelta

from core import actions, db, scheduling
from core.http import Router
from core.metrics import HEALTH_ORDER, enrich
from core.projects import PROJECT_SELECT, load_project, visible_where
from core.validation import query_int

router = Router("dashboard")
UPCOMING_DAYS = 14
WEEK_CAPACITY = 40


def _activity_scope(me):
    """Admins see everything, managers see their projects and their own actions, employees see their
    projects' activity without financial line items."""
    if me["role"] == "admin":
        return "TRUE", []
    if me["role"] == "manager":
        return ("(a.actor_id = %s OR a.project_id IN (SELECT id FROM projects WHERE manager_id = %s))",
                [me["id"], me["id"]])
    return ("(a.project_id IN (SELECT project_id FROM project_members WHERE user_id = %s)"
            " AND a.entity_type <> 'budget_entry')", [me["id"]])


@router.route("GET", "")
def dashboard(req):
    me, today = req.user, date.today()
    where, params = visible_where(me)
    activity_where, activity_params = _activity_scope(me)
    with db.transaction() as cur:
        actions.sync(cur)

        cur.execute(f"{PROJECT_SELECT} WHERE {where} AND p.archived_at IS NULL", params)
        projects = [enrich(p, today) for p in cur.fetchall()]
        projects.sort(key=lambda p: (HEALTH_ORDER[p["health"]], p["end_date"]))

        cur.execute(
            "SELECT m.id, m.name, m.start_date, m.end_date, m.status, p.id AS project_id, p.name AS project_name"
            f" FROM milestones m JOIN projects p ON p.id = m.project_id WHERE {where} AND p.archived_at IS NULL"
            " AND m.status <> 'done' AND m.end_date <= %s ORDER BY m.end_date LIMIT 10",
            [*params, today + timedelta(days=UPCOMING_DAYS)])
        upcoming = cur.fetchall()
        for milestone in upcoming:
            milestone["is_overdue"] = milestone["end_date"] < today

        cur.execute(
            "SELECT d.id, d.title, d.status, d.status_note, d.due_date, m.id AS milestone_id, m.name AS milestone_name,"
            " p.id AS project_id, p.name AS project_name"
            " FROM deliverables d JOIN milestones m ON m.id = d.milestone_id JOIN projects p ON p.id = m.project_id"
            " WHERE d.assignee_id = %s AND d.status <> 'done' AND p.archived_at IS NULL"
            " ORDER BY d.due_date NULLS LAST, d.id LIMIT 10", (me["id"],))
        my_work = cur.fetchall()
        for item in my_work:
            item["is_overdue"] = item["due_date"] is not None and item["due_date"] < today

        cur.execute(
            "SELECT a.id, a.action, a.entity_type, a.entity_id, a.project_id, a.summary, a.created_at,"
            " u.name AS actor_name FROM activity_log a LEFT JOIN users u ON u.id = a.actor_id"
            f" WHERE {activity_where} ORDER BY a.created_at DESC, a.id DESC LIMIT 15", activity_params)
        recent_activity = cur.fetchall()

        cur.execute(
            "SELECT COUNT(*) FILTER (WHERE status IN ('open', 'in_progress')) AS open,"
            " COUNT(*) FILTER (WHERE status IN ('open', 'in_progress') AND priority = 'critical') AS critical"
            " FROM action_items WHERE assignee_id = %s", (me["id"],))
        my_actions = cur.fetchone()

    def count(health):
        return sum(1 for p in projects if p["health"] == health)

    kpis = {
        "active_projects": sum(1 for p in projects if p["health"] != "completed"),
        "on_track": count("on_track"), "at_risk": count("at_risk"), "off_track": count("off_track"),
        "overdue_milestones": sum(int(p["milestones_overdue"]) for p in projects),
        "budget_planned": round(sum(float(p["budget_planned"]) for p in projects), 2),
        "budget_spent": round(sum(p["budget_spent"] for p in projects), 2),
        "my_open_actions": my_actions["open"], "my_critical_actions": my_actions["critical"],
        "my_open_deliverables": len(my_work),
    }
    project_cards = [{k: p[k] for k in (
        "id", "name", "manager_name", "status", "health", "risk_reasons", "progress", "time_elapsed_pct",
        "budget_planned", "budget_spent", "budget_used_pct", "start_date", "end_date", "days_remaining",
        "milestone_count", "milestones_done", "member_count")} for p in projects]
    return 200, {"role": me["role"], "kpis": kpis, "projects": project_cards, "upcoming_milestones": upcoming,
                 "my_work": my_work, "recent_activity": recent_activity}


@router.route("GET", "/workload")
def workload(req):
    """Weekly hours booked per person against a 40-hour week. Filters: weeks (1 to 12, default 6), project_id"""
    me, today = req.user, date.today()
    weeks = query_int(req.query, "weeks", default=6, hi=12)
    project_id = query_int(req.query, "project_id")
    first_monday = today - timedelta(days=today.weekday())
    week_starts = [first_monday + timedelta(weeks=i) for i in range(weeks)]
    window_end = week_starts[-1] + timedelta(days=4)

    with db.transaction() as cur:
        clauses, params = ["u.is_active", "u.role = 'employee'"], []
        if me["role"] == "manager":
            clauses.append("(u.manager_id = %s OR EXISTS (SELECT 1 FROM project_members pm"
                           " JOIN projects p ON p.id = pm.project_id"
                           " WHERE pm.user_id = u.id AND p.manager_id = %s AND p.archived_at IS NULL))")
            params += [me["id"], me["id"]]
        elif me["role"] == "employee":
            clauses.append("u.id = %s")
            params.append(me["id"])
        if project_id:
            load_project(cur, me, project_id)  # 404 if the caller can't see it
            clauses.append("EXISTS (SELECT 1 FROM project_members pm WHERE pm.user_id = u.id AND pm.project_id = %s)")
            params.append(project_id)
        cur.execute(f"SELECT u.id, u.name, u.job_title FROM users u WHERE {' AND '.join(clauses)} ORDER BY u.name",
                    params)
        people = cur.fetchall()

        assignments = []
        if people:
            cur.execute(
                "SELECT ma.user_id, ma.hours_per_day, m.id AS milestone_id, m.name AS milestone_name,"
                " m.start_date, m.end_date, p.id AS project_id, p.name AS project_name"
                " FROM milestone_assignments ma JOIN milestones m ON m.id = ma.milestone_id"
                " JOIN projects p ON p.id = m.project_id"
                " WHERE ma.user_id = ANY(%s) AND m.status <> 'done' AND p.archived_at IS NULL"
                "   AND p.status <> 'completed' AND m.start_date <= %s AND m.end_date >= %s"
                " ORDER BY m.start_date",
                ([p["id"] for p in people], window_end, first_monday))
            assignments = cur.fetchall()

    rows = []
    for person in people:
        mine = [a for a in assignments if a["user_id"] == person["id"]]
        week_rows = []
        for week_start in week_starts:
            hours = round(scheduling.weekly_hours(mine, week_start), 1)
            week_rows.append({"week_start": week_start, "hours": hours, "capacity": WEEK_CAPACITY,
                              "utilization": round(100 * hours / WEEK_CAPACITY)})
        peak, peak_day = scheduling.peak_daily_load(mine, max(today, first_monday), window_end)
        rows.append({
            "user_id": person["id"], "name": person["name"], "job_title": person["job_title"],
            "weeks": week_rows, "peak_daily_hours": peak, "peak_day": peak_day,
            "over_allocated": peak > scheduling.WORKDAY_HOURS,
            "assignments": [{"milestone_id": a["milestone_id"], "milestone": a["milestone_name"],
                             "project_id": a["project_id"], "project": a["project_name"],
                             "hours_per_day": a["hours_per_day"], "start_date": a["start_date"],
                             "end_date": a["end_date"]} for a in mine],
        })
    rows.sort(key=lambda r: (-max(w["hours"] for w in r["weeks"]), r["name"]))
    return 200, {"week_starts": week_starts, "capacity_per_week": WEEK_CAPACITY, "people": rows}


def handler(event, context=None):
    return router.handle(event, context)