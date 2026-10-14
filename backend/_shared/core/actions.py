"""Action Center rules. Each rule finds a situation that needs someone's attention, and sync() turns
the current findings into action items: new problems get an item, problems that come back reopen
their item, and items whose problem was fixed close themselves."""
from datetime import date, timedelta

from . import activity, metrics, scheduling
from .projects import PROJECT_SELECT

ACTIVE_PROJECT = "p.archived_at IS NULL AND p.status <> 'completed'"
LOOKAHEAD_DAYS = 30


def _item(rule_key, title, description, priority, assignee_id, project_id=None,
          entity_type=None, entity_id=None, due_date=None):
    return {"rule_key": rule_key, "title": title[:200], "description": description, "priority": priority,
            "assignee_id": assignee_id, "project_id": project_id, "entity_type": entity_type,
            "entity_id": entity_id, "due_date": due_date}


def _project_findings(cur, today):
    cur.execute(f"{PROJECT_SELECT} WHERE {ACTIVE_PROJECT}")
    found = []
    for p in cur.fetchall():
        p = metrics.enrich(p, today)
        if p["days_remaining"] < 0:
            found.append(_item(
                f"project_overdue:{p['id']}", f"{p['name']} is past its end date",
                f"It was due {p['end_date']} and is {p['progress']}% complete. Finish the remaining work "
                "or extend the dates with a reason.",
                "critical", p["manager_id"], p["id"], "project", p["id"], today))
        planned, spent = float(p["budget_planned"]), float(p["budget_spent"])
        if planned > 0 and spent > planned:
            found.append(_item(
                f"project_over_budget:{p['id']}", f"{p['name']} is over budget",
                f"${spent:,.0f} spent against a ${planned:,.0f} plan (${spent - planned:,.0f} over). "
                "Review the spending or adjust the budget with a reason.",
                "critical", p["manager_id"], p["id"], "project", p["id"], today))
        if p["milestone_count"] and p["milestones_done"] == p["milestone_count"]:
            found.append(_item(
                f"project_ready:{p['id']}", f"{p['name']} is ready to complete",
                "Every milestone is done. Mark the project complete to archive it.",
                "medium", p["manager_id"], p["id"], "project", p["id"]))
    return found


def _milestone_findings(cur, today):
    cur.execute(
        "SELECT m.id, m.name, m.status, m.start_date, m.end_date, p.id AS project_id, p.name AS project_name,"
        " p.manager_id,"
        " (SELECT COUNT(*) FROM deliverables d WHERE d.milestone_id = m.id) AS total,"
        " (SELECT COUNT(*) FROM deliverables d WHERE d.milestone_id = m.id AND d.status <> 'done') AS open,"
        " (SELECT COUNT(*) FROM milestone_dependencies md JOIN milestones x ON x.id = md.depends_on_id"
        "   WHERE md.milestone_id = m.id AND x.status <> 'done') AS waiting"
        f" FROM milestones m JOIN projects p ON p.id = m.project_id WHERE {ACTIVE_PROJECT} AND m.status <> 'done'")
    found = []
    for m in cur.fetchall():
        label = f"{m['name']} ({m['project_name']})"
        if m["end_date"] < today:
            found.append(_item(
                f"milestone_overdue:{m['id']}", f"{label} is overdue",
                f"It was due {m['end_date']}. Finish it or move its dates with a reason "
                "(later milestones can shift automatically).",
                "high", m["manager_id"], m["project_id"], "milestone", m["id"], today))
        if m["total"] and not m["open"]:
            found.append(_item(
                f"milestone_ready_to_close:{m['id']}", f"{label} is ready to close",
                f"All {m['total']} deliverable(s) are done. Mark the milestone done.",
                "medium", m["manager_id"], m["project_id"], "milestone", m["id"]))
        elif m["status"] == "not_started" and not m["waiting"] and m["start_date"] <= today:
            found.append(_item(
                f"milestone_ready_to_start:{m['id']}", f"{label} can start",
                f"Its start date ({m['start_date']}) has arrived and nothing is blocking it. "
                "Assign people and get work moving.",
                "low", m["manager_id"], m["project_id"], "milestone", m["id"]))
    return found


def _deliverable_findings(cur, today):
    cur.execute(
        "SELECT d.id, d.title, d.status, d.status_note, d.due_date, d.assignee_id, u.name AS assignee_name,"
        " m.name AS milestone_name, p.id AS project_id, p.name AS project_name, p.manager_id"
        " FROM deliverables d JOIN milestones m ON m.id = d.milestone_id JOIN projects p ON p.id = m.project_id"
        " LEFT JOIN users u ON u.id = d.assignee_id"
        f" WHERE {ACTIVE_PROJECT} AND d.status <> 'done' AND (d.status = 'blocked' OR d.due_date < %s)", (today,))
    found = []
    for d in cur.fetchall():
        if d["status"] == "blocked":
            who = d["assignee_name"] or "Someone"
            found.append(_item(
                f"deliverable_blocked:{d['id']}", f"{d['title']} is blocked",
                f"{who} reported on {d['milestone_name']} ({d['project_name']}): {d['status_note']}",
                "high", d["manager_id"], d["project_id"], "deliverable", d["id"]))
        if d["due_date"] and d["due_date"] < today:
            found.append(_item(
                f"deliverable_overdue:{d['id']}", f"{d['title']} is overdue",
                f"It was due {d['due_date']} on {d['milestone_name']} ({d['project_name']}). "
                "Finish it or ask your manager to move the date.",
                "medium", d["assignee_id"] or d["manager_id"], d["project_id"], "deliverable", d["id"], today))
    return found


def _workload_findings(cur, today):
    horizon = today + timedelta(days=LOOKAHEAD_DAYS)
    cur.execute(
        "SELECT ma.user_id, u.name, u.manager_id, m.start_date, m.end_date, ma.hours_per_day"
        " FROM milestone_assignments ma JOIN users u ON u.id = ma.user_id"
        " JOIN milestones m ON m.id = ma.milestone_id JOIN projects p ON p.id = m.project_id"
        f" WHERE {ACTIVE_PROJECT} AND m.status <> 'done' AND u.is_active"
        "   AND m.end_date >= %s AND m.start_date <= %s", (today, horizon))
    by_user = {}
    for row in cur.fetchall():
        by_user.setdefault(row["user_id"], []).append(row)
    found = []
    for user_id, rows in by_user.items():
        peak, day = scheduling.peak_daily_load(rows, today, horizon)
        if peak > scheduling.WORKDAY_HOURS and rows[0]["manager_id"]:
            found.append(_item(
                f"overloaded:{user_id}", f"{rows[0]['name']} is over-allocated",
                f"Booked {peak:g} hours on {day}, over the 8-hour workday. Reduce their hours or move a milestone.",
                "high", rows[0]["manager_id"], entity_type="user", entity_id=user_id, due_date=day))
    return found


def _risk_findings(cur, today):
    """Risks whose review date has passed get a reminder for their owner, or the manager if there's none."""
    cur.execute(
        "SELECT r.id, r.title, r.review_date, r.likelihood, r.impact, r.owner_id, p.id AS project_id,"
        " p.name AS project_name, p.manager_id FROM risks r JOIN projects p ON p.id = r.project_id"
        f" WHERE {ACTIVE_PROJECT} AND r.status IN ('open', 'mitigating') AND r.review_date < %s", (today,))
    found = []
    for r in cur.fetchall():
        found.append(_item(
            f"risk_review_overdue:{r['id']}", f"Review the risk: {r['title']} ({r['project_name']})",
            f"Its review date ({r['review_date']}) has passed. Check whether the likelihood or impact changed, "
            "then update the plan or close the risk.",
            "high" if r["likelihood"] * r["impact"] >= 15 else "medium",
            r["owner_id"] or r["manager_id"], r["project_id"], "risk", r["id"], today))
    return found


def sync(cur, today=None):
    """Brings action items in line with the current state of every active project."""
    today = today or date.today()
    # If another request is already refreshing the items, skip instead of queueing behind it.
    # Under load, waiting here made every dashboard request line up (found by the load test).
    cur.execute("SELECT pg_try_advisory_xact_lock(777001) AS acquired")
    if not cur.fetchone()["acquired"]:
        return
    findings = (_project_findings(cur, today) + _milestone_findings(cur, today)
                + _deliverable_findings(cur, today) + _workload_findings(cur, today)
                + _risk_findings(cur, today))
    if findings:
        cur.executemany(
            "INSERT INTO action_items (title, description, priority, source, rule_key, assignee_id, project_id,"
            " entity_type, entity_id, due_date)"
            " VALUES (%(title)s, %(description)s, %(priority)s, 'system', %(rule_key)s, %(assignee_id)s,"
            " %(project_id)s, %(entity_type)s, %(entity_id)s, %(due_date)s)"
            " ON CONFLICT (rule_key) DO UPDATE SET"
            "   title = EXCLUDED.title, description = EXCLUDED.description, priority = EXCLUDED.priority,"
            "   assignee_id = EXCLUDED.assignee_id, due_date = EXCLUDED.due_date,"
            "   status = CASE WHEN action_items.status = 'done' THEN 'open' ELSE action_items.status END,"
            "   resolved_at = CASE WHEN action_items.status = 'done' THEN NULL ELSE action_items.resolved_at END,"
            "   resolved_by = CASE WHEN action_items.status = 'done' THEN NULL ELSE action_items.resolved_by END,"
            "   resolution_note = CASE WHEN action_items.status = 'done' THEN NULL"
            "                          ELSE action_items.resolution_note END,"
            "   updated_at = CASE WHEN action_items.status = 'done' THEN NOW() ELSE action_items.updated_at END",
            findings)
    # Anything still open whose problem no longer exists has been fixed: close it and record that
    cur.execute(
        "UPDATE action_items SET status = 'done', resolved_at = NOW(), resolved_by = NULL,"
        " resolution_note = 'Resolved automatically: the problem was fixed.', updated_at = NOW()"
        " WHERE source = 'system' AND status IN ('open', 'in_progress') AND NOT (rule_key = ANY(%s))"
        " RETURNING id, title, project_id", ([f["rule_key"] for f in findings],))
    for closed in cur.fetchall():
        activity.log(cur, None, "action.auto_resolved", "action_item", f"Resolved automatically: {closed['title']}",
                     entity_id=closed["id"], project_id=closed["project_id"])