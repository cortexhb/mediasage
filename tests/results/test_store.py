"""Tests for saved playlists and recommendations."""

import uuid
from datetime import datetime

import pytest

from backend.results import Result, results_store
from backend.results import store as store_module

TYPES = ("prompt_playlist", "seed_playlist", "album_recommendation")


def make(
    result_type: str = "prompt_playlist",
    title: str = "Title",
    artist: str | None = None,
    art_rating_key: str | None = None,
    created_at: datetime | None = None,
) -> Result:
    """A result with everything the history feed needs."""
    result = Result(
        type=result_type,
        title=title,
        prompt="a prompt",
        snapshot={"tracks": [{"title": "Song"}]},
        track_count=1,
        subtitle="sub",
        artist=artist,
        art_rating_key=art_rating_key,
    )
    # Assigned after construction so the table's own default still applies.
    if created_at is not None:
        result.created_at = created_at
    return result


class TestSave:
    """Saving assigns an id; the caller does not supply one."""

    def test_an_id_is_returned(self, temp_db):
        assert uuid.UUID(results_store.save(make())).version == 4

    def test_the_id_is_written_back_onto_the_result(self, temp_db):
        result = make()
        assert results_store.save(result) == result.id

    def test_two_results_get_different_ids(self, temp_db):
        assert results_store.save(make()) != results_store.save(make())

    def test_a_collision_is_retried(self, temp_db, monkeypatch):
        taken = results_store.save(make())
        free = str(uuid.uuid4())
        ids = iter([uuid.UUID(taken), uuid.UUID(free)])
        monkeypatch.setattr(store_module.uuid, "uuid4", lambda: next(ids))
        assert results_store.save(make()) == free

    def test_persistent_collisions_are_a_fault(self, temp_db, monkeypatch):
        taken = results_store.save(make())
        monkeypatch.setattr(store_module.uuid, "uuid4", lambda: uuid.UUID(taken))
        with pytest.raises(RuntimeError, match="unique result ID"):
            results_store.save(make())

    def test_created_at_is_set_without_a_database_default(self, temp_db):
        saved = results_store.get(results_store.save(make()))
        assert saved is not None
        assert isinstance(saved.created_at, datetime)


class TestGet:
    """Fetching one result returns its snapshot; the list does not."""

    def test_the_snapshot_comes_back(self, temp_db):
        saved = results_store.get(results_store.save(make()))
        assert saved is not None
        assert saved.snapshot == {"tracks": [{"title": "Song"}]}

    def test_every_field_round_trips(self, temp_db):
        saved = results_store.get(results_store.save(make(artist="Artist", art_rating_key="42")))
        assert saved is not None
        assert (saved.artist, saved.art_rating_key, saved.subtitle) == ("Artist", "42", "sub")

    def test_an_unknown_id_is_none(self, temp_db):
        assert results_store.get("deadbeefdeadbeef") is None


class TestPage:
    """History is paginated, newest first, and filterable by type."""

    def test_an_empty_store_reports_nothing(self, temp_db):
        page = results_store.page()
        assert (page.results, page.total) == ([], 0)

    def test_the_total_counts_every_result(self, temp_db):
        for _ in range(3):
            results_store.save(make())
        assert results_store.page(limit=1).total == 3

    def test_the_page_is_capped_by_the_limit(self, temp_db):
        for _ in range(3):
            results_store.save(make())
        assert len(results_store.page(limit=2).results) == 2

    def test_the_offset_skips_rows(self, temp_db):
        for _ in range(3):
            results_store.save(make())
        assert len(results_store.page(limit=10, offset=2).results) == 1

    def test_newest_comes_first(self, temp_db):
        older = results_store.save(make(title="Older", created_at=datetime(2020, 1, 1)))
        newer = results_store.save(make(title="Newer", created_at=datetime(2026, 1, 1)))
        assert [item.id for item in results_store.page().results] == [newer, older]

    def test_one_type_can_be_selected(self, temp_db):
        results_store.save(make("prompt_playlist"))
        results_store.save(make("album_recommendation"))
        page = results_store.page(result_type="album_recommendation")
        assert [item.type for item in page.results] == ["album_recommendation"]

    def test_several_types_can_be_selected(self, temp_db):
        for result_type in TYPES:
            results_store.save(make(result_type))
        page = results_store.page(result_type="prompt_playlist, seed_playlist")
        assert page.total == 2

    def test_the_total_respects_the_type_filter(self, temp_db):
        results_store.save(make("prompt_playlist"))
        results_store.save(make("album_recommendation"))
        assert results_store.page(result_type="prompt_playlist", limit=1).total == 1

    @pytest.mark.parametrize("result_type", ["", "  ,  ", ","])
    def test_a_blank_filter_selects_everything(self, temp_db, result_type):
        results_store.save(make("prompt_playlist"))
        results_store.save(make("album_recommendation"))
        assert results_store.page(result_type=result_type).total == 2

    def test_list_items_carry_no_snapshot(self, temp_db):
        results_store.save(make())
        assert not hasattr(results_store.page().results[0], "snapshot")


class TestRemove:
    """Deleting reports whether there was anything to delete."""

    def test_a_saved_result_is_deleted(self, temp_db):
        result_id = results_store.save(make())
        assert results_store.remove(result_id) is True
        assert results_store.get(result_id) is None

    def test_an_unknown_id_reports_false(self, temp_db):
        assert results_store.remove("deadbeefdeadbeef") is False

    def test_other_results_are_left_alone(self, temp_db):
        kept = results_store.save(make())
        results_store.remove(results_store.save(make()))
        assert results_store.get(kept) is not None
