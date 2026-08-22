"""Tests for normalizing text before fuzzy comparison."""

import pytest

from backend.matching import artist_variants, simplify


class TestSimplify:
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
        assert simplify(text) == expected


class TestArtistVariants:
    """The spellings one act is filed under."""

    def test_an_ampersand_gains_the_written_form(self):
        assert artist_variants("Simon & Garfunkel") == [
            "Simon & Garfunkel",
            "Simon and Garfunkel",
        ]

    def test_the_written_form_gains_an_ampersand(self):
        assert artist_variants("Tom and Jerry") == ["Tom and Jerry", "Tom & Jerry"]

    def test_a_plain_name_has_one_spelling(self):
        assert artist_variants("Radiohead") == ["Radiohead"]
