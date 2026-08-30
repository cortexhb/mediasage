"""The schema renders on both supported backends, without one to render on.

`compare_metadata` in `test_migrate` proves the migration matches the models,
but only against the database the suite is running on. These compile the DDL
for both dialects in process, so a SQLite-only run still catches a column that
Postgres would build differently.
"""

import pytest
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.schema import CreateTable

from backend.db import Base
from backend.db.statements import UPSERT_DIALECTS
from backend.library.tables import Track
from backend.results.tables import Result

# Naming a table from each package registers that module on the metadata.
REGISTERED = (Track, Result)

TABLES = [table.name for table in Base.metadata.sorted_tables]


def ddl(name: str, dialect) -> str:
    """The CREATE TABLE this dialect would emit for one table.

    Module-level: it converts between two third-party shapes, a SQLAlchemy
    `Table` and a dialect, and neither is ours to hang a method on.
    """
    table = Base.metadata.tables[name]
    return str(CreateTable(table).compile(dialect=dialect))


class TestSchemaCompiles:
    """Every table has to render on every backend the upsert supports."""

    @pytest.mark.parametrize("dialect", [sqlite.dialect(), postgresql.dialect()])
    @pytest.mark.parametrize("table", TABLES)
    def test_the_table_renders(self, table, dialect):
        assert ddl(table, dialect).startswith("\nCREATE TABLE")

    def test_the_dialects_tested_are_the_ones_supported(self):
        """A third backend must arrive here too, not just in the upsert table."""
        assert set(UPSERT_DIALECTS) == {"sqlite", "postgresql"}


class TestColumnsPostgresWouldGetWrong:
    """Two declarations exist only because Postgres differs from SQLite."""

    def test_the_sync_state_row_id_is_not_a_sequence(self):
        """The single row supplies its own id; a SERIAL would never advance."""
        assert "SERIAL" not in ddl("sync_state", postgresql.dialect())

    def test_a_saved_result_keeps_its_time_zone(self):
        """`UTC_NOW` is aware; a naive column shifts it by the server's TimeZone."""
        rendered = ddl("results", postgresql.dialect())
        assert "created_at TIMESTAMP WITH TIME ZONE" in rendered
