"""Unit tests for request validation: required fields, formats, coercion, and unknown fields."""
from datetime import date
from decimal import Decimal

import pytest

from core.errors import ApiError
from core.validation import F, validate

SCHEMA = {
    "name": F("str", required=True, max_len=10),
    "email": F("email"),
    "age": F("int", min=0, max=120),
    "budget": F("number", min=0),
    "start": F("date"),
    "active": F("bool"),
    "role": F("enum", choices=["admin", "manager"]),
    "password": F("password"),
    "note": F("str", nullable=True),
}


def errors_of(data, partial=False):
    with pytest.raises(ApiError) as exc:
        validate(data, SCHEMA, partial=partial)
    assert exc.value.status == 400
    return exc.value.details


def test_valid_payload_is_trimmed_and_coerced():
    out = validate({"name": "  Ana  ", "email": "ANA@Acme.com", "age": "30", "budget": 12.5,
                    "start": "2026-01-15", "active": True, "role": "admin"}, SCHEMA)
    assert out == {"name": "Ana", "email": "ana@acme.com", "age": 30, "budget": Decimal("12.5"),
                   "start": date(2026, 1, 15), "active": True, "role": "admin"}


def test_missing_required_field():
    assert errors_of({})["name"] == "This field is required."


def test_blank_string_counts_as_missing():
    assert errors_of({"name": "   "})["name"] == "This field is required."


def test_unknown_fields_are_rejected():
    assert errors_of({"name": "Ana", "role_override": "admin"})["role_override"] == "Unknown field."


@pytest.mark.parametrize("field, value, expected", [
    ("email", "not-an-email", "valid email"),
    ("age", "abc", "whole number"),
    ("age", 3.5, "whole number"),
    ("age", True, "whole number"),
    ("age", 121, "at most 120"),
    ("budget", -1, "at least 0"),
    ("budget", "NaN", "number"),
    ("start", "13/01/2026", "YYYY-MM-DD"),
    ("active", "yes", "true or false"),
    ("role", "superuser", "one of"),
    ("password", "short1", "at least 8"),
    ("password", "NoDigitsHere", "at least 8"),
    ("name", "x" * 11, "at most 10"),
])
def test_invalid_values_get_field_messages(field, value, expected):
    data = {"name": "Ana", field: value}
    assert expected in errors_of(data)[field]


def test_every_bad_field_is_reported_at_once():
    assert set(errors_of({"email": "bad", "age": "x"})) == {"name", "email", "age"}


def test_partial_update_allows_missing_required_fields():
    assert validate({"age": 5}, SCHEMA, partial=True) == {"age": 5}


def test_partial_update_cannot_blank_a_required_field():
    assert errors_of({"name": ""}, partial=True)["name"] == "This field is required."


def test_nullable_field_can_be_cleared():
    assert validate({"name": "Ana", "note": None}, SCHEMA) == {"name": "Ana", "note": None}


def test_passwords_are_never_trimmed():
    assert validate({"name": "Ana", "password": " Secret123 "}, SCHEMA)["password"] == " Secret123 "


def test_non_object_body_is_rejected():
    with pytest.raises(ApiError):
        validate(["not", "an", "object"], SCHEMA)
