"""Tests for one generation run: its matching, its history line, its stream."""

import json
from unittest.mock import MagicMock, patch

from backend.generator.playlists import PlaylistGeneration
from backend.models import Track


def _parse_sse_events(generator):
    """Parse SSE frames from a generation stream into (event, data) tuples."""
    events = []
    event_type = ""
    for raw in generator:
        if raw.startswith(":"):
            continue  # SSE comment (heartbeat)
        for line in raw.strip().split("\n"):
            if line.startswith("event: "):
                event_type = line[len("event: "):]
            elif line.startswith("data: "):
                events.append((event_type, json.loads(line[len("data: "):])))
    return events


class TestMatched:
    """Turning what a model named into the library tracks it meant."""

    @staticmethod
    def named(*tracks: Track) -> list[dict]:
        """Selections naming each track the way a model would."""
        return [{"artist": t.artist, "title": t.title} for t in tracks]

    def test_a_named_track_resolves_to_the_library_one(self, mock_plex_tracks):
        run = PlaylistGeneration()

        matched, _ = run.matched(self.named(mock_plex_tracks[1]), mock_plex_tracks)

        assert [t.rating_key for t in matched] == ["2"]

    def test_the_seed_track_is_skipped(self, mock_plex_tracks):
        """A playlist that opens with the song it grew from reads as a bug."""
        seed = mock_plex_tracks[0]
        run = PlaylistGeneration(seed_track=seed)

        matched, _ = run.matched(self.named(seed, mock_plex_tracks[1]), mock_plex_tracks)

        assert [t.rating_key for t in matched] == ["2"]

    def test_matching_stops_at_the_track_count(self, mock_plex_tracks):
        """A model that returns more than was asked for must not overfill."""
        run = PlaylistGeneration(track_count=2)

        matched, _ = run.matched(self.named(*mock_plex_tracks[:5]), mock_plex_tracks)

        assert len(matched) == 2

    def test_a_reason_is_kept_under_the_matched_rating_key(self, mock_plex_tracks):
        run = PlaylistGeneration()
        selections = [{"artist": "Pearl Jam", "title": "Black", "reason": "Emotional depth"}]

        matched, reasons = run.matched(selections, mock_plex_tracks)

        assert reasons == {matched[0].rating_key: "Emotional depth"}

    def test_a_selection_with_no_reason_records_none(self, mock_plex_tracks):
        run = PlaylistGeneration()

        _, reasons = run.matched(self.named(mock_plex_tracks[1]), mock_plex_tracks)

        assert reasons == {}

    def test_one_library_track_is_used_once(self, mock_plex_tracks):
        """Two selections naming the same song must not duplicate it."""
        wanted = mock_plex_tracks[1]
        run = PlaylistGeneration()

        matched, _ = run.matched(self.named(wanted, wanted), mock_plex_tracks)

        assert [t.rating_key for t in matched] == ["2"]

    def test_nothing_close_matches_nothing(self, mock_plex_tracks):
        run = PlaylistGeneration()
        selections = [{"artist": "Miles Davis", "title": "So What"}]

        matched, reasons = run.matched(selections, mock_plex_tracks)

        assert matched == []
        assert reasons == {}


class TestSubtitle:
    """The line under a run's card in history."""

    def test_a_seed_run_names_the_track_it_grew_from(self, mock_plex_tracks):
        run = PlaylistGeneration(prompt="ignored", seed_track=mock_plex_tracks[0])

        assert run.subtitle(mock_plex_tracks[:3]) == (
            "From: Fake Plastic Trees by Radiohead · 3 tracks"
        )

    def test_a_prompt_run_repeats_the_prompt(self, mock_plex_tracks):
        """The prompt is what the user will recognise the run by."""
        run = PlaylistGeneration(prompt="90s alternative")

        assert run.subtitle(mock_plex_tracks[:3]) == "90s alternative · 3 tracks"

    def test_with_neither_it_is_just_a_count(self):
        assert PlaylistGeneration().subtitle([]) == "0 tracks"


class TestPool:
    """What a run may pick from, before a model is asked."""

    def test_the_request_becomes_the_pool_s_filters(self):
        run = PlaylistGeneration(
            genres=["Rock"], decades=["1990s"], min_rating=8,
            exclude_live=False, max_tracks_to_ai=300,
        )

        assert run.pool.genres == ["Rock"]
        assert run.pool.decades == ["1990s"]
        assert run.pool.min_rating == 8
        assert run.pool.exclude_live is False
        assert run.pool.limit == 300


class TestPlaylistGenerationStream:
    """The stream, end to end, over mocked clients."""

    def test_generate_validates_tracks_against_library(self, mocker, mock_plex_tracks):
        """Generated playlist should only contain tracks from library."""
        from backend.llm import LLMResponse

        mock_response = LLMResponse(
            content=json.dumps([
                {"artist": "Radiohead", "album": "The Bends", "title": "Fake Plastic Trees"},
                {"artist": "Pearl Jam", "album": "Ten", "title": "Black"},
            ]),
            input_tokens=1000,
            output_tokens=100,
            model="test-model", role="analysis")

        with patch("backend.generator.playlists.client_store") as mock_store:
            mock_client = MagicMock()
            mock_client.generate.return_value = mock_response
            mock_client.analyze.return_value = LLMResponse(
                content='{"title": "Test", "narrative": "Test narrative."}',
                input_tokens=100, output_tokens=50, model="test-model", role="analysis")
            mock_store.get.return_value = mock_client

            with patch("backend.generator.playlists.plex_store") as mock_plex:
                mock_plex_client = MagicMock()
                mock_plex_client.library.filtered.return_value = mock_plex_tracks[:5]
                mock_plex.get.return_value = mock_plex_client

                with (
                    patch("backend.library.sync.LibrarySync.has_tracks", return_value=False),
                    patch("backend.generator.playlists.results_store.save", return_value="abc123"),
                ):
                    events = _parse_sse_events(PlaylistGeneration(
                        prompt="90s alternative",
                        genres=["Alternative", "Rock"],
                        decades=["1990s"],
                        track_count=25,
                        exclude_live=True,
                    ).stream())

                    # Collect track rating keys from track batch events
                    track_keys = []
                    for etype, data in events:
                        if etype == "tracks":
                            track_keys.extend(t["rating_key"] for t in data["batch"])

                    library_keys = {t.rating_key for t in mock_plex_tracks}
                    for key in track_keys:
                        assert key in library_keys

    def test_generate_handles_empty_filter_results(self, mocker):
        """Should emit error event when no tracks match filters."""
        with patch("backend.generator.playlists.client_store") as mock_store:
            mock_store.get.return_value = MagicMock()

            with patch("backend.generator.playlists.plex_store") as mock_plex:
                mock_plex_client = MagicMock()
                mock_plex_client.library.filtered.return_value = []
                mock_plex.get.return_value = mock_plex_client

                with patch("backend.library.sync.LibrarySync.has_tracks", return_value=False):
                    events = _parse_sse_events(PlaylistGeneration(
                        prompt="nonexistent genre",
                        genres=["Nonexistent"],
                        decades=["1800s"],
                        track_count=25,
                        exclude_live=True,
                    ).stream())

                    error_events = [d for t, d in events if t == "error"]
                    assert len(error_events) == 1
                    assert "No tracks" in error_events[0]["message"]

    def test_fuzzy_matching_finds_similar_titles(self, mocker, mock_plex_tracks):
        """Should fuzzy match LLM responses to library tracks."""
        from backend.llm import LLMResponse

        mock_response = LLMResponse(
            content=json.dumps([
                {"artist": "Radiohead", "album": "The Bends", "title": "Fake Plastic Tree"},
            ]),
            input_tokens=1000,
            output_tokens=100,
            model="test-model", role="analysis")

        with patch("backend.generator.playlists.client_store") as mock_store:
            mock_client = MagicMock()
            mock_client.generate.return_value = mock_response
            mock_client.analyze.return_value = LLMResponse(
                content='{"title": "Test", "narrative": "Test."}',
                input_tokens=100, output_tokens=50, model="test-model", role="analysis")
            mock_store.get.return_value = mock_client

            with patch("backend.generator.playlists.plex_store") as mock_plex:
                mock_plex_client = MagicMock()
                mock_plex_client.library.filtered.return_value = mock_plex_tracks[:5]
                mock_plex.get.return_value = mock_plex_client

                with (
                    patch("backend.library.sync.LibrarySync.has_tracks", return_value=False),
                    patch("backend.generator.playlists.results_store.save", return_value="abc123"),
                ):
                    events = _parse_sse_events(PlaylistGeneration(
                        prompt="radiohead",
                        genres=["Alternative"],
                        decades=["1990s"],
                        track_count=25,
                        exclude_live=True,
                    ).stream())

                    # Should complete without error
                    error_events = [d for t, d in events if t == "error"]
                    assert len(error_events) == 0
