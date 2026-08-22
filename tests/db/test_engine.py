"""Tests for the engine, its pragmas, and session lifecycle."""

import pytest
from sqlmodel import select

from backend.db import DB_PATH, Database, db, sqlite_url
from backend.library.tables import Track


class TestUrlResolution:
    """The URL decides the backend; nothing above the engine names one."""

    def test_defaults_to_the_data_directory(self):
        assert Database().resolved_url() == sqlite_url(DB_PATH)

    def test_configure_overrides_the_default(self, tmp_path):
        instance = Database()
        instance.configure(f"sqlite:///{tmp_path / 'x.db'}")
        assert instance.resolved_url().endswith("x.db")

    def test_configure_disposes_the_previous_engine(self, tmp_path):
        instance = Database()
        instance.configure(f"sqlite:///{tmp_path / 'a.db'}")
        first = instance.engine()
        instance.configure(f"sqlite:///{tmp_path / 'b.db'}")
        assert instance.engine() is not first


class TestPragmas:
    """SQLite needs pragmas per connection; Postgres needs none of them."""

    @pytest.mark.parametrize(
        ("pragma", "expected"),
        [("journal_mode", "wal"), ("foreign_keys", 1)],
    )
    def test_pragma_is_applied(self, temp_db, pragma, expected):
        with temp_db.connection() as conn:
            value = conn.exec_driver_sql(f"PRAGMA {pragma}").fetchone()[0]
        assert (value.lower() if isinstance(value, str) else value) == expected

    def test_busy_timeout_is_not_left_at_zero(self, temp_db):
        with temp_db.connection() as conn:
            assert conn.exec_driver_sql("PRAGMA busy_timeout").fetchone()[0] > 0


class TestSession:
    """A session commits on success and rolls back on failure."""

    def test_commits_on_clean_exit(self, temp_db):
        with temp_db.session() as session:
            session.add(Track(rating_key="1", title="T", artist="A", album="B"))

        with temp_db.session() as session:
            assert len(session.exec(select(Track)).all()) == 1

    def test_rolls_back_when_the_body_raises(self, temp_db):
        with pytest.raises(RuntimeError), temp_db.session() as session:
            session.add(Track(rating_key="1", title="T", artist="A", album="B"))
            session.flush()
            raise RuntimeError("boom")

        with temp_db.session() as session:
            assert session.exec(select(Track)).all() == []


class TestDispose:
    """Disposing forgets the engine so the next call rebuilds it."""

    def test_engine_is_rebuilt_after_dispose(self, temp_db):
        first = temp_db.engine()
        temp_db.dispose()
        assert temp_db.engine() is not first

    def test_dispose_is_safe_without_an_engine(self):
        Database().dispose()


def test_the_module_instance_is_shared():
    """One engine per process; the store is the single instance."""
    assert isinstance(db, Database)
