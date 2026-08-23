"""Tests for the filter model that replaced the parallel-list SQL builder."""

import pytest
from sqlalchemy.dialects import postgresql, sqlite

from backend.library.filters import DecadeRange, TrackFilter


class TestDecadeRange:
    """Decades arrive as labels like "1990s" and must survive bad input."""

    @pytest.mark.parametrize("label", ["1990s", "1990", " 1990s ", "1990S"])
    def test_a_decade_label_parses(self, label):
        parsed = DecadeRange.parse(label)
        assert parsed is not None
        assert parsed.start_year == 1990

    @pytest.mark.parametrize("label", ["nineties", "", "199Xs"])
    def test_an_unparseable_label_is_ignored_not_fatal(self, label):
        assert DecadeRange.parse(label) is None

    def test_a_decade_spans_ten_years_inclusive(self):
        assert DecadeRange(start_year=1990).end_year == 1999


class TestValidation:
    """Blank entries arrive from the UI and must not become empty predicates."""

    def test_blank_genres_are_dropped(self):
        assert TrackFilter(genres=["Rock", "", "  "]).genres == ["Rock"]

    def test_surrounding_whitespace_is_trimmed(self):
        assert TrackFilter(genres=[" Rock "]).genres == ["Rock"]

    def test_unparseable_decades_do_not_reach_sql(self):
        assert TrackFilter(decades=["1990s", "nineties"]).decade_ranges[0].start_year == 1990

    def test_genres_are_matched_lowercased(self):
        assert TrackFilter(genres=["ROCK"]).genre_keys == ["rock"]


class TestOfQuery:
    """Genres and decades reach the API as one comma-separated string."""

    def test_a_comma_separated_string_becomes_values(self):
        assert TrackFilter.of_query("Rock,Jazz", "1990s,2000s").genres == ["Rock", "Jazz"]

    def test_the_decades_half_is_read_too(self):
        assert TrackFilter.of_query(None, "1990s").decades == ["1990s"]

    @pytest.mark.parametrize("value", [None, "", " ", ",", ", ,"])
    def test_nothing_selected_selects_nothing(self, value):
        parsed = TrackFilter.of_query(value, value)
        assert (parsed.genres, parsed.decades) == ([], [])

    def test_surrounding_whitespace_is_trimmed(self):
        assert TrackFilter.of_query(" Rock , Jazz ", None).genres == ["Rock", "Jazz"]

    def test_the_other_fields_keep_their_defaults(self):
        parsed = TrackFilter.of_query("Rock", None)
        assert (parsed.min_rating, parsed.exclude_live) == (0, True)


class TestClauses:
    """What each option adds, and what an empty filter does not."""

    def test_an_empty_filter_still_excludes_live_versions(self):
        assert len(TrackFilter().clauses()) == 1

    def test_nothing_is_filtered_when_live_versions_are_kept(self):
        assert TrackFilter(exclude_live=False).clauses() == []

    def test_a_zero_rating_is_not_a_filter(self):
        assert len(TrackFilter(min_rating=0, exclude_live=False).clauses()) == 0

    def test_each_option_adds_one_predicate(self):
        track_filter = TrackFilter(
            genres=["Rock"], decades=["1990s"], min_rating=5, exclude_live=True
        )
        assert len(track_filter.clauses()) == 4

    def test_genres_can_be_left_out_for_album_queries(self):
        track_filter = TrackFilter(genres=["Rock"], exclude_live=False)
        assert track_filter.clauses(include_genres=False) == []


class TestDialectPortability:
    """The same filter has to compile on both shipped backends."""

    @pytest.mark.parametrize("dialect", [sqlite.dialect(), postgresql.dialect()])
    def test_every_clause_compiles(self, dialect):
        track_filter = TrackFilter(genres=["Rock"], decades=["1990s"], min_rating=5)
        for clause in track_filter.clauses():
            assert str(clause.compile(dialect=dialect))

    def test_the_live_predicate_avoids_a_boolean_comparison(self):
        """`== False` would need a noqa; `.is_(False)` renders per dialect."""
        clause = TrackFilter().clauses()[0]
        assert "IS 0" in str(clause.compile(dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True}))
        assert "IS false" in str(clause.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))

    def test_the_genre_clause_correlates_instead_of_joining(self):
        rendered = str(TrackFilter(genres=["Rock"]).genre_clause().compile(dialect=sqlite.dialect()))
        assert "EXISTS" in rendered
        assert "track_genres.rating_key = tracks.rating_key" in rendered


class TestAlbumKeys:
    """Albums qualify on any surviving track, so keys are selected first."""

    def test_no_clause_without_a_genre_filter(self):
        assert TrackFilter(decades=["1990s"]).album_key_clause() is None

    def test_the_clause_selects_qualifying_album_keys(self):
        clause = TrackFilter(genres=["Rock"]).album_key_clause()
        assert clause is not None
        rendered = str(clause.compile(dialect=sqlite.dialect()))
        assert "tracks.parent_rating_key IN" in rendered
