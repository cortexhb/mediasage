"""Database engine and session management.

Owns the single SQLAlchemy engine and hands out sessions. Entry points are
`db.engine()`, `db.session()` and `db.configure()`.

The URL decides the backend. SQLite is the default and the only one shipped, but
nothing above this module names a dialect: pragmas are applied on connect only
for SQLite, and `upsert` in `backend.db.statements` dispatches on the dialect.
Moving to Postgres is a URL change plus an Alembic run.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Engine, event
from sqlalchemy.engine import Connection
from sqlmodel import Session, create_engine

# Where a file-backed SQLite database lives when no URL is configured.
DATA_DIR = Path(__file__).parent.parent.parent / "data"
DB_PATH = DATA_DIR / "library_cache.db"

# Seconds a statement waits on a locked SQLite file before giving up.
SQLITE_BUSY_TIMEOUT_MS = 5000
SQLITE_CONNECT_TIMEOUT = 30.0


def sqlite_url(path: Path) -> str:
    """The SQLAlchemy URL for a file-backed SQLite database."""
    return f"sqlite:///{path}"


@event.listens_for(Engine, "connect")
def _apply_sqlite_pragmas(dbapi_connection: Any, record: Any) -> None:
    """Apply the pragmas SQLite needs, and only when the backend is SQLite.

    WAL lets reads proceed during a sync write. Postgres needs none of this, so
    the listener checks the driver rather than assuming a dialect.
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

    url: str | None = None
    _engine: Engine | None = None

    def configure(self, url: str) -> None:
        """Point at a different database, disposing of the current engine.

        Tests use this to redirect to a temporary file; nothing else should.
        """
        self.dispose()
        self.url = url

    def resolved_url(self) -> str:
        """The configured URL, defaulting to the SQLite file under `data/`."""
        if self.url:
            return self.url
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        return sqlite_url(DB_PATH)

    def engine(self) -> Engine:
        """The engine, created on first use."""
        if self._engine is None:
            url = self.resolved_url()
            connect_args: dict[str, Any] = {}
            if url.startswith("sqlite"):
                # FastAPI serves requests across threads; the pool guards access.
                connect_args = {
                    "check_same_thread": False,
                    "timeout": SQLITE_CONNECT_TIMEOUT,
                }
            self._engine = create_engine(url, connect_args=connect_args)
        return self._engine

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
