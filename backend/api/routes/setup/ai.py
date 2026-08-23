"""``/api/setup/validate-ai`` -- prove the provider serves the model, then save.

Listing rather than completing: a key can be valid and the model name wrong,
and the provider's model list answers that without billing for it.
"""

from fastapi import FastAPI
from pydantic import ValidationError

from backend.api.probes import LLMProbe
from backend.config import ConfigSaveError, ConfigUpdate, config_store
from backend.llm import PROVIDER_IDS, LLMClient, client_store
from backend.models import ValidateAIRequest, ValidateAIResponse


async def _validate_ai(request: ValidateAIRequest) -> ValidateAIResponse:
    """``POST /api/setup/validate-ai`` -- list the provider's models, then save."""
    provider_name = request.provider_name

    def rejected(reason: str) -> ValidateAIResponse:
        return ValidateAIResponse(success=False, error=reason, provider_name=provider_name)

    if request.provider not in PROVIDER_IDS:
        return rejected(f"Unknown provider: {request.provider}")
    if not request.model:
        return rejected("A model name is required")
    if not request.context_window:
        return rejected("A context window is required")

    try:
        change = config_store.candidate(
            ConfigUpdate(
                llm_provider=request.provider,
                llm_api_key=request.api_key or None,
                endpoint_url=request.endpoint_url or None,
                model_analysis=request.model,
                model_generation=request.model,
                context_window=request.context_window,
            )
        )
    except ValidationError as err:
        return rejected(str(err))

    probe = await LLMProbe.of(change.config.llm)
    if not probe.ok:
        return rejected(probe.error)

    try:
        config = config_store.commit(change)
    except ConfigSaveError as err:
        return rejected(str(err))

    client_store.client = LLMClient.of(config.llm)
    return ValidateAIResponse(success=True, provider_name=provider_name)


def register_validate_ai_routes(app: FastAPI) -> None:
    app.add_api_route(
        "/api/setup/validate-ai",
        _validate_ai,
        methods=["POST"],
        response_model=ValidateAIResponse,
        operation_id="validateAi",
    )
