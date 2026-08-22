"""Everything that talks to a Plex server.

`connection` owns the handle and the retry loop, `library` reads, `playlists`
and `playback` write, `filters` expresses a query and `models` the answers.
`client` composes them into the one object the application holds.
"""

from backend.plex import library, playback, playlists
from backend.plex.client import PlexClient, PlexClientStore, plex_store
from backend.plex.connection import (
    PlexConnection,
    PlexFetchError,
    PlexQueryError,
    with_retries,
)
from backend.plex.filters import PlexFilter
from backend.plex.models import (
    FetchedItems,
    PlaylistResult,
    PlaylistUpdateResult,
    PlayQueueResult,
    PlexClientInfo,
    PlexPlaylistInfo,
)
from backend.plex.playback import PlaybackError

__all__ = [
    "FetchedItems",
    "PlayQueueResult",
    "PlaybackError",
    "PlaylistResult",
    "PlaylistUpdateResult",
    "PlexClient",
    "PlexClientInfo",
    "PlexClientStore",
    "PlexConnection",
    "PlexFetchError",
    "PlexFilter",
    "PlexPlaylistInfo",
    "PlexQueryError",
    "library",
    "playback",
    "playlists",
    "plex_store",
    "with_retries",
]
