"""Fixtures for the library package: a fake Plex server and seeded tracks."""

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, Self

import pytest

from backend.db import db
from backend.library.models import AlbumMetadata, AlbumProgress
from backend.library.tables import Track, TrackGenre


def plex_track(
    rating_key: str,
    title: str = "Song",
    *,
    artist: str = "Artist",
    album: str = "Album",
    parent_key: str = "100",
    view_count: int = 0,
    last_viewed: datetime | None = None,
) -> SimpleNamespace:
    """A stand-in for a plexapi track, carrying only what the sync reads."""
    return SimpleNamespace(
        ratingKey=rating_key,
        title=title,
        grandparentTitle=artist,
        parentTitle=album,
        parentRatingKey=parent_key,
        duration=180000,
        userRating=None,
        viewCount=view_count,
        lastViewedAt=last_viewed,
    )


class FakePlexClient:
    """The slice of PlexClient that `LibrarySync` depends on.

    Paging is derived from `tracks`, so a subclass only has to say which tracks
    exist and how their albums are described.

    The sync reaches Plex as `client.connection` and `client.library`; the fake
    stands in for all three, so both point back at itself.
    """

    server_id: str | None = "test-server"

    def __init__(
        self,
        tracks: list[SimpleNamespace] | None = None,
        albums: dict[str, AlbumMetadata] | None = None,
    ) -> None:
        self.tracks = tracks if tracks is not None else [plex_track("1")]
        self.albums = (
            albums if albums is not None else {"100": AlbumMetadata(genres=["Rock"], year=1994)}
        )
        self.starts: list[int] = []

    @property
    def connection(self) -> Self:
        return self

    @property
    def library(self) -> Self:
        return self

    def machine_identifier(self) -> str | None:
        return self.server_id

    def total_tracks(self) -> int:
        return len(self.tracks)

    def total_albums(self) -> int:
        return len(self.albums)

    def album_metadata(self, on_progress: AlbumProgress | None = None) -> dict[str, AlbumMetadata]:
        """Report both stages as complete in one step, then answer."""
        if on_progress:
            on_progress("albums", len(self.albums), len(self.albums))
            on_progress("genres", 1, 1)
        return self.albums

    def iter_raw_tracks(self, start: int = 0, page_size: int = 1000):
        self.starts.append(start)
        remaining = self.tracks[start:]
        for offset in range(0, len(remaining), page_size):
            yield remaining[offset : offset + page_size]


@pytest.fixture
def seed_tracks(temp_db):
    """Write tracks and their genre rows the way the sync would."""

    def write(*rows: dict[str, Any]) -> None:
        with db.session() as session:
            for row in rows:
                session.add(Track(**row))
                # From the row, not the instance: column defaults land on insert.
                for entry in TrackGenre.rows_for(row["rating_key"], row.get("genres") or []):
                    session.add(TrackGenre(**entry))

    return write


@pytest.fixture
def sample_library(seed_tracks):
    """Two albums: a 1994 rock one with a live track, and a 2003 jazz one."""
    seed_tracks(
        {
            "rating_key": "1",
            "title": "Song One",
            "artist": "Artist A",
            "album": "Album X",
            "year": 1994,
            "genres": ["Rock"],
            "parent_rating_key": "100",
            "view_count": 5,
            "user_rating": 8,
            "last_viewed_at": datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
        },
        {
            "rating_key": "2",
            "title": "Song Two",
            "artist": "Artist A",
            "album": "Album X",
            "year": 1994,
            "genres": ["Rock", "rock"],
            "parent_rating_key": "100",
            "view_count": 1,
        },
        {
            "rating_key": "3",
            "title": "Song Three (Live)",
            "artist": "Artist A",
            "album": "Album X",
            "year": 1994,
            "genres": ["Rock"],
            "parent_rating_key": "100",
            "is_live": True,
        },
        {
            "rating_key": "4",
            "title": "Song Four",
            "artist": "Artist B",
            "album": "Album Y",
            "year": 2003,
            "genres": ["Jazz"],
            "parent_rating_key": "200",
            "user_rating": 4,
        },
    )
