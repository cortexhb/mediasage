"""Creating, listing and updating Plex playlists.

`PlexPlaylists` holds the connection and makes every write. Each one resolves
rating keys first and acts on what resolved; a key Plex has since dropped costs
one track, not the operation. Entry points: `create`, `listing`, `update`.

Ordering matters on replace: new tracks are added before old ones are removed,
so a failure leaves duplicates rather than an empty playlist.
"""

import logging
import threading
from typing import Any, Final

from pydantic import BaseModel, ConfigDict

from backend.plex.connection import PlexConnection
from backend.plex.models import PlaylistResult, PlaylistUpdateResult, PlexPlaylistInfo

logger = logging.getLogger(__name__)

# Playlist id standing for "the scratch playlist", created on first use.
SCRATCH_SENTINEL: Final = "__scratch__"
SCRATCH_TITLE: Final = "MediaSage - Now Playing"

# Guards find-or-create of the scratch playlist; two requests would otherwise
# each create one.
_scratch_lock = threading.Lock()

# The update modes `update` accepts.
UPDATE_MODES: Final = ("replace", "append")


class PlexPlaylists(BaseModel):
    """Every playlist write the application makes against one Plex server."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    connection: PlexConnection

    @staticmethod
    def _describe(playlist: Any, description: str) -> None:
        """Set a playlist's summary; a failure here does not fail the write."""
        if not description:
            return
        try:
            playlist.edit(summary=description)
        except Exception as error:
            logger.warning("Failed to set playlist description: %s", error)

    def create(self, name: str, rating_keys: list[str], description: str = "") -> PlaylistResult:
        """Create a playlist from rating keys.

        Args:
            name: Playlist title
            rating_keys: Tracks to add, in order
            description: Playlist summary; skipped when empty

        Returns:
            The outcome, including how many keys did not resolve
        """
        if not self.connection.server:
            return PlaylistResult(success=False, error="Not connected to Plex")

        try:
            fetched = self.connection.fetch_items(rating_keys)
            if fetched.skipped:
                logger.info(
                    "Playlist '%s': skipped %d of %d tracks",
                    name,
                    fetched.skipped_count,
                    len(rating_keys),
                )
            if not fetched:
                return PlaylistResult(success=False, error="No valid tracks found")

            playlist = self.connection.server.createPlaylist(name, items=fetched.items)
            self._describe(playlist, description)

            return PlaylistResult(
                success=True,
                playlist_id=str(playlist.ratingKey),
                playlist_url=self.connection.playlist_url(playlist.ratingKey),
                tracks_added=len(fetched.items),
                tracks_skipped=fetched.skipped_count,
            )
        except Exception as error:
            logger.exception("Failed to create playlist '%s'", name)
            return PlaylistResult(success=False, error=str(error))

    def listing(self) -> list[PlexPlaylistInfo]:
        """Audio playlists the user can be offered, alphabetically.

        Smart and radio playlists are excluded: their contents are a query, so
        adding tracks to one would not stick.
        """
        if not self.connection.server:
            return []

        try:
            playlists = self.connection.server.playlists(playlistType="audio")
        except Exception:
            logger.exception("Failed to get playlists")
            return []

        return sorted(
            (
                PlexPlaylistInfo(
                    rating_key=str(playlist.ratingKey),
                    title=playlist.title,
                    track_count=playlist.leafCount,
                )
                for playlist in playlists
                if not playlist.smart and not playlist.radio
            ),
            key=lambda playlist: playlist.title.lower(),
        )

    def update(
        self,
        playlist_id: str,
        rating_keys: list[str],
        mode: str = "replace",
        description: str = "",
    ) -> PlaylistUpdateResult:
        """Replace or append to a playlist, creating the scratch one on demand.

        Args:
            playlist_id: Target playlist's rating key, or `SCRATCH_SENTINEL`
            rating_keys: Tracks to add
            mode: "replace" or "append"
            description: Playlist summary; skipped when empty

        Returns:
            The outcome, including duplicates and unresolvable keys
        """
        if not self.connection.server:
            return PlaylistUpdateResult(success=False, error="Not connected to Plex")
        if mode not in UPDATE_MODES:
            return PlaylistUpdateResult(success=False, error=f"Unknown update mode: {mode}")

        try:
            if playlist_id == SCRATCH_SENTINEL:
                with _scratch_lock:
                    scratch = self._find_scratch()
                    if scratch is None:
                        return self._create_scratch(rating_keys, description)
                    playlist_id = str(scratch.ratingKey)

            playlist = self.connection.server.fetchItem(int(playlist_id))
            if mode == "replace":
                result = self._replace(playlist, rating_keys)
            else:
                result = self._append(playlist, rating_keys)

            if result.success:
                self._describe(playlist, description)
                result.playlist_url = self.connection.playlist_url(playlist.ratingKey)
            return result
        except Exception as error:
            logger.exception("Failed to update playlist '%s'", playlist_id)
            return PlaylistUpdateResult(success=False, error=str(error))

    def _replace(self, playlist: Any, rating_keys: list[str]) -> PlaylistUpdateResult:
        """Swap a playlist's contents, adding before removing.

        Add-then-remove is deliberate: if the add fails the old tracks are still
        there, and if the remove fails the user has duplicates rather than an empty
        playlist. Only the second case is recoverable by hand.
        """
        fetched = self.connection.fetch_items(rating_keys)
        if not fetched:
            return PlaylistUpdateResult(
                success=False,
                error="No valid tracks found to replace with",
                tracks_skipped=fetched.skipped_count,
            )

        existing = playlist.items()
        playlist.addItems(fetched.items)

        warning = None
        if existing:
            try:
                playlist.removeItems(existing)
            except Exception as error:
                logger.warning("Failed to remove old items during replace: %s", error)
                warning = (
                    "Replaced tracks were added but old tracks could not be removed. "
                    "Playlist may contain duplicates."
                )

        return PlaylistUpdateResult(
            success=True,
            tracks_added=len(fetched.items),
            tracks_skipped=fetched.skipped_count,
            warning=warning,
        )

    def _append(self, playlist: Any, rating_keys: list[str]) -> PlaylistUpdateResult:
        """Add tracks the playlist does not already hold."""
        present = {str(item.ratingKey) for item in playlist.items()}
        wanted = [key for key in rating_keys if key not in present]

        fetched = self.connection.fetch_items(wanted)
        if fetched:
            playlist.addItems(fetched.items)

        return PlaylistUpdateResult(
            success=True,
            tracks_added=len(fetched.items),
            tracks_skipped=fetched.skipped_count,
            duplicates_skipped=len(rating_keys) - len(wanted),
        )

    def _find_scratch(self) -> Any | None:
        """The scratch playlist, or None when it has not been created yet."""
        try:
            for playlist in self.connection.server.playlists(playlistType="audio"):
                if playlist.title == SCRATCH_TITLE:
                    return playlist
        except Exception as error:
            logger.warning("Failed to search for scratch playlist: %s", error)
        return None

    def _create_scratch(self, rating_keys: list[str], description: str) -> PlaylistUpdateResult:
        """Create the scratch playlist around its first set of tracks."""
        result = self.create(SCRATCH_TITLE, rating_keys, description)
        return PlaylistUpdateResult(
            success=result.success,
            tracks_added=result.tracks_added,
            tracks_skipped=result.tracks_skipped,
            playlist_url=result.playlist_url,
            error=result.error,
        )
