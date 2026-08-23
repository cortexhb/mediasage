"""Tests for the models the pipeline passes between its stages."""

import pytest

from backend.recommender.models import (
    AlbumRecommendation,
    AlbumRef,
    AnswerSet,
    ExtractedFacts,
    PitchIssue,
    PitchValidation,
    ResearchData,
    SommelierPitch,
    TasteProfile,
)
from tests.recommender.conftest import candidate


class TestAlbumRef:
    def test_key_is_case_folded(self):
        """A model's casing rarely matches the library's."""
        loud = AlbumRef(artist="Sigur Rós", album="Ágætis Byrjun")
        quiet = AlbumRef(artist="sigur rós", album="ágætis byrjun")
        assert loud.key == quiet.key

    def test_str_names_both_halves(self):
        assert str(AlbumRef(artist="Nirvana", album="Nevermind")) == "Nirvana — Nevermind"

    def test_parse_round_trips(self):
        ref = AlbumRef(artist="nirvana", album="nevermind")
        assert AlbumRef.parse(ref.key) == ref

    def test_parse_rejects_a_non_key(self):
        assert AlbumRef.parse("just a title") is None

    def test_is_frozen(self):
        """Refs are dict keys and exclusion entries; a mutated one goes missing."""
        assert AlbumRef.model_config["frozen"] is True

    def test_separator_survives_a_comma_in_the_name(self):
        ref = AlbumRef(artist="Earth, Wind & Fire", album="I Am")
        parsed = AlbumRef.parse(ref.key)
        assert parsed is not None
        assert parsed.artist == "earth, wind & fire"


class TestWithoutEdition:
    """A library files "Nevermind (Deluxe Edition)"; MusicBrainz files "Nevermind"."""

    @pytest.mark.parametrize("album,stripped", (
        ("Nevermind (Deluxe Edition)", "Nevermind"),
        ("Ten (Super Deluxe)", "Ten"),
        ("Ágætis byrjun (Anniversary Edition)", "Ágætis byrjun"),
    ))
    def test_strips_an_edition_suffix(self, album, stripped):
        bare = AlbumRef(artist="A", album=album).without_edition()
        assert bare is not None
        assert bare.album == stripped

    def test_the_artist_is_carried_over(self):
        bare = AlbumRef(artist="Nirvana", album="Nevermind (Deluxe Edition)").without_edition()
        assert bare is not None
        assert bare.artist == "Nirvana"

    def test_a_title_with_no_suffix_yields_nothing(self):
        assert AlbumRef(artist="A", album="Nevermind").without_edition() is None

    def test_an_unlisted_marker_is_left_alone(self):
        """The alternation is a fixed list; a leading "Remastered" is not on it."""
        assert AlbumRef(artist="A", album="Nevermind (Remastered 2011)").without_edition() is None

    def test_a_marker_inside_the_title_is_part_of_it(self):
        """Only the end is stripped, so a real name survives."""
        assert AlbumRef(artist="A", album="Deluxe Trouble").without_edition() is None

    def test_the_original_is_not_mutated(self):
        ref = AlbumRef(artist="A", album="Ten (Super Deluxe)")
        ref.without_edition()
        assert ref.album == "Ten (Super Deluxe)"


class TestAnswerSet:
    def test_selection_marks_a_skip(self):
        answers = AnswerSet(answers=["calm", None], texts=["", ""])
        assert answers.for_selection() == "Q1 answer: calm\nQ2: skipped"

    def test_selection_appends_free_text(self):
        answers = AnswerSet(answers=["calm"], texts=["late at night"])
        assert answers.for_selection() == "Q1 answer: calm (also: late at night)"

    def test_selection_survives_missing_text(self):
        """The UI sends fewer texts than answers when the last is untouched."""
        assert AnswerSet(answers=["calm"]).for_selection() == "Q1 answer: calm"

    def test_pitch_drops_skips(self):
        answers = AnswerSet(answers=["calm", None, "sad"], texts=[])
        assert answers.for_pitch() == "calm; sad"

    def test_pitch_with_nothing_answered(self):
        assert AnswerSet().for_pitch() == "no specific preferences"


class TestSommelierPitch:
    def test_primary_joins_the_long_fields(self):
        pitch = SommelierPitch.primary(
            {"hook": "A hook", "context": "A context", "listening_guide": "", "connection": "C"}
        )
        assert pitch.full_text == "A hook\n\nA context\n\nC"

    def test_primary_tolerates_nulls(self):
        """A model answering `null` for a field must not become the string None."""
        assert SommelierPitch.primary({"hook": None}).hook == ""

    def test_secondary_uses_the_short_pitch(self):
        pitch = SommelierPitch.secondary({"short_pitch": "One line"})
        assert pitch.short_pitch == "One line"
        assert pitch.full_text == "One line"


class TestAlbumRecommendation:
    def test_of_candidate_proxies_art_through_the_first_track(self):
        rec = AlbumRecommendation.of_candidate(
            candidate("Nirvana", "Nevermind", track_rating_keys=["7", "8"]), "primary"
        )
        assert rec.art_url == "/api/art/7"
        assert rec.track_rating_keys == ["7", "8"]

    def test_of_candidate_without_tracks_has_no_art(self):
        rec = AlbumRecommendation.of_candidate(
            candidate("Nirvana", "Nevermind", track_rating_keys=[]), "secondary"
        )
        assert rec.art_url is None

    def test_ref_keys_the_lookups(self):
        rec = AlbumRecommendation(rank="primary", album="Nevermind", artist="Nirvana")
        assert rec.ref.key == AlbumRef(artist="Nirvana", album="Nevermind").key


class TestExtractedFacts:
    def test_defaults_are_empty(self):
        facts = ExtractedFacts()
        assert facts.origin_story == ""
        assert facts.personnel == []
        assert facts.track_listing == []

    def test_to_text_labels_what_is_set(self):
        facts = ExtractedFacts(origin_story="Recorded in Reykjavik", personnel=["Jónsi", "Kjartan"])
        text = facts.to_text()
        assert "- Origin: Recorded in Reykjavik" in text
        assert "- Personnel: Jónsi, Kjartan" in text

    def test_to_text_omits_empty_fields(self):
        assert "Vocal approach" not in ExtractedFacts(origin_story="x").to_text()

    def test_to_text_can_hold_back_the_track_listing(self):
        """Validation sends it separately, marked authoritative."""
        facts = ExtractedFacts(track_listing=["Intro", "Svefn-g-englar"])
        assert "Svefn-g-englar" in facts.to_text()
        assert "Svefn-g-englar" not in facts.to_text(include_track_listing=False)


class TestPitchValidation:
    def test_valid_has_no_issues(self):
        result = PitchValidation(valid=True)
        assert result.valid is True
        assert result.issues == []

    def test_corrections_pair_wrong_with_right(self):
        result = PitchValidation(
            valid=False,
            issues=[
                PitchIssue(
                    claim="touring stint with David Berman",
                    problem="contradicts research",
                    correction="Jenkins rehearsed with Purple Mountains; Berman died first",
                )
            ],
        )
        corrections = result.corrections()
        assert "WRONG: \"touring stint with David Berman\"" in corrections
        assert "RIGHT: \"Jenkins rehearsed" in corrections


class TestResearchData:
    def test_review_texts_default_empty(self):
        assert ResearchData().review_texts == []

    def test_holds_fetched_reviews(self):
        research = ResearchData(
            wikipedia_summary="Album summary here",
            review_texts=["Great album review from Pitchfork"],
        )
        assert research.review_texts[0].startswith("Great")


class TestTasteProfile:
    def test_of_counts_genres_decades_and_artists(self):
        profile = TasteProfile.of([
            candidate("A", "One", genres=["Rock"], decade="1990s"),
            candidate("A", "Two", genres=["Rock", "Jazz"], decade="1990s"),
            candidate("B", "Three", genres=["Jazz"], decade="2000s"),
        ])
        assert profile.genre_distribution == {"Rock": 2, "Jazz": 2}
        assert profile.decade_distribution == {"1990s": 2, "2000s": 1}
        assert profile.top_artists == ["A", "B"]
        assert profile.total_albums == 3

    def test_of_skips_a_missing_decade(self):
        profile = TasteProfile.of([candidate("A", "One", decade="")])
        assert profile.decade_distribution == {}

    def test_owned_keys_cover_every_album(self):
        profile = TasteProfile.of([candidate("A", "One"), candidate("B", "Two")])
        assert profile.owned_keys() == {"a|||one", "b|||two"}

    def test_summary_reports_the_library_size(self):
        profile = TasteProfile.of([candidate("A", "One", genres=["Rock"], decade="1990s")])
        summary = profile.summary()
        assert "Top genres: Rock" in summary
        assert "Library size: 1 albums" in summary
