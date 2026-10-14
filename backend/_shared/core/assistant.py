"""Ask Throughline: an assistant that answers plain-English questions from live project data.

It is deliberately rule-based, not a generative AI model. Questions are matched to an intent with
keyword rules, projects and people are recognised by name, and every answer is assembled from the
same queries and permission checks the rest of the app uses, so it can't invent facts or show
anything the person couldn't already see. All the decision logic lives in pure functions that are
unit tested, and answer() is the single entry point, so a model such as Claude on Amazon Bedrock
could be added behind the same API later."""
import re
from datetime import date, timedelta

from . import db, metrics, scheduling
from .projects import PROJECT_SELECT, visible_where
from .risks import RISK_SELECT, finish as finish_risk
from .validation import F, validate

WORKLOAD_DAYS = 14
DUE_SOON_DAYS = 7
MAX_ITEMS = 6
HEALTH_WORDS = {"on_track": "on track", "at_risk": "at risk", "off_track": "off track",
                "completed": "completed", "archived": "archived"}

# ---------- understanding the question (pure, unit tested) ----------

INTENTS = [
    ("help", ["how do i", "how can i", "how to ", "how does", "where do i", "where can i", "why cant", "why can t",
              "why wont", "what does", "what is a ", "whats a ", "explain"]),
    ("my_work", ["my work", "should i work", "assigned to me", "my tasks", "my deliverables", "on my plate",
                 "what do i have", "what am i"]),
    ("workload", ["overbook", "over book", "overload", "over allocat", "overallocat", "capacity", "workload",
                  "busy", " free ", "available", "bandwidth", "booked"]),
    ("blocked", ["block", "stuck", "waiting on"]),
    ("overdue", ["overdue", " late", "missed", "past due"]),
    ("budget", ["budget", " spend", " spent", " cost", "money", " burn", "dollar"]),
    ("due_soon", ["due", "this week", "next week", "upcoming", "coming up", "deadline"]),
    ("risks", [" risk", "off track", "trouble", "worr", "concern", "danger", "threat", "behind", "problem"]),
    ("team", ["team", "who is on", "whos on", "members", "who is working", "whos working", "people on"]),
    ("status", ["status", "how is", "hows", "doing", "progress", "update", "overview", "summary", "going",
                "tell me about"]),
    ("thanks", [" thanks ", " thank you ", " thx ", " cheers "]),
    ("greeting", [" hi ", " hello ", " hey ", "what can you do", " good morning ", " good afternoon ", " help "]),
]

STOPWORDS = {"the", "and", "for", "with", "project", "projects", "new", "phase", "from", "into", "this", "that",
             "time", "real", "work", "team", "plan", "next", "week", "date", "data", "risk", "risks", "budget",
             "status", "review", "doing", "going", "about", "what", "which", "where"}


def normalize(text):
    """Lowercase, drop apostrophes ("who's" becomes "whos") and punctuation, and pad with spaces."""
    text = text.lower().replace("\u2019", "'").replace("'", "")
    return " " + " ".join(re.sub(r"[^a-z0-9$]+", " ", text).split()) + " "


def classify(question):
    """Returns the first intent whose phrases appear in the question, or None."""
    text = normalize(question)
    for intent, phrases in INTENTS:
        if any(phrase in text for phrase in phrases):
            return intent
    return None


def _tokens(text):
    return set(normalize(text).split())


def _token_hit(token, words):
    return token in words or (len(token) >= 5 and any(w[:5] == token[:5] for w in words if len(w) >= 5))


def match_project(question, projects):
    """Finds the project the question names, by full name or by its distinctive words ("kiosk")."""
    text, words = normalize(question), _tokens(question)
    best, best_score = None, 0
    for project in projects:
        name = normalize(project["name"])
        score = 100 if name.strip() and name in text else sum(
            1 for t in name.split() if len(t) >= 4 and t not in STOPWORDS and _token_hit(t, words))
        if score > best_score:
            best, best_score = project, score
    return best


def match_person(question, people):
    """Finds a person named in the question by first name or full name."""
    words = _tokens(question)
    for person in people:
        parts = normalize(person["name"]).split()
        if parts and (parts[0] in words or " ".join(parts) in normalize(question)):
            return person
    return None


HELP_TOPICS = [
    {"keys": {"reschedule", "move", "date", "dates", "push", "delay", "extend", "deadline", "slip"},
     "title": "Rescheduling a milestone",
     "text": "Open the project, go to the **Milestones** tab and choose **Edit** on the milestone. Change its dates "
             "and give a reason. Before anything is saved, Throughline previews every later milestone that has to "
             "move with it, and if the chain runs past the project end date you can extend the project in the same "
             "step. Only the project's manager or an admin can do this, and the reason shows in the History tab.",
     "link": ("Projects", "/projects")},
    {"keys": {"assign", "assigned", "book", "hours", "eight", "8", "capacity", "allocate", "cant", "wont"},
     "title": "Assigning people and the 8-hour rule",
     "text": "Use **Assign** on a milestone and choose how many hours a day the person works on it. Throughline "
             "checks their busiest weekday across every project, and nobody can go over 8 hours a day. If it refuses, "
             "the message says what they're already booked on: lower their hours elsewhere, or pick someone with "
             "free time. The **Workload** page shows who has room.",
     "link": ("Workload", "/workload")},
    {"keys": {"add", "people", "person", "team", "member", "members", "join", "staff"},
     "title": "Adding people to a project",
     "text": "On the project's **Team** tab, choose **Add people**. Employees from any manager's team can join, and "
             "who they report to doesn't change. Then assign them to milestones with their hours per day.",
     "link": ("Projects", "/projects")},
    {"keys": {"budget", "spend", "spending", "expense", "cost", "costs", "record", "adjust", "money"},
     "title": "Budgets and spending",
     "text": "On the project's **Budget** tab, managers record spending by category and can **Adjust budget**. "
             "Every change needs a reason, which is saved to the history. The burn chart compares spending with the "
             "plan and forecasts where it will land. Employees see progress but not spending.",
     "link": ("Projects", "/projects")},
    {"keys": {"archive", "archived", "restore", "delete", "deleted", "unarchive", "recover", "remove"},
     "title": "Archiving and restoring",
     "text": "Projects are never deleted. An admin archives a project instead, and can bring it back from the "
             "**Archive** page with **Restore**. People are deactivated rather than deleted, so history stays intact.",
     "link": ("Archive", "/archive")},
    {"keys": {"complete", "finish", "close", "closing", "done", "wrap"},
     "title": "Completing a project",
     "text": "When every milestone is done, the project's manager can use **Complete project** on the Overview tab. "
             "The Action Center also reminds them when a project is ready. Completed projects move to the Archive.",
     "link": ("Projects", "/projects")},
    {"keys": {"risk", "risks", "register", "mitigation", "matrix", "likelihood", "impact"},
     "title": "The risk register",
     "text": "Each project has a **Risks** tab. Risks are scored by likelihood and impact from 1 to 5 each, and every "
             "risk has an owner, a mitigation plan and a review date. Throughline also suggests risks from live "
             "signals, like no buffer on the critical path, and a passed review date shows up in the Action Center.",
     "link": ("Projects", "/projects")},
    {"keys": {"blocked", "block", "stuck", "mark", "status", "update", "waiting"},
     "title": "Marking work as blocked",
     "text": "Open **My work** (or the project's Milestones tab), set the deliverable to **Blocked**, and say what "
             "you're waiting on. Your manager gets an Action Center item straight away, and it closes itself once "
             "the work is unblocked.",
     "link": ("My work", "/my-work")},
    {"keys": {"password", "login", "sign", "signin", "email", "name", "profile", "account"},
     "title": "Your profile and password",
     "text": "Choose your name in the menu, then **Your profile**. You can change your name, email and password "
             "there. Changing your password signs you out on other devices.",
     "link": ("Your profile", "/profile")},
    {"keys": {"user", "users", "employee", "manager", "create", "deactivate", "reactivate", "hire"},
     "title": "Managing people",
     "text": "Admins add people, change roles and deactivate accounts on the **People** page. Managers can edit their "
             "direct reports' name, email and job title. A manager can't be deactivated while they still run active "
             "projects or have direct reports.",
     "link": ("People", "/people")},
    {"keys": {"action", "actions", "center", "item", "items", "dismiss", "task", "tasks", "todo"},
     "title": "The Action Center",
     "text": "The **Action Center** lists what needs attention: overdue work, budgets over plan, blocked items, "
             "over-allocated people and risks due for review. Rules open items automatically and close them once the "
             "problem is fixed. Closing one by hand needs a short note, so there's always a record.",
     "link": ("Action Center", "/actions")},
    {"keys": {"audit", "history", "log", "changed", "changes", "who"},
     "title": "History and the audit log",
     "text": "Every project has a **History** tab with each change and its reason. Admins also have the **Audit** "
             "page, which shows every change across the app with before and after values.",
     "link": ("Audit log", "/audit")},
    {"keys": {"critical", "path", "slack", "buffer", "timeline", "forecast", "gantt"},
     "title": "The critical path and forecast",
     "text": "The **Timeline** tab highlights the critical path: the milestones where any delay moves the project "
             "end date. Every other milestone shows how many days it can slip. The forecast on the Overview tab "
             "projects the finish date from the pace of work so far.",
     "link": ("Projects", "/projects")},
]


def match_help(question):
    """Picks the help topic sharing the most words with the question."""
    words = _tokens(question)
    best, best_score = None, 0
    for topic in HELP_TOPICS:
        score = len(topic["keys"] & words)
        if score > best_score:
            best, best_score = topic, score
    return best


# ---------- writing answers (pure, unit tested) ----------

def when(day, today):
    delta = (day - today).days
    label = f"{day:%b} {day.day}"
    if delta == 0:
        return f"{label} (today)"
    if delta == 1:
        return f"{label} (tomorrow)"
    if delta == -1:
        return f"{label} (yesterday)"
    return f"{label} ({delta} days from now)" if delta > 0 else f"{label} ({-delta} days ago)"


def plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def reply(text, links=(), follow_ups=(), project=None, intent=None):
    return {"text": text, "links": [{"label": label, "to": to} for label, to in links],
            "follow_ups": list(follow_ups), "project_id": project["id"] if project else None, "intent": intent}


def suggestions(role, project=None):
    if project:
        short = project["name"].split()[0] if len(project["name"].split()) > 1 else project["name"]
        items = [f"How is {project['name']} doing?", f"What's blocking {short}?", f"What are the risks on {short}?",
                 "Who's on the team?"]
        return items if role != "employee" else items[:2] + ["What should I work on?"]
    if role == "employee":
        return ["What should I work on?", "What's due this week?", "What's blocked?", "How do I mark something blocked?"]
    return ["Which projects are at risk?", "Who's overbooked?", "What's overdue?", "What's due this week?",
            "How do I reschedule a milestone?"]


def safe_reasons(project, role):
    """The health reasons in plain words. Employees don't see financial data, so budget reasons are left out."""
    reasons = project.get("risk_reasons") or []
    if role == "employee":
        reasons = [r for r in reasons if "$" not in r and "budget" not in r.lower() and "spending" not in r.lower()]
    # "Behind schedule: 52% done" reads better in a sentence as "behind schedule (52% done)"
    return [(r.replace(": ", " (", 1) + ")" if ": " in r else r) for r in reasons]


def status_answer(project, role, today, next_milestone=None, forecast=None, buffer_days=None, top_risk=None):
    health = HEALTH_WORDS.get(project["health"], project["health"])
    lines = [f"**{project['name']}** is **{health}**. It's {project['progress']}% done with "
             f"{project['time_elapsed_pct']}% of the time used, and it ends {when(project['end_date'], today)}."]
    reasons = safe_reasons(project, role)
    if reasons:
        lines.append("Flagged for: " + "; ".join(r[0].lower() + r[1:] for r in reasons) + ".")
    if next_milestone:
        lines.append(f"- Next milestone: **{next_milestone['name']}**, due {when(next_milestone['end_date'], today)}")
    if forecast and forecast.get("status") == "late":
        lines.append(f"- Forecast: at the current pace it finishes around {when(forecast['projected_end'], today)}, "
                     f"{plural(forecast['days_late'], 'day')} late")
    elif forecast and forecast.get("status") in ("on_time", "early"):
        lines.append(f"- Forecast: on pace to finish around {when(forecast['projected_end'], today)}")
    if buffer_days is not None:
        lines.append("- Critical path: no buffer, so any delay there moves the end date" if buffer_days <= 0
                     else f"- Critical path: {plural(buffer_days, 'day')} of buffer")
    if top_risk:
        lines.append(f"- Top logged risk: **{top_risk['title']}** ({top_risk['level']}, {top_risk['score']} of 25)")
    return "\n".join(lines)


def workload_answer(people, today, person=None):
    """people: [{"name", "peak", "day"}] over the next two weeks."""
    if person:
        row = next((p for p in people if p["name"] == person["name"]), None)
        if row is None or not row["peak"]:
            return f"**{person['name']}** isn't booked on any open milestones in the next two weeks."
        free = max(8 - row["peak"], 0)
        verdict = ("that's over the 8-hour limit" if row["peak"] > 8 else "fully booked" if free == 0
                   else f"{free:g} hours free that day")
        return (f"**{person['name']}**'s busiest day in the next two weeks is {when(row['day'], today)}, "
                f"at {row['peak']:g} hours: {verdict}.")
    if not people:
        return "Nobody you manage is booked on open milestones in the next two weeks."
    over = [p for p in people if p["peak"] > 8]
    full = [p for p in people if p["peak"] == 8]
    open_ = sorted((p for p in people if p["peak"] < 8), key=lambda p: p["peak"])
    lines = []
    if over:
        lines.append(f"**{plural(len(over), 'person')} over-allocated** in the next two weeks:".replace("persons", "people"))
        lines += [f"- **{p['name']}**: {p['peak']:g}h on {when(p['day'], today)}" for p in over[:MAX_ITEMS]]
    else:
        lines.append("Nobody is over-allocated in the next two weeks.")
    if full:
        lines.append("Fully booked (8h on their busiest day): " + ", ".join(p["name"] for p in full[:MAX_ITEMS]) + ".")
    if open_:
        lines.append("Most room: " + ", ".join(f"{p['name']} ({8 - p['peak']:g}h free)" for p in open_[:4]) + ".")
    return "\n".join(lines)


# ---------- reading live data (each query respects what the caller can see) ----------

def _projects(cur, me):
    where, params = visible_where(me)
    cur.execute(f"{PROJECT_SELECT} WHERE {where} AND p.archived_at IS NULL AND p.status <> 'completed' ORDER BY p.end_date",
                params)
    return [metrics.enrich(p) for p in cur.fetchall()]


def _ids(projects):
    return [p["id"] for p in projects] or [0]


def _milestones(cur, ids):
    cur.execute("SELECT m.id, m.name, m.status, m.start_date, m.end_date, m.project_id, p.name AS project_name"
                " FROM milestones m JOIN projects p ON p.id = m.project_id WHERE m.project_id = ANY(%s)", (ids,))
    return cur.fetchall()


def _deliverables(cur, ids, extra="", params=()):
    cur.execute("SELECT d.id, d.title, d.status, d.status_note, d.due_date, d.assignee_id, u.name AS assignee_name,"
                " m.name AS milestone_name, p.id AS project_id, p.name AS project_name"
                " FROM deliverables d JOIN milestones m ON m.id = d.milestone_id JOIN projects p ON p.id = m.project_id"
                f" LEFT JOIN users u ON u.id = d.assignee_id WHERE p.id = ANY(%s) AND d.status <> 'done' {extra}"
                " ORDER BY d.due_date NULLS LAST, d.id", (ids, *params))
    return cur.fetchall()


def _risks(cur, me, ids):
    budget = " AND r.category <> 'budget'" if me["role"] == "employee" else ""
    cur.execute(f"{RISK_SELECT} WHERE r.project_id = ANY(%s) AND r.status IN ('open', 'mitigating'){budget}", (ids,))
    risks = [finish_risk(r) for r in cur.fetchall()]
    return sorted(risks, key=lambda r: (-r["score"], r["id"]))


def _workload(cur, me, today):
    horizon = today + timedelta(days=WORKLOAD_DAYS)
    scope, params = "TRUE", []
    if me["role"] == "manager":
        scope, params = "(u.manager_id = %s OR p.manager_id = %s OR u.id = %s)", [me["id"]] * 3
    elif me["role"] == "employee":
        scope, params = "u.id = %s", [me["id"]]
    cur.execute(
        "SELECT u.id, u.name, m.start_date, m.end_date, ma.hours_per_day FROM milestone_assignments ma"
        " JOIN users u ON u.id = ma.user_id JOIN milestones m ON m.id = ma.milestone_id"
        " JOIN projects p ON p.id = m.project_id"
        " WHERE p.archived_at IS NULL AND p.status <> 'completed' AND m.status <> 'done' AND u.is_active"
        f" AND m.end_date >= %s AND m.start_date <= %s AND {scope}", [today, horizon, *params])
    by_person = {}
    for row in cur.fetchall():
        by_person.setdefault((row["id"], row["name"]), []).append(row)
    people = []
    for (_, name), rows in by_person.items():
        peak, day = scheduling.peak_daily_load(rows, today, horizon)
        people.append({"name": name, "peak": peak, "day": day})
    return sorted(people, key=lambda p: (-p["peak"], p["name"]))


TAB_LABELS = {None: "Open the project", "timeline": "See the timeline", "risks": "Open the Risks tab",
              "milestones": "Open Milestones", "budget": "Open Budget", "team": "Open Team"}


def _project_link(project, tab=None):
    return (TAB_LABELS[tab], f"/projects/{project['id']}" + (f"?tab={tab}" if tab else ""))


# ---------- answering ----------

def answer(cur, me, question, context_project_id=None, today=None):
    today = today or date.today()
    role, first = me["role"], me["name"].split()[0]
    intent = classify(question)
    projects = _projects(cur, me)
    named = match_project(question, projects)
    project = named or next((p for p in projects if p["id"] == context_project_id), None)
    if intent is None and named:
        intent = "status"
    scope = [project] if project else projects
    ids = _ids(scope)

    if intent == "thanks":
        return reply("You're welcome! Anything else you want to check?", follow_ups=suggestions(role, project),
                     project=project, intent=intent)

    if intent == "greeting":
        return reply(f"Hi {first}! I answer questions about your projects from live data: what's at risk, what's "
                     "overdue or blocked, who has room, and how to do things in Throughline. Try one of these:",
                     follow_ups=suggestions(role, project), intent=intent)

    if intent == "help":
        topic = match_help(question)
        if topic:
            return reply(f"**{topic['title']}**\n{topic['text']}", links=[topic["link"]],
                         follow_ups=suggestions(role, project), intent=intent)
        return reply("I can explain rescheduling, assigning people and the 8-hour rule, budgets, risks, the critical "
                     "path, archiving and restoring, the Action Center, the audit log, and your profile. "
                     "What would you like to know?",
                     follow_ups=["How do I reschedule a milestone?", "Why can't I assign someone?",
                                 "How do I restore a project?"], intent=intent)

    if intent == "my_work":
        work = _deliverables(cur, _ids(projects), "AND d.assignee_id = %s", (me["id"],))
        if not work:
            return reply("You have nothing assigned right now. Nice.", links=[("My work", "/my-work")],
                         follow_ups=suggestions(role), intent=intent)
        lines = [f"You have **{plural(len(work), 'open deliverable')}**. Start at the top:"]
        for d in work[:MAX_ITEMS]:
            due = f"due {when(d['due_date'], today)}" if d["due_date"] else "no due date"
            lines.append(f"- **{d['title']}** ({d['project_name']}): {due}, {d['status'].replace('_', ' ')}")
        return reply("\n".join(lines), links=[("My work", "/my-work")], follow_ups=suggestions(role), intent=intent)

    if intent == "workload":
        people = _workload(cur, me, today)
        person = match_person(question, [{"name": p["name"]} for p in people]) or (
            {"name": me["name"]} if role == "employee" else None)
        links = [("Workload", "/workload")] if role != "employee" else []
        return reply(workload_answer(people, today, person), links=links,
                     follow_ups=["What's overdue?", "Why can't I assign someone?"], intent=intent)

    if intent == "blocked":
        blocked = _deliverables(cur, ids, "AND d.status = 'blocked'")
        stuck = [m for m in _milestones(cur, ids) if m["status"] == "blocked"]
        where = f" on **{project['name']}**" if project else ""
        if not blocked and not stuck:
            return reply(f"Nothing is blocked{where} right now.", follow_ups=suggestions(role, project),
                         project=project, intent=intent)
        lines = [f"**{plural(len(blocked) + len(stuck), 'thing')} blocked**{where}:"]
        lines += [f"- **{m['name']}** milestone ({m['project_name']})" for m in stuck[:MAX_ITEMS]]
        for d in blocked[:MAX_ITEMS]:
            who = f" Reported by {d['assignee_name']}." if d["assignee_name"] else ""
            lines.append(f"- **{d['title']}** ({d['milestone_name']}, {d['project_name']}): {d['status_note'] or 'no note'}.{who}")
        links = [_project_link(project, "milestones")] if project else [("Action Center", "/actions")]
        return reply("\n".join(lines), links=links, follow_ups=suggestions(role, project), project=project, intent=intent)

    if intent == "overdue":
        late_m = [m for m in _milestones(cur, ids) if m["status"] != "done" and m["end_date"] < today]
        late_d = _deliverables(cur, ids, "AND d.due_date < %s", (today,))
        where = f" on **{project['name']}**" if project else ""
        if not late_m and not late_d:
            return reply(f"Nothing is overdue{where}.", follow_ups=suggestions(role, project), project=project,
                         intent=intent)
        lines = [f"**{plural(len(late_m) + len(late_d), 'item')} overdue**{where}:"]
        lines += [f"- **{m['name']}** milestone ({m['project_name']}): was due {when(m['end_date'], today)}"
                  for m in sorted(late_m, key=lambda m: m["end_date"])[:MAX_ITEMS]]
        lines += [f"- **{d['title']}** ({d['project_name']}): was due {when(d['due_date'], today)}"
                  + (f", {d['assignee_name']}" if d["assignee_name"] else "") for d in late_d[:MAX_ITEMS]]
        return reply("\n".join(lines), links=[("Action Center", "/actions")], follow_ups=suggestions(role, project),
                     project=project, intent=intent)

    if intent == "due_soon":
        horizon = today + timedelta(days=DUE_SOON_DAYS)
        soon_m = sorted((m for m in _milestones(cur, ids) if m["status"] != "done" and today <= m["end_date"] <= horizon),
                        key=lambda m: m["end_date"])
        soon_d = _deliverables(cur, ids, "AND d.due_date BETWEEN %s AND %s", (today, horizon))
        where = f" on **{project['name']}**" if project else ""
        if not soon_m and not soon_d:
            return reply(f"Nothing is due in the next {DUE_SOON_DAYS} days{where}.", follow_ups=suggestions(role, project),
                         project=project, intent=intent)
        lines = [f"Due in the next {DUE_SOON_DAYS} days{where}:"]
        lines += [f"- **{m['name']}** milestone ({m['project_name']}): {when(m['end_date'], today)}" for m in soon_m[:MAX_ITEMS]]
        lines += [f"- **{d['title']}** ({d['project_name']}): {when(d['due_date'], today)}"
                  + (f", {d['assignee_name']}" if d["assignee_name"] else "") for d in soon_d[:MAX_ITEMS]]
        return reply("\n".join(lines), follow_ups=suggestions(role, project), project=project, intent=intent)

    if intent == "budget":
        if role == "employee":
            return reply("Budget details are only visible to managers and admins. I can tell you about progress, "
                         "deadlines and your own work instead.", follow_ups=suggestions(role), intent=intent)
        if project:
            planned, spent = float(project["budget_planned"] or 0), float(project["budget_spent"] or 0)
            text = (f"**{project['name']}** has spent **${spent:,.0f}** of ${planned:,.0f} "
                    f"({project['budget_used_pct']}%), with {project['progress']}% of the work done.")
            fc = metrics.budget_forecast(planned, spent, project["start_date"], project["end_date"], today)
            if fc["status"] in ("over", "under", "on_track"):
                verdict = {"over": "over plan", "under": "under plan", "on_track": "close to plan"}[fc["status"]]
                text += f" At the current burn rate it would finish around ${fc['projected_total']:,.0f}, {verdict}."
            return reply(text, links=[_project_link(project, "budget")], follow_ups=suggestions(role, project),
                         project=project, intent=intent)
        rows = sorted(projects, key=lambda p: -p["budget_used_pct"])
        lines = ["Budget used across your active projects:"]
        lines += [f"- **{p['name']}**: {p['budget_used_pct']}% of ${float(p['budget_planned'] or 0):,.0f} spent, "
                  f"{p['progress']}% done" for p in rows[:MAX_ITEMS]]
        return reply("\n".join(lines) if rows else "You have no active projects.", follow_ups=suggestions(role),
                     intent=intent)

    if intent == "risks":
        risks = _risks(cur, me, ids)
        if project:
            text = status_answer(project, role, today)
            if risks:
                text += "\nLogged risks:\n" + "\n".join(
                    f"- **{r['title']}** ({r['level']}, {r['score']} of 25)" + (f", owner {r['owner_name']}" if r["owner_name"] else "")
                    for r in risks[:MAX_ITEMS])
            else:
                text += "\nNo risks are logged in its register yet."
            return reply(text, links=[_project_link(project, "risks")], follow_ups=suggestions(role, project),
                         project=project, intent=intent)
        troubled = [p for p in projects if p["health"] in ("off_track", "at_risk")]
        troubled.sort(key=lambda p: (p["health"] != "off_track", p["end_date"]))
        if not troubled and not risks:
            return reply("Everything is on track, and there are no open risks logged.", follow_ups=suggestions(role),
                         intent=intent)
        lines = []
        if troubled:
            lines.append(f"**{plural(len(troubled), 'project')} {'needs' if len(troubled) == 1 else 'need'} attention:**")
            for p in troubled[:MAX_ITEMS]:
                reasons = safe_reasons(p, role)
                lines.append(f"- **{p['name']}** is {HEALTH_WORDS[p['health']]}" + (f": {'; '.join(reasons[:2])}" if reasons else ""))
        else:
            lines.append("Every active project is on track.")
        if risks:
            lines.append("Highest logged risks:")
            lines += [f"- **{r['title']}** ({r['project_name']}): {r['level']}, {r['score']} of 25" for r in risks[:3]]
        links = [_project_link(p, "risks") for p in troubled[:2]]
        return reply("\n".join(lines), links=links, follow_ups=suggestions(role), intent=intent)

    if intent == "team" and project:
        cur.execute("SELECT u.name, u.job_title FROM project_members pm JOIN users u ON u.id = pm.user_id"
                    " WHERE pm.project_id = %s ORDER BY u.name", (project["id"],))
        members = cur.fetchall()
        lines = [f"**{project['name']}** is run by {project['manager_name']}, with {plural(len(members), 'person')} on "
                 "the team:".replace("persons", "people")]
        lines += [f"- {m['name']}" + (f", {m['job_title']}" if m["job_title"] else "") for m in members[:10]]
        return reply("\n".join(lines), links=[_project_link(project, "team")], follow_ups=suggestions(role, project),
                     project=project, intent=intent)

    if intent in ("status", "team") or project:
        if project:
            nodes = {m["id"]: m for m in _milestones(cur, [project["id"]])}
            cur.execute("SELECT md.milestone_id, md.depends_on_id FROM milestone_dependencies md"
                        " JOIN milestones m ON m.id = md.milestone_id WHERE m.project_id = %s", (project["id"],))
            edges = [(r["milestone_id"], r["depends_on_id"]) for r in cur.fetchall()]
            path = scheduling.critical_path(nodes, edges, project["end_date"])
            upcoming = sorted((m for m in nodes.values() if m["status"] != "done"), key=lambda m: m["end_date"])
            forecast = scheduling.delivery_forecast(project["progress"], project["start_date"], project["end_date"], today)
            risks = _risks(cur, me, [project["id"]])
            text = status_answer(project, role, today, upcoming[0] if upcoming else None, forecast,
                                 path["buffer_days"], risks[0] if risks else None)
            return reply(text, links=[_project_link(project), _project_link(project, "timeline")],
                         follow_ups=suggestions(role, project), project=project, intent="status")
        if not projects:
            return reply("You don't have any active projects right now.", follow_ups=suggestions(role), intent="status")
        counts = {h: sum(1 for p in projects if p["health"] == h) for h in ("on_track", "at_risk", "off_track")}
        lines = [f"You have **{plural(len(projects), 'active project')}**: {counts['on_track']} on track, "
                 f"{counts['at_risk']} at risk and {counts['off_track']} off track."]
        lines += [f"- **{p['name']}**: {HEALTH_WORDS[p['health']]}, {p['progress']}% done, ends {when(p['end_date'], today)}"
                  for p in projects[:MAX_ITEMS]]
        return reply("\n".join(lines), follow_ups=suggestions(role), intent="status")

    return reply("I'm not sure I understood that one. I can answer questions about project status, risks, overdue "
                 "or blocked work, deadlines, workload and budgets, or explain how something works. Try one of these:",
                 follow_ups=suggestions(role, project), intent="unknown")


ASK_SCHEMA = {"question": F("str", required=True, max_len=500), "project_id": F("int", nullable=True, min=1)}


def register(router):
    """Adds POST /dashboard/ask to the dashboard service's router."""

    @router.route("POST", "/ask")
    def ask(req):
        data = validate(req.json(), ASK_SCHEMA)
        with db.transaction() as cur:
            return 200, answer(cur, req.user, data["question"], data.get("project_id"))