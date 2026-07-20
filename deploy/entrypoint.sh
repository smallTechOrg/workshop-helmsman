#!/bin/sh
# Boot sequence: ensure the data dir exists, apply migrations, then serve.
# Migrations are idempotent (alembic tracks the head), safe on every restart.
set -eu

mkdir -p data

echo "[entrypoint] applying migrations..."
uv run --no-dev alembic upgrade head

echo "[entrypoint] starting server on :${PORT:-8001}..."
exec uv run --no-dev python -m src
