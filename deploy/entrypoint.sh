#!/bin/sh
# Container entrypoint.
#   entrypoint.sh           serve; run `alembic upgrade head` first only when
#                           HELMSMAN_MIGRATE_ON_BOOT is 1/true (default 1).
#   entrypoint.sh migrate   run `alembic upgrade head` and exit (Cloud Run job).
# Executes the venv binaries directly (PATH is set in the Dockerfile), not
# `uv run`, to keep cold starts short.
set -eu

mkdir -p data

if [ "${1:-}" = "migrate" ]; then
  echo "[entrypoint] migrate: alembic upgrade head"
  exec alembic upgrade head
fi

case "$(printf '%s' "${HELMSMAN_MIGRATE_ON_BOOT:-1}" | tr '[:upper:]' '[:lower:]')" in
  1|true)
    echo "[entrypoint] applying migrations..."
    alembic upgrade head
    ;;
  *)
    echo "[entrypoint] HELMSMAN_MIGRATE_ON_BOOT off; skipping migrations"
    ;;
esac

PORT="${PORT:-8001}"
export PORT
echo "[entrypoint] starting server on :${PORT}..."
exec python -m src
