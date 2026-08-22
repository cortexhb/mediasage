"""Tests for turning a filter request into Plex search arguments."""

import pytest

from backend.plex.filters import LIVE_OVERFETCH, MIN_RATING_FIELD, PlexFilter


class TestSearchKwargs:
    """What reaches Plex, and what does not."""

    def test_an_empty_filter_asks_for_nothing(self):
        assert PlexFilter().search_kwargs() == {}

    def test_excluding_live_is_not_sent_to_plex(self):
        """Plex has no notion of a live version; that half is applied after."""
        assert PlexFilter(exclude_live=True).search_kwargs() == {}

    def test_every_field_is_carried(self):
        assert PlexFilter(
            genres=["Rock"], decades=["1990s", "2000s"], min_rating=5
        ).search_kwargs() == {
            "genre": ["Rock"],
            "decade": ["1990", "2000"],
            MIN_RATING_FIELD: 5,
        }

    def test_a_zero_rating_is_no_filter(self):
        assert PlexFilter(min_rating=0).search_kwargs() == {}

    def test_blank_entries_are_dropped(self):
        assert PlexFilter(genres=["Rock", "", "  "]).search_kwargs() == {"genre": ["Rock"]}

    @pytest.mark.parametrize(
        ("label", "expected"), [("1990s", "1990"), ("1990S", "1990"), ("1990", "1990")]
    )
    def test_a_decade_loses_its_suffix(self, label, expected):
        assert PlexFilter(decades=[label]).decade_values == [expected]


class TestFetchCount:
    """How much to over-fetch so a limit survives the live filter."""

    def test_no_limit_asks_for_nothing_extra(self):
        assert PlexFilter().fetch_count(0) == 0

    def test_dropping_live_versions_over_fetches(self):
        assert PlexFilter(exclude_live=True).fetch_count(100) == int(100 * LIVE_OVERFETCH)

    def test_keeping_them_asks_for_exactly_the_limit(self):
        assert PlexFilter(exclude_live=False).fetch_count(100) == 100
