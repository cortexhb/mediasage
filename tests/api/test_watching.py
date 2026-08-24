"""Tests for noticing that the client of a plain request has gone."""

import asyncio
from typing import cast

from fastapi import Request

from backend.api.watching import watch_client
from backend.cancellation import Cancellation


class FakeRequest:
    """A request that reports whatever disconnect state a test wants.

    `is_disconnected` is the whole surface `watch_client` touches, so the
    stand-in is cast rather than built around a real ASGI scope.
    """

    def __init__(self, disconnected: bool) -> None:
        self.disconnected = disconnected

    async def is_disconnected(self) -> bool:
        return self.disconnected

    def asked(self) -> Request:
        """This double where a `Request` is expected."""
        return cast(Request, self)


class TestWatchClient:
    """Tests for the dependency the LLM-spending plain routes carry."""

    async def test_flags_the_run_once_the_client_leaves(self):
        """Nothing else notices: uvicorn runs a plain handler to the end."""
        watching = watch_client(FakeRequest(disconnected=True).asked())
        await anext(watching)
        await asyncio.sleep(0)

        assert Cancellation.gone() is True

    async def test_a_reader_that_stays_is_never_flagged(self):
        watching = watch_client(FakeRequest(disconnected=False).asked())
        await anext(watching)
        await asyncio.sleep(0)

        assert Cancellation.gone() is False

    async def test_the_watcher_stops_with_the_request(self):
        """A poll per request outliving it would leak one task each time."""
        request = FakeRequest(disconnected=False)
        watching = watch_client(request.asked())
        await anext(watching)
        await anext(watching, None)

        request.disconnected = True
        await asyncio.sleep(0.01)
        assert Cancellation.gone() is False
