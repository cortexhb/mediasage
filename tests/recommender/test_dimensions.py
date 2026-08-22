"""Tests for the taste dimensions a clarifying question is asked along."""

from backend.recommender import dimensions


class TestLookup:
    def test_by_id_finds_a_real_dimension(self):
        assert dimensions.by_id("energy").label == "Energy Level"

    def test_by_id_rejects_an_invented_one(self):
        """A model asked for ids sometimes answers with a label it made up."""
        assert dimensions.by_id("vibe") is None

    def test_catalogue_lists_every_dimension(self):
        lines = dimensions.catalogue().splitlines()
        assert len(lines) == len(dimensions.DIMENSIONS)
        assert lines[0] == "- energy: Energy Level — Calm vs intense, quiet vs loud"


class TestFill:
    def test_keeps_valid_choices(self):
        assert dimensions.fill(["era", "tempo"]) == ["era", "tempo"]

    def test_drops_invented_ids_and_tops_up(self):
        """One usable dimension still has to produce two questions."""
        filled = dimensions.fill(["vibe", "tempo"])
        assert len(filled) == dimensions.question_count()
        assert filled[0] == "tempo"
        assert all(dimensions.by_id(name) for name in filled)

    def test_fills_from_nothing(self):
        assert dimensions.fill([]) == ["energy", "emotional_direction"]

    def test_does_not_repeat_a_choice(self):
        assert dimensions.fill(["era", "era"]) == ["era", "energy"]

    def test_truncates_an_over_long_answer(self):
        assert len(dimensions.fill(["era", "tempo", "rawness"])) == dimensions.question_count()

    def test_count_is_tunable(self):
        assert len(dimensions.fill([], count=4)) == 4
