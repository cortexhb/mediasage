"""Tests for prompt and track analysis."""

import json
from unittest.mock import MagicMock

import pytest

from backend.analyzer import Analyzer
from backend.library import DecadeCount, GenreCount
from backend.llm import LLMClient, LLMResponse
from backend.models import LibraryStatsResponse, Track
from backend.plex import PlexClient

TRACK = Track(
    rating_key="1", title="Fake Plastic Trees", artist="Radiohead",
    album="The Bends", duration_ms=290000, year=1995, genres=["Alternative", "Rock"],
)


def library(
    genres: list[GenreCount] | None = None, decades: list[DecadeCount] | None = None
) -> LibraryStatsResponse:
    """What Plex reports the library holds."""
    return LibraryStatsResponse(
        total_tracks=300,
        genres=genres if genres is not None else [
            GenreCount(name="Alternative", count=100), GenreCount(name="Rock", count=200),
        ],
        decades=decades if decades is not None else [DecadeCount(name="1990s", count=150)],
    )


def build(
    reply: object, stats: LibraryStatsResponse | None = None
) -> tuple[Analyzer, MagicMock]:
    """An analyzer over a model that answers `reply`, and its Plex double.

    The reply is scripted as content and decoded by the real parser, so the
    analyzer is tested against what a model actually sends. The Plex mock is
    returned rather than reached through the analyzer, which types it real.
    """
    llm = MagicMock(spec=LLMClient)
    llm.analyze.return_value = LLMResponse(
        content=reply if isinstance(reply, str) else json.dumps(reply),
        input_tokens=100, output_tokens=50, model="test-model", role="analysis",
    )

    plex = MagicMock(spec=PlexClient)
    plex.library.stats.return_value = stats or library()
    return Analyzer(llm=llm, plex=plex), plex


class TestAnalyzePrompt:
    def test_it_returns_the_genres_the_model_chose(self):
        analyzer, _ = build({"genres": ["Alternative"], "decades": ["1990s"], "reasoning": "why"})

        found = analyzer.analyze_prompt("melancholy 90s alternative")

        assert found.suggested_genres == ["Alternative"]
        assert found.suggested_decades == ["1990s"]
        assert found.reasoning == "why"

    def test_a_genre_the_library_lacks_is_dropped(self):
        """A filter matching nothing is worse than one fewer filter."""
        analyzer, _ = build({"genres": ["Alt Rock", "Rock"], "decades": []})

        assert analyzer.analyze_prompt("90s alt rock").suggested_genres == ["Rock"]

    def test_a_decade_the_library_lacks_is_dropped(self):
        analyzer, _ = build({"genres": [], "decades": ["1970s", "1990s"]})

        assert analyzer.analyze_prompt("test").suggested_decades == ["1990s"]

    def test_it_returns_everything_the_library_offers(self):
        """The UI renders the full list, not just what was suggested."""
        analyzer, _ = build({"genres": ["Rock"], "decades": []})

        found = analyzer.analyze_prompt("rock music from the 90s")

        assert [genre.name for genre in found.available_genres] == ["Alternative", "Rock"]
        assert [decade.name for decade in found.available_decades] == ["1990s"]

    def test_an_answer_with_no_filters_reads_as_none_suggested(self):
        analyzer, _ = build({"reasoning": "nothing matched"})

        found = analyzer.analyze_prompt("test")

        assert found.suggested_genres == []
        assert found.suggested_decades == []

    def test_an_unparseable_answer_raises(self):
        """The endpoint turns this into a 422 the user can act on."""
        analyzer, _ = build("Sorry, I cannot help with that.")

        with pytest.raises(ValueError, match="Failed to parse"):
            analyzer.analyze_prompt("test")

    def test_it_reports_what_the_call_cost(self):
        analyzer, _ = build({"genres": [], "decades": []})

        assert analyzer.analyze_prompt("test").token_count == 150


class TestAnalyzeTrack:
    def test_it_returns_the_dimensions(self):
        analyzer, _ = build({"dimensions": [
            {"id": "mood", "label": "Melancholy, bittersweet", "description": "Reflective"},
            {"id": "era", "label": "Mid-90s British alternative", "description": "Britpop"},
        ]})

        found = analyzer.analyze_track(TRACK)

        assert found.track.rating_key == "1"
        assert [dim.id for dim in found.dimensions] == ["mood", "era"]
        assert found.dimensions[0].label == "Melancholy, bittersweet"

    def test_a_dimension_with_no_id_is_numbered(self):
        analyzer, _ = build({"dimensions": [{"label": "Something"}, {"label": "Else"}]})

        found = analyzer.analyze_track(TRACK)

        assert [dim.id for dim in found.dimensions] == ["dim_0", "dim_1"]

    def test_a_dimension_with_no_label_is_still_returned(self):
        analyzer, _ = build({"dimensions": [{"id": "mood"}]})

        found = analyzer.analyze_track(TRACK)

        assert found.dimensions[0].label == "Unknown dimension"
        assert found.dimensions[0].description == ""

    def test_an_answer_with_no_dimensions_reads_as_empty(self):
        analyzer, _ = build({})

        assert analyzer.analyze_track(TRACK).dimensions == []

    def test_an_unparseable_answer_raises(self):
        analyzer, _ = build("Sorry, I cannot help with that.")

        with pytest.raises(ValueError, match="Failed to parse"):
            analyzer.analyze_track(TRACK)

    def test_it_reports_what_the_call_cost(self):
        analyzer, _ = build({"dimensions": []})

        assert analyzer.analyze_track(TRACK).token_count == 150

    def test_it_never_asks_plex_anything(self):
        """A track carries everything its own analysis needs."""
        analyzer, plex = build({"dimensions": []})

        analyzer.analyze_track(TRACK)

        plex.library.stats.assert_not_called()
