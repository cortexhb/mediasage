"""Domain models for the cached Plex library.

What the library package hands back: tracks, albums, genre and decade counts,
and the state of the sync that produced them. These are the shapes callers
consume; `backend.library.tables` holds the rows they are built from.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from backend.library.tables import Track

# Which stage of the sync is running, for progress display.
SyncPhase = Literal["fetching_albums", "fetching", "processing"]

# How much of an album the user has already heard.
FamiliarityLevel = Literal["unplayed", "light", "well-loved"]


class TrackRecord(BaseModel):
    """One cached track, as callers outside the package see it."""

    rating_key: str
    title: str
    artist: str
    album: str
    duration_ms: int = 0
    year: int | None = None
    genres: list[str] = []
    user_rating: int | None = None
    is_live: bool = False
    parent_rating_key: str | None = None
    view_count: int = 0
    last_viewed_at: str | None = None

    @classmethod
    def of(cls, track: Track) -> TrackRecord:
        """Build from a `tracks` row."""
        return cls.model_validate(track, from_attributes=True)


class GenreCount(BaseModel):
    """Genre with the number of tracks carrying it."""

    name: str
    count: int | None = None


class DecadeCount(BaseModel):
    """Decade with the number of tracks released in it."""

    name: str
    count: int | None = None


class LibraryStats(BaseModel):
    """Genre and decade breakdowns, both sorted by name."""

    genres: list[GenreCount] = []
    decades: list[DecadeCount] = []


class AlbumCandidate(BaseModel):
    """An album from the user's library, aggregated from cached tracks."""

    parent_rating_key: str
    album: str
    album_artist: str
    year: int | None = None
    genres: list[str] = []
    decade: str = ""
    track_count: int = 0
    track_rating_keys: list[str] = []


class AlbumFamiliarity(BaseModel):
    """How much of one album the user has played."""

    level: FamiliarityLevel
    last_viewed_at: str | None = None

    @classmethod
    def of(
        cls,
        total_plays: int,
        avg_plays: float,
        last_viewed_at: str | None,
        well_loved_avg_plays: float,
    ) -> AlbumFamiliarity:
        """Classify an album from its aggregated play counts.

        Args:
            total_plays: Plays summed across the album's tracks
            avg_plays: Mean plays per track
            last_viewed_at: When any of its tracks was last played
            well_loved_avg_plays: Configured threshold for "well-loved"
        """
        if total_plays == 0:
            level: FamiliarityLevel = "unplayed"
        elif avg_plays >= well_loved_avg_plays:
            level = "well-loved"
        else:
            level = "light"
        return cls(level=level, last_viewed_at=last_viewed_at)


class SyncProgress(BaseModel):
    """How far the running sync has got."""

    phase: SyncPhase | None = None
    current: int = 0
    total: int = 0


class SyncRun(BaseModel):
    """In-memory state of the sync in this process.

    Separate from `sync_state` in the database: that records the last completed
    sync, this records the one happening now.
    """

    is_syncing: bool = False
    progress: SyncProgress = SyncProgress()
    error: str | None = None


class SyncStatus(BaseModel):
    """The last completed sync, plus the running one if there is one."""

    track_count: int = 0
    synced_at: str | None = None
    plex_server_id: str | None = None
    sync_duration_ms: int | None = None
    is_syncing: bool = False
    sync_progress: SyncProgress | None = None
    error: str | None = None


class SyncResult(BaseModel):
    """Outcome of one sync attempt.

    `resumable` marks a failure whose written rows and checkpoint survive, so
    the next attempt continues instead of refetching the library.
    """

    success: bool
    track_count: int = 0
    duration_ms: int = 0
    resumable: bool = False
    error: str | None = None


def usable_genres(value: Any) -> list[str]:
    """Keep only the genres that can be written.

    Plex sometimes reports a genre that is not a string; one of those must not
    fail a whole sync.
    """
    if not isinstance(value, list):
        return []
    return [genre for genre in value if isinstance(genre, str) and genre.strip()]


class AlbumMetadata(BaseModel):
    """What an album contributes to each of its tracks.

    Plex files genre and year on the album, not the track, so the sync reads
    them once per album and copies them down.
    """

    genres: list[str] = []
    year: int | None = None

    @field_validator("genres", mode="before")
    @classmethod
    def drop_unusable_genres(cls, value: Any) -> list[str]:
        return usable_genres(value)


class TrackRow(BaseModel):
    """One track staged for writing, in `tracks` column order.

    Built from a Plex object before the batch is upserted, so the raw plexapi
    attribute reads happen in one place.
    """

    rating_key: str
    title: str
    artist: str
    album: str
    duration_ms: int = 0
    year: int | None = None
    genres: list[str] = []
    user_rating: int | None = None
    is_live: bool = False
    parent_rating_key: str | None = None
    view_count: int = Field(default=0, ge=0)
    last_viewed_at: str | None = None
    sync_token: str

    @field_validator("genres", mode="before")
    @classmethod
    def drop_unusable_genres(cls, value: Any) -> list[str]:
        return usable_genres(value)

    def columns(self) -> dict[str, Any]:
        """Column-keyed values for the upsert."""
        return self.model_dump()
