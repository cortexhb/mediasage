"""Tests for the one module that knows dialect names."""

import pytest
from sqlalchemy.dialects import mysql, postgresql, sqlite
from sqlmodel import select

from backend.db import upsert
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


class TestDialectSupport:
    """Both shipped backends build the same statement shape."""

    @pytest.mark.parametrize("dialect", [sqlite.dialect(), postgresql.dialect()])
    def test_supported_dialects_compile(self, dialect):
        statement = upsert(dialect, Track.__table__, [ROW], ["rating_key"])
        assert "ON CONFLICT" in str(statement.compile(dialect=dialect)).upper()

    def test_an_unsupported_dialect_is_refused(self):
        with pytest.raises(NotImplementedError, match="mysql"):
            upsert(mysql.dialect(), Track.__table__, [ROW], ["rating_key"])

    def test_empty_rows_are_refused(self):
        with pytest.raises(ValueError, match="at least one row"):
            upsert(sqlite.dialect(), Track.__table__, [], ["rating_key"])


class TestConflictBehaviour:
    """The conflict target is excluded from the update set."""

    def test_key_columns_are_not_overwritten(self):
        statement = upsert(sqlite.dialect(), Track.__table__, [ROW], ["rating_key"])
        assert "rating_key" not in statement._post_values_clause.update_values_to_set

    def test_existing_rows_are_updated_in_place(self, temp_db):
        with temp_db.session() as session:
            dialect = session.get_bind().dialect
            session.execute(upsert(dialect, Track.__table__, [ROW], ["rating_key"]))

        changed = {**ROW, "title": "Renamed", "year": 2001}
        with temp_db.session() as session:
            dialect = session.get_bind().dialect
            session.execute(upsert(dialect, Track.__table__, [changed], ["rating_key"]))

        with temp_db.session() as session:
            rows = session.exec(select(Track)).all()
            assert len(rows) == 1
            assert (rows[0].title, rows[0].year) == ("Renamed", 2001)
