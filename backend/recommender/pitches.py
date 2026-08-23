"""Writing the sommelier pitch, checking it, and fixing what it got wrong.

`Pitches` holds three calls: one writes pitches for every recommendation, one
fact-checks the primary against what the sources actually said, and one
rewrites it when the check found something.

Only the primary is checked. It is the one the user reads in full, and it is
the only album deep research was run for.
"""

import logging
from collections.abc import Mapping

from backend.library import AlbumFamiliarity
from backend.recommender import prompts
from backend.recommender.calls import Stage
from backend.recommender.matching import AlbumMatcher
from backend.recommender.models import (
    AlbumRecommendation,
    AlbumRef,
    AnswerSet,
    ExtractedFacts,
    FamiliarityPreference,
    PitchIssue,
    PitchValidation,
    ResearchData,
    SommelierPitch,
)

logger = logging.getLogger(__name__)


class Pitches(Stage):
    """The pitch for each recommendation, and the fact-check over the primary."""

    def write(
        self,
        recommendations: list[AlbumRecommendation],
        prompt: str,
        answers: AnswerSet,
        research: Mapping[str, ResearchData] = {},
        facts: Mapping[str, ExtractedFacts] = {},
        familiarity_pref: FamiliarityPreference = "any",
        familiarity: Mapping[str, AlbumFamiliarity] = {},
    ) -> list[AlbumRecommendation]:
        """Write a pitch for every recommendation, in place.

        Args:
            recommendations: What to pitch; mutated with the pitches written
            prompt: What the user asked for
            answers: What they said to the clarifying questions
            research: Raw research by album key, for track listings and labels
            facts: Extracted facts by album key, which the pitch must stay inside
            familiarity_pref: How to frame an album the user already knows
            familiarity: How much of each album has been played, by album key

        Returns:
            The same recommendations, with `pitch` filled in
        """
        descriptions = [
            self._describe(rec, research, facts, familiarity) for rec in recommendations
        ]

        raw = self.call.analyze(
            prompts.pitch_system(bool(facts), familiarity_pref),
            prompts.pitches(prompt, answers, "\n\n".join(descriptions)),
            "pitch_writing",
        )

        written = {}
        for item in self.as_list(raw):
            fields = self.as_dict(item)
            ref = AlbumRef(
                artist=str(fields.get("artist", "") or ""),
                album=str(fields.get("album", "") or ""),
            )
            written[ref.key] = fields

        matcher = AlbumMatcher.for_pitches()
        for rec in recommendations:
            fields = matcher.find(rec.ref, written) or {}
            if not fields:
                logger.warning("No pitch came back for %s", rec.ref)
            rec.pitch = (
                SommelierPitch.primary(fields)
                if rec.rank == "primary"
                else SommelierPitch.secondary(fields)
            )
            if research and rec.ref.key in research:
                rec.research_available = True

        return recommendations

    def fact_check(self, pitch: SommelierPitch, facts: ExtractedFacts) -> PitchValidation:
        """Check a pitch's factual claims against the extracted facts.

        The track listing is sent separately and marked authoritative: it comes
        from MusicBrainz rather than a model, so a pitch naming a track absent
        from it is naming one that does not exist.
        """
        facts_text = facts.to_text(include_track_listing=False)
        if facts.track_listing:
            facts_text += "\n\nAUTHORITATIVE TRACK LISTING:\n" + "\n".join(
                f"  - {track}" for track in facts.track_listing
            )

        raw = self.as_dict(
            self.call.analyze(
                prompts.VALIDATION_SYSTEM,
                prompts.validation(pitch, facts_text),
                "pitch_validation",
            )
        )

        issues = []
        for item in self.as_list(raw.get("issues")):
            fields = self.as_dict(item)
            issues.append(PitchIssue(
                claim=str(fields.get("claim", "") or ""),
                problem=str(fields.get("problem", "") or ""),
                correction=str(fields.get("correction", "") or ""),
            ))

        # An unparseable reply defaults to valid: an unread answer is not evidence
        # the pitch is wrong, and the user would rather see it than not.
        return PitchValidation(valid=bool(raw.get("valid", True)), issues=issues)

    def rewrite(
        self,
        rec: AlbumRecommendation,
        facts: ExtractedFacts,
        issues: PitchValidation,
        prompt: str,
        answers: AnswerSet,
    ) -> None:
        """Rewrite a primary pitch around its corrections, in place."""
        raw = self.as_dict(
            self.call.analyze(
                prompts.REWRITE_SYSTEM,
                prompts.rewrite(rec, prompt, answers, issues, facts),
                "pitch_rewrite",
            )
        )
        rec.pitch = SommelierPitch.primary(raw)

    @staticmethod
    def _describe(
        rec: AlbumRecommendation,
        research: Mapping[str, ResearchData],
        facts: Mapping[str, ExtractedFacts],
        familiarity: Mapping[str, AlbumFamiliarity],
    ) -> str:
        """One album as the pitch prompt sees it, with whatever is known about it."""
        description = f"[{rec.rank.upper()}] {rec.ref} ({rec.year or '?'})"

        played = familiarity.get(rec.rating_key or "")
        if played:
            description += f"\nFamiliarity: {played.level}"

        known = facts.get(rec.ref.key) if facts else None
        if known:
            facts_text = known.to_text(include_track_listing=False)
            if facts_text:
                description += (
                    "\n\nEXTRACTED FACTS (from Wikipedia, MusicBrainz, and reviews):\n"
                    f"{facts_text}"
                )

        found = research.get(rec.ref.key) if research else None
        if found:
            if found.track_listing:
                description += f"\n\nTRACK LISTING: {', '.join(found.track_listing)}"
            if found.label:
                description += f"\nLabel: {found.label}"
            if found.release_date:
                description += f"\nRelease: {found.release_date}"

        return description
