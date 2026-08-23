"""Alembic environment, wired to the application's own engine.

The URL comes from `backend.db.db`, so migrations and the app can never
disagree about which database they mean. Importing a table from each package
registers that module on `Base.metadata`, which is what autogenerate
compares against.
"""

from alembic import context

from backend.db import Base, db
from backend.library.tables import Track
from backend.results.tables import Result

# Naming a table from each package registers that module on the metadata below.
REGISTERED = (Track, Result)

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
