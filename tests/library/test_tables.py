"""Tests for the table definitions and the genre normalization helper."""

import pytest
from sqlalchemy import delete
from sqlmodel import select

from backend.db import db
from backend.library.tables import SYNC_STATE_ID, SyncState, Track, TrackGenre, genre_rows, utc_now


class TestGenreRows:
    """`genre_rows` replaced the trigger's `json_each` and its type filter."""

    def test_one_row_per_genre(self):
        rows = genre_rows("1", ["Rock", "Jazz"])
        assert [row["genre"] for row in rows] == ["Rock", "Jazz"]

    def test_case_variants_collapse_to_one_row(self):
        rows = genre_rows("1", ["Rock", "rock", "ROCK"])
        assert len(rows) == 1

    def test_the_first_spelling_is_kept_for_display(self):
        assert genre_rows("1", ["rock", "Rock"])[0]["genre"] == "rock"

    def test_the_lowercase_key_is_what_filters_match(self):
        assert genre_rows("1", ["Rock"])[0]["genre_lower"] == "rock"

    @pytest.mark.parametrize("genres", [[], [""], ["   "], [None], [42], [{"a": 1}]])
    def test_unusable_values_are_dropped(self, genres):
        assert genre_rows("1", genres) == []

    def test_the_rating_key_is_carried_onto_every_row(self):
        assert {row["rating_key"] for row in genre_rows("7", ["A", "B"])} == {"7"}


class TestCascade:
    """Deleting a track takes its genre rows, which a trigger used to do."""

    def test_genre_rows_go_with_their_track(self, seed_tracks):
        seed_tracks({"rating_key": "1", "title": "T", "artist": "A", "album": "B",
                     "genres": ["Rock", "Jazz"]})

        with db.session() as session:
            session.execute(delete(Track).where(Track.rating_key == "1"))

        with db.session() as session:
            assert session.exec(select(TrackGenre)).all() == []

    def test_other_tracks_keep_theirs(self, seed_tracks):
        seed_tracks(
            {"rating_key": "1", "title": "T", "artist": "A", "album": "B", "genres": ["Rock"]},
            {"rating_key": "2", "title": "T", "artist": "A", "album": "B", "genres": ["Jazz"]},
        )

        with db.session() as session:
            session.execute(delete(Track).where(Track.rating_key == "1"))

        with db.session() as session:
            remaining = session.exec(select(TrackGenre)).all()
            assert [row.rating_key for row in remaining] == ["2"]


class TestSyncState:
    """One row, enforced by the database rather than by convention."""

    def test_a_second_row_is_refused(self, temp_db):
        with pytest.raises(Exception, match="sync_state_single_row"), db.session() as session:
            session.add(SyncState(id=SYNC_STATE_ID + 1))


def test_utc_now_is_timezone_aware():
    """A naive timestamp would compare wrongly against synced_at."""
    assert utc_now().tzinfo is not None
