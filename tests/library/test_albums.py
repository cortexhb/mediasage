"""Tests for album aggregation and familiarity."""

from datetime import UTC, datetime

import pytest

from backend.library import album_cache
from backend.library.filters import TrackFilter


def by_key(candidates) -> dict:
    return {candidate.parent_rating_key: candidate for candidate in candidates}


class TestCandidates:
    """Albums are derived by grouping tracks, not mirrored as rows."""

    def test_one_candidate_per_album(self, sample_library):
        assert len(album_cache.candidates(TrackFilter(exclude_live=False))) == 2

    def test_tracks_are_counted_per_album(self, sample_library):
        assert (
            by_key(album_cache.candidates(TrackFilter(exclude_live=False)))["100"].track_count == 3
        )

    def test_track_keys_are_collected(self, sample_library):
        candidate = by_key(album_cache.candidates(TrackFilter(exclude_live=False)))["100"]
        assert candidate.track_rating_keys == ["1", "2", "3"]

    def test_the_album_artist_comes_from_the_artist_column(self, sample_library):
        assert by_key(album_cache.candidates(TrackFilter()))["100"].album_artist == "Artist A"

    def test_the_decade_is_derived_from_the_year(self, sample_library):
        assert by_key(album_cache.candidates(TrackFilter()))["100"].decade == "1990s"

    def test_an_album_without_a_year_has_no_decade(self, seed_tracks):
        seed_tracks(
            {
                "rating_key": "1",
                "title": "T",
                "artist": "A",
                "album": "B",
                "parent_rating_key": "100",
            }
        )
        assert album_cache.candidates(TrackFilter())[0].decade == ""

    def test_tracks_with_no_album_key_are_excluded(self, seed_tracks):
        seed_tracks(
            {
                "rating_key": "1",
                "title": "T",
                "artist": "A",
                "album": "B",
                "parent_rating_key": None,
            },
            {"rating_key": "2", "title": "T", "artist": "A", "album": "B", "parent_rating_key": ""},
        )
        assert album_cache.candidates(TrackFilter()) == []

    def test_an_empty_cache_yields_no_albums(self, temp_db):
        assert album_cache.candidates(TrackFilter()) == []


class TestCandidateGenres:
    """Genres are unioned across an album's tracks."""

    def test_genres_are_unioned(self, seed_tracks):
        seed_tracks(
            {
                "rating_key": "1",
                "title": "T",
                "artist": "A",
                "album": "B",
                "parent_rating_key": "100",
                "genres": ["Rock"],
            },
            {
                "rating_key": "2",
                "title": "T",
                "artist": "A",
                "album": "B",
                "parent_rating_key": "100",
                "genres": ["Blues"],
            },
        )
        assert album_cache.candidates(TrackFilter())[0].genres == ["Rock", "Blues"]

    def test_case_variants_collapse(self, sample_library):
        assert by_key(album_cache.candidates(TrackFilter()))["100"].genres == ["Rock"]


class TestCandidateFiltering:
    """An album qualifies on any surviving track, not on all of them."""

    def test_a_genre_filter_selects_whole_albums(self, sample_library):
        assert list(by_key(album_cache.candidates(TrackFilter(genres=["Jazz"])))) == ["200"]

    def test_a_qualifying_album_keeps_its_other_tracks(self, seed_tracks):
        seed_tracks(
            {
                "rating_key": "1",
                "title": "T",
                "artist": "A",
                "album": "B",
                "parent_rating_key": "100",
                "genres": ["Rock"],
            },
            {
                "rating_key": "2",
                "title": "T",
                "artist": "A",
                "album": "B",
                "parent_rating_key": "100",
                "genres": [],
            },
        )
        assert album_cache.candidates(TrackFilter(genres=["Rock"]))[0].track_count == 2

    def test_live_tracks_are_dropped_from_the_count(self, sample_library):
        assert by_key(album_cache.candidates(TrackFilter()))["100"].track_count == 2

    def test_a_decade_filter_selects_albums(self, sample_library):
        assert list(by_key(album_cache.candidates(TrackFilter(decades=["2000s"])))) == ["200"]


class TestFamiliarity:
    """Play counts are aggregated per album and classified."""

    def test_an_unplayed_album_is_unplayed(self, sample_library, library_settings):
        assert album_cache.familiarity()["200"].level == "unplayed"

    def test_a_lightly_played_album_is_light(self, sample_library, library_settings):
        assert album_cache.familiarity()["100"].level == "light"

    def test_the_well_loved_threshold_is_configurable(self, sample_library, library_settings):
        library_settings(well_loved_avg_plays=2.0)
        assert album_cache.familiarity()["100"].level == "well-loved"

    def test_the_last_play_is_the_most_recent_across_tracks(self, sample_library, library_settings):
        assert (
            album_cache.familiarity()["100"].last_viewed_at
            == datetime(2026, 1, 1, tzinfo=UTC).isoformat()
        )

    def test_specific_albums_can_be_requested(self, sample_library, library_settings):
        assert list(album_cache.familiarity(["200"])) == ["200"]

    def test_an_unknown_album_is_simply_absent(self, sample_library, library_settings):
        assert album_cache.familiarity(["nope"]) == {}

    @pytest.mark.parametrize("keys", [None, []])
    def test_no_keys_means_every_album(self, sample_library, library_settings, keys):
        expected = 2 if keys is None else 0
        assert len(album_cache.familiarity(keys)) == expected
