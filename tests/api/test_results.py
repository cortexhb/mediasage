"""Tests for ``/api/results`` -- the saved history."""

from unittest.mock import patch

import pytest

from backend.results import ResultListResponse

# Ids the store never mints. Each has to be a 400 rather than a lookup miss.
BAD_IDS = ("ZZZZZZZZ", "abc", "0" * 20, "deadbeef-x")


@pytest.fixture
def store():
    with (
        patch("backend.api.routes.results.results_store.page") as page,
        patch("backend.api.routes.results.results_store.get") as get,
        patch("backend.api.routes.results.results_store.remove") as remove,
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
        assert client.get("/api/results/deadbeef").status_code == 404

    def test_a_malformed_id_never_reaches_the_store(self, client, store):
        _, get, _ = store
        client.get("/api/results/NOTHEX00")
        get.assert_not_called()


class TestDelete:
    def test_deleting_something_gone_is_404(self, client, store):
        assert client.delete("/api/results/deadbeef").status_code == 404

    def test_deleting_succeeds_with_no_body(self, client, store):
        _, _, remove = store
        remove.return_value = True

        response = client.delete("/api/results/deadbeef")

        assert response.status_code == 204
        assert response.content == b""

    def test_a_malformed_id_never_reaches_the_store(self, client, store):
        _, _, remove = store
        client.delete("/api/results/NOTHEX00")
        remove.assert_not_called()
