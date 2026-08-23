"""Playlist generation with library validation.

`PlaylistGeneration` is one run: the request as a value, and `stream()` as the
order its steps happen in. The shapes it passes between them -- the pool, the
matcher, the narrative -- belong to `models.py`.
"""

import logging
from collections.abc import Generator

from pydantic import BaseModel, ConfigDict

from backend import library
from backend.config import config_store
from backend.generator import prompts
from backend.generator.models import Narrative, TrackMatcher, TrackPool
from backend.llm import client_store
from backend.models import (
    GenerateResponse,
    NarrativeFrame,
    PlaylistCompleteFrame,
    Track,
    TracksFrame,
)
from backend.plex import PlexQueryError, plex_store
from backend.results import Result, results_store
from backend.sse import SSE

logger = logging.getLogger(__name__)

# Tracks per `tracks` frame. iOS Safari silently drops large SSE events.
TRACK_BATCH_SIZE = 5


class PlaylistGeneration(BaseModel):
    """One generation run: what was asked for, and how it is carried out."""

    model_config = ConfigDict(frozen=True)

    prompt: str = ""
    seed_track: Track | None = None
    selected_dimensions: list[str] = []
    additional_notes: str = ""
    refinement_answers: list[str | None] = []
    genres: list[str] = []
    decades: list[str] = []
    track_count: int = 25
    exclude_live: bool = True
    min_rating: int = 0
    max_tracks_to_ai: int = 500

    @property
    def pool(self) -> TrackPool:
        """What this run may pick from, before a model is asked."""
        return TrackPool(
            genres=self.genres,
            decades=self.decades,
            min_rating=self.min_rating,
            exclude_live=self.exclude_live,
            limit=self.max_tracks_to_ai,
        )

    def subtitle(self, matched: list[Track]) -> str:
        """The line under this run's card in history.

        A seed playlist names the track it grew from; a prompt one repeats the
        prompt, because that is what the user will recognise it by.
        """
        if self.seed_track:
            origin = f"{self.seed_track.title} by {self.seed_track.artist}"
            return f"From: {origin} · {len(matched)} tracks"
        if self.prompt:
            return f"{self.prompt} · {len(matched)} tracks"
        return f"{len(matched)} tracks"

    def matched(
        self, selections: list[dict], candidates: list[Track]
    ) -> tuple[list[Track], dict[str, str]]:
        """The library tracks a model's selections name, and why each was picked.

        The seed track is excluded up front: a playlist that opens with the
        song it was grown from reads as a bug.

        Args:
            selections: What the model returned, artist and title per entry
            candidates: The pool the selections must resolve inside

        Returns:
            The matched tracks, and each one's reason keyed by rating key
        """
        tracks: list[Track] = []
        reasons: dict[str, str] = {}
        used = {self.seed_track.rating_key} if self.seed_track else set()

        matcher = TrackMatcher.configured()
        for selection in selections:
            if len(tracks) >= self.track_count:
                break

            artist = selection.get("artist", "")
            title = selection.get("title", "")
            reason = selection.get("reason", "")

            for track in candidates:
                if track.rating_key in used:
                    continue
                if not matcher.matches(artist, title, track):
                    continue

                tracks.append(track)
                used.add(track.rating_key)
                if reason:
                    reasons[track.rating_key] = reason
                break

        return tracks, reasons

    def save(self, result: GenerateResponse, matched: list[Track]) -> str | None:
        """Record the run in history, or None when that failed.

        History is a convenience: losing it must not lose the playlist the
        user is looking at, so nothing here is allowed to raise.
        """
        try:
            return results_store.save(
                Result(
                    type="seed_playlist" if self.seed_track else "prompt_playlist",
                    title=result.playlist_title,
                    prompt=self.prompt,
                    snapshot=result.model_dump(mode="json"),
                    track_count=len(matched),
                    # The first track's art stands in for the whole playlist.
                    art_rating_key=matched[0].rating_key if matched else None,
                    subtitle=self.subtitle(matched),
                )
            )
        except Exception as e:
            logger.warning("Failed to save result: %s", e)
            return None

    def stream(self) -> Generator[str]:
        """Run one generation, reporting each step as it happens.

        Yields SSE frames: progress while it works, then the narrative, the
        tracks in batches, and a final summary. Any failure becomes an error
        frame rather than an exception, because the client is already reading.
        """
        try:
            logger.info("Starting playlist generation (streaming)")
            llm_client = client_store.get()
            plex_client = plex_store.get()

            if not llm_client:
                yield SSE.error("LLM client not initialized")
                return
            if not plex_client:
                yield SSE.error("Plex client not initialized")
                return

            pool = self.pool
            has_filters = pool.is_filtered

            using_cache = library.library_sync.has_tracks()
            if using_cache:
                yield SSE.progress("fetching", "Loading tracks from cache...")
            elif not has_filters:
                yield SSE.progress("fetching", "Sampling random tracks from library...")
            else:
                yield SSE.progress("fetching", "Fetching tracks from library...")

            logger.info(
                "Fetching tracks: genres=%s, decades=%s, min_rating=%s, using_cache=%s",
                self.genres,
                self.decades,
                self.min_rating,
                using_cache,
            )
            try:
                candidates = pool.tracks(plex_client)
            except PlexQueryError as e:
                yield SSE.error(f"Plex server error: {e}")
                return

            logger.info("Got %d tracks", len(candidates))

            if not candidates:
                yield SSE.error(
                    "No tracks match the selected filters. Try broadening your selection."
                )
                return

            shape = "tracks" if has_filters else "random tracks"
            yield SSE.progress("filtering", f"Using {len(candidates)} {shape}...")
            yield SSE.progress("preparing", f"Preparing {len(candidates)} tracks for AI...")

            generation_prompt = prompts.selection(
                tracks=candidates,
                track_count=self.track_count,
                prompt=self.prompt,
                seed_track=self.seed_track,
                selected_dimensions=self.selected_dimensions,
                additional_notes=self.additional_notes,
                refinement_answers=self.refinement_answers,
            )

            yield SSE.progress("ai_working", "AI is curating your playlist...")

            logger.info("Calling LLM with prompt length: %d chars", len(generation_prompt))
            response = llm_client.generate(generation_prompt, prompts.GENERATION_SYSTEM)
            logger.info(
                "LLM response received: %d input, %d output tokens",
                response.input_tokens,
                response.output_tokens,
            )

            yield SSE.progress("parsing", "Parsing AI selections...")

            selections = response.parsed()
            if not isinstance(selections, list):
                yield SSE.error("LLM returned invalid track selection format")
                return

            yield SSE.progress("matching", f"Matching {len(selections)} selections to library...")
            matched, reasons = self.matched(selections, candidates)

            yield SSE.progress("narrative", "Writing playlist narrative...")

            written = Narrative.of(selections, llm_client, self.prompt)
            logger.info(
                "Generated narrative: title='%s', narrative_len=%d",
                written.title,
                len(written.text),
            )

            yield SSE.of(
                "narrative",
                NarrativeFrame(
                    playlist_title=written.title,
                    narrative=written.text,
                    track_reasons=reasons,
                    user_request=self.prompt,
                ),
            )

            logger.info("Track matching complete. Matched %d tracks", len(matched))
            yield SSE.progress("complete", "Playlist ready!")

            cost = response.cost(config_store.get().llm)
            logger.info(
                "Building GenerateResponse: tokens=%s, cost=%s", response.total_tokens, cost
            )

            try:
                result = GenerateResponse(
                    tracks=matched,
                    token_count=response.total_tokens,
                    estimated_cost=cost,
                    playlist_title=written.title,
                    narrative=written.text,
                    track_reasons=reasons,
                )
            except Exception as e:
                logger.exception("Failed to build GenerateResponse: %s", e)
                yield SSE.error(f"Failed to build response: {e}")
                return

            for i in range(0, len(result.tracks), TRACK_BATCH_SIZE):
                batch = result.tracks[i : i + TRACK_BATCH_SIZE]
                logger.info("Emitting track batch %d-%d", i, i + len(batch))
                yield SSE.of("tracks", TracksFrame(batch=batch, index=i))

            result_id = self.save(result, matched)

            yield SSE.of(
                "complete",
                PlaylistCompleteFrame(
                    track_count=len(result.tracks),
                    token_count=result.token_count,
                    estimated_cost=result.estimated_cost,
                    playlist_title=result.playlist_title,
                    narrative=result.narrative,
                    track_reasons=result.track_reasons,
                    result_id=result_id,
                ),
            )
            logger.info("Complete event emitted successfully")

            # An ignored comment frame, sent to flush iOS Safari's buffer.
            yield ": heartbeat\n\n"

        except Exception as e:
            logger.exception("Error during playlist generation")
            yield SSE.error(str(e))
