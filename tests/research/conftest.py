"""Fixtures for the research package: a scripted HTTP client and its answers.

Every source takes a `SharedHttp` and asks it for a client, so a test scripts
what the network replies and then reads back the URLs it was asked for.
"""

from typing import Any

import httpx
import pytest

from backend.config.store import config_store
from backend.research.http import SharedHttp


def response(
    payload: Any = None, status: int = 200, text: str = "", url: str = "https://example.test/x"
) -> httpx.Response:
    """One HTTP answer, built as the real thing rather than a stand-in.

    A real response means `raise_for_status` and `json` behave exactly as the
    sources meet them in production, so a narrow `except` is exercised.
    """
    request = httpx.Request("GET", url)
    if text:
        return httpx.Response(status, text=text, request=request)
    return httpx.Response(status, json=payload if payload is not None else {}, request=request)


class ScriptedClient(httpx.AsyncClient):
    """An httpx client whose GETs come off a queue instead of a socket.

    Subclassed rather than mocked so the sources receive the type they declare,
    and so the call is recorded with the keywords they passed.
    """

    def __init__(self, *answers: httpx.Response | Exception) -> None:
        super().__init__(transport=httpx.MockTransport(self._unreachable))
        self.answers: list[httpx.Response | Exception] = list(answers)
        self.calls: list[tuple[str, dict[str, Any]]] = []

    @staticmethod
    def _unreachable(request: httpx.Request) -> httpx.Response:
        """Every GET is intercepted above, so no request reaches transport."""
        raise AssertionError(f"Unscripted request escaped to transport: {request.url}")

    async def get(self, url: httpx.URL | str, **kwargs: Any) -> httpx.Response:
        """Pop the next scripted answer, raising it when it is an exception."""
        self.calls.append((str(url), kwargs))
        if not self.answers:
            raise AssertionError(f"No scripted answer left for {url}")
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


class FakeHttp(SharedHttp):
    """A `SharedHttp` already holding a scripted client, so nothing is opened.

    A queued `Exception` is raised instead of returned, which is how a source's
    failure path is reached without a real socket.
    """

    def __init__(self, *answers: httpx.Response | Exception) -> None:
        super().__init__(timeout=1.0)
        self.scripted = ScriptedClient(*answers)
        self._client = self.scripted

    @property
    def calls(self) -> list[tuple[str, dict[str, Any]]]:
        """Every GET asked for, as the URL and the keywords it carried."""
        return self.scripted.calls

    @property
    def urls(self) -> list[str]:
        """Every URL asked for, in order."""
        return [url for url, _ in self.scripted.calls]


@pytest.fixture
def research_config():
    """The installed research settings, so a test asserts against them."""
    return config_store.get().research


@pytest.fixture
def http():
    """Build a scripted client over the answers a test hands in."""
    return FakeHttp
