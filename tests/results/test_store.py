"""Tests for saved playlists and recommendations."""

from datetime import datetime

import pytest

from backend.results import Result, store

TYPES = ("prompt_playlist", "seed_playlist", "album_recommendation")


def make(result_type: str = "prompt_playlist", **overrides) -> Result:
    """A result with everything the history feed needs."""
    fields = {
        "type": result_type,
        "title": "Title",
        "prompt": "a prompt",
        "snapshot": {"tracks": [{"title": "Song"}]},
        "track_count": 1,
        "subtitle": "sub",
    }
    return Result(**{**fields, **overrides})


class TestSave:
    """Saving assigns an id; the caller does not supply one."""

    def test_an_id_is_returned(self, temp_db):
        assert len(store.save(make())) == 16

    def test_the_id_is_written_back_onto_the_result(self, temp_db):
        result = make()
        assert store.save(result) == result.id

    def test_two_results_get_different_ids(self, temp_db):
        assert store.save(make()) != store.save(make())

    def test_a_collision_is_retried(self, temp_db, monkeypatch):
        taken = store.save(make())
        ids = iter([taken, "0123456789abcdef"])
        monkeypatch.setattr(store.secrets, "token_hex", lambda _: next(ids))
        assert store.save(make()) == "0123456789abcdef"

    def test_persistent_collisions_are_a_fault(self, temp_db, monkeypatch):
        taken = store.save(make())
        monkeypatch.setattr(store.secrets, "token_hex", lambda _: taken)
        with pytest.raises(RuntimeError, match="unique result ID"):
            store.save(make())

    def test_created_at_is_set_without_a_database_default(self, temp_db):
        saved = store.get(store.save(make()))
        assert isinstance(saved.created_at, datetime)


class TestGet:
    """Fetching one result returns its snapshot; the list does not."""

    def test_the_snapshot_comes_back(self, temp_db):
        result_id = store.save(make())
        assert store.get(result_id).snapshot == {"tracks": [{"title": "Song"}]}

    def test_every_field_round_trips(self, temp_db):
        saved = store.get(store.save(make(artist="Artist", art_rating_key="42")))
        assert (saved.artist, saved.art_rating_key, saved.subtitle) == ("Artist", "42", "sub")

    def test_an_unknown_id_is_none(self, temp_db):
        assert store.get("deadbeefdeadbeef") is None


class TestPage:
    """History is paginated, newest first, and filterable by type."""

    def test_an_empty_store_reports_nothing(self, temp_db):
        page = store.page()
        assert (page.results, page.total) == ([], 0)

    def test_the_total_counts_every_result(self, temp_db):
        for _ in range(3):
            store.save(make())
        assert store.page(limit=1).total == 3

    def test_the_page_is_capped_by_the_limit(self, temp_db):
        for _ in range(3):
            store.save(make())
        assert len(store.page(limit=2).results) == 2

    def test_the_offset_skips_rows(self, temp_db):
        for _ in range(3):
            store.save(make())
        assert len(store.page(limit=10, offset=2).results) == 1

    def test_newest_comes_first(self, temp_db):
        older = store.save(make(title="Older", created_at=datetime(2020, 1, 1)))
        newer = store.save(make(title="Newer", created_at=datetime(2026, 1, 1)))
        assert [item.id for item in store.page().results] == [newer, older]

    def test_one_type_can_be_selected(self, temp_db):
        store.save(make("prompt_playlist"))
        store.save(make("album_recommendation"))
        page = store.page(result_type="album_recommendation")
        assert [item.type for item in page.results] == ["album_recommendation"]

    def test_several_types_can_be_selected(self, temp_db):
        for result_type in TYPES:
            store.save(make(result_type))
        page = store.page(result_type="prompt_playlist, seed_playlist")
        assert page.total == 2

    def test_the_total_respects_the_type_filter(self, temp_db):
        store.save(make("prompt_playlist"))
        store.save(make("album_recommendation"))
        assert store.page(result_type="prompt_playlist", limit=1).total == 1

    @pytest.mark.parametrize("result_type", [None, "", "  ,  "])
    def test_a_blank_filter_selects_everything(self, temp_db, result_type):
        store.save(make("prompt_playlist"))
        store.save(make("album_recommendation"))
        assert store.page(result_type=result_type).total == 2

    def test_list_items_carry_no_snapshot(self, temp_db):
        store.save(make())
        assert not hasattr(store.page().results[0], "snapshot")


class TestRemove:
    """Deleting reports whether there was anything to delete."""

    def test_a_saved_result_is_deleted(self, temp_db):
        result_id = store.save(make())
        assert store.remove(result_id) is True
        assert store.get(result_id) is None

    def test_an_unknown_id_reports_false(self, temp_db):
        assert store.remove("deadbeefdeadbeef") is False

    def test_other_results_are_left_alone(self, temp_db):
        kept = store.save(make())
        store.remove(store.save(make()))
        assert store.get(kept) is not None
