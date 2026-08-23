"""Own the schema with the ORM, replacing the hand-rolled SQLite one.

Revision ID: 0001_orm_schema
Revises:

`tracks`, `track_genres` and `sync_state` are a cache of Plex and can be
rebuilt, so a pre-Alembic database has them dropped and recreated rather than
altered in place: no column rename, no table rebuild for a foreign key, and
nothing dialect-specific to translate. The cost is one re-sync after upgrading.

`results` holds data no sync can rebuild, so an existing one is copied into the
new table rather than dropped. It is rebuilt rather than left alone because the
legacy definition differs in ways that matter: a nullable primary key and a
`CURRENT_TIMESTAMP` server default.

Dropping `tracks` takes the old `track_genres` triggers with it, since SQLite
drops a table's triggers with the table. See docs/track_genres_consistency.md.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_orm_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Cache tables, dropped and recreated when upgrading a pre-Alembic database.
CACHE_TABLES = ("track_genres", "tracks", "sync_state")

# History indexes, dropped before the rename so the new table can reuse the names.
RESULT_INDEXES = ("idx_results_type_created", "idx_results_created_at")

# Where legacy rows wait while the new `results` is built beside them.
LEGACY_RESULTS = "results_legacy"

RESULT_COLUMNS = (
    "id",
    "type",
    "title",
    "prompt",
    "snapshot",
    "track_count",
    "artist",
    "art_rating_key",
    "subtitle",
)


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())

    for table in CACHE_TABLES:
        if table in existing:
            op.drop_table(table)

    op.create_table(
        "tracks",
        sa.Column("rating_key", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("artist", sa.String(), nullable=False),
        sa.Column("album", sa.String(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("genres", sa.JSON(), nullable=True),
        sa.Column("user_rating", sa.Integer(), nullable=True),
        sa.Column("is_live", sa.Boolean(), nullable=False),
        sa.Column("parent_rating_key", sa.String(), nullable=True),
        sa.Column("view_count", sa.Integer(), nullable=False),
        sa.Column("last_viewed_at", sa.String(), nullable=True),
        sa.Column("sync_token", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("rating_key"),
    )
    op.create_index("idx_tracks_artist", "tracks", ["artist"])
    op.create_index(op.f("ix_tracks_year"), "tracks", ["year"])
    op.create_index(op.f("ix_tracks_is_live"), "tracks", ["is_live"])
    op.create_index(op.f("ix_tracks_parent_rating_key"), "tracks", ["parent_rating_key"])

    op.create_table(
        "track_genres",
        sa.Column("rating_key", sa.String(), nullable=False),
        sa.Column("genre_lower", sa.String(), nullable=False),
        sa.Column("genre", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["rating_key"], ["tracks.rating_key"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("rating_key", "genre_lower"),
    )
    op.create_index("idx_track_genres_lower", "track_genres", ["genre_lower", "rating_key"])

    op.create_table(
        "sync_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plex_server_id", sa.String(), nullable=True),
        sa.Column("last_sync_at", sa.String(), nullable=True),
        sa.Column("track_count", sa.Integer(), nullable=False),
        sa.Column("sync_duration_ms", sa.Integer(), nullable=True),
        sa.Column("sync_cursor", sa.Integer(), nullable=False),
        sa.Column("sync_token", sa.String(), nullable=True),
        sa.CheckConstraint("id = 1", name="sync_state_single_row"),
        sa.PrimaryKeyConstraint("id"),
    )

    legacy_results = "results" in existing
    if legacy_results:
        for index in RESULT_INDEXES:
            op.drop_index(index, table_name="results")
        op.rename_table("results", LEGACY_RESULTS)

    create_results()

    if legacy_results:
        columns = ", ".join(RESULT_COLUMNS)
        op.execute(
            f"INSERT INTO results ({columns}, created_at) "
            f"SELECT {columns}, COALESCE(created_at, CURRENT_TIMESTAMP) FROM {LEGACY_RESULTS}"
        )
        op.drop_table(LEGACY_RESULTS)


def create_results() -> None:
    """Create `results` as the model declares it, history indexes included."""
    op.create_table(
        "results",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("prompt", sa.String(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("track_count", sa.Integer(), nullable=False),
        sa.Column("artist", sa.String(), nullable=True),
        sa.Column("art_rating_key", sa.String(), nullable=True),
        sa.Column("subtitle", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_results_type_created", "results", ["type", "created_at"])
    op.create_index("idx_results_created_at", "results", ["created_at"])


def downgrade() -> None:
    """Drop every table this revision owns.

    The pre-Alembic schema is not restored: it was hand-rolled SQLite with
    triggers, and recreating it would recreate what this revision removes.
    """
    op.drop_table("results")
    op.drop_table("track_genres")
    op.drop_table("tracks")
    op.drop_table("sync_state")
