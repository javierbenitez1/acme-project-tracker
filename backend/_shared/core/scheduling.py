"""Pure scheduling logic with no database code, shared by services and covered by unit tests."""
from collections import defaultdict, deque
from datetime import timedelta

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
