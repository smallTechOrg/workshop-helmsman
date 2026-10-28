# Deploy Runbook — Workshop Helmsman (Cloud Run)

Workshop Helmsman runs on **Cloud Run + Cloud SQL**. Architecture detail: `spec/architecture.md` §Production topology. All commands run from the repo root unless stated otherwise; the operator is authenticated with `gcloud auth login` and `gh auth login`. Never paste or echo secret values.

## Topology

```
GitHub Actions (keyless, Workload Identity Federation)
  test (postgres:17) ─▶ build image ─▶ Artifact Registry us-central1/helmsman
     ─▶ Cloud Run Job helmsman-migrate (alembic upgrade head)
     ─▶ Cloud Run service helmsman: new revision --no-traffic (tag candidate)
     ─▶ health check ─▶ shift 100% ─▶ health check ─▶ (any failure => restore previous revision)

Browser ─HTTPS─▶ Cloud Run service helmsman (project ai-agent-boilerplate0, us-central1, 0-3 instances)
                    │  private VPC egress, TLS
                    ▼
                 Cloud SQL PostgreSQL instance ai-agent-db (shared) ─ database helmsman, user helmsman_app
Secrets (Secret Manager): helmsman-database-url, helmsman-openrouter-api-key, helmsman-admin-key
Public URL: https://workshops.smalltech.in (domain mapping -> ghs.googlehosted.com) and the *.run.app URL
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
2. **deploy** — keyless auth (service account `helmsman-deployer`), build and push the image tagged with the commit's first 12 characters, run the `helmsman-migrate` job to completion, deploy a **no-traffic** revision tagged `candidate`, health-check it (`/api/health`, up to ~60 s), shift 100% traffic, health-check the service URL.
3. **Rollback guard** — any failure after the previous revision was captured restores it to 100% and removes the `candidate` tag; the run ends red. The workflow never passes `--allow-unauthenticated`; `provision.sh` owns the public invoker binding.

Manual run (any branch or tag ref): `gh workflow run deploy-cloudrun.yml --ref <ref>` or Actions -> "Deploy (Cloud Run)" -> Run workflow. Inputs: `min_instances` (empty = unchanged, `0`, `1`) and `drill_rollback` (health-checks a path that 404s, so the run **must** fail and roll back — use it to prove the guard).

Repository variable `HELMSMAN_BASE_URL` (set at cutover, e.g. `https://workshops.smalltech.in`) is passed to the service **only when non-empty**; share links then use that domain. Unset, links derive from the request. Set it with `gh variable set HELMSMAN_BASE_URL --body https://workshops.smalltech.in`.

Migrations must stay backward-compatible with the previous revision for the one-deploy overlap window (additive first, destructive in a later release).

## Workshop mode (avoid cold starts)

```bash
bash deploy/cloudrun/workshop-mode.sh on       # min-instances=1 (one warm instance)
bash deploy/cloudrun/workshop-mode.sh off      # min-instances=0 (scale to zero)
bash deploy/cloudrun/workshop-mode.sh status   # min-instances=<n> max-instances=<n>
```

- Run `on` **at least 10 minutes before** a workshop starts, confirm with `status`, and run `off` afterwards.
- **Rehearse with the actual participant count** (join that many browsers or run the e2e/poll-burst checks) before a large workshop.
- Traffic is pinned to a named revision, so a plain `gcloud run services update --min-instances` would create a revision serving 0% traffic. The script reuses the serving revision's image, applies the new `min-instances`, and pins 100% traffic to the new revision. Use the script, not a raw `gcloud` update.

**Cold start:** with `min-instances=0` the first request after idle takes a few seconds while an instance boots (CPU boost is on). That is expected, not a bug; workshop mode removes it.

## Connection-budget rule

The shared Cloud SQL instance has a limited connection budget. Each instance holds up to `HELMSMAN_DB_POOL_SIZE + HELMSMAN_DB_MAX_OVERFLOW` (3 + 2) connections. **Never raise `max-instances` (or the pool settings) without recomputing**: `max-instances x (pool_size + max_overflow) <= ~15`. Today: 3 x 5 = 15.

## Operations: logs, health, rollback

```bash
gcloud run services logs read helmsman --region us-central1 --project ai-agent-boilerplate0 --limit 100
gcloud run revisions list --service helmsman --region us-central1 --project ai-agent-boilerplate0
curl -fsS "$(gcloud run services describe helmsman --region us-central1 --project ai-agent-boilerplate0 --format='value(status.url)')/api/health"
# manual rollback to a known-good revision
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

1. **Day before:** in GoDaddy lower the TTL of the existing `workshops` record to 600 seconds. Pick a window with **no live workshop**: the DNS flip and certificate issuance cause a short HTTPS gap (up to ~30-60 minutes), and anything written on the VM after the final import is not carried over. Note the names, statuses and participant counts of the VM's workshops for comparison.
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
   - **Delete** the existing `A` record, host `workshops`, value `35.200.241.145`.
   - **Delete** any `AAAA` record for host `workshops` (a CNAME cannot coexist with them).
   - **Add** `CNAME` · Host `workshops` · Points to `ghs.googlehosted.com` · TTL `600`.
   - Only if `domain-map.sh` reports the domain as unverified: add the `TXT` record it prints at host `@` (`google-site-verification=...`).

   If `gcloud beta run domain-mappings describe` shows different `resourceRecords`, **those win**: use the values it prints.
5. **Wait for the certificate and health:**

   ```bash
   bash deploy/cloudrun/domain-map.sh --wait
   ```

   Then set share links to the pretty domain and redeploy (merge the PR first):

   ```bash
   gh variable set HELMSMAN_BASE_URL --body https://workshops.smalltech.in
   gh workflow run deploy-cloudrun.yml --ref main
   ```
6. **Smoke test** on the real domain: `curl -sI https://workshops.smalltech.in/ | grep -i '^server: Google Frontend'`; open `/admin` with the admin key and compare workshops with your notes; open an old facilitator link (`/f/<admin_token>`) and an old participant link (`/p/<token>`); create a workshop, join from a second browser, complete a milestone, and check the shown links start with `https://workshops.smalltech.in/`.
7. After a stable period, decommission the VM (checklist below).

## Rollback plan

At any point before the VM is decommissioned: in GoDaddy delete the `CNAME` for `workshops` and **point the GoDaddy record back to `A workshops 35.200.241.145` TTL 600**. The VM stays untouched until the user retires it, and its SQLite volume was never modified by the cutover. Data written on Cloud Run after the import is not carried back to the VM.

To redeploy the old VM deploy path from source, it is preserved in git: `git show vm-deploy-final:deploy/docker-compose.prod.yml` (and the other files of that tag). It is not part of the current tree.

For a bad application release (as opposed to the cutover), use the pipeline's automatic rollback or the manual `update-traffic` command above.

## VM decommission checklist (user-owned; not automated)

Only after a stable period on Cloud Run:

- [ ] Confirm `https://workshops.smalltech.in/` has served from Cloud Run for the agreed period and the admin list matches the import.
- [ ] Take a final copy of the VM's SQLite database (`/srv/helmsman/data/helmsman.db`) and keep it somewhere safe.
- [ ] Snapshot the VM's disk (`helmsman-c`, zone `asia-south1-c`).
- [ ] Stop the VM and watch for a few days for anything still depending on it.
- [ ] Delete the VM `helmsman-c`.
- [ ] Release the static IP `35.200.241.145` (it is no longer the rollback target once released).
- [ ] Remove any now-unused VM firewall rules and old GitHub secrets from the VM deploy.
- [ ] Delete the disk snapshot when you no longer need the safety net.
