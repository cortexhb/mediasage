"""``/api/config`` -- reading and changing settings.

A change is proved before it is kept: whatever it could stop working is probed
against the candidate settings, and only then written and published. A saved
change re-initialises whichever client it touched, so the next request uses
the new settings without a restart.
"""

import asyncio
import logging
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException

from backend.api import probes
from backend.config import ConfigSaveError, ConfigUpdate, MediasageConfig, config_store
from backend.llm import LLMClient, client_store
from backend.models import ConfigResponse
from backend.plex import PlexClient, plex_store

logger = logging.getLogger(__name__)


async def _get_config(
    config: Annotated[MediasageConfig, Depends(config_store.get)],
) -> ConfigResponse:
    """``GET /api/config`` -- current settings, without secrets."""
    return ConfigResponse.of(config, plex_store.is_connected())


async def _update_config(request: ConfigUpdate) -> ConfigResponse:
    """``POST /api/config`` -- prove settings work, save them, rebuild.

    Nothing is written until whatever the change could break has answered, so
    a wrong token is a 422 the form can show rather than a broken deployment
    that survives a restart.
    """
    if request.is_empty:
        raise HTTPException(status_code=400, detail="No configuration values provided")

    # Field names only: two of them are credentials.
    supplied = sorted(name for name, value in request.model_dump().items() if value is not None)
    logger.info("Saving settings: %s", ", ".join(supplied))

    change = config_store.candidate(request)

    refused = await probes.Probe.rejection(request, change.config)
    if refused:
        logger.warning("Refused settings: %s", refused)
        raise HTTPException(status_code=422, detail=refused)

    try:
        config = config_store.commit(change)
    except ConfigSaveError as err:
        raise HTTPException(status_code=500, detail=str(err)) from err

    # Off the event loop: building a Plex client opens the connection.
    if request.touches("plex"):
        plex_store.client = await asyncio.to_thread(PlexClient.of, config.plex)
    if request.touches("llm"):
        client_store.client = LLMClient.of(config.llm)

    return ConfigResponse.of(config, plex_store.is_connected())


def register_settings_routes(app: FastAPI) -> None:
    app.add_api_route(
        "/api/config",
        _get_config,
        methods=["GET"],
        response_model=ConfigResponse,
        operation_id="getConfig",
    )
    app.add_api_route(
        "/api/config",
        _update_config,
        methods=["POST"],
        response_model=ConfigResponse,
        operation_id="updateConfig",
    )
