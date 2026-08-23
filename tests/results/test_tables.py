"""Tests for the shape of a result id, as `Result` defines it."""

import uuid

import pytest

from backend.results import Result

# Forms `uuid.UUID()` accepts but `ResultStore.save` never writes.
ACCEPTED_BUT_NEVER_MINTED = (
    "0f8fad5b7dcb11e0975300215ad9d078",
    "{0f8fad5b-7dcb-11e0-9753-00215ad9d078}",
    "urn:uuid:0f8fad5b-7dcb-11e0-9753-00215ad9d078",
)


class TestIsValidId:
    def test_a_minted_id_is_valid(self):
        assert Result.is_valid_id(str(uuid.uuid4()))

    @pytest.mark.parametrize("result_id", ["", "abc", "ZZZZZZZZ", "deadbeef-x"])
    def test_a_malformed_id_is_not(self, result_id):
        assert not Result.is_valid_id(result_id)

    @pytest.mark.parametrize("result_id", ACCEPTED_BUT_NEVER_MINTED)
    def test_a_uuid_in_another_notation_is_not(self, result_id):
        assert not Result.is_valid_id(result_id)

    def test_uppercase_is_not_the_form_the_store_writes(self):
        assert not Result.is_valid_id(str(uuid.uuid4()).upper())
