"""Unit tests for id-list validation used when adding several people at once."""
import pytest

from core.errors import ApiError
from core.validation import F, validate

SCHEMA = {"user_ids": F("ids", required=True, max_len=3)}


def test_duplicate_ids_are_removed_in_order():
    assert validate({"user_ids": [3, 1, 3]}, SCHEMA) == {"user_ids": [3, 1]}


@pytest.mark.parametrize("value", [[], "1,2", [1, "2"], [0], [True], [1, 2, 3, 4]])
def test_bad_id_lists_are_rejected(value):
    with pytest.raises(ApiError):
        validate({"user_ids": value}, SCHEMA)
