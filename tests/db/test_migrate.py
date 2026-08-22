"""Tests for the migration that replaced the hand-rolled SQLite schema."""

import sqlite3

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect
from sqlmodel import SQLModel

from backend.db import db, upgrade_to_head
from backend.library.tables import Track
from backend.results.tables import Result

# The pre-Alembic schema, kept verbatim so the upgrade path stays testable
# after the module that created it was deleted.
LEGACY_SCHEMA = """
    CREATE TABLE tracks (
        rating_key TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        artist TEXT NOT NULL,
        album TEXT NOT NULL,
        duration_ms INTEGER,
        year INTEGER,
        genres TEXT,
        user_rating INTEGER,
        is_live BOOLEAN,
        parent_rating_key TEXT,
        view_count INTEGER DEFAULT 0,
        last_viewed_at TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX idx_tracks_artist ON tracks(artist);
    CREATE INDEX idx_tracks_year ON tracks(year);

    CREATE TABLE track_genres (
        rating_key TEXT NOT NULL,
        genre TEXT NOT NULL,
        genre_lower TEXT NOT NULL,
        PRIMARY KEY (rating_key, genre_lower)
    ) WITHOUT ROWID;

    CREATE TRIGGER tracks_genres_after_insert AFTER INSERT ON tracks
    BEGIN
        DELETE FROM track_genres WHERE rating_key = NEW.rating_key;
        INSERT OR IGNORE INTO track_genres (rating_key, genre, genre_lower)
        SELECT NEW.rating_key, je.value, lower(je.value)
        FROM json_each(CASE WHEN json_valid(NEW.genres) THEN NEW.genres ELSE '[]' END) je
        WHERE je.type = 'text';
    END;

    CREATE TRIGGER tracks_genres_after_delete AFTER DELETE ON tracks
    BEGIN
        DELETE FROM track_genres WHERE rating_key = OLD.rating_key;
    END;

    CREATE TABLE sync_state (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        plex_server_id TEXT,
        last_sync_at TIMESTAMP,
        track_count INTEGER DEFAULT 0,
        sync_duration_ms INTEGER,
        sync_cursor INTEGER DEFAULT 0,
        sync_token TEXT
    );
    INSERT INTO sync_state (id) VALUES (1);

    CREATE TABLE results (
        id TEXT PRIMARY KEY,
        type TEXT NOT NULL,
        title TEXT NOT NULL,
        prompt TEXT NOT NULL,
        snapshot JSON NOT NULL,
        track_count INTEGER NOT NULL,
        artist TEXT,
        art_rating_key TEXT,
        subtitle TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX idx_results_type_created ON results(type, created_at DESC);
    CREATE INDEX idx_results_created_at ON results(created_at DESC);
"""

# Naming a table from each package registers it on the metadata compared below.
REGISTERED = (Track, Result)


@pytest.fixture
def legacy_database(tmp_path):
    """A database in the pre-Alembic shape, carrying a track and a result."""
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.executescript(LEGACY_SCHEMA)
    conn.execute(
        "INSERT INTO tracks (rating_key, title, artist, album, genres) "
        "VALUES ('1', 'Song', 'Artist', 'Album', '[\"Rock\"]')"
    )
    conn.execute(
        "INSERT INTO results (id, type, title, prompt, snapshot, track_count, subtitle) "
        "VALUES ('abc', 'prompt_playlist', 'Title', 'p', '{\"x\": 1}', 3, 'sub')"
    )
    conn.commit()
    conn.close()

    db.configure(f"sqlite:///{path}")
    yield path
    db.dispose()


def schema_diffs() -> list:
    """What autogenerate would still want to change after migrating."""
    with db.connection() as conn:
        return compare_metadata(MigrationContext.configure(conn), SQLModel.metadata)


class TestFreshDatabase:
    """A new install gets the ORM schema and nothing legacy."""

    def test_every_table_is_created(self, temp_db):
        names = set(inspect(temp_db.engine()).get_table_names())
        assert {"tracks", "track_genres", "sync_state", "results"} <= names

    def test_the_schema_matches_the_models(self, temp_db):
        assert schema_diffs() == []

    def test_track_genres_cascades_from_tracks(self, temp_db):
        keys = inspect(temp_db.engine()).get_foreign_keys("track_genres")
        assert keys[0]["options"]["ondelete"] == "CASCADE"


class TestLegacyDatabase:
    """An existing install keeps its results and loses its triggers."""

    def test_triggers_are_gone(self, legacy_database):
        upgrade_to_head()
        with db.connection() as conn:
            triggers = conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type = 'trigger'"
            ).fetchall()
        assert triggers == []

    def test_results_survive_intact(self, legacy_database):
        upgrade_to_head()
        with db.connection() as conn:
            row = conn.exec_driver_sql(
                "SELECT id, snapshot, track_count, subtitle FROM results"
            ).fetchone()
        assert row == ("abc", '{"x": 1}', 3, "sub")

    def test_the_cache_is_dropped_for_a_re_sync(self, legacy_database):
        upgrade_to_head()
        with db.connection() as conn:
            assert conn.exec_driver_sql("SELECT COUNT(*) FROM tracks").fetchone()[0] == 0

    def test_the_schema_matches_the_models(self, legacy_database):
        upgrade_to_head()
        assert schema_diffs() == []

    def test_migrating_twice_is_a_no_op(self, legacy_database):
        upgrade_to_head()
        upgrade_to_head()
        assert schema_diffs() == []
