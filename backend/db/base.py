"""The declarative base every table class inherits from.

Its `metadata` is what Alembic autogenerate compares the database against, so
a table module has to be imported before a migration is generated -- see
`backend/migrations/env.py`.

Separate from `engine`: the engine knows how to connect, this knows what the
schema is, and Alembic needs the second without building the first.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for the library mirror and the saved results."""
