"""Tests for matching an album a model named back to one we have."""

from backend.config.store import config_store
from backend.recommender.matching import AlbumMatcher
from backend.recommender.models import AlbumRef


def entries(*names: tuple[str, str]) -> dict[str, str]:
    """Candidates keyed the way the pipeline keys them, valued by their label."""
    return {AlbumRef(artist=a, album=b).key: f"{a}/{b}" for a, b in names}


class TestExactMatch:
    def test_case_folded_key_hits(self):
        found = AlbumMatcher.for_selection().find(
            AlbumRef(artist="NIRVANA", album="Nevermind"), entries(("Nirvana", "Nevermind"))
        )
        assert found == "Nirvana/Nevermind"

    def test_nothing_close_returns_none(self):
        assert AlbumMatcher.for_selection().find(
            AlbumRef(artist="Nirvana", album="Nevermind"), entries(("Miles Davis", "Kind of Blue"))
        ) is None

    def test_empty_pool_returns_none(self):
        assert AlbumMatcher.for_selection().find(AlbumRef(artist="a", album="b"), {}) is None


class TestSubstringMatch:
    def test_dropped_suffix_matches(self):
        """The common case: the library has "(Reissue)" and the model does not."""
        found = AlbumMatcher.for_selection().find(
            AlbumRef(artist="Sigur Rós", album="Ágætis byrjun"),
            entries(("Sigur Rós", "Ágætis byrjun (Reissue)")),
        )
        assert found == "Sigur Rós/Ágætis byrjun (Reissue)"

    def test_added_suffix_matches_too(self):
        found = AlbumMatcher.for_selection().find(
            AlbumRef(artist="Sigur Rós", album="Ágætis byrjun (Remastered)"),
            entries(("Sigur Rós", "Ágætis byrjun")),
        )
        assert found == "Sigur Rós/Ágætis byrjun"

    def test_a_different_artist_is_not_a_substring_match(self):
        assert AlbumMatcher.for_selection().find(
            AlbumRef(artist="Someone Else", album="Ten"), entries(("Pearl Jam", "Ten (Deluxe)"))
        ) is None


class TestFuzzyMatch:
    def test_punctuation_and_ampersands_still_match(self):
        found = AlbumMatcher.for_selection().find(
            AlbumRef(artist="Earth Wind and Fire", album="That's the Way of the World"),
            entries(("Earth, Wind & Fire", "Thats the Way of the World")),
        )
        assert found == "Earth, Wind & Fire/Thats the Way of the World"

    def test_a_wrong_artist_is_rejected_by_the_floor(self):
        """A wrong match plays the wrong record, so the artist has to hold up."""
        assert AlbumMatcher.for_selection().find(
            AlbumRef(artist="Radiohead", album="Kind of Blue"),
            entries(("Miles Davis", "Kind of Blue")),
        ) is None

    def test_best_scoring_candidate_wins(self):
        pool = entries(("Radiohead", "The Bends"), ("Radiohead", "Amnesiac"))
        found = AlbumMatcher.for_selection().find(AlbumRef(artist="Radiohead", album="The Bendz"), pool)
        assert found == "Radiohead/The Bends"


class TestThresholds:
    def test_selection_needs_both_halves(self):
        """Selection scores artist and album together; a wild title fails."""
        assert AlbumMatcher.for_selection().find(
            AlbumRef(artist="Radiohead", album="Completely Different Words Here"),
            entries(("Radiohead", "OK Computer")),
        ) is None

    def test_pitch_forgives_a_truncated_title(self):
        """The album list was in the pitch prompt, so the artist is near-certain."""
        assert AlbumMatcher.for_pitches().find(
            AlbumRef(artist="Radiohead", album="OK Comp"), entries(("Radiohead", "OK Computer"))
        ) == "Radiohead/OK Computer"

    def test_an_album_only_floor_can_be_configured(self):
        loose = AlbumMatcher(artist_min=0, album_min=90)
        assert loose.find(
            AlbumRef(artist="Nobody", album="OK Computer"), entries(("Radiohead", "OK Computer"))
        ) == "Radiohead/OK Computer"


class TestConfiguredFloors:
    """The floors come from `MatchingConfig`; a library's tagging decides them."""

    def test_a_lower_floor_admits_what_a_higher_one_rejects(self, monkeypatch, llm_config):
        pool = entries(("Sigur Ros", "Agaetis Byrjun"))
        wanted = AlbumRef(artist="Sigur Rrs", album="Agaetis Byrjun Reissue")

        strict = llm_config.model_copy(update={
            "matching": llm_config.matching.model_copy(
                update={"album_artist_min": 99, "album_combined_min": 99}
            )
        })
        monkeypatch.setattr(config_store, "config", strict)
        assert AlbumMatcher.for_selection().find(wanted, pool) is None

        lenient = llm_config.model_copy(update={
            "matching": llm_config.matching.model_copy(
                update={"album_artist_min": 50, "album_combined_min": 50}
            )
        })
        monkeypatch.setattr(config_store, "config", lenient)
        assert AlbumMatcher.for_selection().find(wanted, pool) is not None

    def test_each_matcher_reads_its_own_floors(self, llm_config):
        assert AlbumMatcher.for_selection().artist_min == llm_config.matching.album_artist_min
        assert AlbumMatcher.for_pitches().artist_min == llm_config.matching.pitch_artist_min
        assert AlbumMatcher.for_pitches().album_min == llm_config.matching.pitch_album_min
