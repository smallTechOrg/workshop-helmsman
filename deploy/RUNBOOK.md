# Deploy Runbook — Workshop Helmsman (Cloud Run)

Workshop Helmsman runs on **Cloud Run + Cloud SQL**. Architecture detail: `spec/architecture.md` §Production topology. All commands run from the repo root unless stated otherwise; the operator is authenticated with `gcloud auth login` and `gh auth login`. Never paste or echo secret values.

## Topology

```
GitHub Actions (keyless, Workload Identity Federation)
  test (postgres:17) ─▶ build image ─▶ Artifact Registry us-central1/helmsman
     ─▶ Cloud Run Job helmsman-migrate (alembic upgrade head)
     ─▶ Cloud Run service helmsman: new revision --no-traffic (tag candidate)
     ─▶ health check ─▶ route traffic to LATEST ─▶ health check ─▶ (any failure => restore previous revision)

Browser ─HTTPS─▶ Cloud Run service helmsman (project ai-agent-boilerplate0, us-central1, 0-3 instances)
                    │  private VPC egress, TLS
                    ▼
                 Cloud SQL PostgreSQL instance ai-agent-db (shared) ─ database helmsman, user helmsman_app
Secrets (Secret Manager): helmsman-database-url, helmsman-openrouter-api-key, helmsman-admin-key
Public URL: https://workshop0.smalltech.in (domain mapping -> ghs.googlehosted.com) and the *.run.app URL
```

One uvicorn process per container serves `/api/*` and the built frontend. Instances are stateless; the database is the only shared state.

## One-time provisioning (idempotent)

```bash
# HELMSMAN_ADMIN_KEY / OPENROUTER_API_KEY are read from the environment or .env (never echoed)
bash deploy/cloudrun/provision.sh --dry-run    # preview
bash deploy/cloudrun/provision.sh              # prints CREATED <thing> / EXISTS <thing>; safe to re-run
```

It enables the APIs, creates the Artifact Registry repo, service accounts, the keyless GitHub WIF provider, the database and user, the `helmsman-*` secrets with per-secret IAM, a placeholder Cloud Run service, and the public-invoker binding. It never prompts: the `helmsman-dbinit` Cloud Run job creates the database as `helmsman_app`. An existing secret is never overwritten unless you pass `--rotate <name>`.

## The pipeline

Every push to `main` runs `.github/workflows/deploy-cloudrun.yml`:

1. **test** — `uv run pytest tests/unit tests/integration -q` against a `postgres:17` service container.
2. **deploy** — keyless auth (service account `helmsman-deployer`), build and push the image tagged with the commit's first 12 characters, run the `helmsman-migrate` job to completion, deploy a **no-traffic** revision tagged `candidate`, health-check it (`/api/health`, up to ~60 s), route traffic to `LATEST` (so later `services update` calls take effect immediately), health-check the service URL.
3. **Rollback guard** — any failure after the previous revision was captured restores it to 100% and removes the `candidate` tag; the run ends red. The workflow never passes `--allow-unauthenticated`; `provision.sh` owns the public invoker binding.

Manual run (any branch or tag ref): `gh workflow run deploy-cloudrun.yml --ref <ref>` or Actions -> "Deploy (Cloud Run)" -> Run workflow. Inputs: `min_instances` (empty = unchanged, `0`, `1`) and `drill_rollback` (health-checks a path that 404s, so the run **must** fail and roll back — use it to prove the guard).

Repository variable `HELMSMAN_BASE_URL` (set at cutover, e.g. `https://workshop0.smalltech.in`) is passed to the service **only when non-empty**; share links then use that domain. Unset, links derive from the request. Set it with `gh variable set HELMSMAN_BASE_URL --body https://workshop0.smalltech.in`.

Migrations must stay backward-compatible with the previous revision for the one-deploy overlap window (additive first, destructive in a later release).

## Workshop mode (avoid cold starts)

```bash
# one warm instance, at least 10 minutes before the workshop starts
gcloud run services update helmsman --region us-central1 --project ai-agent-boilerplate0 --min-instances=1
# back to scale-to-zero afterwards
gcloud run services update helmsman --region us-central1 --project ai-agent-boilerplate0 --min-instances=0
# check the live value
gcloud run services describe helmsman --region us-central1 --project ai-agent-boilerplate0 --format='value(spec.template.metadata.annotations."autoscaling.knative.dev/minScale")'   # empty = 0
```

- **Why a plain update works:** the service routes traffic to `LATEST` (the deploy workflow ends with `update-traffic --to-latest`), so the revision a `services update` creates serves 100% of traffic as soon as it is ready. A normal deploy never changes `min-instances`; the manual-run input `min_instances` (`""`, `0`, `1`) can set it.
- **After a manual rollback or the automatic rollback guard**, traffic is pinned to a named revision and a plain `services update` would create a 0%-traffic revision. Re-enable latest-routing first: `gcloud run services update-traffic helmsman --region us-central1 --project ai-agent-boilerplate0 --to-latest` (the next successful deploy does this too).
- **Rehearse with the actual participant count** (join that many browsers or run the e2e/poll-burst checks) before a large workshop.

**Cold start:** with `min-instances=0` the first request after idle takes a few seconds while an instance boots (CPU boost is on). That is expected, not a bug; workshop mode removes it.

## Connection-budget rule

The shared Cloud SQL instance has a limited connection budget. Each instance holds up to `HELMSMAN_DB_POOL_SIZE + HELMSMAN_DB_MAX_OVERFLOW` (3 + 2) connections. **Never raise `max-instances` (or the pool settings) without recomputing**: `max-instances x (pool_size + max_overflow) <= ~15`. Today: 3 x 5 = 15.

## Operations: logs, health, rollback

```bash
gcloud run services logs read helmsman --region us-central1 --project ai-agent-boilerplate0 --limit 100
gcloud run revisions list --service helmsman --region us-central1 --project ai-agent-boilerplate0
curl -fsS "$(gcloud run services describe helmsman --region us-central1 --project ai-agent-boilerplate0 --format='value(status.url)')/api/health"
# manual rollback to a known-good revision (pins traffic; run `update-traffic ... --to-latest` afterwards to resume latest-routing)
gcloud run services update-traffic helmsman --region us-central1 --project ai-agent-boilerplate0 --to-revisions <REVISION>=100
```

Logs are JSON lines with a `severity` key.

## Database backup and restore

Cloud SQL automated backups / PITR are owned by the instance's owner (the instance is shared); Helmsman does not alter them. Per-database logical export (needs a bucket you own):

```bash
gcloud sql export sql ai-agent-db gs://<bucket>/helmsman-$(date +%F).sql --database=helmsman --project ai-agent-boilerplate0
```

Restore (into the empty `helmsman` database; this is destructive, so stop and confirm first):

```bash
gcloud sql import sql ai-agent-db gs://<bucket>/helmsman-<date>.sql --database=helmsman --project ai-agent-boilerplate0
```

The Cloud SQL service account needs read access to the bucket for imports and write access for exports.

## Cutover from the VM to Cloud Run (human gate)

Prerequisites: provisioned, the Phase-8 image deployed (it contains `scripts/`), `gcloud` and `gh` authenticated, `smalltech.in` verified with Google (`domain-map.sh` tells you if not).

1. **Day before:** the production host is `workshop0.smalltech.in` (host label `workshop0`). Pick a window with **no live workshop**: the DNS flip and certificate issuance cause a short HTTPS gap (up to ~30-60 minutes), and anything written on the VM after the final import is not carried over. Note the names, statuses and participant counts of the VM's workshops for comparison.
2. **Import the VM data** (read-only against the VM; wipes the throw-away Cloud Run data):

   ```bash
   bash deploy/cloudrun/import-data.sh --pull-from-vm --replace
   ```

   It prints a per-table verification table; every row must say `OK`.
3. **Create the domain mapping:**

   ```bash
   bash deploy/cloudrun/domain-map.sh
   ```

   It prints the DNS records to set. If it reports the domain is unverified, add the TXT record below first and re-run it.
4. **GoDaddy DNS for `smalltech.in` (manual).** In the DNS records for `smalltech.in`:
   - **Add** `CNAME` · Host `workshop0` · Points to `ghs.googlehosted.com` · TTL `600`. (Done: the user created this record directly; the old `workshops` A record `35.200.241.145` is gone and `workshops.smalltech.in` no longer resolves.)
   - If any `A` or `AAAA` record exists for host `workshop0`, delete it (a CNAME cannot coexist with them).
   - Only if `domain-map.sh` reports the domain as unverified: add the `TXT` record it prints at host `@` (`google-site-verification=...`).

   If `gcloud beta run domain-mappings describe` shows different `resourceRecords`, **those win**: use the values it prints.
5. **Wait for the certificate and health:**

   ```bash
   bash deploy/cloudrun/domain-map.sh --wait
   ```

   Then set share links to the pretty domain and redeploy (merge the PR first):

   ```bash
   gh variable set HELMSMAN_BASE_URL --body https://workshop0.smalltech.in
   gh workflow run deploy-cloudrun.yml --ref main
   ```
6. **Smoke test** on the real domain: `curl -sI https://workshop0.smalltech.in/ | grep -i '^server: Google Frontend'`; open `/admin` with the admin key and compare workshops with your notes; open an old facilitator link (`/f/<admin_token>`) and an old participant link (`/p/<token>`); create a workshop, join from a second browser, complete a milestone, and check the shown links start with `https://workshop0.smalltech.in/`.
7. The VM has since been decommissioned (see "VM decommission" below).

## Rollback plan

The VM was retired on 2026-10-29 (see below), so there is no VM fallback any more. For a bad application release use the pipeline's automatic rollback or the manual `update-traffic` command in "Operations". For data, use the Cloud SQL export/restore above. A final consistent copy of the old VM's SQLite database (taken before deletion, integrity-checked, row counts and sha256 verified) is kept in the operator's local backups outside this repository; `deploy/cloudrun/import-data.sh --sqlite PATH` can load such a file. The old VM deploy path is recoverable from git tag `vm-deploy-final`.

## Naming note

The Cloud Run resources (service, jobs, database, service accounts, secrets) keep the name `helmsman`. Cloud Run services cannot be renamed in place, and nothing user-visible depends on the name: users only see `workshop0.smalltech.in`.

## VM decommission (done 2026-10-29)

The old GCE VM `helmsman-c` (asia-south1-c), its boot disk and the static IP `helmsman-ip` (35.200.241.145) were deleted after a verified backup of its SQLite database, and the `DEPLOY_HOST`, `DEPLOY_USER` and `DEPLOY_SSH_KEY` GitHub secrets were removed. Nothing in the repository depends on them. `deploy/cloudrun/import-data.sh --pull-from-vm` is therefore obsolete (it needs the VM); use `--sqlite PATH`.
