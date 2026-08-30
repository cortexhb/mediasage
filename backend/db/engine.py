"""Database engine and session management.

Owns the single SQLAlchemy engine and hands out sessions. Entry points are
`db.configure()`, `db.start()`, `db.engine()` and `db.session()`.

The URL decides the backend: a file-backed SQLite database when none is
configured, Postgres when one is. Nothing above this module names a dialect --
pragmas are applied on connect only for SQLite, pool options only for a server
backend, and `Upsert` in `backend.db.statements` dispatches on the dialect.
"""

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import Connection
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from backend.config.models import DatabaseConfig
from backend.db.statements import UPSERT_DIALECTS

logger = logging.getLogger(__name__)

# Where a file-backed SQLite database lives when no URL is configured.
DATA_DIR = Path(__file__).parent.parent.parent / "data"
DB_PATH = DATA_DIR / "library_cache.db"

# Seconds a statement waits on a locked SQLite file before giving up.
SQLITE_BUSY_TIMEOUT_MS = 5000
SQLITE_CONNECT_TIMEOUT = 30.0


@event.listens_for(Engine, "connect")
def _apply_sqlite_pragmas(dbapi_connection: Any, record: Any) -> None:
    """Apply the pragmas SQLite needs, and only when the backend is SQLite.

    WAL lets reads proceed during a sync write. Postgres needs none of this, so
    the listener checks the driver rather than assuming a dialect.

    Module-level because SQLAlchemy registers listeners on a plain function.
    """
    if type(dbapi_connection).__module__.split(".")[0] != "sqlite3":
        return

    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


class Database(BaseModel):
    """The process's database, built once and reused.

    Holds the engine rather than a connection: pooling, per-thread affinity and
    reconnection are the engine's job, not ours.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    settings: DatabaseConfig = DatabaseConfig()
    _engine: Engine | None = None

    @staticmethod
    def sqlite_url(path: Path) -> str:
        """The SQLAlchemy URL for a file-backed SQLite database."""
        return f"sqlite:///{path}"

    @property
    def data_dir(self) -> Path:
        """Where a file-backed database and the saved settings live."""
        return DATA_DIR

    def data_dir_writable(self) -> bool:
        """Whether the data directory can actually be written to.

        Written to rather than checked with `os.access`: a Docker bind mount
        can report permission the kernel then refuses.

        Still meaningful on a server backend: the saved settings live here too.
        """
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            probe = self.data_dir / ".write_test"
            probe.write_text("test")
            probe.unlink()
        except OSError:
            return False
        return True

    def configure(self, settings: DatabaseConfig) -> None:
        """Point at a different database, disposing of the current engine."""
        self.dispose()
        self.settings = settings

    def resolved_url(self) -> str:
        """The configured URL, defaulting to the SQLite file under `data/`."""
        if self.settings.is_default:
            return self.sqlite_url(DB_PATH)
        return self.settings.url.get_secret_value()

    def engine_options(self) -> dict[str, Any]:
        """The connection and pool arguments this backend needs.

        SQLite is a file: there is no server to pool against, and its pool
        exists to guard cross-thread access. A server backend gets the
        opposite -- a sized pool, a liveness check and a connect timeout,
        because a restart or an idle proxy closes connections without saying so.
        """
        if self.resolved_url().startswith("sqlite"):
            # FastAPI serves requests across threads; the pool guards access.
            return {
                "connect_args": {
                    "check_same_thread": False,
                    "timeout": SQLITE_CONNECT_TIMEOUT,
                }
            }

        return {
            "pool_size": self.settings.pool_size,
            "pool_recycle": self.settings.pool_recycle,
            # A connection closed while idle is found here, not mid-request.
            "pool_pre_ping": True,
            "connect_args": {"connect_timeout": self.settings.connect_timeout},
        }

    def engine(self) -> Engine:
        """The engine, created on first use."""
        if self._engine is None:
            if self.settings.is_default:
                DATA_DIR.mkdir(parents=True, exist_ok=True)
            self._engine = create_engine(self.resolved_url(), **self.engine_options())
        return self._engine

    def start(self) -> None:
        """Refuse an unsupported backend, then wait for it to answer.

        Called once at startup, before migrations. A compose file brings the
        database up beside the app, so a refused connection is retried on the
        configured backoff rather than killing the process on the first attempt.

        Raises:
            NotImplementedError: If the URL names a backend with no upsert form
            OperationalError: If the last attempt still cannot connect
        """
        dialect = self.engine().dialect.name
        if dialect not in UPSERT_DIALECTS:
            supported = ", ".join(sorted(UPSERT_DIALECTS))
            raise NotImplementedError(
                f"Unsupported database backend {dialect!r}; supported: {supported}"
            )

        backoff = self.settings.startup_backoff
        for attempt in range(len(backoff) + 1):
            try:
                with self.engine().connect():
                    return
            except OperationalError:
                if attempt == len(backoff):
                    raise
                logger.warning("Database not reachable, retrying in %.1fs", backoff[attempt])
                time.sleep(backoff[attempt])

    @contextmanager
    def session(self) -> Iterator[Session]:
        """A session that commits on success and rolls back on failure.

        Instances are not expired on commit: a caller that reads a returned
        row after the block would otherwise hit a detached-instance error.
        """
        session = Session(self.engine(), expire_on_commit=False)
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @contextmanager
    def connection(self) -> Iterator[Connection]:
        """A raw connection, for DDL and migrations."""
        with self.engine().begin() as conn:
            yield conn

    def dispose(self) -> None:
        """Close the pool and forget the engine."""
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None


# The single instance the application reads and writes through.
db = Database()
