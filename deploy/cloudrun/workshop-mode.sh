#!/usr/bin/env bash
# Workshop mode: keep one Cloud Run instance warm (min-instances=1) during a workshop.
# Usage: bash deploy/cloudrun/workshop-mode.sh on|off|status
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-ai-agent-boilerplate0}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-helmsman}"

usage() { echo "usage: $0 on|off|status" >&2; exit 2; }
[ $# -eq 1 ] || usage

if ! gcloud run services describe "$SERVICE" --region "$REGION" --project "$PROJECT_ID" --format='value(name)' >/dev/null 2>&1; then
  echo "Cloud Run service '$SERVICE' does not exist yet in $PROJECT_ID/$REGION (it is created by the first deploy)." >&2
  exit 1
fi

G=(--region "$REGION" --project "$PROJECT_ID")

# Revision currently receiving traffic (the deploy workflow pins traffic to a named revision).
serving_rev() {
  gcloud run services describe "$SERVICE" "${G[@]}" --format='value(status.traffic[0].revisionName)'
}

rev_min() {
  gcloud run revisions describe "$1" "${G[@]}" \
    --format='value(metadata.annotations."autoscaling.knative.dev/minScale")'
}

status() {
  local rev min max
  rev=$(serving_rev)
  min=$(rev_min "$rev")
  max=$(gcloud run revisions describe "$rev" "${G[@]}" \
    --format='value(metadata.annotations."autoscaling.knative.dev/maxScale")')
  echo "min-instances=${min:-0} max-instances=${max:-unset}"
}

# Set min-instances on the SERVING revision. `services update` creates a NEW revision that
# gets 0% traffic when traffic is pinned, so we re-pin the image to the serving revision's
# (not a possibly-bad latest template) and then shift 100% traffic to the new revision.
set_min() {
  local want="$1" rev cur image new
  rev=$(serving_rev)
  [ -n "$rev" ] || { echo "No serving revision found for '$SERVICE'." >&2; exit 1; }
  cur=$(rev_min "$rev")
  if [ "${cur:-0}" = "$want" ]; then
    echo "EXISTS min-instances=$want already on serving revision $rev (no new revision)"
    status
    return
  fi
  image=$(gcloud run revisions describe "$rev" "${G[@]}" --format='value(spec.containers[0].image)')
  gcloud run services update "$SERVICE" "${G[@]}" --image "$image" --min-instances "$want" --quiet >/dev/null
  new=$(gcloud run services describe "$SERVICE" "${G[@]}" --format='value(status.latestCreatedRevisionName)')
  gcloud run services update-traffic "$SERVICE" "${G[@]}" --to-revisions="$new=100" --quiet >/dev/null
  echo "CREATED revision $new (min-instances=$want) now serving 100% traffic"
  status
}

case "$1" in
  on)  set_min 1 ;;
  off) set_min 0 ;;
  status) status ;;
  *) usage ;;
esac
