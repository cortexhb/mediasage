"""Tests for the one module that knows dialect names."""

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import mysql, postgresql, sqlite
from sqlalchemy.dialects.sqlite.dml import OnConflictDoUpdate

from backend.db import Upsert
from backend.library.tables import Track

ROW = {
    "rating_key": "1",
    "title": "Song",
    "artist": "Artist",
    "album": "Album",
    "duration_ms": 1000,
    "year": 1994,
    "genres": ["Rock"],
    "user_rating": None,
    "is_live": False,
    "parent_rating_key": "100",
    "view_count": 0,
    "last_viewed_at": None,
    "sync_token": "tok",
}


def write(rows: list[dict]) -> Upsert:
    """An upsert of `rows` into tracks, keyed the way sync keys it."""
    return Upsert(table=Track.__table__, rows=rows, keys=["rating_key"])


class TestDialectSupport:
    """Both shipped backends build the same statement shape."""

    @pytest.mark.parametrize("dialect", [sqlite.dialect(), postgresql.dialect()])
    def test_supported_dialects_compile(self, dialect):
        statement = write([ROW]).statement(dialect)
        assert "ON CONFLICT" in str(statement.compile(dialect=dialect)).upper()

    def test_an_unsupported_dialect_is_refused(self):
        with pytest.raises(NotImplementedError, match="mysql"):
            write([ROW]).statement(mysql.dialect())

    def test_empty_rows_are_refused(self):
        with pytest.raises(ValueError, match="at least one row"):
            write([])


class TestConflictBehaviour:
    """The conflict target is excluded from the update set."""

    def test_key_columns_are_not_overwritten(self):
        statement = write([ROW]).statement(sqlite.dialect())
        conflict = statement._post_values_clause
        assert isinstance(conflict, OnConflictDoUpdate)
        assert "rating_key" not in conflict.update_values_to_set

    def test_existing_rows_are_updated_in_place(self, temp_db):
        with temp_db.session() as session:
            session.execute(write([ROW]).statement(session.get_bind().dialect))

        changed = {**ROW, "title": "Renamed", "year": 2001}
        with temp_db.session() as session:
            session.execute(write([changed]).statement(session.get_bind().dialect))

        with temp_db.session() as session:
            rows = session.scalars(select(Track)).all()
            assert len(rows) == 1
            assert (rows[0].title, rows[0].year) == ("Renamed", 2001)
