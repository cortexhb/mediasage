"""The HTTP layer: the application, its routes, and what they share.

  app.py         create_app(), the factory, and the startup/shutdown lifespan
  guards.py      what a route needs before it runs: Plex, an LLM, the pipeline
  sse.py         server-sent events, framed once
  estimates.py   what a run will cost, from measured prompt sizes
  clients.py     the shared outbound clients, built on first use
  background.py  fire-and-forget work, kept referenced until it finishes
  routes/        one module per resource; see its docstring for the map

Nothing here holds domain logic. A route resolves what a request means, hands
it to the package that owns it, and shapes the answer.
"""

from backend.api.app import create_app

__all__ = ["create_app"]
