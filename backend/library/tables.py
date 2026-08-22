"""Table definitions for the Plex library mirror.

Three tables: `tracks` is the mirror itself, `track_genres` is a normalized
index over it so genre filters use an index instead of parsing JSON per row,
and `sync_state` is single-row bookkeeping for the resumable sync.

`track_genres` was previously maintained by SQLite triggers using `json_each`.
It is now written by `backend.library.sync` inside the same transaction as the
track rows, and deletion is the foreign key's cascade: the guarantee is the
same, and nothing here depends on a dialect. See docs/track_genres_consistency.md.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import CheckConstraint, Column, Index
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel

# The single row `sync_state` is constrained to hold.
SYNC_STATE_ID = 1


class Track(SQLModel, table=True):
    """One track, as cached from Plex.

    `genres` holds the album's genre list; `track_genres` carries the same data
    normalized for indexed lookup. `sync_token` marks which sync last wrote the
    row, so a completed sync can sweep rows it did not touch.
    """

    __tablename__ = "tracks"

    rating_key: str = Field(primary_key=True)
    title: str
    artist: str
    album: str
    duration_ms: int = 0
    year: int | None = Field(default=None, index=True)
    genres: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    user_rating: int | None = None
    is_live: bool = Field(default=False, index=True)
    parent_rating_key: str | None = Field(default=None, index=True)
    view_count: int = 0
    last_viewed_at: str | None = None

    # Which sync wrote this row; older tokens are swept on success.
    sync_token: str | None = None

    __table_args__ = (Index("idx_tracks_artist", "artist"),)


class TrackGenre(SQLModel, table=True):
    """One genre of one track, normalized out of `Track.genres`.

    Written only by the sync, in the same transaction as the track itself.
    `genre_lower` is what filters match on; `genre` keeps the original casing
    for display.
    """

    __tablename__ = "track_genres"

    # Cascade replaces the old delete trigger; the engine sweeps orphans.
    rating_key: str = Field(
        primary_key=True, foreign_key="tracks.rating_key", ondelete="CASCADE"
    )
    genre_lower: str = Field(primary_key=True)
    genre: str

    __table_args__ = (Index("idx_track_genres_lower", "genre_lower", "rating_key"),)


class SyncState(SQLModel, table=True):
    """Bookkeeping for the last and the in-flight sync.

    A single row, so `id` is constrained to one value. `sync_token` and
    `sync_cursor` are set while a sync runs and cleared when it completes; a
    non-null token on startup means the previous sync was interrupted.
    """

    __tablename__ = "sync_state"

    id: int = Field(default=SYNC_STATE_ID, primary_key=True)
    plex_server_id: str | None = None
    last_sync_at: str | None = None
    track_count: int = 0
    sync_duration_ms: int | None = None
    sync_cursor: int = 0
    sync_token: str | None = None

    __table_args__ = (CheckConstraint(f"id = {SYNC_STATE_ID}", name="sync_state_single_row"),)


def utc_now() -> datetime:
    """Timezone-aware now, as a Python-side default rather than a SQL one."""
    return datetime.now(UTC)


def genre_rows(rating_key: str, genres: list[Any]) -> list[dict[str, str]]:
    """Normalize a track's genres into `track_genres` rows, deduplicated.

    Args:
        rating_key: The track the genres belong to
        genres: Raw genre values; non-strings and blanks are dropped

    Returns:
        One row per distinct lowercased genre
    """
    seen: dict[str, str] = {}
    for value in genres:
        if not isinstance(value, str) or not value.strip():
            continue
        seen.setdefault(value.lower(), value)

    return [
        {"rating_key": rating_key, "genre_lower": lowered, "genre": original}
        for lowered, original in seen.items()
    ]
