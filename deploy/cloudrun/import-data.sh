#!/usr/bin/env bash
# One-off import of a Helmsman SQLite database into Cloud SQL (PostgreSQL) via a Cloud Run Job.
#
#   bash deploy/cloudrun/import-data.sh --sqlite PATH [--db helmsman] [--replace] [--drop-after]
#   bash deploy/cloudrun/import-data.sh --pull-from-vm [--db helmsman] [--replace] [--drop-after]
#   bash deploy/cloudrun/import-data.sh --pull-from-vm --pull-to DIR     # pull + inspect only; no cloud work
#
# Flow: temp private GCS bucket -> upload the file -> Cloud Run Job `helmsman-import` (CURRENTLY
# DEPLOYED image, runtime SA helmsman-run, VPC egress, bucket mounted read-only at /import,
# DATABASE_URL from secret helmsman-database-url) runs scripts/sqlite_to_postgres.py -> logs
# (the per-table verification table) are printed -> bucket + job are deleted. Exits non-zero on failure.
#
# --db other than `helmsman` targets a SCRATCH database: the job creates it (through helmsman_app),
# migrates it to head, imports into it, and (--drop-after) drops it. `helmsman` is never touched
# unless --db helmsman (the default) is in effect.
#
# --pull-from-vm is strictly READ-ONLY on the VM: a consistent copy is made with SQLite's backup API
# from a throw-away container that mounts the live data volume READ-ONLY; the only thing created on
# the VM is a temp directory holding the export, which is removed afterwards. Nothing is stopped,
# edited or deleted. The copy lands in a local mktemp dir (mode 700, file mode 600).
#
# Prints row COUNTS only, never row data or secret values. Touches only helmsman-prefixed resources
# plus the temporary import bucket.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-ai-agent-boilerplate0}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-helmsman}"
RUN_SA="helmsman-run@${PROJECT_ID}.iam.gserviceaccount.com"
JOB="helmsman-import"
VM_NAME="${VM_NAME:-helmsman-c}"
VM_ZONE="${VM_ZONE:-asia-south1-c}"
VM_CONTAINER="${VM_CONTAINER:-helmsman-app-1}"
VM_DATA_DEST="/srv/helmsman/data"   # mount point INSIDE the app container
G=(--project "$PROJECT_ID")

SQLITE=""; PULL=0; PULL_TO=""; DB="helmsman"; REPLACE=0; DROP_AFTER=0
usage() {
  echo "usage: $0 (--sqlite PATH | --pull-from-vm [--pull-to DIR]) [--db NAME] [--replace] [--drop-after]" >&2
  exit 2
}
while [ $# -gt 0 ]; do
  case "$1" in
    --sqlite) shift; SQLITE="${1:-}"; [ -n "$SQLITE" ] || usage ;;
    --pull-from-vm) PULL=1 ;;
    --pull-to) shift; PULL_TO="${1:-}"; [ -n "$PULL_TO" ] || usage ;;
    --db) shift; DB="${1:-}"; [ -n "$DB" ] || usage ;;
    --replace) REPLACE=1 ;;
    --drop-after) DROP_AFTER=1 ;;
    *) usage ;;
  esac
  shift
done
if [ -n "$SQLITE" ] && [ $PULL -eq 1 ]; then echo "use --sqlite OR --pull-from-vm, not both" >&2; exit 2; fi
if [ -z "$SQLITE" ] && [ $PULL -eq 0 ]; then usage; fi
if [ -n "$PULL_TO" ] && [ $PULL -eq 0 ]; then echo "--pull-to needs --pull-from-vm" >&2; exit 2; fi
case "$DB" in *[!a-z0-9_]*|"") echo "--db must match [a-z0-9_]+" >&2; exit 2 ;; esac
if [ "$DROP_AFTER" -eq 1 ] && [ "$DB" = "helmsman" ]; then
  echo "refusing: --drop-after with --db helmsman would drop the production database" >&2; exit 2
fi

created() { echo "CREATED $1"; }
exists()  { echo "EXISTS $1"; }
info()    { echo "INFO $1"; }
die()     { echo "ERROR $1" >&2; exit 1; }

BUCKET=""; JOB_CREATED=0; LOCAL_TMP=""; REMOTE_TMP=""; KEEP_LOCAL=0
cleanup() {
  local rc=$?
  set +e
  if [ -n "$REMOTE_TMP" ]; then
    gcloud compute ssh "$VM_NAME" --zone "$VM_ZONE" "${G[@]}" --command "rm -rf '$REMOTE_TMP'" >/dev/null 2>&1 \
      && info "removed VM temp dir" || echo "WARN could not remove VM temp dir $REMOTE_TMP on $VM_NAME" >&2
  fi
  if [ "$JOB_CREATED" -eq 1 ]; then
    gcloud run jobs delete "$JOB" --region "$REGION" "${G[@]}" --quiet >/dev/null 2>&1 && info "deleted job $JOB"
  fi
  if [ -n "$BUCKET" ]; then
    gcloud storage rm -r "gs://$BUCKET" "${G[@]}" --quiet >/dev/null 2>&1 && info "deleted bucket $BUCKET" \
      || echo "WARN could not delete bucket $BUCKET (delete it manually)" >&2
  fi
  if [ -n "$LOCAL_TMP" ] && [ "$KEEP_LOCAL" -eq 0 ]; then rm -rf "$LOCAL_TMP"; fi
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

# Read-only consistent copy of the live VM database into $1 (a local dir).
pull_from_vm() {
  local dest="$1" out_name="helmsman.db"
  command -v gcloud >/dev/null || die "gcloud not found"
  info "pulling $VM_DATA_DEST/helmsman.db from $VM_NAME ($VM_ZONE) read-only"
  REMOTE_TMP="$(gcloud compute ssh "$VM_NAME" --zone "$VM_ZONE" "${G[@]}" --command 'umask 077; mktemp -d' 2>/dev/null | tr -d '\r\n')"
  case "$REMOTE_TMP" in /tmp/*) ;; *) REMOTE_TMP=""; die "could not create a temp dir on the VM" ;; esac
  # Runs on the VM. The data volume is mounted :ro; SQLite opens it mode=ro and writes the backup
  # into the temp dir only. Image + volume are discovered from the running app container.
  local remote_cmd
  remote_cmd="set -e
IMG=\$(docker inspect $VM_CONTAINER --format '{{.Config.Image}}')
VOL=\$(docker inspect $VM_CONTAINER --format '{{range .Mounts}}{{if eq .Destination \"$VM_DATA_DEST\"}}{{.Name}}{{end}}{{end}}')
[ -n \"\$VOL\" ] || { echo 'no named volume at $VM_DATA_DEST' >&2; exit 3; }
chmod 777 '$REMOTE_TMP'
if command -v sqlite3 >/dev/null 2>&1; then
  SRC=\$(docker volume inspect \"\$VOL\" --format '{{.Mountpoint}}')
  sudo sqlite3 -readonly \"\$SRC/helmsman.db\" \".backup '$REMOTE_TMP/$out_name'\"
  sudo chown \$(id -u):\$(id -g) '$REMOTE_TMP/$out_name'
else
  docker run --rm --user root --entrypoint python -v \"\$VOL:/data:ro\" -v '$REMOTE_TMP:/out' \"\$IMG\" -c \"
import sqlite3
src = sqlite3.connect('file:/data/helmsman.db?mode=ro', uri=True)
dst = sqlite3.connect('/out/$out_name')
src.backup(dst); dst.close(); src.close()\"
  docker run --rm --user root --entrypoint chown -v '$REMOTE_TMP:/out' \"\$IMG\" \$(id -u):\$(id -g) '/out/$out_name'
fi
chmod 600 '$REMOTE_TMP/$out_name'; ls -l '$REMOTE_TMP/$out_name' | awk '{print \"remote export bytes:\", \$5}'"
  gcloud compute ssh "$VM_NAME" --zone "$VM_ZONE" "${G[@]}" --command "$remote_cmd" 2>/dev/null \
    || die "remote backup failed (nothing on the VM was modified besides the temp export)"
  gcloud compute scp "${G[@]}" --zone "$VM_ZONE" "$VM_NAME:$REMOTE_TMP/$out_name" "$dest/$out_name" >/dev/null 2>&1 \
    || die "scp from VM failed"
  chmod 600 "$dest/$out_name"
  if gcloud compute ssh "$VM_NAME" --zone "$VM_ZONE" "${G[@]}" --command "rm -rf '$REMOTE_TMP'" >/dev/null 2>&1; then
    info "removed VM temp dir"; REMOTE_TMP=""
  fi
  created "local copy $dest/$out_name (mode 600)"
}

if [ $PULL -eq 1 ]; then
  if [ -n "$PULL_TO" ]; then
    mkdir -p "$PULL_TO"; chmod 700 "$PULL_TO"; DEST="$PULL_TO"; KEEP_LOCAL=1
  else
    LOCAL_TMP="$(mktemp -d)"; chmod 700 "$LOCAL_TMP"; DEST="$LOCAL_TMP"
  fi
  pull_from_vm "$DEST"
  SQLITE="$DEST/helmsman.db"
  inspect_sqlite "$SQLITE"
  if [ -n "$PULL_TO" ]; then
    info "pull-only (--pull-to): no cloud import performed; file left at $SQLITE"
    exit 0
  fi
fi

[ -f "$SQLITE" ] || die "SQLite file not found: $SQLITE"
if [ $PULL -eq 0 ]; then
  info "source file:"; inspect_sqlite "$SQLITE"
fi
FILE_NAME="$(basename "$SQLITE")"
gcloud auth list --filter=status:ACTIVE --format='value(account)' | grep -q . || die "gcloud is not authenticated"

# --- 1. temp private bucket + upload -----------------------------------------
BUCKET="${PROJECT_ID}-helmsman-import-$(openssl rand -hex 4)"
gcloud storage buckets create "gs://$BUCKET" --location "$REGION" "${G[@]}" \
  --uniform-bucket-level-access --public-access-prevention >/dev/null
created "bucket $BUCKET (private, uniform access; deleted on exit)"
gcloud storage cp "$SQLITE" "gs://$BUCKET/$FILE_NAME" "${G[@]}" >/dev/null
created "object gs://$BUCKET/$FILE_NAME"
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" "${G[@]}" \
  --member "serviceAccount:$RUN_SA" --role roles/storage.objectViewer >/dev/null
created "iam objectViewer(helmsman-run) on bucket $BUCKET"

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
cd /srv/helmsman
if [ "$IMPORT_DB" != helmsman ]; then
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
if [ "$IMPORT_DROP_AFTER" = 1 ] && [ "$IMPORT_DB" != helmsman ]; then
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
  --set-env-vars "HELMSMAN_MIGRATE_ON_BOOT=0,IMPORT_FILE=${FILE_NAME},IMPORT_DB=${DB},IMPORT_REPLACE=${REPLACE},IMPORT_DROP_AFTER=${DROP_AFTER},DBADMIN_B64=${DBADMIN_B64}" \
  --set-secrets "DATABASE_URL=helmsman-database-url:latest,OPENROUTER_API_KEY=helmsman-openrouter-api-key:latest,HELMSMAN_ADMIN_KEY=helmsman-admin-key:latest" \
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
