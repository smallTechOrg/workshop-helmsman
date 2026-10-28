#!/usr/bin/env bash
# One-off import of a Workshop0 SQLite database into Cloud SQL (PostgreSQL) via a Cloud Run Job.
#
#   bash deploy/cloudrun/import-data.sh --sqlite PATH [--db workshop0] [--replace] [--drop-after]
#
# Flow: temp private GCS bucket -> upload the file -> Cloud Run Job `workshop0-import` (CURRENTLY
# DEPLOYED image, runtime SA workshop0-run, VPC egress, bucket mounted read-only at /import,
# DATABASE_URL from secret workshop0-database-url) runs scripts/sqlite_to_postgres.py -> logs
# (the per-table verification table) are printed -> bucket + job are deleted. Exits non-zero on failure.
#
# --db other than `workshop0` targets a SCRATCH database: the job creates it (through workshop0_app),
# migrates it to head, imports into it, and (--drop-after) drops it. `workshop0` is never touched
# unless --db workshop0 (the default) is in effect.
#
# Prints row COUNTS only, never row data or secret values. Touches only workshop0-prefixed resources
# plus the temporary import bucket.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-ai-agent-boilerplate0}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-workshop0}"
RUN_SA="workshop0-run@${PROJECT_ID}.iam.gserviceaccount.com"
JOB="workshop0-import"
G=(--project "$PROJECT_ID")

SQLITE=""; DB="workshop0"; REPLACE=0; DROP_AFTER=0
usage() {
  echo "usage: $0 --sqlite PATH [--db NAME] [--replace] [--drop-after]" >&2
  exit 2
}
while [ $# -gt 0 ]; do
  case "$1" in
    --sqlite) shift; SQLITE="${1:-}"; [ -n "$SQLITE" ] || usage ;;
    --db) shift; DB="${1:-}"; [ -n "$DB" ] || usage ;;
    --replace) REPLACE=1 ;;
    --drop-after) DROP_AFTER=1 ;;
    *) usage ;;
  esac
  shift
done
[ -n "$SQLITE" ] || usage
case "$DB" in *[!a-z0-9_]*|"") echo "--db must match [a-z0-9_]+" >&2; exit 2 ;; esac
if [ "$DROP_AFTER" -eq 1 ] && [ "$DB" = "workshop0" ]; then
  echo "refusing: --drop-after with --db workshop0 would drop the production database" >&2; exit 2
fi

created() { echo "CREATED $1"; }
exists()  { echo "EXISTS $1"; }
info()    { echo "INFO $1"; }
die()     { echo "ERROR $1" >&2; exit 1; }

BUCKET=""; JOB_CREATED=0; 
cleanup() {
  local rc=$?
  set +e
  if [ "$JOB_CREATED" -eq 1 ]; then
    gcloud run jobs delete "$JOB" --region "$REGION" "${G[@]}" --quiet >/dev/null 2>&1 && info "deleted job $JOB"
  fi
  if [ -n "$BUCKET" ]; then
    gcloud storage rm -r "gs://$BUCKET" "${G[@]}" --quiet >/dev/null 2>&1 && info "deleted bucket $BUCKET" \
      || echo "WARN could not delete bucket $BUCKET (delete it manually)" >&2
  fi
  exit $rc
}
trap cleanup EXIT

# Print alembic_version and per-table row COUNTS of a local SQLite file (read-only; no row data).
inspect_sqlite() {
  python3 -I - "$1" <<'PY'
import sqlite3, sys
def _open(path):
    for flag in ("mode=ro", "immutable=1"):   # immutable: a static copy on a read-only/odd mount
        try:
            c = sqlite3.connect("file:%s?%s" % (path, flag), uri=True)
            c.execute("SELECT 1 FROM sqlite_master LIMIT 1")
            return c
        except sqlite3.Error:
            pass
    sys.exit("cannot open %s read-only" % path)
con = _open(sys.argv[1])
tabs = [r[0] for r in con.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite\\_%' ESCAPE '\\' ORDER BY name")]
ver = "(none)"
if "alembic_version" in tabs:
    row = con.execute("SELECT version_num FROM alembic_version").fetchone()
    ver = row[0] if row else "(empty)"
print("alembic_version: %s" % ver)
for t in tabs:
    if t == "alembic_version":
        continue
    try:
        n = con.execute('SELECT COUNT(*) FROM "%s"' % t.replace('"', '""')).fetchone()[0]
    except sqlite3.Error:
        n = "?"
    print("  %-28s %s" % (t, n))
PY
}

[ -f "$SQLITE" ] || die "SQLite file not found: $SQLITE"
info "source file:"; inspect_sqlite "$SQLITE"
FILE_NAME="$(basename "$SQLITE")"
gcloud auth list --filter=status:ACTIVE --format='value(account)' | grep -q . || die "gcloud is not authenticated"

# --- 1. temp private bucket + upload -----------------------------------------
BUCKET="${PROJECT_ID}-workshop0-import-$(openssl rand -hex 4)"
gcloud storage buckets create "gs://$BUCKET" --location "$REGION" "${G[@]}" \
  --uniform-bucket-level-access --public-access-prevention >/dev/null
created "bucket $BUCKET (private, uniform access; deleted on exit)"
gcloud storage cp "$SQLITE" "gs://$BUCKET/$FILE_NAME" "${G[@]}" >/dev/null
created "object gs://$BUCKET/$FILE_NAME"
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" "${G[@]}" \
  --member "serviceAccount:$RUN_SA" --role roles/storage.objectViewer >/dev/null
created "iam objectViewer(workshop0-run) on bucket $BUCKET"

# --- 2. job from the currently deployed image --------------------------------
REV="$(gcloud run services describe "$SERVICE" --region "$REGION" "${G[@]}" --format='value(status.traffic[0].revisionName)' 2>/dev/null || true)"
[ -n "$REV" ] || REV="$(gcloud run services describe "$SERVICE" --region "$REGION" "${G[@]}" --format='value(status.latestReadyRevisionName)')"
[ -n "$REV" ] || die "no deployed revision of $SERVICE found"
IMAGE="$(gcloud run revisions describe "$REV" --region "$REGION" "${G[@]}" --format='value(spec.containers[0].image)')"
[ -n "$IMAGE" ] || die "could not resolve the image of revision $REV"
info "using image of serving revision $REV"

# Helper run inside the job (psycopg is in the app venv): create / drop a scratch database and
# build its URL from DATABASE_URL (same instance + credentials, database name swapped).
read -r -d '' DBADMIN_PY <<'PY' || true
import os, sys
from urllib.parse import urlsplit, urlunsplit
import psycopg
from psycopg import sql

def conninfo(dbname):
    p = urlsplit(os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://", 1))
    return urlunsplit(p._replace(path="/" + dbname))

cmd, name = sys.argv[1], sys.argv[2]
if cmd == "url":
    p = urlsplit(os.environ["DATABASE_URL"])
    print(urlunsplit(p._replace(path="/" + name)))
    sys.exit(0)
with psycopg.connect(conninfo("postgres"), autocommit=True) as conn:
    if cmd == "create":
        if conn.execute("SELECT 1 FROM pg_database WHERE datname=%s", (name,)).fetchone():
            print("DBADMIN scratch-database-exists")
        else:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
            print("DBADMIN created-scratch-database")
    elif cmd == "drop":
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))
        print("DBADMIN dropped-scratch-database")
PY
DBADMIN_B64="$(printf '%s\n' "$DBADMIN_PY" | base64 | tr -d '\n')"

# Runs inside the job. The image entrypoint is overridden (`sh -c`); the venv python/alembic are on PATH.
JOB_CMD='set -eu
cd /srv/workshop0
if [ "$IMPORT_DB" != workshop0 ]; then
  echo "$DBADMIN_B64" | base64 -d > /tmp/dbadmin.py
  python /tmp/dbadmin.py create "$IMPORT_DB"
  DATABASE_URL="$(python /tmp/dbadmin.py url "$IMPORT_DB")"; export DATABASE_URL
  alembic upgrade head
fi
export TARGET_DATABASE_URL="$DATABASE_URL"
set -- python scripts/sqlite_to_postgres.py --sqlite "/import/$IMPORT_FILE"
[ "$IMPORT_REPLACE" = 1 ] && set -- "$@" --replace
rc=0
"$@" || rc=$?
if [ "$IMPORT_DROP_AFTER" = 1 ] && [ "$IMPORT_DB" != workshop0 ]; then
  DATABASE_URL="$ORIG_DATABASE_URL" python /tmp/dbadmin.py drop "$IMPORT_DB" || echo "WARN scratch drop failed"
fi
exit $rc'

# The scratch-drop needs the ORIGINAL url (the job rebinds DATABASE_URL to the scratch db above).
JOB_CMD="ORIG_DATABASE_URL=\"\$DATABASE_URL\"; export ORIG_DATABASE_URL
$JOB_CMD"

JOB_VERB=create
gcloud run jobs describe "$JOB" --region "$REGION" "${G[@]}" >/dev/null 2>&1 && JOB_VERB=update
gcloud run jobs "$JOB_VERB" "$JOB" --region "$REGION" "${G[@]}" \
  --image "$IMAGE" --service-account "$RUN_SA" \
  --network default --subnet default --vpc-egress private-ranges-only \
  --max-retries 0 --task-timeout 1800 --cpu 1 --memory 1Gi \
  --command sh --args=-c --args="$JOB_CMD" \
  --set-env-vars "WORKSHOP0_MIGRATE_ON_BOOT=0,IMPORT_FILE=${FILE_NAME},IMPORT_DB=${DB},IMPORT_REPLACE=${REPLACE},IMPORT_DROP_AFTER=${DROP_AFTER},DBADMIN_B64=${DBADMIN_B64}" \
  --set-secrets "DATABASE_URL=workshop0-database-url:latest,OPENROUTER_API_KEY=workshop0-openrouter-api-key:latest,WORKSHOP0_ADMIN_KEY=workshop0-admin-key:latest" \
  --add-volume "name=import,type=cloud-storage,bucket=${BUCKET},readonly=true" \
  --add-volume-mount "volume=import,mount-path=/import" >/dev/null
JOB_CREATED=1
[ "$JOB_VERB" = create ] && created "run-job $JOB" || exists "run-job $JOB (updated)"

# --- 3. execute + stream the verification output -----------------------------
info "importing into database '$DB'$([ $REPLACE -eq 1 ] && echo ' (--replace)')"
EXEC_RC=0
EXEC_NAME="$(gcloud run jobs execute "$JOB" --region "$REGION" "${G[@]}" --wait --format='value(metadata.name)' 2>/dev/null)" || EXEC_RC=$?
if [ -z "$EXEC_NAME" ]; then
  EXEC_NAME="$(gcloud run jobs executions list --job "$JOB" --region "$REGION" "${G[@]}" --limit 1 --format='value(name)' 2>/dev/null || true)"
fi
LOGS=""
if [ -n "$EXEC_NAME" ]; then
  for _ in 1 2 3 4 5 6; do   # Cloud Logging ingestion lags a few seconds
    LOGS="$(gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=$JOB AND labels.\"run.googleapis.com/execution_name\"=$EXEC_NAME" \
      "${G[@]}" --order asc --freshness 1h --format='value(textPayload)' 2>/dev/null | grep -v '^$' || true)"
    grep -qE 'OK|MISMATCH|ERROR|abort|Traceback|DBADMIN' <<<"$LOGS" && break
    sleep 5
  done
fi
echo "---- job output (execution ${EXEC_NAME:-unknown}) ----"
printf '%s\n' "$LOGS"
echo "---- end job output ----"
if [ "$EXEC_RC" -ne 0 ]; then die "import job failed (see output above); the target transaction was rolled back by the script"; fi
if grep -qE 'MISMATCH|FAIL' <<<"$LOGS"; then die "verification reported a mismatch"; fi
info "import finished OK into database '$DB'"
# cleanup trap deletes the job and the bucket
