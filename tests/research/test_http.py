"""Tests for the shared research client and the rate limit one source obeys."""

import asyncio
from unittest.mock import patch

from backend.research.http import USER_AGENT, SharedHttp, Throttle


class TestThrottle:
    async def test_the_first_call_does_not_wait(self):
        with patch("backend.research.http.asyncio.sleep") as slept:
            await Throttle(1.0).wait()

        slept.assert_not_called()

    async def test_a_second_call_waits_out_the_interval(self):
        throttle = Throttle(1.0)
        await throttle.wait()

        with patch("backend.research.http.asyncio.sleep") as slept:
            await throttle.wait()

        assert slept.call_count == 1
        assert 0 < slept.call_args[0][0] <= 1.0

    async def test_a_zero_interval_never_waits(self):
        throttle = Throttle(0)
        await throttle.wait()

        with patch("backend.research.http.asyncio.sleep") as slept:
            await throttle.wait()

        slept.assert_not_called()

    async def test_concurrent_callers_are_serialised(self):
        """The lock is held across the sleep, or every waiter bursts through."""
        throttle = Throttle(0.01)
        await asyncio.gather(*(throttle.wait() for _ in range(3)))

        assert throttle._lock.locked() is False


class TestSharedHttp:
    async def test_the_client_is_reused(self):
        http = SharedHttp(timeout=1.0)
        try:
            assert await http.client() is await http.client()
        finally:
            await http.close()

    async def test_it_identifies_the_application(self):
        """MusicBrainz rate-limits a generic User-Agent harder, or blocks it."""
        http = SharedHttp(timeout=1.0)
        try:
            assert (await http.client()).headers["User-Agent"] == USER_AGENT
        finally:
            await http.close()

    async def test_the_timeout_is_the_configured_one(self):
        http = SharedHttp(timeout=2.5)
        try:
            assert (await http.client()).timeout.read == 2.5
        finally:
            await http.close()

    async def test_a_closed_client_is_rebuilt(self):
        """Shutdown closes it, and a test may reuse the process."""
        http = SharedHttp(timeout=1.0)
        first = await http.client()
        await http.close()

        second = await http.client()
        try:
            assert second is not first
            assert second.is_closed is False
        finally:
            await http.close()

    async def test_closing_twice_is_not_an_error(self):
        http = SharedHttp(timeout=1.0)
        await http.client()
        await http.close()
        await http.close()
