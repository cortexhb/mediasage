"""Tests for the taste dimensions a clarifying question is asked along."""

from backend.config.store import config_store
from backend.recommender.dimensions import DIMENSIONS, catalogue


class TestLookup:
    def test_by_id_finds_a_real_dimension(self):
        found = catalogue.by_id("energy")
        assert found is not None
        assert found.label == "Energy Level"

    def test_by_id_rejects_an_invented_one(self):
        """A model asked for ids sometimes answers with a label it made up."""
        assert catalogue.by_id("vibe") is None

    def test_catalogue_lists_every_dimension(self):
        lines = catalogue.listing().splitlines()
        assert len(lines) == len(DIMENSIONS)
        assert lines[0] == "- energy: Energy Level — Calm vs intense, quiet vs loud"


class TestFill:
    def test_keeps_valid_choices(self):
        assert catalogue.fill(["era", "tempo"]) == ["era", "tempo"]

    def test_drops_invented_ids_and_tops_up(self):
        """One usable dimension still has to produce two questions."""
        filled = catalogue.fill(["vibe", "tempo"])
        assert len(filled) == config_store.get().recommend.question_count
        assert filled[0] == "tempo"
        assert all(catalogue.by_id(name) for name in filled)

    def test_fills_from_nothing(self):
        assert catalogue.fill([]) == ["energy", "emotional_direction"]

    def test_does_not_repeat_a_choice(self):
        assert catalogue.fill(["era", "era"]) == ["era", "energy"]

    def test_truncates_an_over_long_answer(self):
        assert len(catalogue.fill(["era", "tempo", "rawness"])) == config_store.get().recommend.question_count

    def test_count_is_tunable(self, tuned):
        tuned("recommend", question_count=4)
        assert len(catalogue.fill([])) == 4
