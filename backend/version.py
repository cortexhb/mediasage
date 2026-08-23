"""The running version, taken from the environment or from git.

Entry point: `Version.current()`. Read at import time by `backend.__init__`
and reported to the UI, so it must never raise.
"""

import os
import subprocess
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict

# Reported when neither the environment nor git can name a version.
FALLBACK_VERSION = "dev"

# Seconds `git describe` may take before the fallback stands in.
GIT_DESCRIBE_TIMEOUT = 5


class Version(BaseModel):
    """Where the running version comes from, in priority order.

    The image ships no `.git`, so the build injects `APP_VERSION`; a checkout
    has no `APP_VERSION`, so git is asked instead. Neither answer changes while
    the process lives, so the lookup is cached.
    """

    model_config = ConfigDict(frozen=True)

    @staticmethod
    @lru_cache(maxsize=1)
    def current() -> str:
        """The running version: `APP_VERSION`, else the git tag, else `dev`.

        Shaped "0.1.0" on a tag, "0.1.0-5-gabcdef" past one, "dev" without.
        """
        injected = os.environ.get("APP_VERSION")
        if injected and injected != FALLBACK_VERSION:
            return injected
        return Version.described() or FALLBACK_VERSION

    @staticmethod
    def described() -> str | None:
        """What `git describe` reports here, or None without git or a repo.

        Run from this file's directory so the working directory cannot decide
        which repository answers.
        """
        try:
            result = subprocess.run(
                ["git", "describe", "--tags", "--always"],
                capture_output=True,
                text=True,
                timeout=GIT_DESCRIBE_TIMEOUT,
                cwd=Path(__file__).resolve().parent,
            )
        except subprocess.TimeoutExpired, FileNotFoundError, OSError:
            return None
        if result.returncode != 0:
            return None
        # Tags are cut as v0.1.0; the UI and the API report 0.1.0.
        return result.stdout.strip().removeprefix("v") or None
