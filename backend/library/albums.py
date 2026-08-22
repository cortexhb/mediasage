"""Album-level views aggregated from cached tracks.

Plex albums are not mirrored as rows; they are derived by grouping tracks on
`parent_rating_key`. Entry points: `candidates` and `familiarity`.
"""

from sqlalchemy import func
from sqlmodel import select

from backend.config.store import config_store
from backend.db import db
from backend.library.filters import TrackFilter, has_album_key
from backend.library.models import AlbumCandidate, AlbumFamiliarity
from backend.library.tables import Track


def candidates(track_filter: TrackFilter) -> list[AlbumCandidate]:
    """Albums whose tracks survive a filter, assembled from those tracks.

    Genres are unioned across an album's tracks, matched case-insensitively so
    "Rock" and "rock" collapse; the first spelling Plex reported wins.

    Args:
        track_filter: Decade and live-version predicates; genres select which
            albums qualify rather than which tracks are kept

    Returns:
        One candidate per album, in no particular order
    """
    clauses = [has_album_key(), *track_filter.clauses(include_genres=False)]
    album_keys = track_filter.album_key_clause()
    if album_keys is not None:
        clauses.append(album_keys)

    statement = (
        select(
            Track.rating_key,
            Track.artist,
            Track.album,
            Track.year,
            Track.genres,
            Track.parent_rating_key,
        )
        .where(*clauses)
        .order_by(Track.parent_rating_key, Track.rating_key)
    )

    albums: dict[str, AlbumCandidate] = {}
    seen_genres: dict[str, set[str]] = {}

    with db.session() as session:
        for rating_key, artist, album, year, genres, parent_key in session.exec(statement):
            candidate = albums.get(parent_key)
            if candidate is None:
                candidate = AlbumCandidate(
                    parent_rating_key=parent_key,
                    album=album,
                    # `artist` holds the album artist, not the track artist.
                    album_artist=artist,
                    year=year,
                    decade=f"{year // 10 * 10}s" if year else "",
                )
                albums[parent_key] = candidate
                seen_genres[parent_key] = set()

            candidate.track_count += 1
            candidate.track_rating_keys.append(rating_key)
            for genre in genres or []:
                if genre.lower() not in seen_genres[parent_key]:
                    seen_genres[parent_key].add(genre.lower())
                    candidate.genres.append(genre)

    return list(albums.values())


def familiarity(parent_rating_keys: list[str] | None = None) -> dict[str, AlbumFamiliarity]:
    """How much of each album the user has played, from cached play counts.

    Args:
        parent_rating_keys: Albums to report on; None covers every album

    Returns:
        Album key mapped to its familiarity
    """
    statement = (
        select(
            Track.parent_rating_key,
            func.sum(Track.view_count),
            func.avg(Track.view_count),
            func.max(Track.last_viewed_at),
        )
        .where(has_album_key())
        .group_by(Track.parent_rating_key)
    )
    if parent_rating_keys is not None:
        statement = statement.where(Track.parent_rating_key.in_(parent_rating_keys))

    threshold = config_store.get().library.well_loved_avg_plays
    with db.session() as session:
        return {
            key: AlbumFamiliarity.of(
                int(total or 0), float(average or 0), last_viewed, threshold
            )
            for key, total, average, last_viewed in session.exec(statement)
        }
