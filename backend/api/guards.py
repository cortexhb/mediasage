"""What an endpoint needs before it can do anything.

Most routes need a connected Plex server, a configured LLM, or the pipeline
built on one, and answer the same 503 when they do not have it. These are
FastAPI dependencies, so a route body starts with the thing it needs rather
than with three lines of guard.

Every store is reached through this module and nowhere else in the API layer,
reads and rebuilds alike, which is also the one place a test has to patch.
"""

from typing import Annotated

from fastapi import Depends, HTTPException

from backend.config import (
    LLMSection,
    LocalLLMConfig,
    MediasageConfig,
    PlexConfig,
    config_store,
)
from backend.llm import LLMClient, client_store
from backend.plex import PlexClient, plex_store
from backend.recommender import RecommendationPipeline, pipeline_store


def llm_is_configured(config: MediasageConfig) -> bool:
    """Whether a provider can be reached: a key for cloud, a URL for local."""
    if isinstance(config.llm, LocalLLMConfig):
        return bool(config.llm.endpoint_url)
    return bool(config.llm.api_key)


def plex() -> PlexClient | None:
    """The Plex client the process holds, connected or not.

    For a route that reports *why* it is not connected; everything else wants
    `plex_client`, which does not hand back a broken one.
    """
    return plex_store.get()


def plex_client() -> PlexClient | None:
    """The Plex client if it is connected, else None.

    For a route that reports connectivity rather than requiring it.
    """
    client = plex()
    return client if client is not None and client.is_connected() else None


def pipeline() -> RecommendationPipeline | None:
    """The recommendation pipeline for the configured LLM, or None without one."""
    return pipeline_store.get(client_store.get())


def init_plex(config: PlexConfig) -> None:
    """Rebuild the Plex client against saved settings."""
    plex_store.init(config)


def init_llm(config: LLMSection) -> None:
    """Rebuild the LLM client against saved settings."""
    client_store.init(config)


def require_plex() -> PlexClient:
    """The connected Plex client, or 503."""
    client = plex_client()
    if client is None:
        raise HTTPException(status_code=503, detail="Plex not connected")
    return client


def require_llm() -> LLMClient:
    """The configured LLM client, or 503."""
    client = client_store.get()
    if client is None:
        raise HTTPException(status_code=503, detail="LLM not configured")
    return client


def require_pipeline() -> RecommendationPipeline:
    """The recommendation pipeline, or 503."""
    built = pipeline()
    if built is None:
        raise HTTPException(status_code=503, detail="LLM not configured")
    return built


def config() -> MediasageConfig:
    """The live configuration."""
    return config_store.get()


Plex = Annotated[PlexClient, Depends(require_plex)]
LLM = Annotated[LLMClient, Depends(require_llm)]
Pipeline = Annotated[RecommendationPipeline, Depends(require_pipeline)]
Config = Annotated[MediasageConfig, Depends(config)]
