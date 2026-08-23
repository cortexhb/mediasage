"""Tests for the read side of the track cache."""

import pytest

from backend.library import track_cache
from backend.library.filters import TrackFilter


class TestReads:
    """Everything comes back as models, not rows."""

    def test_all_tracks_returns_every_cached_track(self, sample_library):
        assert len(track_cache.all()) == 4

    def test_genres_come_back_as_a_list(self, sample_library):
        by_key = {track.rating_key: track for track in track_cache.all()}
        assert by_key["1"].genres == ["Rock"]

    def test_an_empty_cache_reads_as_empty(self, temp_db):
        assert track_cache.all() == []


class TestFiltering:
    """The filter decides the predicate; this module decides the shape."""

    def test_live_versions_are_excluded_by_default(self, sample_library):
        assert track_cache.count(TrackFilter()) == 3

    def test_live_versions_can_be_kept(self, sample_library):
        assert track_cache.count(TrackFilter(exclude_live=False)) == 4

    def test_a_genre_filter_matches_case_insensitively(self, sample_library):
        assert track_cache.count(TrackFilter(genres=["ROCK"], exclude_live=False)) == 3

    def test_several_genres_match_any_of_them(self, sample_library):
        assert track_cache.count(TrackFilter(genres=["Rock", "Jazz"], exclude_live=False)) == 4

    def test_a_decade_filter_bounds_the_year(self, sample_library):
        assert track_cache.count(TrackFilter(decades=["1990s"], exclude_live=False)) == 3

    def test_several_decades_match_any_of_them(self, sample_library):
        assert track_cache.count(TrackFilter(decades=["1990s", "2000s"], exclude_live=False)) == 4

    def test_a_rating_filter_is_a_minimum(self, sample_library):
        assert track_cache.count(TrackFilter(min_rating=5, exclude_live=False)) == 1

    def test_filters_combine(self, sample_library):
        assert track_cache.count(TrackFilter(genres=["Rock"], decades=["2000s"])) == 0

    def test_an_unknown_genre_matches_nothing(self, sample_library):
        assert track_cache.count(TrackFilter(genres=["Polka"])) == 0

    def test_filtered_returns_the_same_tracks_it_counts(self, sample_library):
        track_filter = TrackFilter(genres=["Rock"])
        assert len(track_cache.filtered(track_filter)) == track_cache.count(track_filter)


class TestSampling:
    """Sampling moved into SQL; a genre filter used to skip the limit."""

    def test_a_limit_caps_the_result(self, sample_library):
        assert len(track_cache.filtered(TrackFilter(exclude_live=False), limit=2)) == 2

    def test_a_limit_applies_with_a_genre_filter(self, sample_library):
        assert (
            len(track_cache.filtered(TrackFilter(genres=["Rock"], exclude_live=False), limit=1))
            == 1
        )

    def test_no_limit_returns_everything(self, sample_library):
        assert len(track_cache.filtered(TrackFilter(exclude_live=False), limit=0)) == 4

    def test_a_limit_beyond_the_library_is_harmless(self, sample_library):
        assert len(track_cache.filtered(TrackFilter(exclude_live=False), limit=99)) == 4


class TestStats:
    """Genre counts come from the index, decade counts from the year column."""

    def test_genres_are_counted_from_the_index(self, sample_library):
        stats = track_cache.genre_decade_stats()
        assert {genre.name: genre.count for genre in stats.genres} == {"Rock": 3, "Jazz": 1}

    def test_genres_are_sorted_by_name(self, sample_library):
        names = [genre.name for genre in track_cache.genre_decade_stats().genres]
        assert names == sorted(names)

    def test_years_are_bucketed_into_decades(self, sample_library):
        stats = track_cache.genre_decade_stats()
        assert {decade.name: decade.count for decade in stats.decades} == {"1990s": 3, "2000s": 1}

    @pytest.mark.parametrize("year", [None, 0])
    def test_tracks_without_a_year_are_left_out(self, seed_tracks, year):
        seed_tracks({"rating_key": "1", "title": "T", "artist": "A", "album": "B", "year": year})
        assert track_cache.genre_decade_stats().decades == []

    def test_an_empty_cache_reports_nothing(self, temp_db):
        stats = track_cache.genre_decade_stats()
        assert (stats.genres, stats.decades) == ([], [])
