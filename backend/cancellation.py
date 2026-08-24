"""Whether the client that asked for this work is still there.

The inference server cannot cancel a completion once it has started, so a
request that is already in flight is spent whatever happens. What can be saved
is every call after it: a generation makes several, and a run whose reader has
closed the tab must not start the next one.

That check has to cross a thread boundary -- the pipelines are synchronous and
run in a worker thread, while the disconnect is noticed on the event loop -- so
the flag is a `threading.Event` carried in a `ContextVar`. Both
`asyncio.to_thread` and `anyio.to_thread.run_sync` copy the context into the
worker, so the thread sees the same object the loop sets.

Top-level rather than under `api/`: `backend.llm` is what consults it, and
importing the HTTP layer from a domain package would be a cycle.
"""

import threading
from contextvars import ContextVar

# None wherever no HTTP request is watching: tests and startup probes.
_gone: ContextVar[threading.Event | None] = ContextVar("client_gone", default=None)


class Abandoned(Exception):
    """The client left before this step ran, so it was not run."""


class Cancellation:
    """The client-gone flag for the work running in this context."""

    @staticmethod
    def watch() -> threading.Event:
        """Install a fresh flag and return it, for the watcher to set.

        Install it before the pipeline's generator is built. `@observe` pins
        every step of a generator to the context it was created in, so a flag
        installed afterwards is invisible to the steps that must read it.
        """
        gone = threading.Event()
        _gone.set(gone)
        return gone

    @staticmethod
    def flag() -> threading.Event:
        """This context's flag, installing one only if nothing did."""
        gone = _gone.get()
        return gone if gone is not None else Cancellation.watch()

    @staticmethod
    def gone() -> bool:
        """Whether the client has left. False where nothing is watching."""
        watching = _gone.get()
        return watching is not None and watching.is_set()

    @staticmethod
    def check() -> None:
        """Stop here if the client has left.

        Raises:
            Abandoned: If the client disconnected before this call
        """
        if Cancellation.gone():
            raise Abandoned("The client disconnected")
