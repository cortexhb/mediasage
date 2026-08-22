"""The ASGI entry point: `uvicorn backend.main:app`.

Nothing is assembled here. `backend.api.create_app` builds the application and
mounts every route; this module exists so there is one stable import path for
uvicorn, the Dockerfile, and the tests.
"""

import logging

from backend.api import create_app

logging.basicConfig(level=logging.INFO)

app = create_app()
