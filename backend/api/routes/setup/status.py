"""``/api/setup/status`` -- the onboarding checklist.

Reports what is already configured and what came from the deployment rather
than the form, so the wizard can skip steps the operator has already made.
"""

import asyncio
import os
from typing import Annotated, Final

from fastapi import Depends, FastAPI

from backend import library
from backend.config import MediasageConfig, config_store
from backend.db import db
from backend.models import SetupStatusResponse
from backend.plex import PlexClient, plex_store

# Provider keys the environment may carry. Their presence is reported so the
# wizard can say a value came from the deployment rather than the form.
LLM_ENV_KEYS: Final = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "OLLAMA_URL",
    "CUSTOM_LLM_URL",
)


async def _status(
    config: Annotated[MediasageConfig, Depends(config_store.get)],
    plex: Annotated[PlexClient | None, Depends(plex_store.get)],
) -> SetupStatusResponse:
    """``GET /api/setup/status`` -- the onboarding checklist.

    The uid and gid are reported so a permission failure on the data directory
    can be diagnosed without shelling into the container.
    """
    # Off the event loop: both reach the Plex server over the network.
    connected = plex is not None and await asyncio.to_thread(plex.connection.is_connected)
    libraries = (
        await asyncio.to_thread(plex.connection.music_libraries)
        if plex is not None and connected
        else []
    )
    sync_state = library.library_sync.status()

    return SetupStatusResponse(
        data_dir_writable=db.data_dir_writable(),
        process_uid=getattr(os, "getuid", lambda: 0)(),
        process_gid=getattr(os, "getgid", lambda: 0)(),
        data_dir=str(db.data_dir),
        plex_connected=connected,
        plex_error=plex.connection.error if plex and not connected else None,
        music_libraries=libraries,
        llm_configured=config.llm.is_configured,
        llm_provider=config.llm.provider,
        llm_from_env=any(os.environ.get(key) for key in LLM_ENV_KEYS),
        library_synced=library.library_sync.has_tracks(),
        track_count=sync_state.track_count,
        is_syncing=sync_state.is_syncing,
        sync_progress=sync_state.sync_progress,
    )


def register_setup_status_routes(app: FastAPI) -> None:
    app.add_api_route(
        "/api/setup/status",
        _status,
        methods=["GET"],
        response_model=SetupStatusResponse,
        operation_id="getSetupStatus",
    )
