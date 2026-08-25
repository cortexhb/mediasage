# syntax=docker/dockerfile:1

# The SPA is built where node and its toolchain may live freely. Only `dist`
# is copied forward, so neither node nor `node_modules` reaches the runtime
# image -- which ships no javascript runtime at all.
#
# Pinned to the build platform: the bundle is javascript, identical whatever
# the target is, and emulating this stage costs minutes per extra platform.
FROM --platform=$BUILDPLATFORM node:26-slim AS spa

# The browser project in `vitest.config.ts` is a test concern. `npm ci`
# would otherwise pull ~400MB of Chromium that this stage never runs.
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

WORKDIR /spa

# Its own layer, ahead of the source: the lock file changes far less often
# than the code, so an edit reuses the installed dependencies.
COPY spa/package.json spa/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci

COPY spa/ ./

# `tsc -b && vite build`: a type error fails the image rather than shipping.
RUN npm run build


# The virtualenv is built where uv and its download cache may live freely.
# Only `/app/.venv` is copied forward, so neither reaches the runtime image;
# together they are the bulk of what a single-stage build ships.
FROM python:3.14-slim-trixie AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Bytecode is compiled here because the runtime never writes it: with
# PYTHONDONTWRITEBYTECODE set and a read-only-by-convention image, an absent
# .pyc would be recompiled on every import for the life of the container.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Its own layer, ahead of the source: the lock file changes far less often
# than the code, so an edit reuses the resolved dependencies.
# The cache mount keeps uv's downloads out of the layer entirely.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

# Debug symbols in the compiled extensions are a fifth of the virtualenv and
# are read by nothing at runtime. The imports are the guard: a strip that
# broke an extension fails the build here rather than the first request.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends binutils \
 && find /app/.venv -name '*.so' -exec strip --strip-unneeded {} + \
 && /app/.venv/bin/python -c "\
import cryptography.hazmat.bindings._rust, greenlet, httptools, lxml.etree, \
       pydantic_core, rapidfuzz, regex, sqlalchemy, tiktoken, uvloop, \
       watchfiles, websockets, xxhash, yaml, zstandard"


FROM python:3.14-slim-trixie AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# UID 1000 so a host bind mount of /app/data needs no chown on the host side.
RUN groupadd -r -g 1000 mediasageappuser \
 && useradd -r -u 1000 -g mediasageappuser mediasageappuser

WORKDIR /app

# Created owned, so a volume mounted over it inherits the ownership.
RUN install -d -o mediasageappuser -g mediasageappuser /app/data

# The venv carries absolute paths, so it must land on the path it was built at.
COPY --from=builder --chown=mediasageappuser:mediasageappuser /app/.venv /app/.venv

COPY --chown=mediasageappuser:mediasageappuser backend/ ./backend/

# `IMAGE_FRONTEND` in `backend/api/routes/static.py`. Ahead of the version arg
# but after the venv: the bundle changes far more often than the deps.
COPY --from=spa --chown=mediasageappuser:mediasageappuser /spa/dist ./frontend/

# A runtime dependency left in dev-dependencies resolves fine and installs
# nothing, so without this the failure is a crash on first boot, not a build.
RUN python -c "from backend.main import app"

# Last, because it changes on every build: nothing above is rebuilt for it.
# `backend.version` reads it; the image ships no `.git` for git to describe.
ARG VERSION=dev
ENV APP_VERSION=${VERSION}

EXPOSE 5765

USER mediasageappuser

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; import sys; code = urllib.request.urlopen('http://localhost:5765/api/health').getcode(); sys.exit(0 if code == 200 else 1)"

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port 5765 --workers ${UVICORN_WORKERS:-1}"]
