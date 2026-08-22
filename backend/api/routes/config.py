"""``/api/config`` and ``/api/ollama`` -- reading and changing settings.

A saved change re-initialises whichever client it touched, so the next request
uses the new settings without a restart. Ollama's endpoints live here because
they exist to fill in the settings form.
"""

import asyncio
import os

from fastapi import FastAPI, HTTPException, Query

from backend.api import guards
from backend.config import ConfigSaveError, ConfigUpdate, LocalLLMConfig, config_store
from backend.llm import (
    OllamaClient,
    OllamaModelInfo,
    OllamaModelsResponse,
    OllamaStatus,
    TokenBudget,
)
from backend.models import ConfigResponse
from backend.version import get_version


def configured_endpoint_url() -> str:
    """The configured local endpoint, empty when a cloud provider is active."""
    llm = config_store.get().llm
    return llm.endpoint_url if isinstance(llm, LocalLLMConfig) else ""


def ollama_client(url: str | None = None) -> OllamaClient:
    """An Ollama admin client for `url`, or for the configured endpoint."""
    llm = config_store.get().llm
    return OllamaClient(base_url=url or configured_endpoint_url(), timeout=llm.probe_timeout)


def config_response(config) -> ConfigResponse:
    """The settings the UI shows, with no secret in it.

    Only whether a key is set is reported, never the key.
    """
    budget = TokenBudget.of(config.llm, config.budget)
    is_local = config.llm.is_local

    return ConfigResponse(
        version=get_version(),
        plex_url=config.plex.url,
        plex_connected=guards.plex_client() is not None,
        plex_token_set=bool(config.plex.token),
        music_library=config.plex.music_library,
        llm_provider=config.llm.provider,
        llm_configured=guards.llm_is_configured(config),
        llm_api_key_set=bool(config.llm.api_key),
        model_analysis=config.llm.model_analysis,
        model_generation=config.llm.model_generation,
        max_tracks_to_ai=budget.max_tracks,
        max_albums_to_ai=budget.max_albums,
        cost_generation_input=config.llm.cost_generation_input,
        cost_generation_output=config.llm.cost_generation_output,
        cost_analysis_input=config.llm.cost_analysis_input,
        cost_analysis_output=config.llm.cost_analysis_output,
        is_priced=config.llm.is_priced,
        defaults=config.defaults,
        endpoint_url=config.llm.endpoint_url if is_local else "",
        context_window=config.llm.context_window,
        is_local_provider=is_local,
        # The form disables the provider field when the environment sets it:
        # a saved value would be overridden on the next boot.
        provider_from_env=os.environ.get("MEDIASAGE_LLM__PROVIDER") is not None,
    )


async def _get_config(config: guards.Config) -> ConfigResponse:
    """``GET /api/config`` -- current settings, without secrets."""
    return config_response(config)


async def _update_config(request: ConfigUpdate) -> ConfigResponse:
    """``POST /api/config`` -- save settings and rebuild what they touched."""
    if request.is_empty:
        raise HTTPException(status_code=400, detail="No configuration values provided")

    try:
        config = config_store.apply(request)
    except ConfigSaveError as err:
        raise HTTPException(status_code=500, detail=str(err)) from err

    if request.touches("plex"):
        guards.init_plex(config.plex)
    if request.touches("llm"):
        guards.init_llm(config.llm)

    return config_response(config)


async def _ollama_status(
    url: str | None = Query(None, description="Ollama URL (defaults to config)")
) -> OllamaStatus:
    """``GET /api/ollama/status`` -- whether a local server answers."""
    return await asyncio.to_thread(ollama_client(url).status)


async def _ollama_models(
    url: str | None = Query(None, description="Ollama URL (defaults to config)")
) -> OllamaModelsResponse:
    """``GET /api/ollama/models`` -- what the server has pulled."""
    return await asyncio.to_thread(ollama_client(url).list_models)


async def _ollama_model_info(
    model: str = Query(..., description="Model name"),
    url: str | None = Query(None, description="Ollama URL (defaults to config)"),
) -> OllamaModelInfo | None:
    """``GET /api/ollama/model-info`` -- one model's context window.

    The only place a context window can be discovered rather than typed.
    """
    info = await asyncio.to_thread(ollama_client(url).model_info, model)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Model '{model}' not found")
    return info


def register_config_routes(app: FastAPI) -> None:
    app.add_api_route("/api/config", _get_config, methods=["GET"], response_model=ConfigResponse)
    app.add_api_route(
        "/api/config", _update_config, methods=["POST"], response_model=ConfigResponse
    )
    app.add_api_route(
        "/api/ollama/status", _ollama_status, methods=["GET"], response_model=OllamaStatus
    )
    app.add_api_route(
        "/api/ollama/models", _ollama_models, methods=["GET"],
        response_model=OllamaModelsResponse,
    )
    app.add_api_route(
        "/api/ollama/model-info", _ollama_model_info, methods=["GET"],
        response_model=OllamaModelInfo | None,
    )
