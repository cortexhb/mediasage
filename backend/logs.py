"""One log format for the whole process, timestamps included.

Entry point: `Logs.configure()`, called from `backend.main` at import.

Uvicorn runs its own `dictConfig` in `Config.__init__`, before it imports the
application, so anything done here lands after it and wins. Its loggers do not
propagate to the root, which is why they are re-pointed by name rather than
left to `basicConfig`.

`uvicorn.access` is silenced: `backend.api.middleware` logs the same requests
with the timing that one omits.

Uvicorn logs its whole life through a logger it named `uvicorn.error` --
startup, shutdown and reload notices included -- so that name says nothing
about severity. `Renamed` prints it as `uvicorn`; the level is the severity.
"""

import logging
import os
import sys
from typing import Final

# Milliseconds: a slow request cannot be placed without them.
FORMAT: Final = "%(asctime)s.%(msecs)03d %(levelname)-7s %(name)s: %(message)s"
DATE_FORMAT: Final = "%Y-%m-%d %H:%M:%S"

# Read from the environment rather than `MediasageConfig`: logging has to be
# up before anything that could fail while loading a configuration file.
LEVEL_VAR: Final = "MEDIASAGE_LOG_LEVEL"

# Uvicorn's own loggers: they carry handlers and do not propagate.
UVICORN_LOGGERS: Final = ("uvicorn", "uvicorn.error")

# What each logger is printed as, where its own name would mislead.
DISPLAY_NAMES: Final = {"uvicorn.error": "uvicorn"}


class Renamed(logging.Filter):
    """Print a logger under a clearer name than the one it registered."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Always keeps the record; only its printed name changes."""
        record.name = DISPLAY_NAMES.get(record.name, record.name)
        return True


class Logs:
    """Process-wide logging setup."""

    @staticmethod
    def level() -> int:
        """The configured level, or INFO when the name is unset or unknown."""
        named = os.environ.get(LEVEL_VAR, "").strip().upper()
        resolved = logging.getLevelNamesMapping().get(named)
        return resolved if resolved is not None else logging.INFO

    @classmethod
    def configure(cls) -> None:
        """Install one timestamped handler and route every logger through it."""
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(FORMAT, datefmt=DATE_FORMAT))
        handler.addFilter(Renamed())

        root = logging.getLogger()
        root.handlers = [handler]
        root.setLevel(cls.level())

        for name in UVICORN_LOGGERS:
            uvicorn = logging.getLogger(name)
            uvicorn.handlers = []
            uvicorn.propagate = True

        # Superseded by the request middleware, which also reports duration.
        logging.getLogger("uvicorn.access").disabled = True
