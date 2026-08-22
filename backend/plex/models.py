"""Models for everything the Plex server hands back.

The API returns most of these unchanged: a Plex operation's result is what the
route reports, so there is no second shape to keep in step. `backend.models`
keeps the request models, which validate HTTP input rather than describe Plex.
"""

from typing import Any

from pydantic import BaseModel, Field


class PlexPlaylistInfo(BaseModel):
    """A playlist as the picker lists it."""

    rating_key: str
    title: str
    track_count: int


class PlexClientInfo(BaseModel):
    """A player that can be sent a queue."""

    client_id: str
    name: str
    product: str
    platform: str
    is_playing: bool = False
    # Mobile and TV players only accept a queue while already playing.
    is_mobile: bool = False


class PlaylistResult(BaseModel):
    """Outcome of creating a playlist.

    `tracks_skipped` counts keys Plex could not resolve; a playlist is still
    created from whatever did resolve.
    """

    success: bool
    playlist_id: str | None = None
    playlist_url: str | None = None
    tracks_added: int = 0
    tracks_skipped: int = 0
    error: str | None = None


class PlaylistUpdateResult(BaseModel):
    """Outcome of replacing or appending to a playlist.

    `warning` carries a partial success: on replace, new tracks were added but
    the old ones could not be removed, so the playlist holds duplicates.
    """

    success: bool
    tracks_added: int = 0
    tracks_skipped: int = 0
    duplicates_skipped: int = 0
    playlist_url: str | None = None
    warning: str | None = None
    error: str | None = None


class PlayQueueResult(BaseModel):
    """Outcome of starting playback on a client.

    `error_code` distinguishes an unreachable device, which the API reports as
    404, from a failure of the queue itself.
    """

    success: bool
    client_name: str | None = None
    client_product: str | None = None
    tracks_queued: int = 0
    tracks_skipped: int = 0
    error: str | None = None
    error_code: str | None = None


class FetchedItems(BaseModel):
    """Plex objects resolved from rating keys, and the keys that failed.

    Every write path resolves keys before acting, and every one of them has to
    report how many it lost.
    """

    model_config = {"arbitrary_types_allowed": True}

    items: list[Any] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped)

    def __bool__(self) -> bool:
        """True when anything resolved, so callers can guard on the result."""
        return bool(self.items)
