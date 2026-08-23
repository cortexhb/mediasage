"""Tests for turning raw research into facts a pitch can be held to."""

from backend.recommender.facts import SUMMARY_CHARS, Facts
from backend.recommender.models import AlbumRecommendation, AlbumRef, ExtractedFacts, ResearchData
from tests.recommender.conftest import prompts_of

REF = AlbumRef(artist="Sigur Rós", album="Ágætis byrjun")


def research() -> ResearchData:
    """One album with every kind of source found."""
    return ResearchData(
        wikipedia_summary="Ágætis byrjun is the second album by Sigur Rós",
        review_texts=["Pitchfork review content", "Stereogum review content"],
        track_listing=["Intro", "Svefn-g-englar", "Starálfur"],
        label="Smekkleysa",
        release_date="1999-06-12",
        credits={"Primary Artist": "Sigur Rós"},
    )


class TestExtract:
    def test_returns_structured_facts(self, metered):
        call, llm = metered(
            {
                "origin_story": "Recorded in Reykjavik",
                "personnel": ["Jónsi"],
                "vocal_approach": "Mostly Icelandic, Vonlenska on 2 tracks only",
            }
        )

        extracted = Facts(call=call).extract(REF, research())

        assert isinstance(extracted, ExtractedFacts)
        assert extracted.origin_story == "Recorded in Reykjavik"
        assert "Vonlenska" in extracted.vocal_approach
        llm.generate.assert_called_once()

    def test_every_source_reaches_the_prompt(self, metered):
        call, llm = metered({})

        Facts(call=call).extract(REF, research())

        _, user = prompts_of(llm.generate)
        assert "Ágætis byrjun is the second album" in user
        assert "Pitchfork review content" in user
        assert "Stereogum review content" in user
        assert "Svefn-g-englar" in user
        assert "Smekkleysa" in user
        assert "Primary Artist: Sigur Rós" in user

    def test_wikipedia_is_not_truncated(self, metered):
        """The pitch reads the full article; an earlier version cut it at 500."""
        call, llm = metered({})
        long_summary = "x" * 3000

        Facts(call=call).extract(REF, ResearchData(wikipedia_summary=long_summary))

        assert long_summary in prompts_of(llm.generate)[1]

    def test_track_listing_is_copied_not_extracted(self, metered):
        """It comes from MusicBrainz, so the fact-checker treats it as authoritative."""
        call, _ = metered({"track_listing": ["Something The Model Invented"]})

        extracted = Facts(call=call).extract(REF, research())

        assert extracted.track_listing == ["Intro", "Svefn-g-englar", "Starálfur"]

    def test_no_sources_says_so(self, metered):
        call, llm = metered({"source_coverage": "No Wikipedia or review sources available"})

        extracted = Facts(call=call).extract(REF, ResearchData())

        assert "No sources available." in prompts_of(llm.generate)[1]
        assert isinstance(extracted, ExtractedFacts)

    def test_a_non_object_reply_yields_empty_facts(self, metered):
        call, _ = metered(["not an object"])
        assert Facts(call=call).extract(REF, ResearchData()) == ExtractedFacts()


class TestMatchesRequest:
    def rec(self) -> AlbumRecommendation:
        return AlbumRecommendation(rank="primary", artist="Sigur Rós", album="Ágætis byrjun")

    def test_a_matching_pick_passes(self, metered):
        call, _ = metered({"valid": True})
        assert Facts(call=call).matches_request(self.rec(), research(), "atmospheric") is True

    def test_a_mismatched_pick_fails(self, metered):
        call, _ = metered({"valid": False})
        assert Facts(call=call).matches_request(self.rec(), research(), "death metal") is False

    def test_an_answer_that_is_not_an_object_counts_as_a_failure(self, metered):
        """Better to say a pick could not be verified than to show it as verified."""
        call, _ = metered("a sentence, not an object")
        assert Facts(call=call).matches_request(self.rec(), research(), "test") is False

    def test_the_summary_is_short(self, metered):
        """Enough to tell a genre and era; the full text is for the pitch."""
        call, llm = metered({"valid": True})
        long_research = research()
        long_research.wikipedia_summary = "y" * 2000

        Facts(call=call).matches_request(self.rec(), long_research, "test")

        _, user = prompts_of(llm.generate)
        assert "y" * SUMMARY_CHARS in user
        assert "y" * (SUMMARY_CHARS + 1) not in user
