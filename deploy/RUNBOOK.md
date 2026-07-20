# Deploy Runbook — Workshop Helmsman → workshops.smalltech.in

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
docker compose -f deploy/docker-compose.yml --env-file /opt/helmsman/.env up -d --build
docker compose -f deploy/docker-compose.yml logs -f caddy   # watch cert issuance
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
4. Merge to `main`. `.github/workflows/deploy.yml` builds the image, pushes it to
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
