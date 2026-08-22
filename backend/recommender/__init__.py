"""The album recommendation pipeline.

A sentence becomes three albums with a pitch, over a handful of LLM calls.
Split by responsibility:

  models      the shapes every stage passes: albums, answers, pitches, facts
  dimensions  the taste axes a clarifying question can be asked along
  prompts     every word sent to a model, and nothing else
  calls       MeteredClient, one call charged to one session
  sessions    SessionStore, the flow held between requests
  matching    an album a model named, matched back to one we have
  selection   what to ask, what to filter, and which albums to pick
  facts       raw research read into facts a pitch can be held to
  pitches     writing the pitch, fact-checking it, rewriting what it got wrong
  pipeline    RecommendationPipeline, the facade the application talks through

`pipeline_store` is the entry point: it hands out the pipeline for the
configured LLM and rebuilds it when that client changes.

Submodules import each other by module rather than by symbol, so patching one
stage covers every caller of it.
"""

from backend.recommender import dimensions, facts, matching, pitches, prompts, selection
from backend.recommender.calls import MeteredClient
from backend.recommender.matching import AlbumMatcher
from backend.recommender.models import (
    AlbumRecommendation,
    AlbumRef,
    AnswerSet,
    ClarifyingQuestion,
    ExtractedFacts,
    FamiliarityPreference,
    FilterSuggestion,
    Mode,
    PitchIssue,
    PitchValidation,
    Rank,
    RecommendGenerateResponse,
    RecommendSession,
    ResearchData,
    SommelierPitch,
    TasteDimension,
    TasteProfile,
)
from backend.recommender.pipeline import PipelineStore, RecommendationPipeline, pipeline_store
from backend.recommender.round import RecommendationRound, RoundInputs, Step
from backend.recommender.sessions import SessionStore

__all__ = [
    "AlbumMatcher",
    "AlbumRecommendation",
    "AlbumRef",
    "AnswerSet",
    "ClarifyingQuestion",
    "ExtractedFacts",
    "FamiliarityPreference",
    "FilterSuggestion",
    "MeteredClient",
    "Mode",
    "PipelineStore",
    "PitchIssue",
    "PitchValidation",
    "Rank",
    "RecommendGenerateResponse",
    "RecommendSession",
    "RecommendationPipeline",
    "RecommendationRound",
    "ResearchData",
    "RoundInputs",
    "SessionStore",
    "SommelierPitch",
    "Step",
    "TasteDimension",
    "TasteProfile",
    "dimensions",
    "facts",
    "matching",
    "pipeline_store",
    "pitches",
    "prompts",
    "selection",
]
