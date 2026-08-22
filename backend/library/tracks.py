"""Reads over the cached `tracks` table.

Every query here is built from SQLAlchemy expressions, so the same code runs on
SQLite and Postgres. Filtering is expressed by `TrackFilter`; this module only
decides what to select and how to shape the result.
"""

from sqlalchemy import func
from sqlmodel import select

from backend.db import db
from backend.library.filters import TrackFilter
from backend.library.models import DecadeCount, GenreCount, LibraryStats, TrackRecord
from backend.library.tables import Track, TrackGenre


def all_tracks() -> list[TrackRecord]:
    """Every cached track."""
    with db.session() as session:
        return [TrackRecord.of(row) for row in session.exec(select(Track)).all()]


def filtered(track_filter: TrackFilter, limit: int = 0) -> list[TrackRecord]:
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
        return [TrackRecord.of(row) for row in session.exec(statement).all()]


def count(track_filter: TrackFilter) -> int:
    """How many cached tracks match a filter."""
    statement = select(func.count()).select_from(Track).where(*track_filter.clauses())
    with db.session() as session:
        return session.exec(statement).one()


def genre_decade_stats() -> LibraryStats:
    """Genre and decade breakdowns of the cache, avoiding a Plex round-trip.

    Genres come from the normalized index rather than the JSON column, so this
    is a grouped index scan.
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
        genres = [
            GenreCount(name=name, count=n) for name, n in session.exec(genre_query).all()
        ]
        decades = [
            DecadeCount(name=f"{int(start)}s", count=n)
            for start, n in session.exec(decade_query).all()
        ]

    return LibraryStats(genres=genres, decades=decades)
