"""Turning raw research into facts a pitch can be held to.

`Facts` holds two calls: one reads Wikipedia, reviews and MusicBrainz metadata
into labelled fields, and one asks whether a discovery pick really matches what
was asked for.

Extraction runs on the cheap model: it is a reformatting job, and the prompt
forbids it from adding anything the sources do not say.
"""

import logging

from backend.recommender import prompts
from backend.recommender.calls import Stage
from backend.recommender.models import AlbumRecommendation, AlbumRef, ExtractedFacts, ResearchData

logger = logging.getLogger(__name__)

# Characters of the Wikipedia summary sent when validating a discovery pick.
# Enough to tell a genre and era; the full text is for the pitch, not this.
SUMMARY_CHARS = 300


class Facts(Stage):
    """Research read into checkable facts, and the discovery pick checked."""

    def extract(self, ref: AlbumRef, research: ResearchData) -> ExtractedFacts:
        """Read the research for one album into labelled facts.

        `track_listing` is copied straight from MusicBrainz rather than
        extracted: it is the one field the fact-checker treats as authoritative.
        """
        raw = self.as_dict(
            self.call.generate(
                prompts.FACTS_SYSTEM,
                prompts.facts(ref, self._sources(research)),
                "fact_extraction",
            )
        )

        return ExtractedFacts(
            origin_story=str(raw.get("origin_story", "") or ""),
            personnel=[str(name) for name in self.as_list(raw.get("personnel"))],
            musical_style=str(raw.get("musical_style", "") or ""),
            vocal_approach=str(raw.get("vocal_approach", "") or ""),
            cultural_context=str(raw.get("cultural_context", "") or ""),
            track_highlights=str(raw.get("track_highlights", "") or ""),
            common_misconceptions=str(raw.get("common_misconceptions", "") or ""),
            source_coverage=str(raw.get("source_coverage", "") or ""),
            track_listing=research.track_listing,
        )

    def matches_request(
        self, rec: AlbumRecommendation, research: ResearchData, prompt: str
    ) -> bool:
        """Whether a discovery pick genuinely fits what the user asked for.

        A model recommending from its own knowledge can name an album that
        exists but is nothing like the request. An unreadable answer counts as a
        failure: the user is told the pick could not be verified rather than
        shown it as if it had been.
        """
        raw = self.as_dict(
            self.call.generate(
                prompts.DISCOVERY_VALIDATION_SYSTEM,
                prompts.discovery_validation(prompt, self._research_summary(rec, research)),
                "discovery_validation",
            )
        )
        if not raw:
            logger.warning("Discovery validation for %s returned no usable answer", rec.ref)
        return bool(raw.get("valid", False))

    @staticmethod
    def _sources(research: ResearchData) -> str:
        """Everything found about an album, labelled by where it came from."""
        sources = []

        if research.wikipedia_summary:
            sources.append(f"WIKIPEDIA:\n{research.wikipedia_summary}")

        for index, review in enumerate(research.review_texts):
            sources.append(f"REVIEW {index + 1}:\n{review}")

        if research.track_listing:
            sources.append("TRACK LISTING:\n" + ", ".join(research.track_listing))

        metadata = []
        if research.release_date:
            metadata.append(f"Release date: {research.release_date}")
        if research.label:
            metadata.append(f"Label: {research.label}")
        if research.credits:
            credits = ", ".join(f"{role}: {name}" for role, name in research.credits.items())
            metadata.append(f"Credits: {credits}")
        if metadata:
            sources.append("MUSICBRAINZ METADATA:\n" + "\n".join(metadata))

        return "\n\n".join(sources) if sources else "No sources available."

    @staticmethod
    def _research_summary(rec: AlbumRecommendation, research: ResearchData) -> str:
        """The short form a discovery check is decided on."""
        lines = [f"Album: {rec.ref}"]
        if research.release_date:
            lines.append(f"Release date: {research.release_date}")
        if research.label:
            lines.append(f"Label: {research.label}")
        if research.genre_tags:
            lines.append(f"Genres: {', '.join(research.genre_tags)}")
        if research.wikipedia_summary:
            lines.append(f"About: {research.wikipedia_summary[:SUMMARY_CHARS]}")
        return "\n".join(lines)
