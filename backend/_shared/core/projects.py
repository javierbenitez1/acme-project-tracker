"""Project lookups and permission checks shared by every project-related service."""
from . import metrics
from .errors import conflict, forbidden, not_found

PROJECT_SELECT = """
SELECT p.id, p.name, p.description, p.department, p.manager_id, mgr.name AS manager_name,
       p.start_date, p.end_date, p.budget_planned, p.status,
       p.archived_at, p.archived_by, p.archive_reason, p.created_at, p.updated_at,
       (SELECT COUNT(*) FROM project_members pm WHERE pm.project_id = p.id) AS member_count,
       (SELECT COUNT(*) FROM milestones m WHERE m.project_id = p.id) AS milestone_count,
       (SELECT COUNT(*) FROM milestones m WHERE m.project_id = p.id AND m.status = 'done') AS milestones_done,
       (SELECT COUNT(*) FROM milestones m WHERE m.project_id = p.id AND m.status = 'blocked') AS milestones_blocked,
       (SELECT COUNT(*) FROM milestones m
         WHERE m.project_id = p.id AND m.status <> 'done' AND m.end_date < CURRENT_DATE) AS milestones_overdue,
       COALESCE((SELECT SUM(b.amount) FROM budget_entries b WHERE b.project_id = p.id), 0) AS budget_spent,
       COALESCE((SELECT ROUND(AVG(CASE WHEN m.status = 'done' THEN 100
                                       WHEN dc.total > 0 THEN 100.0 * dc.done / dc.total
                                       ELSE 0 END))
                 FROM milestones m
                 LEFT JOIN LATERAL (SELECT COUNT(*) AS total,
                                           COUNT(*) FILTER (WHERE d.status = 'done') AS done
                                    FROM deliverables d WHERE d.milestone_id = m.id) dc ON TRUE
                 WHERE m.project_id = p.id), 0) AS progress
FROM projects p
JOIN users mgr ON mgr.id = p.manager_id
"""


def visible_where(me, alias="p"):
    """Admins see every project, managers see projects they run, employees see projects they're on."""
    if me["role"] == "admin":
        return "TRUE", []
    if me["role"] == "manager":
        return f"{alias}.manager_id = %s", [me["id"]]
    return (f"EXISTS (SELECT 1 FROM project_members pm WHERE pm.project_id = {alias}.id AND pm.user_id = %s)",
            [me["id"]])


def load_project(cur, me, project_id):
    """Loads a project the caller can see, or raises 404 so hidden projects can't be probed."""
    where, params = visible_where(me)
    cur.execute(f"{PROJECT_SELECT} WHERE p.id = %s AND {where}", [project_id, *params])
    project = cur.fetchone()
    if project is None:
        raise not_found("Project")
    return metrics.enrich(project)


def fetch_project(cur, project_id):
    """Reloads a project after a write. Callers must already have checked permissions."""
    cur.execute(f"{PROJECT_SELECT} WHERE p.id = %s", (project_id,))
    return metrics.enrich(cur.fetchone())


def can_manage(me, project):
    return me["role"] == "admin" or (me["role"] == "manager" and project["manager_id"] == me["id"])


def require_manager(me, project, action="edit this project"):
    if not can_manage(me, project):
        raise forbidden(f"Only this project's manager or an admin can {action}.")


def require_active(project):
    if project["archived_at"] is not None:
        raise conflict("This project is archived and read-only. An admin must restore it first.")
