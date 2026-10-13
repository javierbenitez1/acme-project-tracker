"""Declarative validation that returns a message for every invalid field."""
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from .errors import bad_request

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
TEXT_KINDS = ("str", "email", "password", "enum")


class F:
    """A rule for one field. kind is one of: str, email, password, int, number, date, bool, enum."""

    def __init__(self, kind, required=False, nullable=False, min_len=None, max_len=None,
                 min=None, max=None, choices=None, strip=True):
        self.kind = kind
        self.required = required
        self.nullable = nullable
        self.min_len = min_len
        self.max_len = max_len
        self.min = min
        self.max = max
        self.choices = choices
        self.strip = strip and kind != "password"


def _coerce(value, f):
    kind = f.kind
    if kind in TEXT_KINDS:
        if not isinstance(value, str):
            raise ValueError("Must be text.")
        if kind == "email":
            value = value.lower()
            if not EMAIL_RE.match(value):
                raise ValueError("Must be a valid email address.")
        if kind == "password" and (len(value) < 8 or not re.search(r"[A-Za-z]", value)
                                   or not re.search(r"\d", value)):
            raise ValueError("Must be at least 8 characters and include a letter and a number.")
        if kind == "enum" and value not in f.choices:
            raise ValueError(f"Must be one of: {', '.join(f.choices)}.")
        if f.min_len is not None and len(value) < f.min_len:
            raise ValueError(f"Must be at least {f.min_len} characters.")
        if f.max_len is not None and len(value) > f.max_len:
            raise ValueError(f"Must be at most {f.max_len} characters.")
        return value
    if kind == "ids":
        if not isinstance(value, list) or not value:
            raise ValueError("Must be a non-empty list of ids.")
        if f.max_len is not None and len(value) > f.max_len:
            raise ValueError(f"Must contain at most {f.max_len} ids.")
        ids = []
        for item in value:
            if isinstance(item, bool) or not isinstance(item, int) or item < 1:
                raise ValueError("Every id must be a positive whole number.")
            if item not in ids:
                ids.append(item)
        return ids
    if kind == "int":
        if isinstance(value, bool) or (isinstance(value, float) and not value.is_integer()):
            raise ValueError("Must be a whole number.")
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise ValueError("Must be a whole number.")
    elif kind == "number":
        if isinstance(value, bool):
            raise ValueError("Must be a number.")
        try:
            value = Decimal(str(value))
        except InvalidOperation:
            raise ValueError("Must be a number.")
        if not value.is_finite():
            raise ValueError("Must be a number.")
    elif kind == "date":
        try:
            value = date.fromisoformat(str(value))
        except ValueError:
            raise ValueError("Must be a date in YYYY-MM-DD format.")
    elif kind == "bool":
        if not isinstance(value, bool):
            raise ValueError("Must be true or false.")
        return value
    if f.min is not None and value < f.min:
        raise ValueError(f"Must be at least {f.min}.")
    if f.max is not None and value > f.max:
        raise ValueError(f"Must be at most {f.max}.")
    return value


def validate(data, schema, partial=False):
    """Return cleaned data or raise a 400 listing every bad field.
    partial=True is for updates: missing fields are fine, but fields sent must be valid.
    Unknown fields are rejected so nobody can sneak in fields like role."""
    if not isinstance(data, dict):
        raise bad_request("Request body must be a JSON object.")
    errors = {name: "Unknown field." for name in data if name not in schema}
    cleaned = {}
    for name, f in schema.items():
        present = name in data
        value = data.get(name)
        if isinstance(value, str) and f.strip:
            value = value.strip()
        if value is None or value == "":
            if f.required and (not partial or present):
                errors[name] = "This field is required."
            elif present and f.nullable:
                cleaned[name] = None
            continue
        try:
            cleaned[name] = _coerce(value, f)
        except ValueError as e:
            errors[name] = str(e)
    if errors:
        raise bad_request("Some fields are invalid.", details=errors)
    return cleaned
