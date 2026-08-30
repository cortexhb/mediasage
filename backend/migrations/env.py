"""Alembic environment, wired to the application's own engine.

The URL comes from `backend.db.db`, so migrations and the app can never
disagree about which database they mean. Importing a table from each package
registers that module on `Base.metadata`, which is what autogenerate
compares against.

The app configures `db` before calling Alembic. Run from the command line it is
unconfigured, and would migrate the default SQLite file rather than the
deployment's own database, so the URL is read from the environment here too.
"""

import os

from alembic import context

from backend.config.models import DatabaseConfig
from backend.db import Base, db
from backend.library.tables import Track
from backend.results.tables import Result

# Naming a table from each package registers that module on the metadata below.
REGISTERED = (Track, Result)

# Read directly, not through `MediasageConfig`: autogenerate has to work in a
# checkout with no LLM provider set, and that section has no default.
DATABASE_URL_ENV = "MEDIASAGE_DATABASE__URL"

if not db.settings.url and os.environ.get(DATABASE_URL_ENV):
    db.configure(DatabaseConfig(url=os.environ[DATABASE_URL_ENV]))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it, for review or manual apply."""
    context.configure(
        url=db.resolved_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against the engine the application uses."""
    with db.engine().connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite cannot ALTER most things in place; batch mode rebuilds.
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
