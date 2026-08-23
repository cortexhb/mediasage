"""Tests for writing the sommelier pitch, checking it, and fixing it."""

from backend.library import AlbumFamiliarity
from backend.recommender.models import (
    AlbumRecommendation,
    AnswerSet,
    ExtractedFacts,
    PitchIssue,
    PitchValidation,
    ResearchData,
    SommelierPitch,
)
from backend.recommender.pitches import Pitches
from tests.recommender.conftest import prompts_of

KEY = "sigur rós|||ágætis byrjun"


def primary() -> AlbumRecommendation:
    return AlbumRecommendation(
        rank="primary", album="Ágætis byrjun", artist="Sigur Rós", year=1999,
        rating_key="123", track_rating_keys=["456"],
    )


def written(**overrides) -> dict[str, str]:
    """One pitch as the model returns it."""
    fields = {
        "artist": "Sigur Rós", "album": "Ágætis byrjun",
        "hook": "A hook", "context": "A context",
        "listening_guide": "A guide", "connection": "A connection",
    }
    fields.update(overrides)
    return fields


class TestWrite:
    def test_fills_in_the_primary_pitch(self, metered):
        call, _ = metered([written()])
        recs = [primary()]

        Pitches(call=call).write(recs, "atmospheric", AnswerSet())

        assert recs[0].pitch.hook == "A hook"
        assert recs[0].pitch.full_text.startswith("A hook\n\nA context")

    def test_a_secondary_gets_only_the_short_pitch(self, metered):
        call, _ = metered([written(rank="secondary", short_pitch="One line")])
        recs = [AlbumRecommendation(rank="secondary", album="Ágætis byrjun", artist="Sigur Rós")]

        Pitches(call=call).write(recs, "test", AnswerSet())

        assert recs[0].pitch.short_pitch == "One line"
        assert recs[0].pitch.hook == ""

    def test_the_grounding_rules_are_in_the_system_prompt(self, metered):
        call, llm = metered([written()])

        Pitches(call=call).write([primary()], "test", AnswerSet(), facts={KEY: ExtractedFacts()})

        system, _ = prompts_of(llm.analyze)
        assert "GROUNDING RULES" in system
        assert "NOT IN SOURCES" in system

    def test_the_extracted_facts_are_in_the_user_prompt(self, metered):
        call, llm = metered([written()])
        facts = {KEY: ExtractedFacts(
            origin_story="Recorded in a Reykjavik swimming pool",
            vocal_approach="Mostly Icelandic; Vonlenska on 2 tracks only",
            common_misconceptions="Not entirely in Vonlenska despite common belief",
        )}
        research = {KEY: ResearchData(track_listing=["Intro", "Svefn-g-englar"], label="Smekkleysa")}

        Pitches(call=call).write([primary()], "test", AnswerSet(), research, facts)

        _, user = prompts_of(llm.analyze)
        assert "Vonlenska on 2 tracks only" in user
        assert "Common misconceptions" in user
        assert "Svefn-g-englar" in user
        assert "Smekkleysa" in user

    def test_works_without_any_research(self, metered):
        """Library picks that failed research still get a pitch."""
        call, _ = metered([written()])
        recs = [primary()]

        Pitches(call=call).write(recs, "test", AnswerSet())

        assert recs[0].pitch.hook == "A hook"
        assert recs[0].research_available is False

    def test_marks_which_albums_were_researched(self, metered):
        call, _ = metered([written()])
        recs = [primary()]

        Pitches(call=call).write(recs, "test", AnswerSet(), research={KEY: ResearchData()})

        assert recs[0].research_available is True

    def test_a_truncated_title_still_finds_its_album(self, metered):
        call, _ = metered([written(album="Ágætis")])
        recs = [primary()]

        Pitches(call=call).write(recs, "test", AnswerSet())

        assert recs[0].pitch.hook == "A hook"

    def test_an_album_with_no_pitch_gets_an_empty_one(self, metered):
        call, _ = metered([written(artist="Somebody Else", album="Another Record")])
        recs = [primary()]

        Pitches(call=call).write(recs, "test", AnswerSet())

        assert recs[0].pitch.hook == ""

    def test_familiarity_frames_an_album_the_user_knows(self, metered):
        call, llm = metered([written()])
        played = {"123": AlbumFamiliarity(level="well-loved")}

        Pitches(call=call).write([primary()], "test", AnswerSet(), familiarity=played)

        assert "Familiarity: well-loved" in prompts_of(llm.analyze)[1]


class TestValidate:
    def test_a_clean_pitch_passes(self, metered):
        call, _ = metered({"valid": True, "issues": []})

        result = Pitches(call=call).fact_check(SommelierPitch(full_text="A pitch"), ExtractedFacts())

        assert result.valid is True
        assert result.issues == []

    def test_a_contradiction_is_flagged(self, metered):
        call, _ = metered({"valid": False, "issues": [{
            "claim": "touring stint with David Berman",
            "problem": "contradicts research",
            "correction": "Jenkins rehearsed with Purple Mountains; Berman died first",
        }]})

        result = Pitches(call=call).fact_check(
            SommelierPitch(full_text="Born from her touring stint with David Berman"),
            ExtractedFacts(origin_story="Jenkins rehearsed for four days before Berman died"),
        )

        assert not result.valid
        assert "rehearsed" in result.issues[0].correction

    def test_an_answer_that_is_not_an_object_defaults_to_valid(self, metered):
        """An unread answer is not evidence the pitch is wrong."""
        call, _ = metered("a sentence, not an object")
        assert Pitches(call=call).fact_check(SommelierPitch(), ExtractedFacts()).valid is True

    def test_the_track_listing_is_marked_authoritative(self, metered):
        call, llm = metered({"valid": True})
        facts = ExtractedFacts(origin_story="x", track_listing=["Intro", "Svefn-g-englar"])

        Pitches(call=call).fact_check(SommelierPitch(full_text="A pitch"), facts)

        _, user = prompts_of(llm.analyze)
        assert "AUTHORITATIVE TRACK LISTING" in user
        assert "- Svefn-g-englar" in user


class TestRewrite:
    def test_the_corrections_reach_the_prompt(self, metered):
        call, llm = metered({"hook": "Corrected hook", "context": "What really happened"})
        rec = primary()
        issues = PitchValidation(valid=False, issues=[PitchIssue(
            claim="touring stint with David Berman",
            problem="contradicts research",
            correction="Rehearsed for four days, never toured",
        )])

        Pitches(call=call).rewrite(rec, ExtractedFacts(), issues, "contemplative", AnswerSet())

        _, user = prompts_of(llm.analyze)
        assert "touring stint with David Berman" in user
        assert "Rehearsed for four days" in user

    def test_the_pitch_is_replaced(self, metered):
        call, _ = metered({"hook": "Corrected hook", "context": "What really happened"})
        rec = primary()
        rec.pitch = SommelierPitch(hook="The wrong hook")

        Pitches(call=call).rewrite(rec, ExtractedFacts(), PitchValidation(valid=False), "x", AnswerSet())

        assert rec.pitch.hook == "Corrected hook"
        assert rec.pitch.full_text == "Corrected hook\n\nWhat really happened"
