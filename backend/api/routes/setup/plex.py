"""``/api/setup/validate-plex`` -- connect, then save on success.

What is probed is the merged candidate, not the form: a wizard field is one
part of a section, and the rest has to come from what is already configured.
"""

from fastapi import FastAPI

from backend.api.probes import PlexProbe
from backend.config import ConfigSaveError, ConfigUpdate, config_store
from backend.models import ValidatePlexRequest, ValidatePlexResponse
from backend.plex import PlexClient, plex_store


async def _validate_plex(request: ValidatePlexRequest) -> ValidatePlexResponse:
    """``POST /api/setup/validate-plex`` -- connect, then save on success."""
    change = config_store.candidate(
        ConfigUpdate(
            plex_url=request.plex_url,
            plex_token=request.plex_token,
            music_library=request.music_library,
        )
    )

    probe = await PlexProbe.of(change.config.plex)
    if not probe.ok:
        return ValidatePlexResponse(success=False, error=probe.error)

    try:
        config = config_store.commit(change)
    except ConfigSaveError as err:
        return ValidatePlexResponse(success=False, error=str(err))

    plex_store.client = PlexClient.of(config.plex)
    return ValidatePlexResponse(
        success=True,
        server_name=probe.server_name,
        music_libraries=probe.music_libraries,
    )


def register_validate_plex_routes(app: FastAPI) -> None:
    app.add_api_route(
        "/api/setup/validate-plex", _validate_plex, methods=["POST"],
        response_model=ValidatePlexResponse,
    )
