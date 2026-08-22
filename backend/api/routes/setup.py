"""``/api/setup`` -- the onboarding wizard.

Each validate endpoint proves a dependency works before saving it, so a wrong
credential is a form error rather than something the user discovers on their
first generation. Both save on success and rebuild the client they configured.
"""

import asyncio
import logging
import os
from typing import Final

from fastapi import FastAPI
from pydantic import ValidationError

from backend import library
from backend.api import guards
from backend.config import (
    LLM_SECTION_ADAPTER,
    ConfigSaveError,
    ConfigUpdate,
    PlexConfig,
    config_store,
)
from backend.db import DATA_DIR
from backend.llm import PROVIDER_IDS, LLMClient
from backend.models import (
    SetupCompleteResponse,
    SetupStatusResponse,
    ValidateAIRequest,
    ValidateAIResponse,
    ValidatePlexRequest,
    ValidatePlexResponse,
)
from backend.plex import PlexClient

logger = logging.getLogger(__name__)

# Shown in the wizard; keys match the configured provider.
PROVIDER_LABELS: Final[dict[str, str]] = {
    "anthropic": "Anthropic (Claude)",
    "openai": "OpenAI (GPT)",
    "gemini": "Google (Gemini)",
    "ollama": "Ollama (Local)",
    "custom": "Custom (OpenAI-compatible)",
}

# Provider keys the environment may carry. Their presence is reported so the
# wizard can say a value came from the deployment rather than the form.
LLM_ENV_KEYS: Final = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "OLLAMA_URL",
    "CUSTOM_LLM_URL",
)

# The probe the wizard spends to prove a provider answers.
PROBE_PROMPT: Final = "hi"
PROBE_SYSTEM: Final = "Reply with one word."


def _data_dir_writable() -> bool:
    """Whether the data directory can actually be written to.

    Written to rather than checked with `os.access`: a Docker bind mount can
    report permission the kernel then refuses.
    """
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        probe = DATA_DIR / ".write_test"
        probe.write_text("test")
        probe.unlink()
    except OSError:
        return False
    return True


def _friendly_provider_error(message: str, provider_name: str) -> str:
    """A provider SDK error, as something a setup form can show."""
    if any(token in message for token in ("401", "Unauthorized", "AuthenticationError")):
        return "Invalid API key"
    if "Could not resolve" in message or "connection" in message.lower():
        return f"Cannot connect to {provider_name}"
    return message


async def _status(config: guards.Config) -> SetupStatusResponse:
    """``GET /api/setup/status`` -- the onboarding checklist.

    The uid and gid are reported so a permission failure on the data directory
    can be diagnosed without shelling into the container.
    """
    plex = guards.plex()
    connected = plex is not None and plex.is_connected()
    sync_state = library.sync_status()

    return SetupStatusResponse(
        data_dir_writable=_data_dir_writable(),
        process_uid=getattr(os, "getuid", lambda: 0)(),
        process_gid=getattr(os, "getgid", lambda: 0)(),
        data_dir=str(DATA_DIR),
        plex_connected=connected,
        plex_error=plex.error if plex and not connected else None,
        plex_from_env=bool(os.environ.get("PLEX_URL")),
        music_libraries=plex.music_libraries() if connected else [],
        llm_configured=guards.llm_is_configured(config),
        llm_provider=config.llm.provider,
        llm_from_env=any(os.environ.get(key) for key in LLM_ENV_KEYS),
        library_synced=library.has_tracks(),
        track_count=sync_state.track_count,
        is_syncing=sync_state.is_syncing,
        sync_progress=sync_state.sync_progress,
        setup_complete=config_store.read_user_yaml().get("setup", {}).get("complete", False),
    )


async def _validate_plex(request: ValidatePlexRequest) -> ValidatePlexResponse:
    """``POST /api/setup/validate-plex`` -- connect, then save on success."""
    candidate = PlexConfig(
        url=request.plex_url, token=request.plex_token, music_library=request.music_library
    )
    try:
        probe = await asyncio.to_thread(PlexClient.of, candidate)
    except Exception as err:
        return ValidatePlexResponse(success=False, error=str(err))

    if not probe.is_connected():
        return ValidatePlexResponse(success=False, error=probe.error or "Connection failed")

    # Read off the probe before saving: `init` replaces the held client, and
    # these are what the wizard shows next.
    music_libraries = probe.music_libraries()
    server_name = probe.server_name

    try:
        config_store.apply(
            ConfigUpdate(
                plex_url=request.plex_url,
                plex_token=request.plex_token,
                music_library=request.music_library,
            )
        )
    except ConfigSaveError as err:
        return ValidatePlexResponse(success=False, error=str(err))

    guards.init_plex(candidate)
    return ValidatePlexResponse(
        success=True, server_name=server_name, music_libraries=music_libraries
    )


async def _validate_ai(request: ValidateAIRequest) -> ValidateAIResponse:
    """``POST /api/setup/validate-ai`` -- spend one real completion, then save.

    A real call rather than a reachability check: a key can be valid and the
    model name wrong, and only the provider knows.
    """
    provider_name = PROVIDER_LABELS.get(request.provider, request.provider)

    def rejected(reason: str) -> ValidateAIResponse:
        return ValidateAIResponse(success=False, error=reason, provider_name=provider_name)

    if request.provider not in PROVIDER_IDS:
        return rejected(f"Unknown provider: {request.provider}")
    if not request.model:
        return rejected("A model name is required")
    if not request.context_window:
        return rejected("A context window is required")

    try:
        section = LLM_SECTION_ADAPTER.validate_python({
            "provider": request.provider,
            "api_key": request.api_key,
            "endpoint_url": request.endpoint_url,
            "model_analysis": request.model,
            "model_generation": request.model,
            "context_window": request.context_window,
        })
    except ValidationError as err:
        return rejected(str(err))

    try:
        await asyncio.to_thread(
            LLMClient(section).complete, PROBE_PROMPT, PROBE_SYSTEM, "analysis"
        )
    except Exception as err:
        return rejected(_friendly_provider_error(str(err), provider_name))

    try:
        config = config_store.apply(ConfigUpdate(
            llm_provider=request.provider,
            llm_api_key=request.api_key or None,
            endpoint_url=request.endpoint_url or None,
            model_analysis=request.model,
            model_generation=request.model,
            context_window=request.context_window,
        ))
    except ConfigSaveError as err:
        return rejected(str(err))

    guards.init_llm(config.llm)
    return ValidateAIResponse(success=True, provider_name=provider_name)


async def _complete() -> SetupCompleteResponse:
    """``POST /api/setup/complete`` -- stop showing the wizard.

    A failed write is logged rather than raised: the flag is a preference, and
    refusing to finish onboarding over it would be worse than showing it again.
    """
    try:
        config_store.save({"setup": {"complete": True}})
    except Exception as err:
        logger.warning("Failed to save setup complete flag: %s", err)
    return SetupCompleteResponse(success=True)


def register_setup_routes(app: FastAPI) -> None:
    app.add_api_route(
        "/api/setup/status", _status, methods=["GET"], response_model=SetupStatusResponse
    )
    app.add_api_route(
        "/api/setup/validate-plex", _validate_plex, methods=["POST"],
        response_model=ValidatePlexResponse,
    )
    app.add_api_route(
        "/api/setup/validate-ai", _validate_ai, methods=["POST"],
        response_model=ValidateAIResponse,
    )
    app.add_api_route(
        "/api/setup/complete", _complete, methods=["POST"],
        response_model=SetupCompleteResponse,
    )
