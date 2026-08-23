"""Tests for the request log wrapped around the application."""

import logging
import re

import pytest

from backend.api.middleware import RequestLog


class TestSeverity:
    """An outcome is reported at the level it deserves, never below arrival."""

    @pytest.mark.parametrize(
        ("status", "elapsed_ms", "expected"),
        [
            (200, 10.0, logging.INFO),
            (503, 10.0, logging.ERROR),
            (422, 10.0, logging.WARNING),
            (404, 10.0, logging.WARNING),
            (200, 5000.0, logging.WARNING),
        ],
    )
    def test_grades_an_outcome(self, status, elapsed_ms, expected):
        assert RequestLog.severity(logging.INFO, status, elapsed_ms) == expected

    def test_keeps_a_quiet_path_quiet_when_nothing_went_wrong(self):
        """A page load fetches dozens of covers; they must not fill the log."""
        assert RequestLog.severity(logging.DEBUG, 200, 10.0) == logging.DEBUG

    def test_reports_a_quiet_path_that_failed_anyway(self):
        assert RequestLog.severity(logging.DEBUG, 500, 10.0) == logging.ERROR


class TestTarget:
    def test_names_the_path(self):
        assert RequestLog.target({"path": "/api/config", "query_string": b""}) == "/api/config"

    def test_keeps_the_query_string(self):
        """Which endpoint an art or stats read asked for is in the query."""
        scope = {"path": "/api/ollama/model-info", "query_string": b"model=qwen3%3A8b"}

        assert RequestLog.target(scope) == "/api/ollama/model-info?model=qwen3%3A8b"


class TestLogging:
    """Two lines per request: one on arrival, one on the answer."""

    def test_logs_the_arrival_before_the_app_runs(self, client, plex, caplog):
        with caplog.at_level(logging.INFO, logger="backend.api.middleware"):
            client.get("/api/health")

        assert "GET /api/health started" in caplog.text

    def test_logs_the_answer_with_its_status_and_duration(self, client, plex, caplog):
        with caplog.at_level(logging.INFO, logger="backend.api.middleware"):
            client.get("/api/health")

        assert any(re.fullmatch(r"GET /api/health 200 in \d+ms", line) for line in caplog.messages)

    def test_reports_a_refusal_as_a_warning(self, client, plex, caplog):
        """A rejected save is the line worth finding in a log nobody watches."""
        with caplog.at_level(logging.INFO, logger="backend.api.middleware"):
            client.post("/api/config", json={})

        refused = [r for r in caplog.records if " 400 in " in r.getMessage()]
        assert [r.levelno for r in refused] == [logging.WARNING]
