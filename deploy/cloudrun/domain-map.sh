#!/usr/bin/env bash
# Map workshop0.smalltech.in to the Cloud Run service `helmsman` (Cloud Run domain mapping).
#
#   bash deploy/cloudrun/domain-map.sh [--wait]
#
# 1. Requires `smalltech.in` to be a verified domain for the active gcloud account
#    (`gcloud domains list-user-verified`); otherwise prints the Search Console step and exits 2.
# 2. Creates the mapping if absent (EXISTS otherwise).
# 3. Prints the DNS records exactly as returned by `domain-mappings describe` (resourceRecords).
# 4. --wait polls every 10 s (90 min cap) until Ready=True and CertificateProvisioned=True,
#    then runs `curl -fsS https://workshop0.smalltech.in/api/health`.
# Needs the gcloud `beta` component (`gcloud components install beta`). No secrets involved.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-ai-agent-boilerplate0}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-helmsman}"
BASE_DOMAIN="smalltech.in"
DOMAIN="workshop0.smalltech.in"
POLL_SECONDS=10
POLL_CAP_SECONDS=$((90 * 60))
G=(--project "$PROJECT_ID")
M=(--domain "$DOMAIN" --region "$REGION" "${G[@]}")

created() { echo "CREATED $1"; }
exists()  { echo "EXISTS $1"; }
info()    { echo "INFO $1"; }
die()     { echo "ERROR $1" >&2; exit 1; }

WAIT=0
case "${1:-}" in
  "") ;;
  --wait) WAIT=1 ;;
  *) echo "usage: $0 [--wait]" >&2; exit 2 ;;
esac
[ $# -le 1 ] || { echo "usage: $0 [--wait]" >&2; exit 2; }

gcloud auth list --filter=status:ACTIVE --format='value(account)' | grep -q . || die "gcloud is not authenticated"
gcloud beta run domain-mappings list --region "$REGION" "${G[@]}" >/dev/null 2>&1 \
  || die "gcloud beta run domain-mappings unavailable (run: gcloud components install beta)"

# --- 1. domain ownership -------------------------------------------------------
ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)')"
if ! gcloud domains list-user-verified "${G[@]}" --format='value(id)' 2>/dev/null | grep -qx "$BASE_DOMAIN"; then
  cat >&2 <<MSG
ERROR $BASE_DOMAIN is not a verified domain for $ACCOUNT.
Verify it once, then re-run this script:
  1. Open https://search.google.com/search-console and add the property "$BASE_DOMAIN" (Domain type)
     while signed in as $ACCOUNT (or: gcloud domains verify $BASE_DOMAIN).
  2. Search Console shows a TXT record (google-site-verification=...). In GoDaddy DNS for $BASE_DOMAIN
     add:  TXT · Host @ · Value <the google-site-verification=... string> · TTL 600
  3. Click Verify in Search Console, then run this script again.
MSG
  exit 2
fi
exists "verified domain $BASE_DOMAIN ($ACCOUNT)"

# --- 2. mapping ---------------------------------------------------------------
gcloud run services describe "$SERVICE" --region "$REGION" "${G[@]}" --format='value(name)' >/dev/null 2>&1 \
  || die "Cloud Run service '$SERVICE' does not exist in $PROJECT_ID/$REGION"
if gcloud beta run domain-mappings describe "${M[@]}" >/dev/null 2>&1; then
  exists "domain-mapping $DOMAIN -> $SERVICE"
else
  gcloud beta run domain-mappings create --service "$SERVICE" "${M[@]}" >/dev/null
  created "domain-mapping $DOMAIN -> $SERVICE"
fi

# --- 3. DNS records exactly as Cloud Run returns them ---------------------------
print_records() {
  echo "DNS records to set at the DNS host for $BASE_DOMAIN (exactly as returned by Cloud Run):"
  gcloud beta run domain-mappings describe "${M[@]}" --flatten='status.resourceRecords[]' \
    --format='table[no-heading](status.resourceRecords.type,status.resourceRecords.name,status.resourceRecords.rrdata)' \
    | sed 's/^/  /'
  echo "  (if the host currently has an A or AAAA record for 'workshop0', delete it first: a CNAME cannot coexist with them)"
}
print_records

cond() { # condition type -> True/False/Unknown/"" 
  gcloud beta run domain-mappings describe "${M[@]}" \
    --format="value(status.conditions.filter(type:'$1').extract(status).flatten())" 2>/dev/null || true
}

# --- 4. optional wait ------------------------------------------------------------
if [ $WAIT -eq 0 ]; then
  info "mapping state: Ready=$(cond Ready) CertificateProvisioned=$(cond CertificateProvisioned) (re-run with --wait to poll)"
  exit 0
fi
info "waiting for Ready=True and CertificateProvisioned=True (poll ${POLL_SECONDS}s, cap 90 min)"
elapsed=0
while :; do
  ready="$(cond Ready)"; cert="$(cond CertificateProvisioned)"
  info "Ready=${ready:-?} CertificateProvisioned=${cert:-?} (${elapsed}s)"
  if [ "$ready" = "True" ] && [ "$cert" = "True" ]; then break; fi
  if [ "$elapsed" -ge "$POLL_CAP_SECONDS" ]; then
    print_records >&2
    die "timed out after 90 min; check that the DNS record above is in place and has propagated"
  fi
  sleep "$POLL_SECONDS"; elapsed=$((elapsed + POLL_SECONDS))
done
info "certificate ready; health check https://$DOMAIN/api/health"
curl -fsS "https://$DOMAIN/api/health"; echo
