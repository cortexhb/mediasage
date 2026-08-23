"""The Plex client the application talks through, and the store holding it.

`PlexClient` is one connection with the three readers and writers built over
it: `library` for reads, `playlists` and `playback` for writes. A caller needs
one handle rather than four. Entry points: `plex_store.require`, `plex_store.get`.

Every call reached from here is synchronous and may block on the network. Call
them from an endpoint through `asyncio.to_thread`.
"""

from functools import cached_property
from typing import Self

from pydantic import BaseModel, ConfigDict

from backend.config import PlexConfig
from backend.plex.connection import PlexConnection
from backend.plex.library import PlexLibrary
from backend.plex.playback import PlexPlayback
from backend.plex.playlists import PlexPlaylists


class PlexClient(BaseModel):
    """One Plex server, with everything the application asks of it.

    `library`, `playlists` and `playback` are built over `connection` rather
    than supplied: all three are views of the same handle, and a caller passing
    a different one would give the client two servers.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    connection: PlexConnection

    @cached_property
    def library(self) -> PlexLibrary:
        """Every read: pages for the sync, queries for the UI."""
        return PlexLibrary(connection=self.connection)

    @cached_property
    def playlists(self) -> PlexPlaylists:
        """Creating, listing and updating playlists."""
        return PlexPlaylists(connection=self.connection)

    @cached_property
    def playback(self) -> PlexPlayback:
        """Finding players and sending them a queue."""
        return PlexPlayback(connection=self.connection)

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


class PlexNotConnected(RuntimeError):
    """Raised when work needs a Plex server and there is none reachable."""


class PlexClientStore:
    """Holds the Plex client the application talks through.

    Built from configuration at startup and rebuilt whenever the Plex settings
    change, so a stale connection can never outlive the config that made it.

    A plain class, not a model: its methods are depended on directly by the
    routes, and a bound method of an unfrozen pydantic model is unhashable.
    """

    def __init__(self) -> None:
        self.client: PlexClient | None = None

    def get(self) -> PlexClient | None:
        """The client the process holds, connected or not.

        For a caller that reports *why* Plex is unreachable rather than needing
        it; everything else wants `require`.
        """
        return self.client

    def require(self) -> PlexClient:
        """The connected client, for a caller that cannot work without one.

        Raises:
            PlexNotConnected: If none was built, or the built one cannot reach Plex
        """
        if self.client is None or not self.client.connection.is_connected():
            raise PlexNotConnected("Plex not connected")
        return self.client

    def is_connected(self) -> bool:
        """Whether Plex is reachable right now."""
        return self.client is not None and self.client.connection.is_connected()


# The single instance the application talks through. `client` is assigned
# wherever the Plex settings change: at boot, and after a save.
plex_store = PlexClientStore()
