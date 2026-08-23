"""``/api/ollama`` -- discovery for the settings form.

These exist to fill the form in: what a local server has pulled, and how large
a model's context window is. The URL is a query parameter because the wizard
probes an endpoint before it has been saved.
"""

import asyncio

from fastapi import FastAPI, HTTPException, Query

from backend.llm import OllamaClient, OllamaModelInfo, OllamaModelsResponse, OllamaStatus


async def _ollama_status(
    url: str = Query("", description="Ollama URL (defaults to config)"),
) -> OllamaStatus:
    """``GET /api/ollama/status`` -- whether a local server answers."""
    return await asyncio.to_thread(OllamaClient.configured(url).status)


async def _ollama_models(
    url: str = Query("", description="Ollama URL (defaults to config)"),
) -> OllamaModelsResponse:
    """``GET /api/ollama/models`` -- what the server has pulled."""
    return await asyncio.to_thread(OllamaClient.configured(url).list_models)


async def _ollama_model_info(
    model: str = Query(..., description="Model name"),
    url: str = Query("", description="Ollama URL (defaults to config)"),
) -> OllamaModelInfo | None:
    """``GET /api/ollama/model-info`` -- one model's context window.

    The only place a context window can be discovered rather than typed.
    """
    info = await asyncio.to_thread(OllamaClient.configured(url).model_info, model)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Model '{model}' not found")
    return info


def register_ollama_routes(app: FastAPI) -> None:
    app.add_api_route(
        "/api/ollama/status",
        _ollama_status,
        methods=["GET"],
        response_model=OllamaStatus,
        operation_id="getOllamaStatus",
    )
    app.add_api_route(
        "/api/ollama/models",
        _ollama_models,
        methods=["GET"],
        response_model=OllamaModelsResponse,
        operation_id="listOllamaModels",
    )
    app.add_api_route(
        "/api/ollama/model-info",
        _ollama_model_info,
        methods=["GET"],
        response_model=OllamaModelInfo | None,
        operation_id="getOllamaModelInfo",
    )
