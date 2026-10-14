"""Weekly status report: the one-page RAG (red, amber, green) summary that steering committees read.
Each rating comes from live data with a stated reason, so nobody has to fill in a status by hand and
the colors can't drift from reality. Route: GET /projects/{id}/report, for the project's manager and
admins."""
from datetime import date

from . import actions, db, metrics, scheduling
from .projects import load_project, require_manager
from .risks import RISK_SELECT, _graph, finish as finish_risk

MANAGERS = ["admin", "manager"]
ORDER = {"green": 0, "amber": 1, "red": 2}
WORDS = {"green": "green", "amber": "amber", "red": "red"}
PRIORITY_ORDER = "CASE a.priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END"


def _rag(status, reason):
    return {"status": status, "reason": reason}


def _plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def _when(day):
    return f"{day:%b} {day.day}"


# ---------- ratings (pure, unit tested) ----------

def rate_schedule(project, forecast):
    if project["status"] == "completed":
        return _rag("green", "Complete")
    overdue = int(project.get("milestones_overdue") or 0)
    late = forecast["days_late"] if forecast.get("status") == "late" else 0
    gap = project["time_elapsed_pct"] - project["progress"]
    if project["days_remaining"] < 0:
        return _rag("red", f"Past its end date by {_plural(-project['days_remaining'], 'day')}")
    if overdue:
        return _rag("red", f"{_plural(overdue, 'overdue milestone')}")
    if late > 14:
        return _rag("red", f"Forecast to finish {late} days late")
    if late:
        return _rag("amber", f"Forecast to finish {late} days late")
    if gap >= 15:
        return _rag("amber", f"Behind plan: {project['progress']}% done with {project['time_elapsed_pct']}% of the time used")
    if int(project.get("milestones_blocked") or 0):
        return _rag("amber", f"{_plural(int(project['milestones_blocked']), 'blocked milestone')}")
    return _rag("green", "On plan" if forecast.get("status") != "on_time" else "Forecast to finish on time")


def rate_budget(project, forecast):
    planned, spent = float(project["budget_planned"] or 0), float(project["budget_spent"] or 0)
    if planned <= 0:
        return _rag("red", "Spending recorded with no budget") if spent > 0 else _rag("green", "No budget set")
    if spent > planned:
        return _rag("red", f"Over budget by ${spent - planned:,.0f}")
    projected = forecast.get("projected_total")
    if forecast.get("status") == "over" and projected and projected > planned * 1.10:
        return _rag("red", f"Forecast to spend ${projected:,.0f} against ${planned:,.0f}")
    if forecast.get("status") == "over":
        return _rag("amber", f"Forecast to spend ${projected:,.0f} against ${planned:,.0f}")
    if project["budget_used_pct"] - project["progress"] >= 15:
        return _rag("amber", f"Spending ahead of progress: {project['budget_used_pct']}% used, {project['progress']}% done")
    return _rag("green", f"{project['budget_used_pct']}% used with {project['progress']}% of the work done")


def rate_risks(risks):
    high = [r for r in risks if r["level"] == "high"]
    medium = [r for r in risks if r["level"] == "medium"]
    if high:
        return _rag("red", f"{_plural(len(high), 'high risk')} open")
    if medium:
        return _rag("amber", f"{_plural(len(medium), 'medium risk')} open")
    return _rag("green", "Only low risks open" if risks else "No open risks logged")


def rate_overall(schedule, budget, risks):
    parts = {"schedule": schedule, "budget": budget, "risks": risks}
    worst = max(parts.values(), key=lambda r: ORDER[r["status"]])["status"]
    drivers = [name for name, r in parts.items() if r["status"] == worst]
    reason = "All areas on track" if worst == "green" else "Driven by " + " and ".join(drivers)
    return _rag(worst, reason)


def summary(project, overall, forecast, critical_names, buffer_days, open_risks, attention):
    text = (f"{project['name']} is {WORDS[overall['status']]} overall. It is {project['progress']}% complete with "
            f"{project['time_elapsed_pct']}% of the time used")
    if forecast.get("status") == "late":
        text += (f", and at the current pace it finishes around {_when(forecast['projected_end'])}, "
                 f"{_plural(forecast['days_late'], 'day')} after its {_when(project['end_date'])} end date.")
    elif forecast.get("status") in ("on_time", "early"):
        text += f", and it is on pace to finish by its {_when(project['end_date'])} end date."
    else:
        text += f". It is due to finish on {_when(project['end_date'])}."
    if critical_names:
        buffer = "no buffer" if buffer_days <= 0 else f"{_plural(buffer_days, 'day')} of buffer"
        text += f" The critical path ({', '.join(critical_names)}) has {buffer}."
    text += f" {_plural(open_risks, 'open risk')} and {_plural(attention, 'item')} need attention."
    return text


# ---------- route ----------

def register(router):
    """Adds GET /projects/{id}/report to the projects service's router."""

    @router.route("GET", "/{id}/report", roles=MANAGERS)
    def status_report(req):
        me, today = req.user, date.today()
        with db.transaction() as cur:
            project = load_project(cur, me, req.params["id"])
            require_manager(me, project, "see its status report")
            actions.sync(cur)
            nodes, edges = _graph(cur, project["id"])
            path = scheduling.critical_path(nodes, edges, project["end_date"])
            cur.execute(f"{RISK_SELECT} WHERE r.project_id = %s AND r.status IN ('open', 'mitigating')", (project["id"],))
            risks = sorted((finish_risk(r) for r in cur.fetchall()), key=lambda r: (-r["score"], r["id"]))
            cur.execute("SELECT a.title, a.priority, a.due_date, u.name AS assignee_name FROM action_items a"
                        " LEFT JOIN users u ON u.id = a.assignee_id"
                        " WHERE a.project_id = %s AND a.status IN ('open', 'in_progress')"
                        f" ORDER BY {PRIORITY_ORDER}, a.due_date NULLS LAST, a.id", (project["id"],))
            attention = cur.fetchall()
        if project["status"] == "completed":
            forecast = {"status": "complete", "projected_end": None, "days_late": None}
        else:
            forecast = scheduling.delivery_forecast(project["progress"], project["start_date"], project["end_date"], today)
        spend = metrics.budget_forecast(float(project["budget_planned"] or 0), float(project["budget_spent"] or 0),
                                        project["start_date"], project["end_date"], today)
        schedule_rag, budget_rag, risk_rag = rate_schedule(project, forecast), rate_budget(project, spend), rate_risks(risks)
        overall = rate_overall(schedule_rag, budget_rag, risk_rag)
        critical = [nodes[nid]["name"] for nid in path["critical"]]
        milestones = sorted(nodes.values(), key=lambda m: (m["start_date"], m["id"]))
        return 200, {
            "generated_at": today,
            "project": {k: project[k] for k in ("id", "name", "manager_name", "department", "start_date", "end_date",
                                                 "status", "progress", "time_elapsed_pct", "days_remaining",
                                                 "budget_planned", "budget_spent", "budget_used_pct", "health")},
            "rag": {"overall": overall, "schedule": schedule_rag, "budget": budget_rag, "risks": risk_rag},
            "summary": summary(project, overall, forecast, critical, path["buffer_days"], len(risks), len(attention)),
            "forecast": forecast,
            "budget_forecast": spend,
            "milestones": [{"name": m["name"], "start_date": m["start_date"], "end_date": m["end_date"],
                            "status": m["status"], "slack_days": path["slack"].get(m["id"]),
                            "critical": m["id"] in path["critical"]} for m in milestones],
            "risks": [{k: r[k] for k in ("title", "category", "score", "level", "owner_name", "mitigation", "status")}
                      for r in risks[:6]],
            "attention": attention[:8],
        }