"""The ASGI entry point: `uvicorn backend.main:app`.

Nothing is assembled here. `backend.api.create_app` builds the application and
mounts every route; this module exists so there is one stable import path for
uvicorn, the Dockerfile, and the tests.
"""

from backend.api import create_app
from backend.logs import Logs

# Before the app: uvicorn has already configured logging by the time this
# module is imported, so this is what replaces it.
Logs.configure()

app = create_app()
