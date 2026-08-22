"""Tests for choosing albums, and for what is asked before choosing."""

from backend.library import AlbumFamiliarity
from backend.recommender import dimensions, prompts, selection
from backend.recommender.models import AlbumRef, AnswerSet, TasteProfile
from tests.recommender.conftest import candidate, prompts_of


class TestGapAnalysis:
    def test_returns_the_dimensions_the_model_chose(self, metered):
        call, _ = metered(["era", "tempo"])
        assert selection.gap_analysis(call, "something nostalgic") == ["era", "tempo"]

    def test_tops_up_an_invented_answer(self, metered, limits):
        call, _ = metered(["not_a_dimension"])
        chosen = selection.gap_analysis(call, "test")
        assert len(chosen) == limits.question_count
        assert all(dimensions.by_id(name) for name in chosen)

    def test_offers_the_catalogue_to_the_model(self, metered):
        call, llm = metered(["era", "tempo"])
        selection.gap_analysis(call, "something nostalgic")

        _, user = prompts_of(llm.analyze)
        assert "energy: Energy Level" in user
        assert "something nostalgic" in user


class TestSuggestFilters:
    def test_keeps_only_what_the_library_offers(self, metered):
        call, _ = metered({"genres": ["Rock", "Polka"], "decades": ["1990s"], "reasoning": "why"})

        suggestion = selection.suggest_filters(call, "test", ["Rock", "Jazz"], ["1990s", "2000s"])

        assert suggestion.genres == ["Rock"]
        assert suggestion.decades == ["1990s"]
        assert suggestion.reasoning == "why"

    def test_nothing_usable_leaves_everything_selected(self, metered):
        """Narrowing to nothing would return no albums at all."""
        call, _ = metered({"genres": ["Polka"], "decades": []})

        suggestion = selection.suggest_filters(call, "test", ["Rock", "Jazz"], ["1990s"])

        assert suggestion.genres == ["Rock", "Jazz"]
        assert suggestion.decades == ["1990s"]

    def test_a_non_object_reply_falls_back(self, metered):
        call, _ = metered(["Rock"])
        assert selection.suggest_filters(call, "test", ["Rock"], ["1990s"]).genres == ["Rock"]


class TestGenerateQuestions:
    def test_builds_questions_from_the_reply(self, metered):
        call, _ = metered([
            {"question_text": "How loud?", "options": ["Quiet", "Loud"], "dimension": "energy"},
        ])

        questions = selection.generate_questions(call, "test", ["energy"])

        assert questions[0].question_text == "How loud?"
        assert questions[0].options == ["Quiet", "Loud"]

    def test_caps_the_options_at_four(self, metered):
        call, _ = metered([{"question_text": "?", "options": list("abcdef"), "dimension": "era"}])
        assert len(selection.generate_questions(call, "test", ["era"])[0].options) == 4

    def test_caps_the_questions_at_the_round_size(self, metered, limits):
        call, _ = metered([{"question_text": f"Q{i}"} for i in range(5)])
        questions = selection.generate_questions(call, "test", ["era", "tempo"])
        assert len(questions) == limits.question_count

    def test_describes_each_dimension_to_the_model(self, metered):
        call, llm = metered([])
        selection.generate_questions(call, "test", ["energy", "invented"])

        _, user = prompts_of(llm.generate)
        assert "energy: Energy Level: Calm vs intense" in user
        assert "- invented: invented" in user


class TestSelectAlbums:
    def test_a_pool_that_small_skips_the_model(self, metered):
        """Three candidates for three picks: an LLM call would echo the list back."""
        call, llm = metered()
        pool = [candidate("A", "One"), candidate("B", "Two")]

        picked = selection.select_albums(call, "test", AnswerSet(), pool)

        llm.generate.assert_not_called()
        assert [rec.album for rec in picked] == ["One", "Two"]
        assert picked[0].rank == "primary"
        assert picked[1].rank == "secondary"

    def test_matches_the_model_back_to_the_library(self, metered):
        call, _ = metered([
            {"artist": "Nirvana", "album": "Nevermind", "rank": "primary"},
            {"artist": "pearl jam", "album": "ten", "rank": "secondary"},
        ])
        pool = [candidate(f"Filler{i}", f"Album{i}") for i in range(5)]
        pool += [candidate("Nirvana", "Nevermind"), candidate("Pearl Jam", "Ten")]

        picked = selection.select_albums(call, "test", AnswerSet(), pool)

        assert [rec.album for rec in picked] == ["Nevermind", "Ten"]

    def test_drops_an_album_it_cannot_place(self, metered):
        """Library mode guarantees a pick is playable, so a stray name is dropped."""
        call, _ = metered([
            {"artist": "Nirvana", "album": "Nevermind", "rank": "primary"},
            {"artist": "Some Band", "album": "Not In The Library", "rank": "secondary"},
        ])
        pool = [candidate(f"Filler{i}", f"Album{i}") for i in range(5)]
        pool += [candidate("Nirvana", "Nevermind")]

        picked = selection.select_albums(call, "test", AnswerSet(), pool)

        assert [rec.album for rec in picked] == ["Nevermind"]

    def test_promotes_a_primary_when_the_model_marked_none(self, metered):
        call, _ = metered([{"artist": "Nirvana", "album": "Nevermind"}])
        pool = [candidate(f"Filler{i}", f"Album{i}") for i in range(5)]
        pool += [candidate("Nirvana", "Nevermind")]

        assert selection.select_albums(call, "test", AnswerSet(), pool)[0].rank == "primary"

    def test_excludes_what_earlier_rounds_showed(self, metered):
        call, llm = metered([])
        pool = [candidate(f"Band{i}", f"Album{i}") for i in range(6)]
        shown = [AlbumRef(artist="Band0", album="Album0")]

        selection.select_albums(call, "test", AnswerSet(), pool, already_shown=shown)

        _, user = prompts_of(llm.generate)
        assert "Band0 — Album0" not in user
        assert "Band1 — Album1" in user

    def test_exclusions_can_shrink_the_pool_past_the_model(self, metered):
        call, llm = metered()
        pool = [candidate(f"Band{i}", f"Album{i}") for i in range(4)]
        shown = [AlbumRef(artist="Band0", album="Album0")]

        picked = selection.select_albums(call, "test", AnswerSet(), pool, already_shown=shown)

        llm.generate.assert_not_called()
        assert len(picked) == 3

    def test_familiarity_is_shown_only_when_it_is_asked_for(self, metered):
        played = {"key1": AlbumFamiliarity(level="well-loved")}
        pool = [candidate(f"Band{i}", f"Album{i}") for i in range(5)]
        pool.append(candidate("Nirvana", "Nevermind", parent_rating_key="key1"))

        call, llm = metered([])
        selection.select_albums(call, "test", AnswerSet(), pool, "any", played)
        _, ignored = prompts_of(llm.generate)

        call, llm = metered([])
        selection.select_albums(call, "test", AnswerSet(), pool, "comfort", played)
        _, honoured = prompts_of(llm.generate)

        assert "{well-loved}" not in ignored
        assert "Nirvana — Nevermind (1999) [Rock] {well-loved}" in honoured

    def test_a_thin_pool_is_flagged_to_the_model(self, metered, limits):
        call, llm = metered([])
        pool = [candidate(f"Band{i}", f"Album{i}") for i in range(limits.small_pool - 1)]

        selection.select_albums(call, "test", AnswerSet(), pool)

        assert prompts.SMALL_POOL_NOTE in prompts_of(llm.generate)[1]

    def test_a_full_pool_is_not_flagged(self, metered, limits):
        call, llm = metered([])
        pool = [candidate(f"Band{i}", f"Album{i}") for i in range(limits.small_pool + 1)]

        selection.select_albums(call, "test", AnswerSet(), pool)

        assert prompts.SMALL_POOL_NOTE not in prompts_of(llm.generate)[1]


class TestSelectDiscoveryAlbums:
    def test_filters_out_albums_the_user_already_owns(self, metered):
        """The exclusion list in the prompt is capped, so some owned names return."""
        call, _ = metered([
            {"artist": "Nirvana", "album": "Nevermind", "rank": "primary"},
            {"artist": "Slint", "album": "Spiderland", "rank": "secondary"},
        ])
        profile = TasteProfile.of([candidate("Nirvana", "Nevermind")])

        picked = selection.select_discovery_albums(call, "test", AnswerSet(), profile)

        assert [rec.album for rec in picked] == ["Spiderland"]

    def test_stops_at_the_pick_count(self, metered, limits):
        call, _ = metered([
            {"artist": f"Band{i}", "album": f"Album{i}"}
            for i in range(limits.discovery_request)
        ])

        picked = selection.select_discovery_albums(call, "test", AnswerSet(), TasteProfile())

        assert len(picked) == limits.pick_count

    def test_keeps_a_year_only_when_it_is_a_number(self, metered):
        call, _ = metered([
            {"artist": "A", "album": "One", "year": 1991},
            {"artist": "B", "album": "Two", "year": "sometime"},
        ])

        picked = selection.select_discovery_albums(call, "test", AnswerSet(), TasteProfile())

        assert picked[0].year == 1991
        assert picked[1].year is None

    def test_discovery_picks_carry_no_library_keys(self, metered):
        call, _ = metered([{"artist": "A", "album": "One"}])

        rec = selection.select_discovery_albums(call, "test", AnswerSet(), TasteProfile())[0]

        assert rec.rating_key is None
        assert rec.track_rating_keys == []

    def test_the_exclusion_list_is_capped(self, metered):
        call, llm = metered([])
        profile = TasteProfile.of([candidate(f"Band{i}", f"Album{i}") for i in range(5)])

        selection.select_discovery_albums(
            call, "test", AnswerSet(), profile, max_exclusion_albums=2
        )

        _, user = prompts_of(llm.analyze)
        assert "Band1 — Album1" in user
        assert "Band4 — Album4" not in user
