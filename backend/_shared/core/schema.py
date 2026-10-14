"""Creates all tables on first run and seeds a default admin, so a fresh AWS database needs no manual setup."""
from . import db
from .auth import hash_password

DEFAULT_ADMIN = ("admin", "Admin123!", "Javier Benitez", "javier.benitez@acme.com", "Administrator")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS app_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    job_title VARCHAR(100),
    role VARCHAR(20) NOT NULL CHECK (role IN ('admin', 'manager', 'employee')),
    manager_id INTEGER REFERENCES users(id),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS teams (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    manager_id INTEGER NOT NULL REFERENCES users(id),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (manager_id, name)
);

CREATE TABLE IF NOT EXISTS team_members (
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id),
    PRIMARY KEY (team_id, user_id)
);

CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    description TEXT,
    department VARCHAR(100),
    manager_id INTEGER NOT NULL REFERENCES users(id),
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    budget_planned NUMERIC(14, 2) NOT NULL DEFAULT 0 CHECK (budget_planned >= 0),
    status VARCHAR(20) NOT NULL DEFAULT 'planning'
        CHECK (status IN ('planning', 'active', 'on_hold', 'completed')),
    archived_at TIMESTAMPTZ,
    archived_by INTEGER REFERENCES users(id),
    archive_reason TEXT,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (end_date >= start_date)
);

CREATE TABLE IF NOT EXISTS project_members (
    project_id INTEGER NOT NULL REFERENCES projects(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    added_by INTEGER REFERENCES users(id),
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (project_id, user_id)
);

CREATE TABLE IF NOT EXISTS milestones (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    name VARCHAR(150) NOT NULL,
    description TEXT,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'not_started'
        CHECK (status IN ('not_started', 'in_progress', 'blocked', 'done')),
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (end_date >= start_date)
);

CREATE TABLE IF NOT EXISTS milestone_dependencies (
    milestone_id INTEGER NOT NULL REFERENCES milestones(id) ON DELETE CASCADE,
    depends_on_id INTEGER NOT NULL REFERENCES milestones(id) ON DELETE CASCADE,
    PRIMARY KEY (milestone_id, depends_on_id),
    CHECK (milestone_id <> depends_on_id)
);

CREATE TABLE IF NOT EXISTS milestone_assignments (
    milestone_id INTEGER NOT NULL REFERENCES milestones(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id),
    hours_per_day NUMERIC(4, 2) NOT NULL DEFAULT 8 CHECK (hours_per_day > 0 AND hours_per_day <= 8),
    assigned_by INTEGER REFERENCES users(id),
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (milestone_id, user_id)
);

CREATE TABLE IF NOT EXISTS deliverables (
    id SERIAL PRIMARY KEY,
    milestone_id INTEGER NOT NULL REFERENCES milestones(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    assignee_id INTEGER REFERENCES users(id),
    status VARCHAR(20) NOT NULL DEFAULT 'todo'
        CHECK (status IN ('todo', 'in_progress', 'blocked', 'done')),
    due_date DATE,
    completed_at TIMESTAMPTZ,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS budget_entries (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    amount NUMERIC(14, 2) NOT NULL CHECK (amount > 0),
    category VARCHAR(50) NOT NULL,
    description TEXT,
    entry_date DATE NOT NULL DEFAULT CURRENT_DATE,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS budget_changes (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    old_amount NUMERIC(14, 2) NOT NULL,
    new_amount NUMERIC(14, 2) NOT NULL,
    reason TEXT NOT NULL,
    changed_by INTEGER REFERENCES users(id),
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS date_changes (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(20) NOT NULL CHECK (entity_type IN ('project', 'milestone')),
    entity_id INTEGER NOT NULL,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    old_start DATE NOT NULL,
    old_end DATE NOT NULL,
    new_start DATE NOT NULL,
    new_end DATE NOT NULL,
    reason TEXT NOT NULL,
    changed_by INTEGER REFERENCES users(id),
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS activity_log (
    id BIGSERIAL PRIMARY KEY,
    actor_id INTEGER REFERENCES users(id),
    action VARCHAR(50) NOT NULL,
    entity_type VARCHAR(30) NOT NULL,
    entity_id INTEGER,
    project_id INTEGER,
    summary TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE activity_log ADD COLUMN IF NOT EXISTS details JSONB;

CREATE TABLE IF NOT EXISTS action_items (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    priority VARCHAR(10) NOT NULL DEFAULT 'medium'
        CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    status VARCHAR(20) NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'in_progress', 'done', 'dismissed')),
    source VARCHAR(10) NOT NULL DEFAULT 'manual' CHECK (source IN ('manual', 'system')),
    rule_key VARCHAR(120) UNIQUE,
    assignee_id INTEGER REFERENCES users(id),
    project_id INTEGER REFERENCES projects(id),
    entity_type VARCHAR(30),
    entity_id INTEGER,
    due_date DATE,
    created_by INTEGER REFERENCES users(id),
    resolved_by INTEGER REFERENCES users(id),
    resolved_at TIMESTAMPTZ,
    resolution_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_action_items_assignee ON action_items(assignee_id, status);
CREATE INDEX IF NOT EXISTS idx_action_items_project ON action_items(project_id, status);
CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_activity_actor ON activity_log(actor_id, created_at DESC);

ALTER TABLE deliverables ADD COLUMN IF NOT EXISTS status_note TEXT;

CREATE INDEX IF NOT EXISTS idx_users_manager ON users(manager_id);
CREATE INDEX IF NOT EXISTS idx_projects_manager ON projects(manager_id);
CREATE INDEX IF NOT EXISTS idx_milestones_project ON milestones(project_id);
CREATE INDEX IF NOT EXISTS idx_deliverables_milestone ON deliverables(milestone_id);
CREATE INDEX IF NOT EXISTS idx_deliverables_assignee ON deliverables(assignee_id);
CREATE INDEX IF NOT EXISTS idx_assignments_user ON milestone_assignments(user_id);
CREATE INDEX IF NOT EXISTS idx_budget_entries_project ON budget_entries(project_id);
CREATE INDEX IF NOT EXISTS idx_activity_project ON activity_log(project_id, created_at DESC);

CREATE TABLE IF NOT EXISTS risks (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    title VARCHAR(200) NOT NULL,
    description TEXT,
    category VARCHAR(20) NOT NULL DEFAULT 'other'
        CHECK (category IN ('schedule', 'budget', 'resources', 'vendor', 'technical', 'scope', 'other')),
    likelihood SMALLINT NOT NULL CHECK (likelihood BETWEEN 1 AND 5),
    impact SMALLINT NOT NULL CHECK (impact BETWEEN 1 AND 5),
    status VARCHAR(20) NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'mitigating', 'closed', 'occurred', 'dismissed')),
    owner_id INTEGER REFERENCES users(id),
    mitigation TEXT,
    review_date DATE,
    source_key VARCHAR(120),
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    UNIQUE (project_id, source_key)
);
CREATE INDEX IF NOT EXISTS idx_risks_project ON risks(project_id, status);

CREATE TABLE IF NOT EXISTS sign_in_events (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    succeeded BOOLEAN NOT NULL,
    device VARCHAR(100),
    ip_masked VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sign_in_events_user ON sign_in_events(user_id, created_at DESC);
"""

_READY = False


def ensure_schema():
    """Runs once per Lambda container. The advisory lock stops two cold starts from racing."""
    global _READY
    if _READY:
        return
    with db.transaction() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(424242)")
        cur.execute(SCHEMA_SQL)
        cur.execute("SELECT COUNT(*) AS n FROM users")
        if cur.fetchone()["n"] == 0:
            username, password, name, email, title = DEFAULT_ADMIN
            cur.execute(
                "INSERT INTO users (username, password_hash, name, email, job_title, role) "
                "VALUES (%s, %s, %s, %s, %s, 'admin')",
                (username, hash_password(password), name, email, title))
    _READY = True
