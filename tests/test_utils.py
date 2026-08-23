"""Tests for comparing names two catalogues spelled differently."""

import pytest

from backend.utils import FuzzyMatcher


class TestFolding:
    """What a title is reduced to before it is compared."""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("Don't Stop", "dont stop"),
            ("(Remastered)", "remastered"),
            ("Rock & Roll", "rock  roll"),
            ("Café", "cafe"),
            ("Motörhead", "motorhead"),
            ("ALREADY plain", "already plain"),
        ],
    )
    def test_it_strips_what_carries_no_meaning(self, text, expected):
        assert FuzzyMatcher.folded(text) == expected


class TestRatio:
    """How alike two names score once folded."""

    def test_identical_after_folding_scores_full_marks(self):
        """Punctuation and case must not cost a point."""
        assert FuzzyMatcher.ratio("Don't Stop", "dont stop") == 100

    def test_an_accent_costs_nothing(self):
        """Plex and a model disagree about accents constantly."""
        assert FuzzyMatcher.ratio("Motörhead", "Motorhead") == 100

    def test_unrelated_names_score_low(self):
        """A floor is only useful if unrelated names fall under it."""
        assert FuzzyMatcher.ratio("Radiohead", "Dolly Parton") < 40
