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
2. **deploy** — keyless auth (service account `helmsman-deployer`), build and push the image tagged with the commit's first 12 characters, run the `helmsman-migrate` job to completion, deploy a **no-traffic** revision tagged `candidate`, health-check it (`/api/health`, up to ~60 s), shift 100% traffic, health-check the service URL.
3. **Rollback guard** — any failure after the previous revision was captured restores it to 100% and removes the `candidate` tag; the run ends red. The workflow never passes `--allow-unauthenticated`; `provision.sh` owns the public invoker binding.

Manual run (any branch or tag ref): `gh workflow run deploy-cloudrun.yml --ref <ref>` or Actions -> "Deploy (Cloud Run)" -> Run workflow. Inputs: `min_instances` (empty = unchanged, `0`, `1`) and `drill_rollback` (health-checks a path that 404s, so the run **must** fail and roll back — use it to prove the guard).

Repository variable `HELMSMAN_BASE_URL` (set at cutover, e.g. `https://workshop0.smalltech.in`) is passed to the service **only when non-empty**; share links then use that domain. Unset, links derive from the request. Set it with `gh variable set HELMSMAN_BASE_URL --body https://workshop0.smalltech.in`.

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
7. After a stable period, decommission the VM (checklist below).

## Rollback plan

> **Status: the VM rollback is NOT currently serving by name.** The `workshops` DNS record was deleted, and the VM's reverse proxy is still configured for the old hostname, so the VM does not answer for `workshop0.smalltech.in` until the steps below are done. The VM itself is untouched.

Rollback is possible at any point before the VM is decommissioned. **Data warning:** the VM's SQLite database is stale. Anything written to Cloud SQL after the import/cutover is not on the VM and is lost by a rollback unless you export it first (for example, run a Cloud SQL export of database `helmsman` to a bucket, or note the workshops you need to recreate).

1. **GoDaddy:** delete the `CNAME` for host `workshop0`, then add `A` · Host `workshop0` · Points to `35.200.241.145` · TTL `600`.
2. **On the VM** (`helmsman-c`, `asia-south1-c`), the reverse proxy gets its certificate for whatever `HELMSMAN_DOMAIN` says, and `HELMSMAN_BASE_URL` is derived from it (`https://${HELMSMAN_DOMAIN}`). Edit `/opt/helmsman/.env` and set:

   ```
   HELMSMAN_DOMAIN=workshop0.smalltech.in
   ```

   (it currently holds the old `workshops.smalltech.in`; keep the other values).
3. **Recreate the stack on the VM** with the compose and proxy config from the tag. The old deploy path is preserved in git, not in the current tree:

   ```bash
   git show vm-deploy-final:deploy/docker-compose.prod.yml > /opt/helmsman/docker-compose.prod.yml
   git ls-tree --name-only vm-deploy-final deploy/   # find the reverse-proxy config file the compose file mounts
   git show vm-deploy-final:deploy/<proxy-config-file> > /opt/helmsman/<proxy-config-file>
   cd /opt/helmsman && docker compose -f docker-compose.prod.yml --env-file .env up -d --force-recreate
   ```

   Compare file locations with `git show vm-deploy-final:deploy/RUNBOOK.md` (the VM layout section) before running. The proxy then obtains a certificate for `workshop0.smalltech.in`; this needs the A record from step 1 to have propagated, and takes a few minutes.
4. Verify: `curl -fsS https://workshop0.smalltech.in/api/health`, and that the response is no longer from Google (`curl -sI ... | grep -i '^server:'` should not show `Google Frontend`).

For a bad application release (as opposed to the cutover), use the pipeline's automatic rollback or the manual `update-traffic` command above.

## Naming note

The Cloud Run resources (service, jobs, database, service accounts, secrets) keep the name `helmsman`. Cloud Run services cannot be renamed in place, and nothing user-visible depends on the name: users only see `workshop0.smalltech.in`.

## VM decommission checklist (user-owned; not automated)

Only after a stable period on Cloud Run:

- [ ] Confirm `https://workshop0.smalltech.in/` has served from Cloud Run for the agreed period and the admin list matches the import.
- [ ] Take a final copy of the VM's SQLite database (`/srv/helmsman/data/helmsman.db`) and keep it somewhere safe.
- [ ] Snapshot the VM's disk (`helmsman-c`, zone `asia-south1-c`).
- [ ] Stop the VM and watch for a few days for anything still depending on it.
- [ ] Delete the VM `helmsman-c`.
- [ ] Release the static IP `35.200.241.145` (it is no longer the rollback target once released).
- [ ] Remove any now-unused VM firewall rules and old GitHub secrets from the VM deploy.
- [ ] Delete the disk snapshot when you no longer need the safety net.
