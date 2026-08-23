"""Choosing which albums to recommend, and what to ask before choosing.

`Selection` holds four calls: the gap analysis that decides what to ask, the
filter suggestion that narrows the library, the question generation itself, and
the selection that picks the albums -- from the library, or from everything else.

Library mode may only return albums the user owns, so anything the model names
that cannot be matched back to a candidate is dropped rather than shown.
"""

import logging
from collections.abc import Mapping, Sequence

from backend.config.store import config_store
from backend.library import AlbumCandidate, AlbumFamiliarity
from backend.recommender import prompts
from backend.recommender.calls import Stage
from backend.recommender.dimensions import catalogue
from backend.recommender.matching import AlbumMatcher
from backend.recommender.models import (
    AlbumRecommendation,
    AlbumRef,
    AnswerSet,
    ClarifyingQuestion,
    FamiliarityPreference,
    FilterSuggestion,
    Rank,
    TasteProfile,
)

logger = logging.getLogger(__name__)


class Selection(Stage):
    """What to ask the user, what to filter on, and which albums to pick."""

    def gap_analysis(self, prompt: str) -> list[str]:
        """The dimensions worth asking the user about.

        Returns:
            As many valid dimension ids as `question_count` asks for
        """
        raw = self.call.analyze(
            prompts.GAP_ANALYSIS_SYSTEM,
            prompts.gap_analysis(prompt, catalogue.listing()),
            "gap_analysis",
        )
        chosen = [item for item in self.as_list(raw) if isinstance(item, str)]
        return catalogue.fill(chosen)

    def suggest_filters(
        self, prompt: str, genres: list[str], decades: list[str]
    ) -> FilterSuggestion:
        """Which of the available genres and decades the prompt implies.

        Anything the model names that is not on offer is discarded; naming
        nothing usable means every option stays selected, the safe default.
        """
        raw = self.as_dict(
            self.call.generate(
                prompts.FILTER_SYSTEM, prompts.filters(prompt, genres, decades), "prompt_filters"
            )
        )

        available_genres = set(genres)
        available_decades = set(decades)
        chosen_genres = [name for name in self.as_list(raw.get("genres")) if name in available_genres]
        chosen_decades = [name for name in self.as_list(raw.get("decades")) if name in available_decades]

        return FilterSuggestion(
            genres=chosen_genres or list(genres),
            decades=chosen_decades or list(decades),
            reasoning=str(raw.get("reasoning", "") or ""),
        )

    def generate_questions(
        self, prompt: str, dimension_ids: list[str]
    ) -> list[ClarifyingQuestion]:
        """Write one question per dimension, in the user's own terms."""
        lines = []
        for dimension_id in dimension_ids:
            dimension = catalogue.by_id(dimension_id)
            label = f"{dimension.label}: {dimension.description}" if dimension else dimension_id
            lines.append(f"- {dimension_id}: {label}")

        raw = self.call.generate(
            prompts.QUESTIONS_SYSTEM, prompts.questions(prompt, lines), "question_gen"
        )

        questions = []
        for item in self.as_list(raw)[: config_store.get().recommend.question_count]:
            fields = self.as_dict(item)
            questions.append(ClarifyingQuestion(
                question_text=str(fields.get("question_text", "") or ""),
                options=[str(option) for option in self.as_list(fields.get("options"))[:4]],
                dimension=str(fields.get("dimension", "") or ""),
            ))
        return questions

    def select_albums(
        self,
        prompt: str,
        answers: AnswerSet,
        candidates: list[AlbumCandidate],
        familiarity_pref: FamiliarityPreference = "any",
        familiarity: Mapping[str, AlbumFamiliarity] = {},
        already_shown: Sequence[AlbumRef] = (),
    ) -> list[AlbumRecommendation]:
        """Pick one primary and two secondary albums out of the library.

        Args:
            prompt: What the user asked for
            answers: What they said to the clarifying questions
            candidates: Every album the filters left in play
            familiarity_pref: Whether to lean on well-loved or unplayed albums
            familiarity: How much of each album has been played, by album key
            already_shown: Albums earlier rounds recommended, to be skipped

        Returns:
            Recommendations without pitches; empty when nothing could be matched
        """
        round_shape = config_store.get().recommend
        pool = self._remaining(candidates, already_shown)
        if len(pool) <= round_shape.pick_count:
            # Nothing to choose between: an LLM call would just echo the list back.
            return [self._ranked(candidate, index) for index, candidate in enumerate(pool)]

        lines = [
            self._album_line(candidate, familiarity_pref, familiarity, round_shape.genres_per_line)
            for candidate in pool
        ]
        note = prompts.SMALL_POOL_NOTE if len(pool) < round_shape.small_pool else ""

        raw = self.call.generate(
            prompts.selection_system(familiarity_pref, round_shape.pick_count),
            prompts.selection(
                prompt, answers, "\n".join(lines), len(pool), round_shape.pick_count, note
            ),
            "selection",
            albums=len(pool),
        )

        lookup = {AlbumRef(artist=c.album_artist, album=c.album).key: c for c in pool}
        matcher = AlbumMatcher.for_selection()
        picked = []
        for item in self.as_list(raw)[: round_shape.pick_count]:
            fields = self.as_dict(item)
            wanted = AlbumRef(
                artist=str(fields.get("artist", "") or ""),
                album=str(fields.get("album", "") or ""),
            )
            candidate = matcher.find(wanted, lookup)
            if candidate is None:
                # Library mode guarantees every pick is playable, so an album we
                # cannot place is dropped rather than shown as unplayable.
                logger.warning("Skipping unmatched album selection: %s", wanted)
                continue
            picked.append(AlbumRecommendation.of_candidate(candidate, self._rank_of(fields)))

        return self._with_a_primary(picked)

    def select_discovery_albums(
        self,
        prompt: str,
        answers: AnswerSet,
        profile: TasteProfile,
        already_shown: Sequence[AlbumRef] = (),
        max_exclusion_albums: int = 0,
    ) -> list[AlbumRecommendation]:
        """Pick albums the user does not own, from the model's own knowledge.

        More are requested than shown: the exclusion list in the prompt is
        capped, so some of what comes back is already owned and filtered here.

        Args:
            max_exclusion_albums: Owned albums to list; 0 takes the configured cap
        """
        round_shape = config_store.get().recommend
        excluded = max_exclusion_albums or round_shape.max_exclusion_albums
        raw = self.call.analyze(
            prompts.discovery_system(round_shape.discovery_request),
            prompts.discovery(
                prompt,
                answers,
                profile,
                profile.owned[:excluded],
                already_shown,
                round_shape.discovery_request,
            ),
            "discovery_selection",
        )

        owned = profile.owned_keys()
        picked: list[AlbumRecommendation] = []
        for item in self.as_list(raw)[: round_shape.discovery_request]:
            if len(picked) >= round_shape.pick_count:
                break
            fields = self.as_dict(item)
            ref = AlbumRef(
                artist=str(fields.get("artist", "") or ""),
                album=str(fields.get("album", "") or ""),
            )
            if ref.key in owned:
                logger.info("Discovery post-filter: skipping owned album %s", ref)
                continue

            picked.append(AlbumRecommendation(
                rank=self._rank_of(fields),
                album=ref.album,
                artist=ref.artist,
                year=fields.get("year") if isinstance(fields.get("year"), int) else None,
            ))

        return self._with_a_primary(picked)

    # -- helpers ---------------------------------------------------------

    @staticmethod
    def _remaining(
        candidates: list[AlbumCandidate], already_shown: Sequence[AlbumRef]
    ) -> list[AlbumCandidate]:
        """The candidates earlier rounds have not already recommended."""
        if not already_shown:
            return candidates
        excluded = {ref.key for ref in already_shown}
        return [
            candidate
            for candidate in candidates
            if AlbumRef(artist=candidate.album_artist, album=candidate.album).key not in excluded
        ]

    @staticmethod
    def _album_line(
        candidate: AlbumCandidate,
        familiarity_pref: FamiliarityPreference,
        familiarity: Mapping[str, AlbumFamiliarity],
        genres_per_line: int,
    ) -> str:
        """One album as the selection prompt lists it."""
        genres = ", ".join(candidate.genres[:genres_per_line]) if candidate.genres else "Unknown"
        line = f"- {candidate.album_artist} — {candidate.album} ({candidate.year or '?'}) [{genres}]"

        if familiarity_pref != "any" and familiarity:
            played = familiarity.get(candidate.parent_rating_key or "")
            if played:
                line += f" {{{played.level}}}"
        return line

    @staticmethod
    def _rank_of(fields: dict[str, object]) -> Rank:
        """The rank the model gave, defaulting to secondary."""
        return "primary" if fields.get("rank") == "primary" else "secondary"

    @staticmethod
    def _ranked(candidate: AlbumCandidate, index: int) -> AlbumRecommendation:
        """First candidate is the primary pick; the rest are secondary."""
        return AlbumRecommendation.of_candidate(candidate, "primary" if index == 0 else "secondary")

    @staticmethod
    def _with_a_primary(picked: list[AlbumRecommendation]) -> list[AlbumRecommendation]:
        """Promote the first pick when the model marked them all secondary."""
        if picked and all(rec.rank == "secondary" for rec in picked):
            picked[0].rank = "primary"
        return picked
