"""Fire-and-forget work started by an endpoint.

asyncio keeps only weak references to tasks, so a task nothing holds can be
collected mid-flight. `background` is the process-wide set that holds them.
"""

import asyncio
from collections.abc import Coroutine
from typing import Any


class BackgroundTasks:
    """The tasks still running, held so none is collected before it finishes.

    A plain class rather than a model: the set is mutable process state, and
    the only instance is the module-level `background`.
    """

    def __init__(self) -> None:
        self.running: set[asyncio.Task] = set()

    def spawn(self, coro: Coroutine[Any, Any, Any]) -> asyncio.Task:
        """Schedule a coroutine and keep it referenced until it finishes."""
        task = asyncio.create_task(coro)
        self.running.add(task)
        task.add_done_callback(self.running.discard)
        return task


background = BackgroundTasks()
