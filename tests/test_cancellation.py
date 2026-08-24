"""Tests for the flag that says whether anyone is still reading."""

import pytest

from backend.cancellation import Abandoned, Cancellation


class TestCancellation:
    """Tests for the client-gone flag."""

    def test_nothing_is_abandoned_when_nobody_is_watching(self):
        """A CLI run and a test have no client to lose."""
        assert Cancellation.gone() is False
        Cancellation.check()

    def test_a_watched_run_is_not_gone_until_it_is(self):
        """Installing the flag must not stop the work it guards."""
        Cancellation.watch()

        assert Cancellation.gone() is False

    def test_check_stops_the_run_once_the_client_leaves(self):
        gone = Cancellation.watch()
        gone.set()

        assert Cancellation.gone() is True
        with pytest.raises(Abandoned):
            Cancellation.check()

    def test_a_second_run_starts_unabandoned(self):
        """The flag is per run: one reader leaving cannot stop the next."""
        Cancellation.watch().set()
        Cancellation.watch()

        assert Cancellation.gone() is False
