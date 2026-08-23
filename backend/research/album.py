"""The research pipeline for one album, over all four sources.

`AlbumResearch.of_album` is the whole entry point: find the album in
MusicBrainz, read what it links to, and hand back whatever was found. Cover art
is asked of `.covers` directly -- it is keyed on the mbids `of_album` returned,
not on the album, so routing it through here would compose nothing. Nothing
here raises. Research grounds a pitch, it does not gate one, so every source
that fails simply contributes nothing and the pitch says less.

Light research stops after the MusicBrainz metadata: a secondary pick is shown
as one line, so an article and two reviews would be spent on nothing.
"""

import logging
from typing import Self

from backend.config import ResearchConfig
from backend.config.store import config_store
from backend.recommender import AlbumRef, ResearchData
from backend.research.covers import CoverArt
from backend.research.http import SharedHttp, Throttle
from backend.research.musicbrainz import MusicBrainz
from backend.research.reviews import Reviews
from backend.research.wikipedia import Wikipedia

logger = logging.getLogger(__name__)


class AlbumResearch:
    """Every source, over one shared HTTP client.

    Held open for the process: the client pools connections, and MusicBrainz's
    rate limit has to be counted across every caller rather than per request.
    """

    def __init__(self, http: SharedHttp, config: ResearchConfig) -> None:
        """Build every source over one client.

        Args:
            http: The client every source shares
            config: The research settings, read once and held
        """
        self.config = config
        self.http = http
        self.musicbrainz = MusicBrainz(http, Throttle(config.musicbrainz_interval), config)
        self.wikipedia = Wikipedia(http, config)
        self.covers = CoverArt(http, config)
        self.reviews = Reviews(http, config)

    @classmethod
    def configured(cls) -> Self:
        """Every source over a client of its own, on the saved settings.

        The settings are read once, here: this client is held for the process,
        and a mid-flight change to a rate limit would not be honoured anyway.
        """
        config = config_store.get().research
        return cls(SharedHttp(timeout=config.request_timeout), config)

    async def of_album(
        self, ref: AlbumRef, full: bool = True, year: int | None = None
    ) -> ResearchData:
        """Everything that could be found about one album.

        Args:
            ref: The album as the library or a model names it
            full: Read the article and the reviews too, not just the metadata
            year: The library's year, which disambiguates a common title

        Returns:
            Whatever was found; an empty `ResearchData` when the album was not
        """
        found = ResearchData()

        mbid = await self.musicbrainz.search(ref, year=year)
        if not mbid:
            return found
        found.musicbrainz_id = mbid

        group = await self.musicbrainz.release_group(mbid)
        if group is None:
            return found

        found.release_date = group.release_date
        found.review_links = group.review_urls
        found.earliest_release_mbid = group.earliest_release_mbid

        if group.earliest_release_mbid:
            release = await self.musicbrainz.release(group.earliest_release_mbid)
            if release is not None:
                found.track_listing = release.track_listing
                found.label = release.label
                found.credits = release.credits

        if full:
            found.wikipedia_summary = await self._article(group.wikipedia_url, group.wikidata_url)
            found.review_texts = await self._reviews(group.review_urls)

        return found

    async def close(self) -> None:
        """Release the shared connection pool."""
        await self.http.close()

    async def _article(self, wikipedia_url: str, wikidata_url: str) -> str | None:
        """The article text, resolving through Wikidata when that is all there is.

        Some release groups carry only a Wikidata relation; the item links to
        the article the direct relation would have named.
        """
        url = wikipedia_url
        if not url and wikidata_url:
            url = await self.wikipedia.article_for(wikidata_url) or ""
        return await self.wikipedia.summary(url) if url else None

    async def _reviews(self, urls: list[str]) -> list[str]:
        """The text of each review that could be read; the rest are dropped."""
        texts = []
        for url in urls:
            text = await self.reviews.text(url)
            if text:
                texts.append(text)
        return texts
