"""PostgreSQL connection management. One connection per Lambda container, reused across calls."""
import os
from contextlib import contextmanager

from psycopg import connect
from psycopg.rows import dict_row

_CONN = None


def _conninfo():
    is_local = os.getenv("IS_LOCAL", "false") == "true"
    parts = [
        f"host={os.getenv('POSTGRES_HOST') or 'localhost'}",
        f"port={os.getenv('POSTGRES_PORT') or '5432'}",
        f"user={os.getenv('POSTGRES_USER') or 'postgres'}",
        f"password={os.getenv('POSTGRES_PASS') or 'postgres123'}",
        f"dbname={os.getenv('POSTGRES_NAME') or 'postgres'}",
        "connect_timeout=8",
    ]
    if not is_local:
        parts.append("sslmode=require")
    return " ".join(parts)


def get_conn():
    global _CONN
    if _CONN is None or _CONN.closed:
        _CONN = connect(_conninfo(), row_factory=dict_row)
    return _CONN


def reset():
    """Drop the cached connection so the next call reconnects."""
    global _CONN
    try:
        if _CONN is not None:
            _CONN.close()
    except Exception:
        pass
    _CONN = None


@contextmanager
def transaction():
    """Yields a cursor. Commits if the block succeeds, rolls back if anything fails."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            reset()
        raise
