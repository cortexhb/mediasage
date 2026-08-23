"""What the research APIs answer, typed.

Every lookup used to hand back a bare `dict`, so a caller reading the wrong
key got `None` and no error. These parse one JSON payload each: the `.get()`
chains live in `of()` and nowhere else, and a shape change upstream breaks in
one place rather than at whichever field is read first.
"""

from typing import Any, Final, Self

from pydantic import BaseModel, ConfigDict

from backend.config import ResearchConfig

# Sorted lexically, so a release with no date has to sort last.
NO_DATE: Final = "9999"

# --- release-group search scoring ---------------------------------------
# Weights, not thresholds: the highest total wins, so only their order and
# their gaps matter. Artist and year outweigh everything because a wrong
# artist or a wrong decade is a different album, not a worse match.

# The artist credit names the artist we asked for.
ARTIST_MATCH: Final = 60

# The first release year is the one we asked for.
YEAR_MATCH: Final = 40

# The title matches exactly, then by prefix, then anywhere.
TITLE_EXACT: Final = 50
TITLE_PREFIX: Final = 30
TITLE_CONTAINS: Final = 10

# An album rather than a compilation, live record or EP.
TYPE_ALBUM: Final = 20

# MusicBrainz reports its own 0-100 relevance. Divided down to 0-10 so it only
# breaks ties between candidates our own signals scored the same.
MB_SCORE_DIVISOR: Final = 10

# Shortest credit that may match by containment. Below this, "Air" is inside
# far too many names to mean anything.
MIN_CONTAINMENT: Final = 3


class ReleaseGroupMatch(BaseModel):
    """One candidate from a release-group search, and how well it fits."""

    model_config = ConfigDict(frozen=True)

    mbid: str
    title: str = ""
    primary_type: str = ""
    first_release_date: str = ""
    artist_credits: list[str] = []
    relevance: float = 0.0

    @classmethod
    def of(cls, payload: dict[str, Any]) -> Self:
        """Read one entry of a search response."""
        return cls(
            mbid=str(payload.get("id", "")),
            title=str(payload.get("title", "") or ""),
            primary_type=str(payload.get("primary-type", "") or ""),
            first_release_date=str(payload.get("first-release-date", "") or ""),
            artist_credits=[
                str(credit.get("name", "") or "")
                for credit in payload.get("artist-credit", [])
                if isinstance(credit, dict)
            ],
            relevance=float(payload.get("score", 0) or 0),
        )

    def score(self, album: str, year: int | None, artist: str | None) -> float:
        """How well this candidate answers the query it came back for."""
        return (
            self._artist_score(artist)
            + self._title_score(album)
            + (TYPE_ALBUM if self.primary_type == "Album" else 0)
            + self._year_score(year)
            + self.relevance / MB_SCORE_DIVISOR
        )

    def _artist_score(self, artist: str | None) -> int:
        """Whether any credit names the artist, exactly or by containment.

        Containment catches "Sigur Rós" against "Sigur Rós & Steindór", which
        MusicBrainz credits separately.
        """
        if not artist:
            return 0
        wanted = artist.lower()
        for credit in self.artist_credits:
            named = credit.lower()
            if wanted == named:
                return ARTIST_MATCH
            if len(named) >= MIN_CONTAINMENT and (wanted in named or named in wanted):
                return ARTIST_MATCH
        return 0

    def _title_score(self, album: str) -> int:
        """Exact beats prefix beats anywhere; nothing else counts."""
        title = self.title.lower()
        wanted = album.lower()
        if title == wanted:
            return TITLE_EXACT
        if title.startswith(wanted):
            return TITLE_PREFIX
        return TITLE_CONTAINS if wanted in title else 0

    def _year_score(self, year: int | None) -> int:
        return YEAR_MATCH if year and self.first_release_date.startswith(str(year)) else 0


class ReleaseGroup(BaseModel):
    """One release group: where to read more about it, and its first release.

    The URLs come from MusicBrainz relations, which is why the review fetcher
    trusts them enough to follow: they are curated, not user input.
    """

    model_config = ConfigDict(frozen=True)

    wikipedia_url: str = ""
    wikidata_url: str = ""
    discogs_url: str = ""
    review_urls: list[str] = []
    earliest_release_mbid: str = ""
    release_date: str = ""

    @classmethod
    def of(cls, payload: dict[str, Any], config: ResearchConfig) -> Self:
        """Read a release-group lookup, relations and releases included.

        Args:
            payload: One `release-group` lookup with `url-rels` and `releases`
            config: Supplies which review hosts to drop and how many to keep
        """
        urls: dict[str, str] = {}
        reviews: list[str] = []

        for relation in payload.get("relations", []):
            kind = relation.get("type", "")
            url = str(relation.get("url", {}).get("resource", "") or "")
            if not url:
                continue
            if kind in ("wikipedia", "wikidata", "discogs"):
                urls[kind] = url
            elif kind == "review" and not any(host in url for host in config.blocked_review_hosts):
                reviews.append(url)

        # Earliest release: it carries the original track listing and label,
        # where a later one carries a reissue's bonus tracks.
        earliest = min(
            payload.get("releases", []),
            key=lambda release: release.get("date") or NO_DATE,
            default={},
        )

        return cls(
            wikipedia_url=urls.get("wikipedia", ""),
            wikidata_url=urls.get("wikidata", ""),
            discogs_url=urls.get("discogs", ""),
            review_urls=reviews[: config.max_reviews],
            earliest_release_mbid=str(earliest.get("id", "") or ""),
            release_date=str(earliest.get("date", "") or ""),
        )


class ReleaseDetail(BaseModel):
    """One release: what is on it, who put it out, and who made it."""

    model_config = ConfigDict(frozen=True)

    track_listing: list[str] = []
    label: str = ""
    credits: dict[str, str] = {}

    @classmethod
    def of(cls, payload: dict[str, Any]) -> Self:
        """Read a release lookup with recordings, labels and credits."""
        tracks = [
            str(track.get("title", "") or "")
            for medium in payload.get("media", [])
            for track in medium.get("tracks", [])
            if track.get("title")
        ]

        labels = payload.get("label-info", [])
        label = labels[0].get("label", {}).get("name", "") if labels else ""

        credits = {}
        for credit in payload.get("artist-credit", []):
            name = credit.get("artist", {}).get("name")
            if name:
                credits["Primary Artist"] = name
                break

        return cls(track_listing=tracks, label=str(label or ""), credits=credits)
