"""The local mirror of the Plex music library.

`sync` writes it and answers for its state, `track_cache` and `album_cache`
read it, `filters` expresses what to keep, and `tables` defines the rows.
Nothing here names a SQL dialect.

`library_sync` runs the sync and reports what the cache holds, since every one
of those answers comes off the row it writes.
"""

from backend.library.albums import AlbumCache, album_cache
from backend.library.filters import DecadeRange, TrackFilter
from backend.library.live import LiveVersionRule
from backend.library.models import (
    AlbumCandidate,
    AlbumFamiliarity,
    AlbumMetadata,
    AlbumProgress,
    AlbumStage,
    DecadeCount,
    FamiliarityLevel,
    GenreCount,
    LibraryStats,
    SyncPhase,
    SyncProgress,
    SyncResult,
    SyncRun,
    SyncStatus,
    TrackRecord,
    TrackRow,
)
from backend.library.sync import library_sync
from backend.library.tables import SyncState, Track, TrackGenre
from backend.library.tracks import TrackCache, track_cache

__all__ = [
    "AlbumCache",
    "AlbumCandidate",
    "AlbumFamiliarity",
    "AlbumMetadata",
    "AlbumProgress",
    "AlbumStage",
    "DecadeCount",
    "DecadeRange",
    "FamiliarityLevel",
    "GenreCount",
    "LibraryStats",
    "LiveVersionRule",
    "SyncPhase",
    "SyncProgress",
    "SyncResult",
    "SyncRun",
    "SyncState",
    "SyncStatus",
    "Track",
    "TrackCache",
    "TrackFilter",
    "TrackGenre",
    "TrackRecord",
    "TrackRow",
    "album_cache",
    "library_sync",
    "track_cache",
]
