"""MusicBrainz: finding an album, then reading what it knows about it.

Three searches, tried cheapest first, because Plex album titles rarely match
MusicBrainz exactly. Every call is rate-limited; see `http.Throttle`.

Entry point: `MusicBrainz`.
"""

import logging
import re
from typing import Any, Final

import httpx

from backend.config import ResearchConfig
from backend.research.http import SharedHttp, Throttle
from backend.research.models import ReleaseDetail, ReleaseGroup, ReleaseGroupMatch

logger = logging.getLogger(__name__)

# Candidates a strict search returns. It either matches or it does not; more
# would only be worse matches.
STRICT_LIMIT: Final = 5

# Candidates the album-only search returns. This one is scored, so it wants a
# field to choose from.
FALLBACK_LIMIT: Final = 10

# Edition markers Plex carries in an album title and MusicBrainz does not.
# Stripped only from the end, where an edition suffix goes -- "Deluxe" inside
# a real title is part of the title.
EDITION_SUFFIX: Final = re.compile(
    r"\s*\("
    r"(?:Explicit|Clean|Deluxe|Special|Expanded|Anniversary|Limited|"
    r"Bonus Track|Collector(?:'s)?|International|Standard|Super Deluxe|"
    r"Premium|Platinum|Ultimate|Complete|Original|Extended)"
    r"[^)]*\)\s*$",
    re.IGNORECASE,
)


def without_edition(album: str) -> str | None:
    """The album title with its edition suffix removed, or None if it had none."""
    stripped = EDITION_SUFFIX.sub("", album).strip()
    return stripped if stripped and stripped != album else None


class MusicBrainz:
    """Every MusicBrainz call, over one shared client and one rate limit."""

    def __init__(self, http: SharedHttp, throttle: Throttle, config: ResearchConfig) -> None:
        self.http = http
        self.throttle = throttle
        self.config = config

    async def search(self, artist: str, album: str, year: int | None = None) -> str | None:
        """The release-group MBID for an album, or None when nothing matches.

        Three strategies, each tried only when the last found nothing:

        1. Artist and full title. Right whenever Plex's metadata is clean.
        2. Artist and title without its edition suffix, for "(Deluxe Edition)".
        3. Title alone, scored. Catches a soundtrack or cast recording, which
           Plex files under a performer and MusicBrainz under the composer.
        """
        exact = await self._first(f'artist:"{artist}" AND releasegroup:"{album}"', STRICT_LIMIT)
        if exact:
            return exact

        stripped = without_edition(album)
        if stripped:
            logger.info("Trying album name without its edition: %s -> %s", album, stripped)
            exact = await self._first(
                f'artist:"{artist}" AND releasegroup:"{stripped}"', STRICT_LIMIT
            )
            if exact:
                return exact

        wanted = stripped or album
        logger.info("No strict match for %s - %s, searching by album alone", artist, album)
        return await self._best(wanted, year, artist)

    async def release_group(self, mbid: str) -> ReleaseGroup | None:
        """Where to read about a release group, and its earliest release."""
        payload = await self._get(
            f"release-group/{mbid}", {"inc": "url-rels+releases", "fmt": "json"}
        )
        return ReleaseGroup.of(payload, self.config) if payload is not None else None

    async def release(self, mbid: str) -> ReleaseDetail | None:
        """One release's track listing, label and credits."""
        payload = await self._get(
            f"release/{mbid}", {"inc": "recordings+labels+artist-credits", "fmt": "json"}
        )
        return ReleaseDetail.of(payload) if payload is not None else None

    # -- searching -------------------------------------------------------

    async def _first(self, query: str, limit: int) -> str | None:
        """The top hit for a query, or None when there is none."""
        matches = await self._search(query, limit)
        return matches[0].mbid if matches else None

    async def _best(self, album: str, year: int | None, artist: str) -> str | None:
        """The best-scoring candidate for an album-only search."""
        candidates = await self._search(f'releasegroup:"{album}"', FALLBACK_LIMIT)
        if not candidates:
            logger.info("No MusicBrainz match for %s - %s", artist, album)
            return None

        best = max(candidates, key=lambda match: match.score(album, year, artist))
        logger.info(
            "Picked release group %s (score=%.1f)", best.mbid, best.score(album, year, artist)
        )
        return best.mbid or None

    async def _search(self, query: str, limit: int) -> list[ReleaseGroupMatch]:
        """Run one release-group search; an empty list is also a failure."""
        payload = await self._get(
            "release-group", {"query": query, "fmt": "json", "limit": limit}
        )
        if payload is None:
            return []
        return [
            ReleaseGroupMatch.of(entry)
            for entry in payload.get("release-groups", [])
            if entry.get("id")
        ]

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any] | None:
        """One rate-limited call, or None when it failed.

        A failure is never raised: research grounds a pitch, it does not gate
        one, and every caller degrades to less grounding rather than no album.
        """
        client = await self.http.client()
        await self.throttle.wait()
        try:
            response = await client.get(f"{self.config.musicbrainz_url}/{path}", params=params)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as err:
            logger.warning("MusicBrainz %s failed: %s", path, err)
            return None
