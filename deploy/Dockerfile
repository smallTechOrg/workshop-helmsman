# syntax=docker/dockerfile:1
# Workshop0 v0.2 — production image.
# Stage 1 builds the Next.js static export; stage 2 runs FastAPI which serves
# that export at /app and the JSON API at /api. Single container, single port.

# ---- Stage 1: build the frontend static export (frontend/out) ----
FROM node:22-slim AS frontend
WORKDIR /build
RUN corepack enable
# Install deps against the lockfile first for better layer caching.
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml frontend/.nvmrc ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build   # next.config.ts sets output:'export' basePath:'/app' -> ./out

# ---- Stage 2: python runtime ----
FROM python:3.12-slim-bookworm AS runtime
# uv for reproducible, fast installs (matches local toolchain).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/srv/workshop0/.venv \
    UV_CACHE_DIR=/srv/workshop0/.cache/uv \
    HOME=/srv/workshop0 \
    PATH=/srv/workshop0/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1
WORKDIR /srv/workshop0

# Dependency layer — only re-runs when the lockfile changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Application code. Layout must mirror the repo: src/ and frontend/ are
# siblings so that _REPO_ROOT (parents[3]) resolves frontend/out correctly.
COPY alembic.ini ./
COPY alembic/ ./alembic/
COPY src/ ./src/
# One-off cutover tooling (Cloud Run Job workshop0-import runs scripts/sqlite_to_postgres.py)
COPY scripts/ ./scripts/
COPY --from=frontend /build/out ./frontend/out
# One-off Cloud Run Job workshop0-dbinit runs: python deploy/cloudrun/dbinit.py
COPY deploy/cloudrun/dbinit.py ./deploy/cloudrun/dbinit.py
COPY deploy/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Non-root; owns the workdir so the data/ volume is writable.
RUN useradd --system --uid 10001 workshop0 && chown -R workshop0:workshop0 /srv/workshop0
USER workshop0

# Listens on $PORT (Cloud Run injects 8080); defaults to 8001 when unset.
EXPOSE 8001
# `entrypoint.sh` serves (running migrations first only if
# WORKSHOP0_MIGRATE_ON_BOOT is 1/true, the default); `entrypoint.sh migrate`
# runs `alembic upgrade head` and exits (the Cloud Run migrate job).
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
