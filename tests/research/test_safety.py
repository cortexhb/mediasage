"""Tests for the fetch that refuses anything resolving inside the network."""

import socket
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.research import safety
from backend.research.safety import SafeFetcher


def resolves_to(address: str):
    """Patch name resolution so a test does not depend on a working DNS."""
    family = socket.AF_INET6 if ":" in address else socket.AF_INET
    return patch.object(
        safety.socket, "getaddrinfo",
        return_value=[(family, socket.SOCK_STREAM, 6, "", (address, 0))],
    )


def always_safe():
    """Patch the address check on the class; pydantic blocks instance patching."""
    return patch.object(SafeFetcher, "is_safe", return_value=True)


def safe_then_not():
    """A safe start whose redirect target is not."""
    return patch.object(SafeFetcher, "is_safe", side_effect=[True, False])


def redirect(location: str) -> MagicMock:
    """A response httpx reports as a redirect, pointing at `location`."""
    answer = MagicMock()
    answer.is_redirect = True
    answer.next_request = MagicMock()
    answer.next_request.url = location
    return answer


def final() -> MagicMock:
    """A response that is not a redirect."""
    answer = MagicMock()
    answer.is_redirect = False
    return answer


class TestIsSafe:
    @pytest.mark.parametrize("url", (
        "file:///etc/passwd",
        "ftp://example.com/x",
        "gopher://example.com",
    ))
    def test_rejects_a_non_http_scheme(self, url):
        assert SafeFetcher.is_safe(url) is False

    def test_rejects_a_url_with_no_host(self):
        assert SafeFetcher.is_safe("http://") is False

    def test_rejects_a_malformed_url(self):
        assert SafeFetcher.is_safe("http://[") is False

    @pytest.mark.parametrize("address", (
        "127.0.0.1",      # loopback
        "10.0.0.5",       # private
        "192.168.1.10",   # private
        "169.254.1.1",    # link-local
        "::1",            # loopback, v6
    ))
    def test_rejects_a_host_resolving_to_a_reserved_address(self, address):
        """An open redirect on a public host would otherwise reach the LAN."""
        with resolves_to(address):
            assert SafeFetcher.is_safe("https://internal.example.com/x") is False

    def test_accepts_a_public_address(self):
        with resolves_to("93.184.216.34"):
            assert SafeFetcher.is_safe("https://example.com/article") is True

    def test_rejects_a_name_that_does_not_resolve(self):
        with patch.object(safety.socket, "getaddrinfo", side_effect=socket.gaierror("nope")):
            assert SafeFetcher.is_safe("https://nowhere.invalid/x") is False


class TestGet:
    async def test_refuses_an_unsafe_start(self):
        client = MagicMock()
        client.get = AsyncMock()

        with resolves_to("127.0.0.1"):
            assert await SafeFetcher(max_redirects=5).get(client, "https://internal/x") is None

        client.get.assert_not_called()

    async def test_returns_a_direct_answer(self):
        client = MagicMock()
        client.get = AsyncMock(return_value=final())

        with resolves_to("93.184.216.34"):
            fetched = await SafeFetcher(max_redirects=5).get(client, "https://example.com/x")

        assert fetched is not None

    async def test_follows_a_safe_redirect(self):
        answer = final()
        client = MagicMock()
        client.get = AsyncMock(side_effect=[redirect("https://example.com/moved"), answer])

        with resolves_to("93.184.216.34"):
            fetched = await SafeFetcher(max_redirects=5).get(client, "https://example.com/x")

        assert fetched is answer

    async def test_refuses_a_redirect_into_private_space(self):
        client = MagicMock()
        client.get = AsyncMock(return_value=redirect("https://internal/x"))

        with safe_then_not():
            assert await SafeFetcher(max_redirects=5).get(client, "https://example.com/x") is None

    async def test_gives_up_past_the_hop_limit(self):
        client = MagicMock()
        client.get = AsyncMock(return_value=redirect("https://example.com/again"))

        with always_safe():
            assert await SafeFetcher(max_redirects=2).get(client, "https://example.com/x") is None

        assert client.get.await_count == 3

    async def test_the_hop_limit_is_the_fetcher_s(self):
        """The limit is configured, so a deployment can tighten or loosen it."""
        client = MagicMock()
        client.get = AsyncMock(return_value=redirect("https://example.com/again"))

        with always_safe():
            await SafeFetcher(max_redirects=1).get(client, "https://example.com/x")

        assert client.get.await_count == 2
