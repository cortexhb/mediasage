"""Database engine, session handling, and the one dialect-aware statement.

Nothing above this package names a SQL dialect. Entry points: `db` for sessions
and connections, `Upsert` for insert-or-update, `migrations` to bring the
schema current at startup.

Modules:
    base        -- the declarative base every table class inherits from
    engine      -- the engine, its pragmas, and the session context managers
    migrate     -- the Alembic revisions and how to apply them
    statements  -- the one statement whose SQL differs between backends
"""

from backend.db.base import Base
from backend.db.engine import DATA_DIR, DB_PATH, Database, db
from backend.db.migrate import Migrations, migrations
from backend.db.statements import Upsert

__all__ = ["DATA_DIR", "DB_PATH", "Base", "Database", "Migrations", "Upsert", "db", "migrations"]
