# syntax=docker/dockerfile:1
# Workshop Helmsman v0.2 — production image.
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
    UV_PROJECT_ENVIRONMENT=/srv/helmsman/.venv \
    UV_CACHE_DIR=/srv/helmsman/.cache/uv \
    HOME=/srv/helmsman \
    PORT=8001 \
    PYTHONUNBUFFERED=1
WORKDIR /srv/helmsman

# Dependency layer — only re-runs when the lockfile changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Application code. Layout must mirror the repo: src/ and frontend/ are
# siblings so that _REPO_ROOT (parents[3]) resolves frontend/out correctly.
COPY alembic.ini ./
COPY alembic/ ./alembic/
COPY src/ ./src/
COPY --from=frontend /build/out ./frontend/out
COPY deploy/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Non-root; owns the workdir so the data/ volume is writable.
RUN useradd --system --uid 10001 helmsman && chown -R helmsman:helmsman /srv/helmsman
USER helmsman

EXPOSE 8001
# Migrations run on boot inside the entrypoint (idempotent).
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
