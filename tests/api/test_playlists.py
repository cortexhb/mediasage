"""Tests for ``/api/playlist``, ``/api/play-queue`` and the generation stream."""

from unittest.mock import MagicMock, patch

import pytest

from backend.plex import PlaylistResult, PlaylistUpdateResult, PlayQueueResult
from tests.api.conftest import connected_plex


@pytest.fixture
def plex_writer():
    """A connected Plex client whose writes all succeed."""
    plex = connected_plex()
    plex.create_playlist.return_value = PlaylistResult(
        success=True, playlist_id="42", track_count=3
    )
    plex.update_playlist.return_value = PlaylistUpdateResult(success=True, track_count=3)
    plex.play_queue.return_value = PlayQueueResult(success=True, track_count=3)
    plex.playlists.return_value = []
    plex.clients.return_value = []

    store = MagicMock()
    store.get.return_value = plex
    with patch("backend.api.guards.plex_store", store):
        yield plex


class TestSavePlaylist:
    def test_writes_to_plex(self, client, plex_writer):
        response = client.post(
            "/api/playlist",
            json={"name": "Test", "rating_keys": ["1", "2", "3"], "description": "why"},
        )

        assert response.status_code == 200
        plex_writer.create_playlist.assert_called_once_with("Test", ["1", "2", "3"], "why")


class TestUpdatePlaylist:
    def test_appends(self, client, plex_writer):
        response = client.post(
            "/api/playlist/update",
            json={"playlist_id": "42", "rating_keys": ["4"], "mode": "append"},
        )

        assert response.status_code == 200
        assert plex_writer.update_playlist.call_args[0][2] == "append"

    def test_a_failed_write_is_500(self, client, plex_writer):
        plex_writer.update_playlist.return_value = PlaylistUpdateResult(
            success=False, error="Playlist is locked"
        )

        response = client.post(
            "/api/playlist/update",
            json={"playlist_id": "42", "rating_keys": ["4"], "mode": "replace"},
        )

        assert response.status_code == 500
        assert response.json()["detail"] == "Playlist is locked"


class TestPlayQueue:
    def test_starts_playback(self, client, plex_writer):
        response = client.post(
            "/api/play-queue", json={"rating_keys": ["1"], "client_id": "abc", "mode": "replace"}
        )

        assert response.status_code == 200

    def test_a_client_that_went_away_is_404(self, client, plex_writer):
        """It was listed a moment ago; the user can just pick another."""
        plex_writer.play_queue.return_value = PlayQueueResult(
            success=False, error="Client not found", error_code="not_found"
        )

        response = client.post(
            "/api/play-queue", json={"rating_keys": ["1"], "client_id": "gone", "mode": "replace"}
        )

        assert response.status_code == 404

    def test_any_other_failure_is_500(self, client, plex_writer):
        plex_writer.play_queue.return_value = PlayQueueResult(
            success=False, error="Transcoder unavailable"
        )

        response = client.post(
            "/api/play-queue", json={"rating_keys": ["1"], "client_id": "abc", "mode": "replace"}
        )

        assert response.status_code == 500


class TestGenerateStream:
    def test_a_bad_seed_track_is_404_before_the_stream_opens(self, client, plex_writer):
        """Better a status code than an error frame the user has to read."""
        plex_writer.track_by_key.return_value = None

        with patch("backend.api.guards.client_store") as llm:
            llm.get.return_value = MagicMock()
            response = client.post(
                "/api/generate/stream",
                json={
                    "prompt": "test",
                    "genres": [],
                    "decades": [],
                    "seed_track": {"rating_key": "999", "selected_dimensions": []},
                },
            )

        assert response.status_code == 404

    def test_streams_as_server_sent_events(self, client, plex_writer):
        with (
            patch("backend.api.guards.client_store") as llm,
            patch(
                "backend.api.routes.playlists.generate_playlist_stream",
                return_value=iter(["event: progress\ndata: {}\n\n"]),
            ),
        ):
            llm.get.return_value = MagicMock()
            response = client.post("/api/generate/stream", json={"prompt": "test", "genres": [], "decades": []})

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["x-accel-buffering"] == "no"
