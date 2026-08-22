"""Fixtures for the research package: a scripted HTTP client and its answers.

Every source takes a `SharedHttp` and asks it for a client, so a test scripts
what the network replies and then reads back the URLs it was asked for.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from backend.config.store import config_store


def response(
    payload: Any = None, status: int = 200, text: str = "", url: str = "https://example.test/x"
) -> MagicMock:
    """One HTTP answer, with the three things the sources read off it.

    `raise_for_status` raises the way httpx does, so a source narrowing its
    except to `httpx.HTTPError` is exercised rather than bypassed.
    """
    answer = MagicMock()
    answer.status_code = status
    answer.text = text
    answer.url = url
    answer.json.return_value = payload if payload is not None else {}

    def raise_for_status() -> None:
        if status >= 400:
            raise httpx.HTTPStatusError(f"{status}", request=MagicMock(), response=answer)

    answer.raise_for_status.side_effect = raise_for_status
    return answer


class FakeHttp:
    """A `SharedHttp` stand-in answering from a scripted queue.

    A queued `Exception` is raised instead of returned, which is how a source's
    failure path is reached without a real socket.
    """

    def __init__(self, *answers: Any) -> None:
        self.answers = list(answers)
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._client = MagicMock()
        self._client.get = AsyncMock(side_effect=self._get)

    async def _get(self, url: str, **kwargs: Any) -> Any:
        self.calls.append((url, kwargs))
        if not self.answers:
            raise AssertionError(f"No scripted answer left for {url}")
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    async def client(self) -> MagicMock:
        return self._client

    async def close(self) -> None:
        return None

    @property
    def urls(self) -> list[str]:
        """Every URL asked for, in order."""
        return [url for url, _ in self.calls]


@pytest.fixture
def research_config():
    """The installed research settings, so a test asserts against them."""
    return config_store.get().research


@pytest.fixture
def http():
    """Build a scripted client over the answers a test hands in."""
    return FakeHttp
