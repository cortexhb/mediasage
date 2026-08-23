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
from functools import partial
from typing import Any, Final, Self

from sqlalchemy import CheckConstraint, ColumnElement, ForeignKey, Index, and_
from sqlalchemy.orm import Mapped, Session, mapped_column
from sqlalchemy.types import JSON

from backend.db.base import Base

# The single row `sync_state` is constrained to hold.
SYNC_STATE_ID = 1

# A default factory takes no arguments; aware, so it compares against synced_at.
UTC_NOW: Final = partial(datetime.now, UTC)


class Track(Base):
    """One track, as cached from Plex.

    `genres` holds the album's genre list; `track_genres` carries the same data
    normalized for indexed lookup. `sync_token` marks which sync last wrote the
    row, so a completed sync can sweep rows it did not touch.
    """

    __tablename__ = "tracks"

    rating_key: Mapped[str] = mapped_column(primary_key=True)
    title: Mapped[str]
    artist: Mapped[str]
    album: Mapped[str]
    duration_ms: Mapped[int] = mapped_column(default=0)
    year: Mapped[int | None] = mapped_column(default=None, index=True)
    # Nullable since the first migration; rows written before genres were kept hold NULL.
    genres: Mapped[list[str] | None] = mapped_column(JSON, default=list)
    user_rating: Mapped[int | None] = mapped_column(default=None)
    is_live: Mapped[bool] = mapped_column(default=False, index=True)
    parent_rating_key: Mapped[str | None] = mapped_column(default=None, index=True)
    view_count: Mapped[int] = mapped_column(default=0)
    last_viewed_at: Mapped[str | None] = mapped_column(default=None)

    # Which sync wrote this row; older tokens are swept on success.
    sync_token: Mapped[str | None] = mapped_column(default=None)

    __table_args__ = (Index("idx_tracks_artist", "artist"),)

    @classmethod
    def has_album_key(cls) -> ColumnElement[bool]:
        """Tracks that belong to an identifiable album."""
        return and_(cls.parent_rating_key.is_not(None), cls.parent_rating_key != "")


class TrackGenre(Base):
    """One genre of one track, normalized out of `Track.genres`.

    Written only by the sync, in the same transaction as the track itself.
    `genre_lower` is what filters match on; `genre` keeps the original casing
    for display.
    """

    __tablename__ = "track_genres"

    # Cascade replaces the old delete trigger; the engine sweeps orphans.
    rating_key: Mapped[str] = mapped_column(
        ForeignKey("tracks.rating_key", ondelete="CASCADE"), primary_key=True
    )
    genre_lower: Mapped[str] = mapped_column(primary_key=True)
    genre: Mapped[str]

    __table_args__ = (Index("idx_track_genres_lower", "genre_lower", "rating_key"),)

    @classmethod
    def rows_for(cls, rating_key: str, genres: list[Any]) -> list[dict[str, str]]:
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


class SyncState(Base):
    """Bookkeeping for the last and the in-flight sync.

    A single row, so `id` is constrained to one value. `sync_token` and
    `sync_cursor` are set while a sync runs and cleared when it completes; a
    non-null token on startup means the previous sync was interrupted.
    """

    __tablename__ = "sync_state"

    id: Mapped[int] = mapped_column(primary_key=True, default=SYNC_STATE_ID)
    plex_server_id: Mapped[str | None] = mapped_column(default=None)
    last_sync_at: Mapped[str | None] = mapped_column(default=None)
    track_count: Mapped[int] = mapped_column(default=0)
    sync_duration_ms: Mapped[int | None] = mapped_column(default=None)
    sync_cursor: Mapped[int] = mapped_column(default=0)
    sync_token: Mapped[str | None] = mapped_column(default=None)

    __table_args__ = (CheckConstraint(f"id = {SYNC_STATE_ID}", name="sync_state_single_row"),)

    @classmethod
    def load(cls, session: Session) -> Self:
        """The single row, created on first use.

        Flushed rather than committed: the caller's transaction owns when this
        lands, and a sync writes the checkpoint alongside the rows it counts.
        """
        state = session.get(cls, SYNC_STATE_ID)
        if state is None:
            state = cls(id=SYNC_STATE_ID)
            session.add(state)
            session.flush()
        return state
