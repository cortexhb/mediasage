"""Finding players and sending them a queue.

`PlexPlayback` holds the connection and answers both. Players reach the server
two ways -- GDM discovery on the LAN and the account's cloud resources -- and
neither alone sees them all, so both are asked. Entry points: `clients`,
`play_queue`.

Mobile and TV players only accept a queue while something is already playing;
`PlexClientInfo.is_mobile` marks the ones the UI must warn about.
"""

import contextlib
import logging
from typing import Any, Final

from plexapi.playqueue import PlayQueue
from pydantic import BaseModel, ConfigDict
from requests.exceptions import ConnectionError

from backend.plex.connection import PlexConnection
from backend.plex.models import PlayQueueResult, PlexClientInfo

logger = logging.getLogger(__name__)

# The play queue modes `play_queue` accepts.
QUEUE_MODES: Final = ("replace", "play_next")


class PlaybackError(Exception):
    """A queue could not be sent, for a reason worth showing the user."""


class PlexPlayback(BaseModel):
    """Discovering players on one Plex server, and queueing tracks to them."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    connection: PlexConnection

    def clients(self) -> list[PlexClientInfo]:
        """Every reachable player, from LAN discovery and the account's resources.

        A player that does not answer is dropped rather than listed: offering it in
        the picker would only fail later.
        """
        if not self.connection.server:
            return []

        found = self._local_clients()
        local_count = len(found)
        found.extend(self._cloud_clients({client.client_id for client in found}))

        logger.debug(
            "Client discovery: %d found (%d local, %d cloud)",
            len(found),
            local_count,
            len(found) - local_count,
        )
        return found

    def _local_clients(self) -> list[PlexClientInfo]:
        """Players the server discovered on the local network."""
        try:
            discovered = self.connection.server.clients()
        except Exception as error:
            logger.warning("Failed to get local Plex clients: %s", error)
            return []

        found: list[PlexClientInfo] = []
        for client in discovered:
            capabilities = getattr(client, "protocolCapabilities", None) or []
            if isinstance(capabilities, str):
                capabilities = [item.strip() for item in capabilities.split(",")]
            if "playback" not in capabilities:
                continue

            try:
                is_playing = client.isPlayingMedia(includePaused=True)
            except Exception:
                logger.warning(
                    "Client '%s' unresponsive, skipping", getattr(client, "title", "unknown")
                )
                continue

            found.append(
                PlexClientInfo(
                    client_id=client.machineIdentifier,
                    name=client.title,
                    product=client.product,
                    platform=client.platform,
                    is_playing=is_playing,
                )
            )
        return found

    def _cloud_clients(self, seen: set[str]) -> list[PlexClientInfo]:
        """Players reachable through the Plex account rather than the LAN.

        Whether one is playing comes from the server's sessions, fetched once:
        a cloud resource cannot be asked directly without connecting to it.
        """
        try:
            resources = self.connection.server.myPlexAccount().resources()
        except Exception as error:
            logger.warning("Failed to query account resources for players: %s", error)
            return []

        playing: set[str] = set()
        try:
            for session in self.connection.server.sessions():
                if session.player:
                    playing.add(session.player.machineIdentifier)
        except Exception as error:
            logger.warning("Could not read active sessions: %s", error)

        found: list[PlexClientInfo] = []
        for resource in resources:
            client_id = resource.clientIdentifier
            if "player" not in (getattr(resource, "provides", "") or ""):
                continue
            if client_id in seen or not getattr(resource, "presence", False):
                continue

            seen.add(client_id)
            product = getattr(resource, "product", "Unknown")
            platform = (
                getattr(resource, "platform", None)
                or getattr(resource, "platformVersion", None)
                or "Unknown"
            )
            found.append(
                PlexClientInfo(
                    client_id=client_id,
                    name=resource.name,
                    product=product,
                    platform=platform,
                    is_playing=client_id in playing,
                )
            )
        return found

    def play_queue(
        self, rating_keys: list[str], client_id: str, mode: str = "replace"
    ) -> PlayQueueResult:
        """Send tracks to a player, either as a new queue or after the current one.

        Args:
            rating_keys: Tracks to queue, in order
            client_id: The player's machine identifier
            mode: "replace" starts a new queue, "play_next" inserts into the live one

        Returns:
            The outcome; `error_code` is "not_found" when the player is unreachable
        """
        if not self.connection.server:
            return PlayQueueResult(success=False, error="Not connected to Plex")
        if mode not in QUEUE_MODES:
            return PlayQueueResult(success=False, error=f"Unknown play queue mode: {mode}")

        client = self._find_client(client_id)
        if not client:
            return PlayQueueResult(
                success=False,
                error=(
                    "Device couldn't be reached. Try starting playback on the device "
                    "first, then re-open the picker."
                ),
                error_code="not_found",
            )

        # Routing commands through the server is more reliable than talking to the
        # player directly; not every client supports it, so failure is ignored.
        with contextlib.suppress(Exception):
            client.proxyThroughServer(value=True)

        fetched = self.connection.fetch_items(rating_keys)
        if not fetched:
            return PlayQueueResult(success=False, error="No valid tracks found")

        try:
            if mode == "replace":
                queued = self._start_queue(client, fetched.items)
            else:
                queued = self._queue_next(client, client_id, fetched.items)
        except ConnectionError:
            return PlayQueueResult(
                success=False, error=f"Client '{client.title}' went offline during playback"
            )
        except PlaybackError as error:
            return PlayQueueResult(success=False, error=str(error))
        except Exception as error:
            logger.exception("Failed to create play queue on '%s'", client.title)
            return PlayQueueResult(success=False, error=str(error))

        return PlayQueueResult(
            success=True,
            client_name=client.title,
            client_product=client.product,
            tracks_queued=queued,
            tracks_skipped=fetched.skipped_count,
        )

    def _find_client(self, client_id: str) -> Any | None:
        """The player with this machine identifier, LAN first then cloud."""
        with contextlib.suppress(Exception):
            for client in self.connection.server.clients():
                if client.machineIdentifier == client_id:
                    return client

        try:
            for resource in self.connection.server.myPlexAccount().resources():
                if resource.clientIdentifier == client_id:
                    return resource.connect()
        except Exception as error:
            logger.warning("Failed to connect to cloud client %s: %s", client_id, error)

        return None

    def _active_queue_id(self, client: Any, client_id: str) -> int | None:
        """The id of the music queue the player is running, if any.

        Raises:
            PlaybackError: When the player will not report its timelines
        """
        try:
            timelines = client.timelines()
        except Exception as error:
            logger.warning("Failed to get timelines from client %s: %s", client_id, error)
            raise PlaybackError("Could not read active queue from client") from error

        for entry in timelines:
            if entry.type == "music" and getattr(entry, "playQueueID", None):
                return entry.playQueueID
        return None

    def _start_queue(self, client: Any, items: list[Any]) -> int:
        """Replace whatever the player is doing with a new queue."""
        queue = PlayQueue.create(
            self.connection.server, items=items, startItem=items[0], includeRelated=0
        )
        client.playMedia(queue)
        return len(items)

    def _queue_next(self, client: Any, client_id: str, items: list[Any]) -> int:
        """Insert tracks after the currently playing one, keeping their order.

        Each insert goes to the front, so the list is added in reverse. Only the
        last one refreshes the client, which is what makes the queue reappear.

        Raises:
            PlaybackError: When the player has no queue to insert into, or none of
                the tracks could be added
        """
        queue_id = self._active_queue_id(client, client_id)
        if not queue_id:
            raise PlaybackError("No active play queue on this client")

        queue = PlayQueue.get(self.connection.server, queue_id, own=True)
        reversed_items = list(reversed(items))

        queued = 0
        for index, item in enumerate(reversed_items):
            try:
                queue.addItem(item, playNext=True, refresh=index == len(reversed_items) - 1)
                queued += 1
            except Exception:
                logger.warning("Failed to add track %s to queue", item.ratingKey)

        if not queued:
            raise PlaybackError("Could not add any tracks to the active queue")
        return queued
