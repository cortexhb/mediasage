"""Connecting to a Plex server, and surviving its bad days.

Owns the server handle, the reconnect cooldown, and the retry loop every bulk
fetch runs through. Entry points: `PlexConnection`, `with_retries`.

A large sync is the hardest thing this app asks of a Plex server, and an
overloaded server fails with a transient error rather than a clean one. Those
are retried; an authentication or lookup failure is not.
"""

import os
import threading
import time
from collections.abc import Callable
from typing import Any, Final

# autoreload=true refetches each object when an attribute is absent from the
# listing; Plex omits userRating/viewCount on unrated items, so a 30k sync
# becomes 30k requests. getattr(obj, x, default) does not avoid it -- plexapi
# sets missing attributes to None, so no AttributeError is ever raised.
# Must be set before plexapi is imported; setdefault lets user env win.
os.environ.setdefault("PLEXAPI_PLEXAPI_AUTORELOAD", "false")
os.environ.setdefault("PLEXAPI_PLEXAPI_CONTAINER_SIZE", "1000")

import logging

from plexapi.exceptions import NotFound, Unauthorized
from plexapi.server import PlexServer
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr
from requests.exceptions import ConnectionError, Timeout

from backend.config import PlexConfig
from backend.config.store import config_store
from backend.plex.models import FetchedItems

logger = logging.getLogger(__name__)

# Substrings marking a Plex failure as transient rather than permanent.
TRANSIENT_MARKERS: Final = (
    "overload",
    "timed out",
    "timeout",
    "503",
    "502",
    "504",
    "connection",
    "temporarily",
)


class PlexFetchError(Exception):
    """A Plex bulk fetch failed after exhausting retries."""


class PlexQueryError(Exception):
    """A Plex library query failed."""


def settings() -> PlexConfig:
    """The configured Plex timings, read at call time."""
    return config_store.get().plex


def is_transient(error: Exception) -> bool:
    """Whether a Plex error is worth retrying."""
    if isinstance(error, ConnectionError | Timeout):
        return True
    if isinstance(error, Unauthorized | NotFound):
        return False
    return any(marker in str(error).lower() for marker in TRANSIENT_MARKERS)


def with_retries(label: str, fetch: Callable[[], Any]) -> Any:
    """Run a Plex fetch, backing off on transient failures.

    Args:
        label: Description of the fetch, used in log messages
        fetch: Zero-argument callable performing the request

    Returns:
        Whatever `fetch` returns

    Raises:
        PlexFetchError: On permanent failure, or once retries are exhausted
    """
    last: Exception | None = None
    for attempt, delay in enumerate((*settings().retry_backoff, None)):
        try:
            return fetch()
        except Exception as error:
            last = error
            if delay is None or not is_transient(error):
                break
            logger.warning(
                "Plex fetch %s failed (attempt %d), retrying in %.0fs: %s",
                label, attempt + 1, delay, error,
            )
            time.sleep(delay)

    raise PlexFetchError(f"Plex fetch {label} failed: {last}") from last


class PlexConnection(BaseModel):
    """A Plex server and one of its music libraries.

    Holds both handles because they fail independently: a wrong library name
    leaves the server reachable, which is what lets the setup wizard list the
    libraries that do exist.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    url: str
    token: str
    music_library: str = "Music"

    # Defaulted rather than required so a test can build one without a config.
    connect_timeout: float = Field(default=30.0, gt=0)
    reconnect_cooldown: float = Field(default=30.0, ge=0)

    _server: Any = PrivateAttr(default=None)
    _library: Any = PrivateAttr(default=None)
    _error: str | None = PrivateAttr(default=None)
    _last_attempt: float = PrivateAttr(default=0.0)
    _lock: threading.Lock = PrivateAttr(default_factory=threading.Lock)

    def model_post_init(self, context: object, /) -> None:
        """Connect eagerly, so a bad configuration is visible immediately."""
        self._last_attempt = time.time()
        self.connect()

    def connect(self) -> None:
        """Open the server and library handles, recording why if it fails."""
        if not self.url or not self.token:
            self._error = "Plex URL and token are required"
            return

        try:
            self._server = PlexServer(self.url, self.token, timeout=self.connect_timeout)
            self._library = self._server.library.section(self.music_library)
            self._error = None
        except Unauthorized:
            self._fail("Invalid Plex token - unauthorized")
        except NotFound:
            # The server answered; only the library name was wrong.
            self._library = None
            self._error = f"Music library '{self.music_library}' not found"
        except ConnectionError:
            self._fail(f"Cannot connect to Plex server at {self.url}")
        except Timeout:
            self._fail("Connection to Plex server timed out")
        except Exception as error:
            self._fail(f"Plex connection error: {error!s}")

    def _fail(self, message: str) -> None:
        """Drop both handles and record why."""
        self._server = None
        self._library = None
        self._error = message

    def is_connected(self) -> bool:
        """Whether both handles are live, reconnecting at most once a cooldown."""
        if self._server is not None and self._library is not None:
            return True

        now = time.time()
        with self._lock:
            if self._server is not None and self._library is not None:
                return True
            if now - self._last_attempt >= self.reconnect_cooldown:
                self._last_attempt = now
                logger.info("Attempting to reconnect to Plex server...")
                self.connect()

        return self._server is not None and self._library is not None

    @property
    def server(self) -> Any:
        """The server handle, or None when unreachable."""
        return self._server

    @property
    def library(self) -> Any:
        """The music library section, or None when it could not be opened."""
        return self._library

    @property
    def error(self) -> str | None:
        """Why the last connection attempt failed, if it did."""
        return self._error

    @property
    def server_name(self) -> str | None:
        """The server's friendly name, for confirming the right one is configured."""
        return getattr(self._server, "friendlyName", None)

    def machine_identifier(self) -> str | None:
        """The server's stable id, used to notice the library was swapped."""
        if not self._server:
            return None
        return self._server.machineIdentifier

    def music_libraries(self) -> list[str]:
        """Every music library on the server, whichever one is configured."""
        if not self._server:
            return []
        try:
            return [s.title for s in self._server.library.sections() if s.type == "artist"]
        except Exception:
            logger.warning("Could not list Plex library sections", exc_info=True)
            return []

    def fetch_items(self, rating_keys: list[str]) -> FetchedItems:
        """Resolve rating keys to Plex objects, collecting the ones that fail.

        A key that no longer resolves is not fatal: the caller acts on what it
        got and reports the rest.
        """
        fetched = FetchedItems()
        for key in rating_keys:
            try:
                fetched.items.append(self._server.fetchItem(int(key)))
            except Exception as error:
                logger.warning("Failed to fetch track %s: %s", key, error)
                fetched.skipped.append(key)
        return fetched

    def playlist_url(self, rating_key: int) -> str | None:
        """The Plex web app URL for a playlist on this server."""
        machine_id = self.machine_identifier()
        if not machine_id:
            return None
        return (
            f"{self.url}/web/index.html#!/server/{machine_id}"
            f"/playlist?key=%2Fplaylists%2F{rating_key}"
        )
