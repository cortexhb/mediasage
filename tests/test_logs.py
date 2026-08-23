"""Tests for the process-wide logging setup."""

import logging

import pytest

from backend.logs import DATE_FORMAT, LEVEL_VAR, Logs


@pytest.fixture(autouse=True)
def restore_logging():
    """Put the root and uvicorn loggers back, whatever a test did to them."""
    root = logging.getLogger()
    held = (root.handlers[:], root.level)
    uvicorn = {name: logging.getLogger(name) for name in ("uvicorn", "uvicorn.access")}
    states = {name: (log.handlers[:], log.propagate, log.disabled) for name, log in uvicorn.items()}

    yield

    root.handlers, root.level = held
    for name, (handlers, propagate, disabled) in states.items():
        uvicorn[name].handlers = handlers
        uvicorn[name].propagate = propagate
        uvicorn[name].disabled = disabled


class TestLevel:
    def test_defaults_to_info(self, monkeypatch):
        monkeypatch.delenv(LEVEL_VAR, raising=False)

        assert Logs.level() == logging.INFO

    @pytest.mark.parametrize("named", ["DEBUG", "debug", " Debug "])
    def test_reads_a_name_however_it_is_written(self, monkeypatch, named):
        monkeypatch.setenv(LEVEL_VAR, named)

        assert Logs.level() == logging.DEBUG

    def test_falls_back_on_a_name_that_means_nothing(self, monkeypatch):
        """A typo must not silence the process."""
        monkeypatch.setenv(LEVEL_VAR, "LOUD")

        assert Logs.level() == logging.INFO


class TestConfigure:
    def test_every_line_carries_a_timestamp(self, monkeypatch):
        monkeypatch.delenv(LEVEL_VAR, raising=False)
        Logs.configure()

        formatter = logging.getLogger().handlers[0].formatter
        assert formatter is not None
        written = formatter.format(
            logging.LogRecord("backend.test", logging.INFO, "f.py", 1, "hello", None, None)
        )

        assert written.endswith("INFO    backend.test: hello")
        assert written[:4].isdigit()

    def test_prints_uvicorn_error_as_uvicorn(self, monkeypatch):
        """Uvicorn logs its startup through it, so the name reads as a failure."""
        monkeypatch.delenv(LEVEL_VAR, raising=False)
        Logs.configure()

        handler = logging.getLogger().handlers[0]
        record = logging.LogRecord(
            "uvicorn.error", logging.INFO, "server.py", 94, "Started server process [6]", None, None
        )
        # Truthy, not True: 3.14 hands the record back rather than a bool.
        assert handler.filter(record)
        assert record.name == "uvicorn"

    def test_replaces_the_handlers_rather_than_adding_to_them(self, monkeypatch):
        """Uvicorn configured logging first; a second handler doubles every line."""
        monkeypatch.delenv(LEVEL_VAR, raising=False)
        logging.getLogger().addHandler(logging.NullHandler())

        Logs.configure()

        assert len(logging.getLogger().handlers) == 1

    def test_sends_uvicorn_through_the_same_handler(self, monkeypatch):
        """Its own handler has no timestamp, and it does not propagate by default."""
        monkeypatch.delenv(LEVEL_VAR, raising=False)
        uvicorn = logging.getLogger("uvicorn")
        uvicorn.handlers = [logging.NullHandler()]
        uvicorn.propagate = False

        Logs.configure()

        assert uvicorn.handlers == []
        assert uvicorn.propagate is True

    def test_silences_the_access_log(self, monkeypatch):
        """The request middleware logs the same lines, with the duration."""
        monkeypatch.delenv(LEVEL_VAR, raising=False)

        Logs.configure()

        assert logging.getLogger("uvicorn.access").disabled is True

    def test_applies_the_configured_level(self, monkeypatch):
        monkeypatch.setenv(LEVEL_VAR, "WARNING")

        Logs.configure()

        assert logging.getLogger().level == logging.WARNING

    def test_renders_a_real_date(self, monkeypatch):
        """`asctime` is only a date if `datefmt` says so; the default holds none."""
        monkeypatch.delenv(LEVEL_VAR, raising=False)
        Logs.configure()

        formatter = logging.getLogger().handlers[0].formatter
        assert formatter is not None
        stamped = formatter.formatTime(
            logging.LogRecord("t", logging.INFO, "f.py", 1, "", None, None), DATE_FORMAT
        )

        assert len(stamped) == len("2026-08-23 20:15:19")
