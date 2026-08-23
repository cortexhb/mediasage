"""Prompt analysis and seed track dimension extraction.

`Analyzer` holds the clients its two calls read: one turns a sentence into
library filters, one turns a seed track into the dimensions a user can explore
along. Both spend the analysis model.

A prompt may only be answered with filters the library actually has, so what
the model names is checked against the Plex stats before it is returned.
"""

from pydantic import BaseModel, ConfigDict

from backend.analyzer import prompts
from backend.config import config_store
from backend.llm import LLMClient
from backend.models import AnalyzePromptResponse, AnalyzeTrackResponse, Dimension, Track
from backend.plex import PlexClient


class Analyzer(BaseModel):
    """What a prompt implies, and what makes a seed track distinctive.

    `plex` supplies the genres and decades a prompt's filters are drawn from;
    a track carries everything its own analysis needs.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    llm: LLMClient
    plex: PlexClient

    def analyze_prompt(self, prompt: str) -> AnalyzePromptResponse:
        """Read a natural language prompt into filters the library can serve.

        Anything the model names that is not in the library is dropped rather
        than returned as a filter that would match nothing.

        Raises:
            ValueError: The model returned something that will not parse
        """
        stats = self.plex.library.stats()
        response = self.llm.analyze(prompts.filters(prompt, stats), prompts.PROMPT_ANALYSIS_SYSTEM)
        data = response.parsed()

        available_genres = {genre.name for genre in stats.genres}
        available_decades = {decade.name for decade in stats.decades}

        return AnalyzePromptResponse(
            suggested_genres=[name for name in data.get("genres", []) if name in available_genres],
            suggested_decades=[
                name for name in data.get("decades", []) if name in available_decades
            ],
            available_genres=stats.genres,
            available_decades=stats.decades,
            reasoning=data.get("reasoning", ""),
            token_count=response.total_tokens,
            estimated_cost=response.cost(config_store.get().llm),
        )

    def analyze_track(self, track: Track) -> AnalyzeTrackResponse:
        """Read a seed track into the dimensions it can be explored along.

        Raises:
            ValueError: The model returned something that will not parse
        """
        response = self.llm.analyze(prompts.track(track), prompts.TRACK_ANALYSIS_SYSTEM)
        data = response.parsed()

        return AnalyzeTrackResponse(
            track=track,
            dimensions=[
                Dimension(
                    id=fields.get("id", f"dim_{index}"),
                    label=fields.get("label", "Unknown dimension"),
                    description=fields.get("description", ""),
                )
                for index, fields in enumerate(data.get("dimensions", []))
            ],
            token_count=response.total_tokens,
            estimated_cost=response.cost(config_store.get().llm),
        )
