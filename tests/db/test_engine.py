"""Tests for the engine, its pragmas, its backend dispatch, and sessions."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.exc import OperationalError

from backend.config.models import DatabaseConfig
from backend.db import DB_PATH, Database, db
from backend.library.tables import Track

# Never connected to: dialect and pool arguments are decided before any I/O.
POSTGRES_URL = "postgresql+psycopg://mediasage:secret@nowhere.invalid:5432/mediasage"


def sqlite(path: Path) -> DatabaseConfig:
    """A configuration pointing at one SQLite file.

    Module-level because it builds a third-party shape from a path, and the
    `DatabaseConfig` it returns is a frozen model with nowhere to hang it.
    """
    return DatabaseConfig(url=Database.sqlite_url(path))


class TestUrlResolution:
    """The URL decides the backend; nothing above the engine names one."""

    def test_defaults_to_the_data_directory(self):
        assert Database().resolved_url() == Database.sqlite_url(DB_PATH)

    def test_configure_overrides_the_default(self, tmp_path):
        instance = Database()
        instance.configure(sqlite(tmp_path / "x.db"))
        assert instance.resolved_url().endswith("x.db")

    def test_configure_disposes_the_previous_engine(self, tmp_path):
        instance = Database()
        instance.configure(sqlite(tmp_path / "a.db"))
        first = instance.engine()
        instance.configure(sqlite(tmp_path / "b.db"))
        assert instance.engine() is not first


class TestEngineOptions:
    """A file and a server want opposite things from the pool."""

    def test_sqlite_shares_connections_across_threads(self, tmp_path):
        instance = Database()
        instance.configure(sqlite(tmp_path / "x.db"))
        assert instance.engine_options()["connect_args"]["check_same_thread"] is False

    def test_sqlite_is_given_no_pool_size(self, tmp_path):
        """There is no server to hold connections to, so the knobs do not apply."""
        instance = Database()
        instance.configure(sqlite(tmp_path / "x.db"))
        assert "pool_size" not in instance.engine_options()

    def test_a_server_backend_pools_from_the_configuration(self):
        instance = Database()
        instance.configure(DatabaseConfig(url=POSTGRES_URL, pool_size=9, pool_recycle=60))
        options = instance.engine_options()
        assert (options["pool_size"], options["pool_recycle"]) == (9, 60)

    def test_a_server_backend_checks_a_connection_before_using_it(self):
        """A container restart closes connections without telling the pool."""
        instance = Database()
        instance.configure(DatabaseConfig(url=POSTGRES_URL))
        assert instance.engine_options()["pool_pre_ping"] is True

    def test_a_server_backend_gets_a_connect_timeout(self):
        instance = Database()
        instance.configure(DatabaseConfig(url=POSTGRES_URL, connect_timeout=3))
        assert instance.engine_options()["connect_args"] == {"connect_timeout": 3}

    def test_the_postgres_url_builds_an_engine(self):
        """The driver is a dependency, so the dialect resolves without a server."""
        instance = Database()
        instance.configure(DatabaseConfig(url=POSTGRES_URL))
        assert instance.engine().dialect.name == "postgresql"


class TestStart:
    """Startup refuses a backend we cannot write to, and waits for a slow one."""

    def test_a_backend_without_an_upsert_is_refused(self, tmp_path, monkeypatch):
        """Named rather than exotic: the check is the upsert table, not the URL."""
        monkeypatch.setattr("backend.db.engine.UPSERT_DIALECTS", {"postgresql": None})
        instance = Database()
        instance.configure(sqlite(tmp_path / "x.db"))

        with pytest.raises(NotImplementedError, match="sqlite"):
            instance.start()

    def test_a_reachable_database_is_accepted(self, tmp_path):
        instance = Database()
        instance.configure(sqlite(tmp_path / "x.db"))
        instance.start()

    def test_a_refused_connection_is_retried(self, tmp_path, monkeypatch):
        refusals = [OperationalError("connect", None, Exception("refused"))] * 2
        connect = MagicMock(side_effect=[*refusals, MagicMock()])
        monkeypatch.setattr(Engine, "connect", connect)

        instance = Database()
        instance.configure(
            DatabaseConfig(url=Database.sqlite_url(tmp_path / "x.db"), startup_backoff=[0.0, 0.0])
        )
        instance.start()

        assert connect.call_count == 3

    def test_the_last_refusal_is_raised(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            Engine, "connect", MagicMock(side_effect=OperationalError("c", None, Exception()))
        )
        instance = Database()
        instance.configure(
            DatabaseConfig(url=Database.sqlite_url(tmp_path / "x.db"), startup_backoff=[])
        )

        with pytest.raises(OperationalError):
            instance.start()


class TestDataDirectory:
    """The setup wizard reports this, so a bind mount is diagnosable."""

    def test_a_writable_directory_is_reported_writable(self, tmp_path, monkeypatch):
        monkeypatch.setattr("backend.db.engine.DATA_DIR", tmp_path)
        assert Database().data_dir_writable()

    def test_the_probe_file_is_not_left_behind(self, tmp_path, monkeypatch):
        monkeypatch.setattr("backend.db.engine.DATA_DIR", tmp_path)
        Database().data_dir_writable()
        assert list(tmp_path.iterdir()) == []

    def test_a_missing_directory_is_created(self, tmp_path, monkeypatch):
        monkeypatch.setattr("backend.db.engine.DATA_DIR", tmp_path / "fresh")
        assert Database().data_dir_writable()

    def test_a_refused_write_is_not_writable(self, tmp_path, monkeypatch):
        """`os.access` can disagree, so the answer comes from writing."""
        monkeypatch.setattr("backend.db.engine.DATA_DIR", tmp_path)
        monkeypatch.setattr(Path, "write_text", MagicMock(side_effect=PermissionError("read-only")))
        assert not Database().data_dir_writable()

    def test_the_directory_is_the_one_the_engine_defaults_to(self, tmp_path, monkeypatch):
        monkeypatch.setattr("backend.db.engine.DATA_DIR", tmp_path)
        assert Database().data_dir == tmp_path


class TestPragmas:
    """SQLite needs pragmas per connection; Postgres needs none of them."""

    @pytest.mark.parametrize(
        ("pragma", "expected"),
        [("journal_mode", "wal"), ("foreign_keys", 1)],
    )
    def test_pragma_is_applied(self, sqlite_only, pragma, expected):
        with sqlite_only.connection() as conn:
            value = conn.exec_driver_sql(f"PRAGMA {pragma}").fetchone()[0]
        assert (value.lower() if isinstance(value, str) else value) == expected

    def test_busy_timeout_is_not_left_at_zero(self, sqlite_only):
        with sqlite_only.connection() as conn:
            assert conn.exec_driver_sql("PRAGMA busy_timeout").fetchone()[0] > 0


class TestSession:
    """A session commits on success and rolls back on failure."""

    def test_commits_on_clean_exit(self, temp_db):
        with temp_db.session() as session:
            session.add(Track(rating_key="1", title="T", artist="A", album="B"))

        with temp_db.session() as session:
            assert len(session.scalars(select(Track)).all()) == 1

    def test_rolls_back_when_the_body_raises(self, temp_db):
        with pytest.raises(RuntimeError), temp_db.session() as session:
            session.add(Track(rating_key="1", title="T", artist="A", album="B"))
            session.flush()
            raise RuntimeError("boom")

        with temp_db.session() as session:
            assert session.scalars(select(Track)).all() == []


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
