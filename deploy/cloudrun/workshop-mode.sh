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

status() {
  local min max
  min=$(gcloud run services describe "$SERVICE" --region "$REGION" --project "$PROJECT_ID" \
    --format='value(spec.template.metadata.annotations."autoscaling.knative.dev/minScale")')
  max=$(gcloud run services describe "$SERVICE" --region "$REGION" --project "$PROJECT_ID" \
    --format='value(spec.template.metadata.annotations."autoscaling.knative.dev/maxScale")')
  echo "min-instances=${min:-0} max-instances=${max:-unset}"
}

case "$1" in
  on)  gcloud run services update "$SERVICE" --region "$REGION" --project "$PROJECT_ID" --min-instances 1 --quiet >/dev/null; status ;;
  off) gcloud run services update "$SERVICE" --region "$REGION" --project "$PROJECT_ID" --min-instances 0 --quiet >/dev/null; status ;;
  status) status ;;
  *) usage ;;
esac
