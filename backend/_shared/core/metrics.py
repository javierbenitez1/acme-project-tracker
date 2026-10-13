"""Project health scoring, shared by the projects and dashboard services."""
from datetime import date

SCHEDULE_GAP = 25      # warn when time used is this many points ahead of progress
SPEND_GAP = 25         # warn when budget used is this many points ahead of progress
ENDING_SOON_DAYS = 7

HEALTH_ORDER = {"off_track": 0, "at_risk": 1, "on_track": 2, "completed": 3, "archived": 4}


def project_health(project, today=None):
    today = today or date.today()
    start, end = project["start_date"], project["end_date"]
    total_days = max((end - start).days + 1, 1)
    elapsed_days = min(max((today - start).days + 1, 0), total_days)
    time_pct = round(100 * elapsed_days / total_days)
    progress = int(project.get("progress") or 0)
    planned = float(project.get("budget_planned") or 0)
    spent = float(project.get("budget_spent") or 0)
    budget_pct = round(100 * spent / planned) if planned > 0 else (100 if spent > 0 else 0)
    days_remaining = (end - today).days
    overdue = int(project.get("milestones_overdue") or 0)
    blocked = int(project.get("milestones_blocked") or 0)
    completed = project.get("status") == "completed"

    critical, warnings = [], []
    if not completed:
        if days_remaining < 0:
            critical.append(f"Past its end date by {-days_remaining} day(s)")
        if overdue:
            critical.append(f"{overdue} overdue milestone(s)")
        if planned > 0 and spent > planned:
            critical.append(f"Over budget by ${spent - planned:,.0f}")
        elif planned == 0 and spent > 0:
            critical.append("Spending recorded with no planned budget")
        if blocked:
            warnings.append(f"{blocked} blocked milestone(s)")
        if days_remaining >= 0 and time_pct >= 20 and time_pct - progress >= SCHEDULE_GAP:
            warnings.append(f"Behind schedule: {progress}% done with {time_pct}% of the time used")
        if planned > 0 and spent <= planned and budget_pct - progress >= SPEND_GAP:
            warnings.append(f"Spending ahead of progress: {budget_pct}% of budget used, {progress}% done")
        if 0 <= days_remaining <= ENDING_SOON_DAYS and progress < 90:
            warnings.append(f"Ends in {days_remaining} day(s) at {progress}% complete")

    if project.get("archived_at") and not completed:
        health = "archived"
    elif completed:
        health = "completed"
    elif critical:
        health = "off_track"
    elif warnings:
        health = "at_risk"
    else:
        health = "on_track"
    return {
        "progress": progress, "time_elapsed_pct": time_pct, "days_remaining": days_remaining,
        "budget_spent": round(spent, 2), "budget_remaining": round(planned - spent, 2),
        "budget_used_pct": budget_pct, "health": health, "risk_reasons": critical + warnings,
    }


def enrich(project, today=None):
    """Adds health fields to a project row from PROJECT_SELECT."""
    project.update(project_health(project, today))
    project["is_archived"] = project.get("archived_at") is not None
    return project
