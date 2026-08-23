"""Tests for ``/api/library`` -- the local mirror's endpoints."""

from unittest.mock import MagicMock, patch

import pytest

from backend.api.background import background
from backend.library import DecadeCount, GenreCount, LibraryStats
from backend.models import LibraryStatsResponse
from backend.plex import PlexQueryError
from tests.api.conftest import connected_plex_mock, serve_plex


@pytest.fixture
def plex_library(client, monkeypatch):
    """A connected Plex client with a small library behind it."""
    plex = connected_plex_mock()
    plex.library.stats.return_value = LibraryStatsResponse(
        total_tracks=100,
        genres=[GenreCount(name="Rock", count=100)],
        decades=[DecadeCount(name="1990s", count=100)],
    )
    plex.library.search.return_value = []

    serve_plex(client.app, monkeypatch, plex)
    yield plex
    client.app.dependency_overrides.clear()


class TestStats:
    def test_reads_live_from_plex(self, client, plex_library):
        data = client.get("/api/library/stats").json()

        assert data["total_tracks"] == 100
        assert data["genres"][0]["name"] == "Rock"

    def test_a_plex_query_failure_is_502(self, client, plex_library):
        """The server answered, badly. That is upstream's fault, not ours."""
        plex_library.library.stats.side_effect = PlexQueryError("timeout reading sections")

        assert client.get("/api/library/stats").status_code == 502

    def test_cached_stats_never_touch_plex(self, client, plex_library):
        with patch(
            "backend.library.tracks.TrackCache.genre_decade_stats",
            return_value=LibraryStats(
                genres=[GenreCount(name="Jazz", count=5)],
                decades=[DecadeCount(name="1960s", count=5)],
            ),
        ):
            data = client.get("/api/library/stats/cached").json()

        plex_library.library.stats.assert_not_called()
        assert data["genres"][0]["name"] == "Jazz"

    def test_cached_stats_do_not_count_tracks(self, client, plex_library):
        """The filter chips do not show it, and counting costs a scan."""
        with patch(
            "backend.library.tracks.TrackCache.genre_decade_stats", return_value=LibraryStats()
        ):
            assert client.get("/api/library/stats/cached").json()["total_tracks"] == 0


class TestSearch:
    def test_passes_the_query_through(self, client, plex_library):
        client.get("/api/library/search?q=nirvana")
        plex_library.library.search.assert_called_once_with("nirvana")

    def test_straightens_ios_smart_quotes(self, client, plex_library):
        """iOS auto-correction curls a typed quote, which matches nothing."""
        client.get("/api/library/search", params={"q": "it\u2019s \u201cok\u201d"})
        plex_library.library.search.assert_called_once_with('it\'s "ok"')

    def test_a_missing_query_is_422(self, client, plex_library):
        assert client.get("/api/library/search").status_code == 422


class TestSync:
    def test_starts_in_the_background(self, client, plex_library, temp_db):
        """Backgrounded so progress can be polled rather than waited on."""
        with patch.object(background, "spawn") as spawn:
            # Closed rather than dropped: an un-awaited coroutine warns at GC.
            spawn.side_effect = lambda coro: coro.close()
            response = client.post("/api/library/sync")

        assert response.status_code == 200
        assert response.json() == {"started": True, "blocking": False}
        spawn.assert_called_once()

    def test_a_second_sync_is_refused(self, client, plex_library):
        running = MagicMock()
        running.snapshot.return_value.is_syncing = True

        with patch("backend.api.routes.library.sync.library.library_sync", running):
            response = client.post("/api/library/sync")

        assert response.status_code == 409


class TestStatus:
    def test_reports_the_cache_and_the_connection(self, client, plex_library, temp_db):
        data = client.get("/api/library/status").json()

        assert data["plex_connected"] is True
        assert data["track_count"] == 0
