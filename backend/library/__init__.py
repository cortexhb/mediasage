"""The local mirror of the Plex music library.

`sync` writes it, `tracks` and `albums` read it, `filters` expresses what to
keep, and `tables` defines the rows. Nothing here names a SQL dialect.
"""

from backend.library import albums, tracks
from backend.library.filters import DecadeRange, TrackFilter, has_album_key
from backend.library.live import LiveVersionRule
from backend.library.models import (
    AlbumCandidate,
    AlbumFamiliarity,
    AlbumMetadata,
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
from backend.library.sync import (
    clear_cache,
    has_tracks,
    is_stale,
    library_sync,
    server_changed,
    sync_status,
)
from backend.library.tables import SyncState, Track, TrackGenre, genre_rows

__all__ = [
    "AlbumCandidate",
    "AlbumFamiliarity",
    "AlbumMetadata",
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
    "TrackFilter",
    "TrackGenre",
    "TrackRecord",
    "TrackRow",
    "albums",
    "clear_cache",
    "genre_rows",
    "has_album_key",
    "has_tracks",
    "is_stale",
    "library_sync",
    "server_changed",
    "sync_status",
    "tracks",
]
