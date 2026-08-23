"""``/api/plex`` -- signing in to Plex, and choosing a server.

The only way the application gets a Plex token. Four routes, in the order the
UI walks them: create a pin, poll it, choose a server, sign out. See
`docs/plex_login.md` for why it is a pin exchange rather than OAuth 2.

The poll is stateless. Nothing is held between `POST /api/plex/link` and
`GET /api/plex/link/{id}` except the pin id the browser carries and the client
identifier already on disk, so a restart mid-sign-in loses nothing.

Every plex.tv and Plex call reached from here is synchronous; each goes
through `asyncio.to_thread`.
"""

import asyncio
import logging
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from pydantic import SecretStr

from backend.config import ConfigSaveError, MediasageConfig, config_store
from backend.config.store import ConfigChange
from backend.models import (
    PlexLinkedResponse,
    PlexLinkResponse,
    PlexLinkStatusResponse,
    PlexServerChoice,
    PlexServerRequest,
)
from backend.plex import PlexClient, plex_store
from backend.plex.link import PlexIdentity, PlexLink, PlexLinkError, PlexServers

logger = logging.getLogger(__name__)


def _link(config: MediasageConfig) -> PlexLink:
    """The sign-in helper for this installation's client identifier.

    A module-level function because it is what every route here starts with
    and there is no object either side of it to own it: `PlexLink` must not
    read the config store, and the routes must not restate this.
    """
    return PlexLink.of(config.plex.client_id)


def _servers(config: MediasageConfig) -> PlexServers:
    """The server list for the stored account token.

    Raises:
        HTTPException: 409 when nothing has signed in yet
    """
    if not config.plex.account_token:
        raise HTTPException(status_code=409, detail="Not signed in to Plex")
    return PlexServers(
        account_token=config.plex.account_token,
        identity=PlexIdentity(client_id=config.plex.client_id),
        connect_timeout=config.plex.connect_timeout,
    )


async def _begin(
    config: Annotated[MediasageConfig, Depends(config_store.get)],
) -> PlexLinkResponse:
    """``POST /api/plex/link`` -- create a pin to approve in the browser.

    The client identifier is written now rather than on success: a pin
    approved against one identifier cannot be claimed with another, so a
    restart between the two calls would otherwise lose the sign-in.
    """
    link = _link(config)

    try:
        pin = await link.begin()
    except PlexLinkError as err:
        raise HTTPException(status_code=502, detail=str(err)) from err

    if config.plex.client_id != link.identity.client_id:
        _keep(config, {"client_id": link.identity.client_id})

    return PlexLinkResponse(pin_id=pin.id, code=pin.code, url=pin.url, expires_in=pin.expires_in)


async def _poll(
    pin_id: int,
    config: Annotated[MediasageConfig, Depends(config_store.get)],
) -> PlexLinkStatusResponse:
    """``GET /api/plex/link/{pin_id}`` -- pending, or signed in with a server list.

    The account token is saved the moment it arrives, before any server is
    chosen: it is what makes the sign-in survive the user closing the tab.
    """
    try:
        token = await _link(config).claim(pin_id)
    except PlexLinkError as err:
        raise HTTPException(status_code=502, detail=str(err)) from err

    if token is None:
        return PlexLinkStatusResponse(state="pending")

    kept = _keep(config, {"account_token": token})

    return PlexLinkStatusResponse(state="linked", servers=await _choices(kept))


async def _list(
    config: Annotated[MediasageConfig, Depends(config_store.get)],
) -> PlexLinkStatusResponse:
    """``GET /api/plex/servers`` -- the account's servers, listed again.

    Required by a reload between signing in and choosing: the list arrives
    with the poll, and without this the picker would have nowhere to come
    back from short of a second pin exchange.
    """
    return PlexLinkStatusResponse(state="linked", servers=await _choices(config))


async def _choose(
    request: PlexServerRequest,
    config: Annotated[MediasageConfig, Depends(config_store.get)],
) -> PlexLinkedResponse:
    """``POST /api/plex/server`` -- resolve an address, connect, keep it.

    Nothing is written until one of the server's addresses answered, so a
    server that is off leaves the previous one in force.
    """
    servers = _servers(config)

    try:
        resolved = await asyncio.to_thread(
            servers.resolve, request.server_id, config.plex.music_library
        )
    except PlexLinkError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err

    kept = _keep(
        config,
        {
            "url": resolved.url,
            "token": resolved.token,
            "server_id": resolved.server_id,
            "server_name": resolved.server_name,
        },
    )
    plex_store.client = await asyncio.to_thread(PlexClient.of, kept.plex)

    return await _linked(kept)


async def _forget(
    config: Annotated[MediasageConfig, Depends(config_store.get)],
) -> PlexLinkedResponse:
    """``DELETE /api/plex/link`` -- clear the stored identity.

    The track cache is left alone: signing out of Plex is not a request to
    discard a synced library. `client_id` stays too, so signing back in
    reuses the device already registered in the user's account.
    """
    kept = _keep(
        config,
        {
            "account_token": SecretStr(""),
            "token": SecretStr(""),
            "server_id": "",
            "server_name": "",
            "url": "",
        },
    )
    plex_store.client = None

    return await _linked(kept)


def _keep(config: MediasageConfig, changes: dict[str, object]) -> MediasageConfig:
    """Write Plex section changes and publish them.

    Raises:
        HTTPException: 500 if the file could not be written; nothing is published
    """
    try:
        return config_store.commit(ConfigChange.to_plex(config, changes))
    except ConfigSaveError as err:
        raise HTTPException(status_code=500, detail=str(err)) from err


async def _choices(config: MediasageConfig) -> list[PlexServerChoice]:
    """The account's servers, or none when plex.tv would not list them.

    A failure here is not a failed sign-in: the token is already stored, and
    the UI offers a retry rather than starting the pin exchange again.
    """
    try:
        return await asyncio.to_thread(_servers(config).choices)
    except PlexLinkError:
        logger.warning("Signed in, but could not list Plex servers", exc_info=True)
        return []


async def _linked(config: MediasageConfig) -> PlexLinkedResponse:
    """What the Plex card shows, after a sign-in or a sign-out."""
    client = plex_store.client
    connected = client is not None and await asyncio.to_thread(client.connection.is_connected)
    libraries = (
        await asyncio.to_thread(client.connection.music_libraries)
        if client is not None and connected
        else []
    )

    return PlexLinkedResponse(
        linked=bool(config.plex.account_token),
        connected=connected,
        server_name=config.plex.server_name,
        server_id=config.plex.server_id,
        music_libraries=libraries,
    )


def register_plex_link_routes(app: FastAPI) -> None:
    app.add_api_route(
        "/api/plex/link",
        _begin,
        methods=["POST"],
        response_model=PlexLinkResponse,
        operation_id="beginPlexLink",
    )
    app.add_api_route(
        "/api/plex/link/{pin_id}",
        _poll,
        methods=["GET"],
        response_model=PlexLinkStatusResponse,
        operation_id="pollPlexLink",
    )
    app.add_api_route(
        "/api/plex/servers",
        _list,
        methods=["GET"],
        response_model=PlexLinkStatusResponse,
        operation_id="listPlexServers",
    )
    app.add_api_route(
        "/api/plex/server",
        _choose,
        methods=["POST"],
        response_model=PlexLinkedResponse,
        operation_id="choosePlexServer",
    )
    app.add_api_route(
        "/api/plex/link",
        _forget,
        methods=["DELETE"],
        response_model=PlexLinkedResponse,
        operation_id="forgetPlexLink",
    )
