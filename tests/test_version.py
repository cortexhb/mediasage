"""Tests for how the running version is resolved."""

import subprocess

import pytest

from backend.version import FALLBACK_VERSION, Version


@pytest.fixture(autouse=True)
def uncached():
    """The lookup is cached for the process; each test needs a fresh answer."""
    Version.current.cache_clear()
    yield
    Version.current.cache_clear()


class TestPriority:
    """The environment wins, then git, then the fallback."""

    def test_an_injected_version_is_used(self, monkeypatch):
        monkeypatch.setenv("APP_VERSION", "1.2.3")
        assert Version.current() == "1.2.3"

    def test_the_docker_placeholder_is_ignored(self, monkeypatch):
        """The image sets APP_VERSION=dev when the build knows no tag."""
        monkeypatch.setenv("APP_VERSION", FALLBACK_VERSION)
        monkeypatch.setattr(Version, "described", staticmethod(lambda: "0.9.0"))
        assert Version.current() == "0.9.0"

    def test_git_is_asked_without_an_injected_version(self, monkeypatch):
        monkeypatch.delenv("APP_VERSION", raising=False)
        monkeypatch.setattr(Version, "described", staticmethod(lambda: "0.1.0-5-gabc"))
        assert Version.current() == "0.1.0-5-gabc"

    def test_falls_back_when_nothing_answers(self, monkeypatch):
        monkeypatch.delenv("APP_VERSION", raising=False)
        monkeypatch.setattr(Version, "described", staticmethod(lambda: None))
        assert Version.current() == FALLBACK_VERSION

    def test_the_answer_is_cached(self, monkeypatch):
        monkeypatch.setenv("APP_VERSION", "1.0.0")
        first = Version.current()
        monkeypatch.setenv("APP_VERSION", "2.0.0")
        assert Version.current() == first


class TestDescribed:
    """`git describe` may be missing, may fail, and prefixes tags with v."""

    def test_the_v_prefix_is_dropped(self, monkeypatch):
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Completed(0, "v0.1.0\n"))
        assert Version.described() == "0.1.0"

    def test_a_failed_describe_answers_none(self, monkeypatch):
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Completed(128, ""))
        assert Version.described() is None

    @pytest.mark.parametrize(
        "error",
        [FileNotFoundError, OSError, subprocess.TimeoutExpired("git", 5)],
    )
    def test_a_missing_or_slow_git_answers_none(self, monkeypatch, error):
        def raise_it(*args, **kwargs):
            raise error

        monkeypatch.setattr(subprocess, "run", raise_it)
        assert Version.described() is None


class _Completed:
    """The two fields of `CompletedProcess` that the lookup reads."""

    def __init__(self, returncode: int, stdout: str) -> None:
        self.returncode = returncode
        self.stdout = stdout
