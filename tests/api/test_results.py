"""Tests for ``/api/results`` -- the saved history."""

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from backend.results import ResultListResponse, ResultType, SavedResult

# A canonical uuid4, the one shape `results_store` mints.
GOOD_ID = "0f8fad5b-7dcb-11e0-9753-00215ad9d078"

# Snapshots as the two generators write them, cut down to required fields.
PLAYLIST_SNAPSHOT = {
    "tracks": [
        {
            "rating_key": "1",
            "title": "Song",
            "artist": "Band",
            "album": "Record",
            "duration_ms": 1000,
        }
    ],
    "token_count": 10,
    "estimated_cost": 0.5,
    "playlist_title": "Rainy Monday",
}

ALBUM_SNAPSHOT = {"recommendations": [{"rank": "primary", "album": "Kid A", "artist": "Radiohead"}]}


def saved(result_type: ResultType, snapshot: dict) -> SavedResult:
    """One stored row, as `results_store.get` hands it back."""
    return SavedResult(
        id=GOOD_ID,
        type=result_type,
        title="Saved",
        prompt="something",
        track_count=1,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        snapshot=snapshot,
    )


# Ids the store never mints, each a 400 rather than a lookup miss. The last
# three are forms `uuid.UUID()` accepts but `save()` never writes.
BAD_IDS = (
    "ZZZZZZZZ",
    "abc",
    "0123456789abcdef",
    "deadbeef-x",
    "0f8fad5b7dcb11e0975300215ad9d078",
    "{0f8fad5b-7dcb-11e0-9753-00215ad9d078}",
    "urn:uuid:0f8fad5b-7dcb-11e0-9753-00215ad9d078",
)


@pytest.fixture
def store():
    with (
        patch("backend.api.routes.results.listing.results_store.page") as page,
        patch("backend.api.routes.results.detail.results_store.get") as get,
        patch("backend.api.routes.results.detail.results_store.remove") as remove,
    ):
        page.return_value = ResultListResponse(results=[], total=0)
        get.return_value = None
        remove.return_value = False
        yield page, get, remove


class TestList:
    def test_pages(self, client, store):
        page, _, _ = store

        assert client.get("/api/results?limit=5&offset=10").status_code == 200
        assert page.call_args.kwargs["limit"] == 5
        assert page.call_args.kwargs["offset"] == 10

    def test_accepts_known_types(self, client, store):
        response = client.get("/api/results?type=prompt_playlist,album_recommendation")
        assert response.status_code == 200

    def test_rejects_an_unknown_type(self, client, store):
        """A type outside the set is a client bug, not an empty page."""
        response = client.get("/api/results?type=made_up")

        assert response.status_code == 400
        assert "made_up" in response.json()["detail"]

    def test_rejects_an_out_of_range_limit(self, client, store):
        assert client.get("/api/results?limit=1000").status_code == 422


class TestFetch:
    @pytest.mark.parametrize("result_id", BAD_IDS)
    def test_a_malformed_id_is_400(self, client, store, result_id):
        assert client.get(f"/api/results/{result_id}").status_code == 400

    def test_a_well_formed_id_that_is_gone_is_404(self, client, store):
        assert client.get(f"/api/results/{GOOD_ID}").status_code == 404

    def test_a_malformed_id_never_reaches_the_store(self, client, store):
        _, get, _ = store
        client.get("/api/results/NOTHEX00")
        get.assert_not_called()


class TestSnapshotIsTyped:
    """The snapshot is narrowed to the shape its `type` says it is."""

    def test_a_playlist_snapshot_comes_back_whole(self, client, store):
        _, get, _ = store
        get.return_value = saved("prompt_playlist", PLAYLIST_SNAPSHOT)

        body = client.get(f"/api/results/{GOOD_ID}").json()

        assert body["snapshot"]["playlist_title"] == "Rainy Monday"
        assert body["snapshot"]["tracks"][0]["title"] == "Song"

    def test_an_album_snapshot_comes_back_whole(self, client, store):
        _, get, _ = store
        get.return_value = saved("album_recommendation", ALBUM_SNAPSHOT)

        body = client.get(f"/api/results/{GOOD_ID}").json()

        assert body["snapshot"]["recommendations"][0]["album"] == "Kid A"

    def test_a_snapshot_of_the_wrong_shape_for_its_type_is_refused(self, client, store):
        """The discriminator is `type`; an album payload is not a playlist."""
        _, get, _ = store
        get.return_value = saved("prompt_playlist", ALBUM_SNAPSHOT)

        assert client.get(f"/api/results/{GOOD_ID}").status_code == 422

    def test_a_snapshot_the_models_outgrew_is_422_not_500(self, client, store):
        """An older row is unrenderable, which is an answer rather than a fault."""
        _, get, _ = store
        get.return_value = saved("prompt_playlist", {"tracks": [], "token_count": 1})

        response = client.get(f"/api/results/{GOOD_ID}")

        assert response.status_code == 422
        assert "earlier version" in response.json()["detail"]


class TestDelete:
    def test_deleting_something_gone_is_404(self, client, store):
        assert client.delete(f"/api/results/{GOOD_ID}").status_code == 404

    def test_deleting_succeeds_with_no_body(self, client, store):
        _, _, remove = store
        remove.return_value = True

        response = client.delete(f"/api/results/{GOOD_ID}")

        assert response.status_code == 204
        assert response.content == b""

    def test_a_malformed_id_never_reaches_the_store(self, client, store):
        _, _, remove = store
        client.delete("/api/results/NOTHEX00")
        remove.assert_not_called()
