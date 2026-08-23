"""Tests for the shapes one generation passes between its steps."""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from backend.generator.models import Narrative, TrackMatcher, TrackPool
from backend.library.models import TrackRecord
from backend.llm import LLMResponse
from backend.models import Track


def candidate(artist: str, title: str) -> Track:
    """A library track, with only the compared fields worth setting."""
    return Track(rating_key="1", title=title, artist=artist, album="Record", duration_ms=180000)


class TestCachedTracks:
    """The cache path, which is the one a synced library actually takes."""

    def test_a_cached_row_becomes_a_track(self, temp_db):
        """`library.tracks` answers with models, not the dicts this once read."""
        cached = TrackRecord(
            rating_key="42", title="Song", artist="Band", album="Record",
            duration_ms=180000, year=1994, genres=["Rock"],
        )
        with (
            patch("backend.library.sync.LibrarySync.has_tracks", return_value=True),
            patch("backend.library.tracks.TrackCache.filtered", return_value=[cached]),
        ):
            tracks = TrackPool(limit=100).tracks(MagicMock())

        assert [track.rating_key for track in tracks] == ["42"]
        assert tracks[0].genres == ["Rock"]

    def test_art_is_proxied_under_the_rating_key(self, temp_db):
        """The cache stores no art URL, so it has to be derived."""
        cached = TrackRecord(rating_key="42", title="Song", artist="Band", album="Record")
        with (
            patch("backend.library.sync.LibrarySync.has_tracks", return_value=True),
            patch("backend.library.tracks.TrackCache.filtered", return_value=[cached]),
        ):
            tracks = TrackPool(limit=100).tracks(MagicMock())

        assert tracks[0].art_url == "/api/art/42"


class TestArtistVariants:
    """The spellings one act is filed under."""

    def test_an_ampersand_gains_the_written_form(self):
        assert TrackMatcher.variants("Simon & Garfunkel") == [
            "Simon & Garfunkel",
            "Simon and Garfunkel",
        ]

    def test_the_written_form_gains_an_ampersand(self):
        assert TrackMatcher.variants("Tom and Jerry") == ["Tom and Jerry", "Tom & Jerry"]

    def test_a_plain_name_has_one_spelling(self):
        assert TrackMatcher.variants("Radiohead") == ["Radiohead"]


class TestTrackMatching:
    """Whether a track a model named is one the library holds."""

    def test_a_near_spelling_of_both_halves_matches(self):
        matcher = TrackMatcher(floor=60)
        assert matcher.matches(
            "Radiohead", "Fake Plastic Tree", candidate("Radiohead", "Fake Plastic Trees")
        )

    def test_a_title_below_the_floor_is_rejected(self):
        """A wrong match plays the wrong song, so the title has to hold up."""
        matcher = TrackMatcher(floor=60)
        assert not matcher.matches(
            "Radiohead", "Paranoid Android", candidate("Radiohead", "Fake Plastic Trees")
        )

    def test_an_ampersand_variant_of_the_artist_is_accepted(self):
        """Written out, the name scores below this floor; the variant carries it."""
        matcher = TrackMatcher(floor=90)
        assert matcher.ratio("Hall and Oates", "Hall & Oates") < 90
        assert matcher.matches(
            "Hall and Oates", "Sara Smile", candidate("Hall & Oates", "Sara Smile")
        )

    def test_a_wrong_artist_is_rejected(self):
        matcher = TrackMatcher(floor=60)
        assert not matcher.matches(
            "Pearl Jam", "Fake Plastic Trees", candidate("Radiohead", "Fake Plastic Trees")
        )


class TestConfiguredFloor:
    """The floor comes from `MatchingConfig`; a library's tagging decides it."""

    def test_it_reads_the_configured_threshold(self, tuned):
        tuned("matching", track_threshold=77)

        assert TrackMatcher.configured().floor == 77

    def test_a_lower_floor_admits_what_a_higher_one_rejects(self, tuned):
        held = candidate("Radiohead", "Fake Plastic Trees")

        tuned("matching", track_threshold=99)
        assert not TrackMatcher.configured().matches("Radiohead", "Fake Plastic Tree", held)

        tuned("matching", track_threshold=60)
        assert TrackMatcher.configured().matches("Radiohead", "Fake Plastic Tree", held)


class TestNarrative:
    """The title and the few sentences a finished playlist is presented with."""

    @staticmethod
    def answering(payload: object) -> MagicMock:
        """An LLM client whose analysis call answers with `payload` as JSON."""
        client = MagicMock()
        client.analyze.return_value = LLMResponse(
            content=json.dumps(payload), input_tokens=500, output_tokens=50,
            model="test-model", role="analysis",
        )
        return client

    def selections(self) -> list[dict]:
        return [
            {"artist": "Radiohead", "title": "Fake Plastic Trees", "reason": "Melancholy"},
            {"artist": "Pearl Jam", "title": "Black", "reason": "Emotional depth"},
        ]

    def test_it_returns_the_title_and_the_narrative(self):
        client = self.answering({
            "title": "Rainstorm Reverie",
            "narrative": "It weaves through 'Fake Plastic Trees' and 'Black'.",
        })

        written = Narrative.of(self.selections(), client)

        assert written.title.startswith("Rainstorm Reverie - ")
        assert written.text == "It weaves through 'Fake Plastic Trees' and 'Black'."

    def test_the_title_carries_the_month_and_year(self):
        """The playlist name has to stay distinct across months."""
        client = self.answering({"title": "Rainstorm Reverie", "narrative": "x"})

        written = Narrative.of(self.selections(), client)

        assert written.title.endswith(datetime.now().strftime("%b %Y"))

    def test_a_failed_call_falls_back_to_a_dated_title(self):
        client = MagicMock()
        client.analyze.side_effect = RuntimeError("LLM error")

        written = Narrative.of(self.selections(), client)

        assert written.title == f"{datetime.now().strftime('%b %Y')} Playlist"
        assert written.text == ""

    def test_a_long_narrative_is_not_truncated(self):
        """The prompt guides the length; cutting mid-sentence reads worse."""
        long_narrative = "A" * 600
        client = self.answering({"title": "Test", "narrative": long_narrative})

        written = Narrative.of(self.selections(), client)

        assert written.text == long_narrative

    def test_an_array_wrapped_answer_is_unwrapped(self):
        """Some models wrap the object they were asked for in an array."""
        client = self.answering([{"title": "Wrapped", "narrative": "In an array."}])

        written = Narrative.of(self.selections(), client)

        assert written.title.startswith("Wrapped - ")
        assert written.text == "In an array."

    def test_an_empty_array_falls_back(self):
        client = self.answering([])

        written = Narrative.of(self.selections(), client)

        assert written.title == f"{datetime.now().strftime('%b %Y')} Playlist"
        assert written.text == ""

    @pytest.mark.parametrize("key", ["description", "text", "content"])
    def test_an_alternate_narrative_key_is_read(self, key):
        """Models rename this field freely; the text is what matters."""
        client = self.answering({"title": "Alt Key Test", key: "Under another name."})

        assert Narrative.of(self.selections(), client).text == "Under another name."

    def test_the_narrative_key_wins_over_the_alternatives(self):
        client = self.answering({
            "title": "Test", "narrative": "Primary value", "description": "Not this",
        })

        assert Narrative.of(self.selections(), client).text == "Primary value"

    def test_an_empty_narrative_falls_through_to_an_alternative(self):
        client = self.answering({
            "title": "Test", "narrative": "", "description": "Fallback used",
        })

        assert Narrative.of(self.selections(), client).text == "Fallback used"

    def test_a_title_with_no_narrative_still_returns(self):
        """Worth showing: the playlist is named even when the note is missing."""
        client = self.answering({"title": "Named Only"})

        written = Narrative.of(self.selections(), client)

        assert written.title.startswith("Named Only - ")
        assert written.text == ""
