"""The Plex client the application talks through, and the store holding it.

`PlexClient` is a facade: it owns one `PlexConnection` and forwards to the
modules that do the work, so a caller needs one handle rather than five.
Entry points: `plex_store.get`, `plex_store.init`.

Every method here is synchronous and may block on the network. Call them from
an endpoint through `asyncio.to_thread`.
"""

from collections.abc import Iterator
from typing import Any, Self

from pydantic import BaseModel, ConfigDict

from backend.config import PlexConfig
from backend.library import AlbumMetadata
from backend.models import LibraryStatsResponse, Track
from backend.plex import library, playback, playlists
from backend.plex.connection import PlexConnection
from backend.plex.filters import PlexFilter
from backend.plex.models import (
    PlaylistResult,
    PlaylistUpdateResult,
    PlayQueueResult,
    PlexClientInfo,
    PlexPlaylistInfo,
)


class PlexClient(BaseModel):
    """One Plex server, with everything the application asks of it."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    connection: PlexConnection

    @classmethod
    def of(cls, config: PlexConfig) -> Self:
        """Build from the Plex configuration section, connecting immediately."""
        return cls(
            connection=PlexConnection(
                url=config.url,
                token=config.token,
                music_library=config.music_library,
                connect_timeout=config.connect_timeout,
                reconnect_cooldown=config.reconnect_cooldown,
            )
        )

    # -- connection ------------------------------------------------------

    def is_connected(self) -> bool:
        """Whether the server and library are both reachable."""
        return self.connection.is_connected()

    @property
    def error(self) -> str | None:
        """Why the last connection attempt failed, if it did."""
        return self.connection.error

    @property
    def server_name(self) -> str | None:
        """The server's friendly name, for confirming the right one is set."""
        return self.connection.server_name

    def machine_identifier(self) -> str | None:
        """The server's stable id, used to notice the library was swapped."""
        return self.connection.machine_identifier()

    def music_libraries(self) -> list[str]:
        """Every music library on the server, whichever one is configured."""
        return self.connection.music_libraries()

    # -- library ---------------------------------------------------------

    def total_tracks(self) -> int:
        return library.total_tracks(self.connection)

    def iter_raw_tracks(
        self, start: int = 0, page_size: int | None = None
    ) -> Iterator[list[Any]]:
        return library.iter_raw_tracks(self.connection, start, page_size)

    def all_raw_tracks(self) -> list[Any]:
        return library.all_raw_tracks(self.connection)

    def album_metadata(self) -> dict[str, AlbumMetadata]:
        return library.album_metadata(self.connection)

    def stats(self) -> LibraryStatsResponse:
        return library.stats(self.connection)

    def filtered(self, plex_filter: PlexFilter, limit: int = 0) -> list[Track]:
        return library.filtered(self.connection, plex_filter, limit)

    def count(self, plex_filter: PlexFilter) -> int:
        return library.count(self.connection, plex_filter)

    def random_tracks(self, wanted: int, exclude_live: bool = True) -> list[Track]:
        return library.random_tracks(self.connection, wanted, exclude_live)

    def search(self, query: str, limit: int = 20) -> list[Track]:
        return library.search(self.connection, query, limit)

    def track_by_key(self, rating_key: str) -> Track | None:
        return library.track_by_key(self.connection, rating_key)

    def thumb_path(self, rating_key: str) -> str | None:
        return library.thumb_path(self.connection, rating_key)

    # -- playlists -------------------------------------------------------

    def create_playlist(
        self, name: str, rating_keys: list[str], description: str = ""
    ) -> PlaylistResult:
        return playlists.create(self.connection, name, rating_keys, description)

    def playlists(self) -> list[PlexPlaylistInfo]:
        return playlists.listing(self.connection)

    def update_playlist(
        self,
        playlist_id: str,
        rating_keys: list[str],
        mode: str = "replace",
        description: str = "",
    ) -> PlaylistUpdateResult:
        return playlists.update(self.connection, playlist_id, rating_keys, mode, description)

    # -- playback --------------------------------------------------------

    def clients(self) -> list[PlexClientInfo]:
        return playback.clients(self.connection)

    def play_queue(
        self, rating_keys: list[str], client_id: str, mode: str = "replace"
    ) -> PlayQueueResult:
        return playback.play_queue(self.connection, rating_keys, client_id, mode)


class PlexClientStore(BaseModel):
    """Holds the Plex client the application talks through.

    Built from configuration at startup and rebuilt whenever the Plex settings
    change, so a stale connection can never outlive the config that made it.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, validate_assignment=True)

    client: PlexClient | None = None

    def get(self) -> PlexClient | None:
        """The current client, or None before one is configured."""
        return self.client

    def init(self, config: PlexConfig) -> PlexClient:
        """Replace the client with one built from `config`."""
        self.client = PlexClient.of(config)
        return self.client


# The single instance the application talks through.
plex_store = PlexClientStore()
