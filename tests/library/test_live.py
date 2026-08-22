"""Tests for the configurable live-recording rule."""

import pytest

from backend.config import LibraryConfig
from backend.library.live import LiveVersionRule


@pytest.fixture
def default_rule() -> LiveVersionRule:
    return LiveVersionRule.of(LibraryConfig())


class TestDefaults:
    """Out of the box, keywords and dated titles both mark a track live."""

    @pytest.mark.parametrize("title", ["Song (Live)", "Song - LIVE", "Concert Version", "Bootleg Take"])
    def test_a_keyword_in_the_title_matches(self, default_rule, title):
        assert default_rule.matches(title, "Album") is True

    def test_a_keyword_in_the_album_matches(self, default_rule):
        assert default_rule.matches("Song", "Live at Knebworth") is True

    @pytest.mark.parametrize("text", ["1994-05-08", "1994/05/08"])
    def test_a_dated_title_matches(self, default_rule, text):
        assert default_rule.matches(text, "Album") is True

    def test_a_studio_track_does_not_match(self, default_rule):
        assert default_rule.matches("Fake Plastic Trees", "The Bends") is False

    def test_a_keyword_inside_a_word_does_not_match(self, default_rule):
        """Word boundaries: "Oliver" must not read as "live"."""
        assert default_rule.matches("Oliver's Army", "Armed Forces") is False


class TestConfiguration:
    """Both halves of the rule are the user's to turn off."""

    def test_dates_can_be_ignored_for_dated_studio_work(self):
        rule = LiveVersionRule.of(LibraryConfig(dated_titles_are_live=False))
        assert rule.matches("1994-05-08", "Album") is False

    def test_keywords_can_be_replaced(self):
        rule = LiveVersionRule.of(LibraryConfig(live_keywords=["unplugged"]))
        assert rule.matches("Song (Live)", "Album") is False
        assert rule.matches("Song Unplugged", "Album") is True

    def test_an_empty_keyword_list_disables_keyword_matching(self):
        rule = LiveVersionRule.of(LibraryConfig(live_keywords=[], dated_titles_are_live=False))
        assert rule.matches("Song (Live)", "1994-05-08") is False

    def test_blank_keywords_do_not_match_everything(self):
        rule = LiveVersionRule.of(
            LibraryConfig(live_keywords=["", "  "], dated_titles_are_live=False)
        )
        assert rule.matches("Song", "Album") is False

    def test_keywords_with_regex_characters_are_taken_literally(self):
        rule = LiveVersionRule.of(
            LibraryConfig(live_keywords=["a.b"], dated_titles_are_live=False)
        )
        assert rule.matches("axb", "Album") is False
        assert rule.matches("a.b", "Album") is True
