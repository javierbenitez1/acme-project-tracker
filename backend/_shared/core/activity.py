"""Audit trail: every change records who did it, what changed, and the before and after values."""
import json
from datetime import date, datetime
from decimal import Decimal

from psycopg.types.json import Jsonb


def _default(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def _dumps(obj):
    return json.dumps(obj, default=_default)


def diff(before, after, fields):
    """Returns {field: {"from": old, "to": new}} for every field whose value changed."""
    return {f: {"from": before.get(f), "to": after.get(f)} for f in fields if before.get(f) != after.get(f)}


def log(cur, actor_id, action, entity_type, summary, entity_id=None, project_id=None, details=None):
    cur.execute(
        "INSERT INTO activity_log (actor_id, action, entity_type, entity_id, project_id, summary, details) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (actor_id, action, entity_type, entity_id, project_id, summary,
         Jsonb(details, dumps=_dumps) if details else None))
