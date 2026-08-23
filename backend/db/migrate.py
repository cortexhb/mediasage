"""Bringing the database up to the current schema.

Entry point: `migrations.upgrade_to_head()`, called once at startup. Alembic
owns every schema change; nothing else in the codebase issues DDL, tests
included.
"""

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)

# Resolved from this file, so the working directory does not decide it.
MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


class Migrations(BaseModel):
    """The Alembic revisions this package ships, and how to apply them."""

    model_config = ConfigDict(frozen=True)

    directory: Path = MIGRATIONS_DIR

    def config(self) -> Config:
        """The Alembic config, built in memory.

        `alembic.ini` is for the command line only; the app must not need a
        file beside the package to know where its own migrations are.
        """
        config = Config()
        config.set_main_option("script_location", str(self.directory))
        return config

    def upgrade_to_head(self) -> None:
        """Apply every pending migration to the configured database."""
        logger.info("Applying database migrations")
        command.upgrade(self.config(), "head")
        logger.info("Database schema is current")


# The revisions the application runs, resolved once.
migrations = Migrations()
