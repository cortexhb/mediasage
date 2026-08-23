"""Reads over the cached `tracks` table.

Every query here is built from SQLAlchemy expressions, so the same code runs on
SQLite and Postgres. Filtering is expressed by `TrackFilter`; `TrackCache` only
decides what to select and how to shape the result. `track_cache` is the
instance the application reads through.
"""

from pydantic import BaseModel
from sqlalchemy import func, select

from backend.db import db
from backend.library.filters import TrackFilter
from backend.library.models import DecadeCount, GenreCount, LibraryStats, TrackRecord
from backend.library.tables import Track, TrackGenre


class TrackCache(BaseModel):
    """Every read the application makes against the cached tracks."""

    def all(self) -> list[TrackRecord]:
        """Every cached track."""
        with db.session() as session:
            return [TrackRecord.of(row) for row in session.scalars(select(Track))]

    def filtered(self, track_filter: TrackFilter, limit: int = 0) -> list[TrackRecord]:
        """Cached tracks matching a filter.

        Args:
            track_filter: Genre, decade, rating and live-version predicates
            limit: Random sample size; 0 returns every match

        Returns:
            Matching tracks, sampled in SQL when limited
        """
        statement = select(Track).where(*track_filter.clauses())
        if limit > 0:
            # Sampling in SQL, so a genre filter no longer skips the limit.
            statement = statement.order_by(func.random()).limit(limit)

        with db.session() as session:
            return [TrackRecord.of(row) for row in session.scalars(statement)]

    def count(self, track_filter: TrackFilter) -> int:
        """How many cached tracks match a filter."""
        statement = select(func.count()).select_from(Track).where(*track_filter.clauses())
        with db.session() as session:
            return session.execute(statement).scalar_one()

    def genre_decade_stats(self) -> LibraryStats:
        """Genre and decade breakdowns of the cache, avoiding a Plex round-trip.

        Genres come from the normalized index rather than the JSON column, so
        this is a grouped index scan.
        """
        genre_query = (
            select(TrackGenre.genre, func.count().label("n"))
            .group_by(TrackGenre.genre)
            .order_by(TrackGenre.genre)
        )

        # Floor division: SQLAlchemy's `/` casts to numeric, giving 1994 not 1990.
        decade_start = (Track.year // 10 * 10).label("decade_start")
        decade_query = (
            select(decade_start, func.count().label("n"))
            .where(Track.year.is_not(None), Track.year != 0)
            .group_by(decade_start)
            .order_by(decade_start)
        )

        with db.session() as session:
            genres = [GenreCount(name=name, count=n) for name, n in session.execute(genre_query)]
            decades = [
                DecadeCount(name=f"{int(start)}s", count=n)
                for start, n in session.execute(decade_query)
            ]

        return LibraryStats(genres=genres, decades=decades)


track_cache = TrackCache()
