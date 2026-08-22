"""Database engine, session handling, and the one dialect-aware statement.

Nothing above this package names a SQL dialect. Entry points: `db` for sessions
and connections, `upsert` for insert-or-update, `upgrade_to_head` to bring the
schema current at startup.
"""

from backend.db.engine import DATA_DIR, DB_PATH, Database, db, sqlite_url
from backend.db.migrate import upgrade_to_head
from backend.db.statements import upsert

__all__ = ["DATA_DIR", "DB_PATH", "Database", "db", "sqlite_url", "upgrade_to_head", "upsert"]
