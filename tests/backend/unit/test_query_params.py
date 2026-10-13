"""Unit tests for shared query-string helpers."""
import pytest

from core.errors import ApiError
from core.validation import query_choice, query_int


def test_query_int_reads_values_and_defaults():
    assert query_int({"page": "3"}, "page") == 3
    assert query_int({}, "page", default=1) == 1


@pytest.mark.parametrize("raw", ["abc", "0", "300"])
def test_query_int_rejects_bad_values(raw):
    with pytest.raises(ApiError):
        query_int({"page": raw}, "page", hi=200)


def test_query_choice_reads_values_and_defaults():
    assert query_choice({"status": "done"}, "status", ["done", "open"]) == "done"
    assert query_choice({}, "status", ["done", "open"], default="open") == "open"


def test_query_choice_rejects_unknown_values():
    with pytest.raises(ApiError):
        query_choice({"status": "finished"}, "status", ["done", "open"])
