"""Fire-and-forget work started by an endpoint.

asyncio keeps only weak references to tasks, so a task nothing holds can be
collected mid-flight. Everything spawned here is referenced until it finishes.
"""

import asyncio
from collections.abc import Coroutine
from typing import Any

_tasks: set[asyncio.Task] = set()


def spawn(coro: Coroutine[Any, Any, Any]) -> asyncio.Task:
    """Schedule a coroutine and keep it referenced until it finishes."""
    task = asyncio.create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return task
