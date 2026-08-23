"""Tests for ``/api/analyze`` and ``/api/filter/preview``."""

from unittest.mock import MagicMock, patch

import pytest

from backend.library import DecadeCount, GenreCount
from backend.llm import client_store
from backend.models import AnalyzePromptResponse, AnalyzeTrackResponse, Track
from backend.plex import PlexQueryError
from tests.api.conftest import connected_plex_mock, mediasage_config, serve_plex

TRACK = Track(
    rating_key="1",
    title="Fake Plastic Trees",
    artist="Radiohead",
    album="The Bends",
    duration_ms=290000,
    year=1995,
    genres=["Alternative"],
)


@pytest.fixture
def analysable(client, monkeypatch):
    """Plex connected, an LLM configured, and one track findable."""
    plex = connected_plex_mock()
    plex.library.track_by_key.return_value = TRACK
    plex.library.count.return_value = 500

    serve_plex(client.app, monkeypatch, plex)
    client.app.dependency_overrides[client_store.require] = lambda: MagicMock()

    with patch("backend.config.store.ConfigStore.get", return_value=mediasage_config()):
        yield plex
    client.app.dependency_overrides.clear()


def analyzer(method: str, return_value: object = None, side_effect: Exception | None = None):
    """Patch the analyzer the route builds, scripting one of its two calls."""
    built = MagicMock()
    setattr(built, method, MagicMock(return_value=return_value, side_effect=side_effect))
    return patch("backend.api.routes.analyze.analysis.Analyzer", return_value=built)


class TestAnalyzePrompt:
    def test_returns_the_analysis(self, client, analysable):
        answer = AnalyzePromptResponse(
            suggested_genres=["Rock"],
            suggested_decades=["1990s"],
            available_genres=[GenreCount(name="Rock", count=100)],
            available_decades=[DecadeCount(name="1990s", count=100)],
            reasoning="why",
        )
        with analyzer("analyze_prompt", return_value=answer):
            response = client.post("/api/analyze/prompt", json={"prompt": "90s rock"})

        assert response.status_code == 200
        assert response.json()["suggested_genres"] == ["Rock"]

    def test_an_unusable_reply_is_422(self, client, analysable):
        """The user can act on this one by rephrasing."""
        with analyzer("analyze_prompt", side_effect=ValueError("Invalid JSON")):
            response = client.post("/api/analyze/prompt", json={"prompt": "test"})

        assert response.status_code == 422
        assert "Invalid JSON" in response.json()["detail"]

    def test_anything_else_is_500(self, client, analysable):
        with analyzer("analyze_prompt", side_effect=RuntimeError("connection reset")):
            assert client.post("/api/analyze/prompt", json={"prompt": "test"}).status_code == 500


class TestAnalyzeTrack:
    def test_returns_the_dimensions(self, client, analysable):
        answer = AnalyzeTrackResponse(track=TRACK, dimensions=[])
        with analyzer("analyze_track", return_value=answer):
            response = client.post("/api/analyze/track", json={"rating_key": "1"})

        assert response.status_code == 200

    def test_a_missing_track_is_404(self, client, analysable):
        analysable.library.track_by_key.return_value = None

        assert client.post("/api/analyze/track", json={"rating_key": "999"}).status_code == 404


class TestFilterPreview:
    def preview(self, client, **overrides):
        body = {"genres": [], "decades": [], "track_count": 25, "max_tracks_to_ai": 500}
        body.update(overrides)
        return client.post("/api/filter/preview", json=body)

    def test_counts_from_the_cache_when_there_is_one(self, client, analysable, temp_db):
        with (
            patch("backend.library.sync.LibrarySync.has_tracks", return_value=True),
            patch("backend.library.tracks.TrackCache.count", return_value=1234) as counted,
        ):
            data = self.preview(client).json()

        counted.assert_called_once()
        analysable.library.count.assert_not_called()
        assert data["matching_tracks"] == 1234

    def test_falls_back_to_plex_without_a_cache(self, client, analysable, temp_db):
        with patch("backend.library.sync.LibrarySync.has_tracks", return_value=False):
            data = self.preview(client).json()

        analysable.library.count.assert_called_once()
        assert data["matching_tracks"] == 500

    def test_a_plex_query_failure_is_502(self, client, analysable, temp_db):
        analysable.library.count.side_effect = PlexQueryError("timeout")

        with patch("backend.library.sync.LibrarySync.has_tracks", return_value=False):
            assert self.preview(client).status_code == 502

    def test_caps_what_would_be_sent(self, client, analysable, temp_db):
        with (
            patch("backend.library.sync.LibrarySync.has_tracks", return_value=True),
            patch("backend.library.tracks.TrackCache.count", return_value=5000),
        ):
            data = self.preview(client, max_tracks_to_ai=100).json()

        assert data["tracks_to_send"] == 100
