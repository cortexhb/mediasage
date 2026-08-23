"""Everything that talks to a Plex server.

`connection` owns the handle and the retry loop, `PlexLibrary` reads,
`PlexPlaylists` and `PlexPlayback` write, `filters` expresses a query and
`models` the answers. `client` composes the three over one connection into the
single object the application holds.

`link` is upstream of all of it: the browser sign-in that produces the address
and token `connection` is built from.
"""

from backend.plex.client import PlexClient, PlexClientStore, PlexNotConnected, plex_store
from backend.plex.connection import PlexConnection, PlexFetchError, PlexQueryError
from backend.plex.filters import PlexFilter
from backend.plex.library import PlexLibrary
from backend.plex.link import (
    PlexIdentity,
    PlexLink,
    PlexLinkError,
    PlexPin,
    PlexResolution,
    PlexServers,
)
from backend.plex.models import (
    FetchedItems,
    PlaylistResult,
    PlaylistUpdateResult,
    PlayQueueResult,
    PlexClientInfo,
    PlexPlaylistInfo,
)
from backend.plex.playback import PlaybackError, PlexPlayback
from backend.plex.playlists import PlexPlaylists

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
    "PlexIdentity",
    "PlexLibrary",
    "PlexLink",
    "PlexLinkError",
    "PlexNotConnected",
    "PlexPin",
    "PlexPlayback",
    "PlexPlaylistInfo",
    "PlexPlaylists",
    "PlexQueryError",
    "PlexResolution",
    "PlexServers",
    "plex_store",
]
