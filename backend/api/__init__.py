"""The HTTP layer: the application, its routes, and what they share.

  app.py         create_app(), the factory, and the startup/shutdown lifespan
  middleware.py  RequestLog, one log line per request with its duration
  probes.py      whether settings that are not saved yet actually work
  estimates.py   the preview responses, each estimating itself before a run
  clients.py     SharedClients, the outbound clients built on first use
  background.py  fire-and-forget work, kept referenced until it finishes
  routes/        one module per resource; see its docstring for the map

Nothing here holds domain logic. A route resolves what a request means, hands
it to the package that owns it, and shapes the answer. What a route needs it
declares as a FastAPI dependency, resolved by the package that owns the thing;
`app.py` turns an unconfigured dependency into a 503.
"""

from backend.api.app import create_app

__all__ = ["create_app"]
