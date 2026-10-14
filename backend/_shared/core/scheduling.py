"""Pure scheduling logic with no database code, shared by services and covered by unit tests."""
import math
from collections import defaultdict, deque
from datetime import date, timedelta

WORKDAY_HOURS = 8.0


def would_create_cycle(edges, milestone_id, depends_on_id):
    """edges are (milestone_id, depends_on_id) pairs. Making milestone depend on depends_on creates a
    cycle if depends_on already depends, directly or indirectly, on milestone."""
    if milestone_id == depends_on_id:
        return True
    prereqs = defaultdict(list)
    for milestone, prerequisite in edges:
        prereqs[milestone].append(prerequisite)
    stack, seen = [depends_on_id], set()
    while stack:
        current = stack.pop()
        if current == milestone_id:
            return True
        if current in seen:
            continue
        seen.add(current)
        stack.extend(prereqs[current])
    return False


def plan_reschedule(nodes, edges, target_id, new_start, new_end):
    """Returns {id: (start, end)} for every milestone whose dates change when target moves.
    Dependents are pushed later just enough to start on or after all their prerequisites end, and
    they keep their length. Completed milestones never move, and nothing is pulled earlier."""
    dependents, prereqs = defaultdict(list), defaultdict(list)
    for milestone, prerequisite in edges:
        dependents[prerequisite].append(milestone)
        prereqs[milestone].append(prerequisite)
    plan = {nid: (n["start_date"], n["end_date"]) for nid, n in nodes.items()}
    plan[target_id] = (new_start, new_end)
    queue = deque(dependents[target_id])
    steps = 0
    while queue:
        steps += 1
        if steps > 100_000:
            raise ValueError("Dependency cycle detected")
        nid = queue.popleft()
        if nodes[nid]["status"] == "done":
            continue
        required = max(plan[p][1] for p in prereqs[nid])
        start, end = plan[nid]
        if start < required:
            delta = required - start
            plan[nid] = (start + delta, end + delta)
            queue.extend(dependents[nid])
    return {nid: dates for nid, dates in plan.items()
            if dates != (nodes[nid]["start_date"], nodes[nid]["end_date"])}


def peak_daily_load(assignments, start, end):
    """Highest total hours_per_day booked on any weekday from start to end, and the day it happens."""
    peak, peak_day = 0.0, None
    day = start
    while day <= end:
        if day.weekday() < 5:
            load = sum(float(a["hours_per_day"]) for a in assignments if a["start_date"] <= day <= a["end_date"])
            if load > peak:
                peak, peak_day = load, day
        day += timedelta(days=1)
    return peak, peak_day


def weekly_hours(assignments, week_start):
    """Total hours booked Monday to Friday of the week that starts on week_start (a Monday)."""
    total = 0.0
    for offset in range(5):
        day = week_start + timedelta(days=offset)
        total += sum(float(a["hours_per_day"]) for a in assignments if a["start_date"] <= day <= a["end_date"])
    return total


def critical_path(nodes, edges, project_end):
    """Critical path analysis for the open milestones of one project.

    slack_days is how many calendar days a milestone can slip before the project end date has to
    move. It counts any gap before the milestones that wait on it, which is the same rule
    plan_reschedule uses when it shifts dependents. The critical path is the set of milestones with
    the least slack: a delay on any of them delays the whole project by the same amount.
    Completed milestones are fixed history, so they are left out."""
    open_ids = {nid for nid, node in nodes.items() if node["status"] != "done"}
    dependents, prereqs = defaultdict(list), defaultdict(list)
    for milestone, prerequisite in edges:
        if milestone in open_ids and prerequisite in open_ids:
            dependents[prerequisite].append(milestone)
            prereqs[milestone].append(prerequisite)

    # Backward pass in reverse topological order: a milestone is handled once everything that
    # waits on it has been handled (Kahn's algorithm on the reversed graph).
    waiting = {nid: len(dependents[nid]) for nid in open_ids}
    queue = deque(sorted(nid for nid, count in waiting.items() if count == 0))
    slack = {}
    while queue:
        nid = queue.popleft()
        end = nodes[nid]["end_date"]
        if dependents[nid]:
            slack[nid] = min((nodes[d]["start_date"] - end).days + slack[d] for d in dependents[nid])
        else:
            slack[nid] = (project_end - end).days
        for prerequisite in prereqs[nid]:
            waiting[prerequisite] -= 1
            if waiting[prerequisite] == 0:
                queue.append(prerequisite)
    if len(slack) != len(open_ids):
        raise ValueError("Dependency cycle detected")
    if not slack:
        return {"slack": {}, "critical": [], "buffer_days": None}
    buffer_days = min(slack.values())
    critical = sorted((nid for nid, days in slack.items() if days == buffer_days),
                      key=lambda nid: (nodes[nid]["start_date"], nid))
    return {"slack": slack, "critical": critical, "buffer_days": buffer_days}


def delivery_forecast(progress, start, end, today=None):
    """Projects the finish date by assuming work keeps getting done at the same pace as so far."""
    today = today or date.today()
    progress = float(progress or 0)
    if progress >= 100:
        return {"status": "complete", "projected_end": None, "days_late": None}
    total_days = max((end - start).days + 1, 1)
    elapsed = (today - start).days + 1
    if progress <= 0 or elapsed < max(total_days * 0.1, 1):
        return {"status": "not_enough_data", "projected_end": None, "days_late": None}
    projected_end = start + timedelta(days=math.ceil(elapsed * 100 / progress) - 1)
    days_late = (projected_end - end).days
    if days_late > 3:
        status = "late"
    elif days_late < -3:
        status = "early"
    else:
        status = "on_time"
    return {"status": status, "projected_end": projected_end, "days_late": days_late}
