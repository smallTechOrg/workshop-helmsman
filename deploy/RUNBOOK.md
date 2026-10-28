# Deploy Runbook — Workshop Helmsman

## Cloud Run (current production path from Phase 7)

Workshop Helmsman runs on **Cloud Run** (service `helmsman`, project `ai-agent-boilerplate0`, region `us-central1`, 0–3 instances) against the shared **Cloud SQL** PostgreSQL instance `ai-agent-db` (database `helmsman`, user `helmsman_app`, private IP, TLS). Until the Phase 8 cutover the product URL is the service's `*.run.app` URL; `workshops.smalltech.in` and the VM (legacy sections below) are untouched. Architecture: `spec/architecture.md` §Production topology.

### One-time provisioning (idempotent)

```bash
# from the repo root; operator authenticated with `gcloud auth login`
# HELMSMAN_ADMIN_KEY / OPENROUTER_API_KEY are read from the environment or .env (never echoed)
bash deploy/cloudrun/provision.sh --dry-run    # preview
bash deploy/cloudrun/provision.sh              # prints CREATED <thing> / EXISTS <thing>; safe to re-run
```

It enables the APIs, creates the Artifact Registry repo, service accounts, the keyless GitHub WIF provider, the database/user, the `helmsman-*` secrets and their per-secret IAM, and the public-invoker binding. It may prompt once (no echo) for the shared instance's `postgres` password to grant schema privileges; that password is never stored. An existing secret is never overwritten unless you pass `--rotate <name>`.

### Deploying

Every push to `main` (and, during Phase 7 only, `feature/cloud-run-v0.1`) runs `.github/workflows/deploy-cloudrun.yml`:

1. **test** — `uv run pytest tests/unit tests/integration -q` against a `postgres:17` service container.
2. **deploy** — keyless auth (Workload Identity Federation, SA `helmsman-deployer`), build + push `us-central1-docker.pkg.dev/ai-agent-boilerplate0/helmsman/helmsman:<sha12>`, run the `helmsman-migrate` Cloud Run job (`alembic upgrade head`) to completion, deploy a **no-traffic** revision tagged `candidate`, health-check it (`/api/health`, up to ~60 s), shift 100% traffic, health-check the service URL.
3. **Rollback guard** — any failure after the previous revision was captured restores `PREV=100` and removes the `candidate` tag; the run ends red. The workflow never passes `--allow-unauthenticated` (the deployer lacks setIamPolicy): `provision.sh` pre-creates a placeholder `helmsman` service and the public `allUsers` invoker binding, so the workflow always takes the no-traffic candidate path.

Manual run: Actions -> "Deploy (Cloud Run)" -> Run workflow. Inputs: `min_instances` (empty = leave unchanged, `0`, `1`) and `drill_rollback` (health-check `/api/health-drill-404`, so the run **must** fail and roll back — use it to prove the guard).

Optional repository variable `HELMSMAN_BASE_URL` (e.g. `https://workshops.smalltech.in`, set at the Phase 8 cutover) is passed to the service so share links use that domain; unset, links derive from the request.

Migrations must stay backward-compatible with the previous revision for the one-deploy overlap window (additive first, destructive in a later release). Never raise `max-instances` without recomputing the DB pool budget: `max-instances x (pool_size + max_overflow) <= ~15`.

### Workshop mode (avoid cold starts)

```bash
# from the repo root
bash deploy/cloudrun/workshop-mode.sh on       # min-instances=1 before the workshop
bash deploy/cloudrun/workshop-mode.sh off      # min-instances=0 afterwards
bash deploy/cloudrun/workshop-mode.sh status   # min-instances=<n> max-instances=<n>
```

Equivalent one-liners:

```bash
gcloud run services update helmsman --region us-central1 --project ai-agent-boilerplate0 --min-instances 1
gcloud run services update helmsman --region us-central1 --project ai-agent-boilerplate0 --min-instances 0
```

### Operations

```bash
# from any directory (gcloud authenticated)
gcloud run services logs read helmsman --region us-central1 --project ai-agent-boilerplate0 --limit 100
gcloud run revisions list --service helmsman --region us-central1 --project ai-agent-boilerplate0
curl -fsS "$(gcloud run services describe helmsman --region us-central1 --project ai-agent-boilerplate0 --format='value(status.url)')/api/health"
# manual rollback to a known-good revision
gcloud run services update-traffic helmsman --region us-central1 --project ai-agent-boilerplate0 --to-revisions <REVISION>=100
```

### Backup

Cloud SQL automated backups / PITR are owned by the instance's owner (the instance is shared); Helmsman does not alter them. Per-database logical export (needs a bucket you own):

```bash
gcloud sql export sql ai-agent-db gs://<bucket>/helmsman-$(date +%F).sql --database=helmsman --project ai-agent-boilerplate0
```

Reverting to the VM (until it is retired in Phase 8) means pointing DNS back at it; data written on Cloud Run is not carried back.

---

# LEGACY — VM + Caddy deploy (Workshop Helmsman -> workshops.smalltech.in)

> Everything below is the **legacy VM path**. It is manual-only (`.github/workflows/deploy.yml` is `workflow_dispatch`-only) and is retired in Phase 8. It uses `docker-compose.prod.yml` and the Caddyfile; `docker-compose.yml` is now the local-dev compose.

Production is a single GCP VM running Docker Compose: the **app** container
(FastAPI serving the built Next.js frontend) behind a **Caddy** container that
terminates TLS with an automatic Let's Encrypt certificate.

```
Internet ──443──▶ Caddy (TLS for workshops.smalltech.in) ──▶ app:8001
                                                              └▶ /srv/helmsman/data (SQLite, volume)
```

Two ways to ship:
- **Manual** (§1–§5): build/run on the VM directly. Enough to go live today.
- **Automated** (§6): push to `main` → GitHub Actions builds, pushes to GHCR, and
  rolls the VM. Set up once, then every merge deploys.

---

## 1. Provision the VM (GCP)

```bash
gcloud compute instances create helmsman \
  --project=YOUR_PROJECT --zone=asia-south1-a \
  --machine-type=e2-small \
  --image-family=debian-12 --image-project=debian-cloud \
  --boot-disk-size=20GB \
  --tags=http-server,https-server

# Allow 80/443 (skip any that already exist on the network)
gcloud compute firewall-rules create allow-http  --allow=tcp:80  --target-tags=http-server
gcloud compute firewall-rules create allow-https --allow=tcp:443 --target-tags=https-server
```

`e2-small` (2 vCPU / 2 GB) is the floor for ~150 concurrent participants. Step up
to `e2-medium` (4 GB) for the 300+ target. A static external IP is recommended so
DNS never breaks:

```bash
gcloud compute addresses create helmsman-ip --region=asia-south1
gcloud compute instances delete-access-config helmsman --zone=asia-south1-a --access-config-name="external-nat"
gcloud compute instances add-access-config helmsman --zone=asia-south1-a --address=HELMSMAN_IP
```

## 2. DNS

Point the hostname at the VM's external IP, then wait for propagation:

```
Type: A    Name: workshops    Value: <VM_EXTERNAL_IP>    TTL: 300
```

Verify before continuing (TLS issuance fails if DNS isn't live):

```bash
dig +short workshops.smalltech.in    # must return the VM IP
```

## 3. Install Docker on the VM

```bash
gcloud compute ssh helmsman --zone=asia-south1-a
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"   # log out/in so the group applies
```

## 4. Configure secrets on the VM

```bash
sudo mkdir -p /opt/helmsman && sudo chown "$USER" /opt/helmsman
cd /opt/helmsman
cat > .env <<'EOF'
HELMSMAN_DOMAIN=workshops.smalltech.in
ACME_EMAIL=contact@smalltech.in
HELMSMAN_ADMIN_KEY=<A_STRONG_RANDOM_STRING_16+_CHARS>
# Optional — Phase 4 AI help-desk. Leave blank to run air-gapped.
OPENROUTER_API_KEY=
EOF
chmod 600 .env
```

Generate a strong admin key with `openssl rand -base64 24`.

## 5. First deploy (manual build on the VM)

Get the code onto the box (git clone the repo, or `scp` the `deploy/` dir plus
source). From the repo root on the VM:

```bash
docker compose -f deploy/docker-compose.prod.yml --env-file /opt/helmsman/.env up -d
docker compose -f deploy/docker-compose.prod.yml logs -f caddy   # watch cert issuance
```

Check it:

```bash
curl -fsS https://workshops.smalltech.in/api/health   # {"data":{"status":"ok","db":"ok"},...}
```

Open `https://workshops.smalltech.in/app/`, enter the admin key, run the create →
join → complete → help loop. **The first HTTPS request may take ~10–30s** while
Caddy provisions the certificate; subsequent requests are instant.

---

## 6. Automated CD (GitHub Actions → VM)

Once §1–§5 work manually, wire up hands-free deploys.

1. Create a deploy SSH keypair; put the **public** key in the VM's
   `~/.ssh/authorized_keys`, the **private** key in the repo secret `DEPLOY_SSH_KEY`.
2. Add repo secrets (Settings → Secrets and variables → Actions):
   `DEPLOY_HOST` = VM IP, `DEPLOY_USER` = your SSH user. `GITHUB_TOKEN` is
   provided automatically for GHCR.
3. Ensure `/opt/helmsman/.env` exists on the VM (from §4) — CD never ships secrets.
4. Run the `Deploy` workflow manually (Actions -> Run workflow). `.github/workflows/deploy.yml` builds the image, pushes it to
   `ghcr.io/<org>/workshop-helmsman`, copies the prod compose + Caddyfile to
   `/opt/helmsman`, pulls, and re-ups. The job fails if `/api/health` doesn't come
   back green, so a bad image won't silently take the site down.

> Note: `main` is currently the pre-rebuild branch. The rebuild lives on
> `feature/rebuild-v0.2` (PR #2). CD to production should only be armed after that
> PR merges to `main` — until then, deploy manually from the branch (§5).

---

## 7. Backup & restore

All durable state is the SQLite DB in the `helmsman-data` volume.

**Backup** (cron it):

```bash
docker compose -f docker-compose.prod.yml exec -T app \
  sh -c 'cd data && sqlite3 helmsman.db ".backup /tmp/backup.db" && cat /tmp/backup.db' \
  > "helmsman-$(date +%F).db"     # date via shell substitution on the VM
```

If the image lacks `sqlite3`, snapshot the file directly (SQLite WAL is enabled;
copy while briefly paused or use `.backup` as above):

```bash
docker run --rm -v helmsman_helmsman-data:/d -v "$PWD":/out alpine \
  cp /d/helmsman.db /out/helmsman-backup.db
```

**Restore:**

```bash
docker compose -f docker-compose.prod.yml stop app
docker run --rm -v helmsman_helmsman-data:/d -v "$PWD":/in alpine \
  cp /in/helmsman-backup.db /d/helmsman.db
docker compose -f docker-compose.prod.yml start app
```

## 8. Operations quick reference

| Task | Command (in `/opt/helmsman`) |
|------|------|
| Logs | `docker compose -f docker-compose.prod.yml logs -f app` |
| Restart app | `docker compose -f docker-compose.prod.yml restart app` |
| Roll to latest | `docker compose -f docker-compose.prod.yml pull app && docker compose -f docker-compose.prod.yml up -d` |
| Health | `curl -fsS https://workshops.smalltech.in/api/health` |
| DB size | `docker compose -f docker-compose.prod.yml exec app du -h data/helmsman.db` |

Migrations run automatically on every boot (idempotent) — no manual step.
