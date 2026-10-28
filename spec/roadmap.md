# Roadmap — Workshop Helmsman (v0.2)

Ground-up rebuild. The old `src/` and `frontend/` are **removed at scaffold**; nothing is preserved by inertia. Canonical run path (every phase): `(cd frontend && pnpm build)` → `uv run python -m src` → open **http://localhost:8001/app/**. `pnpm dev` is inner-loop only, never the test path.

**Shared scaffold (laid down by the orchestrator BEFORE any generator runs, so slices stay disjoint):** `pyproject.toml` (full Phase-1 dependency list from architecture.md §Stack), `alembic.ini`, `.env.example` (all vars from architecture.md §Environment variables), `README.md` skeleton, `.gitignore` (`data/`, `.env`, `frontend/out/`, `node_modules/`), `data/.gitkeep`, removal of the v0.1 app code. Generators never edit another slice's files; root scaffold files are edited only by the orchestrator between fan-outs.

## Phases of Development

---

## Phase 1 — Core Live Loop *(scope fixed; smallest user-testable win, first-time-right)*

**Goal:** A facilitator creates a workshop, shares the join link; 300 participants join with just a name, work content-rich milestones; the dashboard is genuinely live; one help request is submitted, answered, and seen — beautiful and rock-solid, with every future surface present as a clearly-labelled stub.

**Capabilities delivered:** C1 Workshop creation & facilitator access · C2 Frictionless participant identity (cookie auto-resume, personal links, lost-link recovery) · C3 Content-rich milestone tracking + live dashboard · C4 Help desk (manual). Plus cross-cutting: versioned coalesced polling, structured JSON logging to stdout, resilience (restart-safe, reconnect-safe), labelled stubs for broadcast/pause/AI/templates/intelligence/audit/spend.

**Independent slices (all three fan out in parallel — disjoint paths, no build dependencies):**

| Slice | Owns (exclusive paths) | Notes |
|---|---|---|
| **S1 backend** | `src/**`, `alembic/**`, `tests/conftest.py`, `tests/unit/**`, `tests/integration/**` | Full Phase-1 API per api.md; models are the **full v0.2 schema** (data-model.md) in migration `0001_initial`; snapshot cache + version counters; structlog middleware; static mount + pretty redirects; audit rows for `workshop.create`/`help.answer`/`help.resolve` |
| **S2 frontend** | `frontend/**` | All four pages + design system + StubBadge surfaces per capabilities.md; typed client + polling hook per api.md (contract-first — no backend needed to build) |
| **S3 e2e** | `tests/e2e/**`, `playwright.config.ts`, `package.json` (root), `pnpm-lock.yaml` (root) | Playwright specs written from api.md + capabilities.md. No build dependency; **runtime dependency on S1+S2 at gate time only** (specs run against the live server) |

**Key surfaces/files:** see architecture.md §Repo layout — S1: `api/{admin,facilitator,participant,health}.py`, `services/snapshots.py`, `db/models.py`, `security.py`, `observability/logging.py`; S2: `app/{page,f/page,join/page,p/page}.tsx`, `components/{ui,facilitator,participant}/`, `lib/{api,poll}.ts`; S3: `tests/e2e/core-loop.spec.ts`.

**Gate (exact commands, from repo root; once beforehand: `cp .env.example .env` and set `HELMSMAN_ADMIN_KEY`):**

```bash
uv sync
(cd frontend && pnpm install) && pnpm install && pnpm exec playwright install chromium
uv run alembic upgrade head
uv run alembic current            # MUST print a revision hash — blank output = gate failed
uv run pytest tests/unit tests/integration -q
(cd frontend && pnpm build)
grep -q '\.flex' frontend/out/_next/static/css/*.css         # styled-render: real utilities present
! grep -q '@source' frontend/out/_next/static/css/*.css      # …and no unexpanded Tailwind directives
uv run python -m src &            # live server on :8001 (leave running)
pnpm exec playwright test tests/e2e --reporter=line
kill %1
```

The e2e smoke covers the full loop against the live single-origin app: create workshop (3 milestones incl. a code block) → join as two participants in separate contexts → tracker renders styled markdown → mark complete → dashboard reflects it within one poll → help request → answer from queue → answer visible on tracker → participant resolves → **browser reload restores state (cookie)** and **the personal link opens identical state in a fresh context (cross-device)** → labelled stubs are visible and non-interactive. Integration tests additionally cover: idempotent complete/uncomplete, version-counter bumps, unchanged-poll short-circuit, server-restart state survival (new process, same DB file), and every documented error code.

**How the user tests it:** run the three commands above (sync/build/serve), open `http://localhost:8001/app/` → enter your `HELMSMAN_ADMIN_KEY` → **New workshop** → add 3 milestones with markdown + a code snippet → create → copy the join link → open it in a private window → join as "Priya" → read a milestone, mark it complete → watch the dashboard bars move within ~2 s → submit a help request from the tracker → answer it from the dashboard queue (use markdown + code) → see the badged answer appear on the tracker → mark resolved → close and reopen the private window (auto-resume) and paste the personal link into another browser (same state). **Labelled stubs (not bugs):** Broadcast, Pause, End workshop, AI toggle, Spend, stuck/bottleneck/pulse cards, Audit tab, Template library, Upcoming/Ended groups — all carry a "Coming in a later phase" pill.

---

## Phase 2 — Facilitator Command & Proactive Intelligence

**Goal:** The facilitator can steer the room — broadcast, pause, advance, reorder/edit, undo a fat-fingered action — and the dashboard tells them proactively who is stuck, where the pile-up is, and how the session is pacing.

**Capabilities delivered:** Broadcast announcements · Milestone controls (advance all/selected, pause/resume, reorder, edit/add/delete) · Undo (30 s window) · Audit trail UI · Proactive intelligence (stuck alerts, bottleneck, session pulse).

**Independent slices (parallel; no intra-phase dependencies):**

| Slice | Owns |
|---|---|
| **S1 backend** | `src/**` (facilitator endpoints, `services/{undo,intelligence}.py`, snapshot additions), `tests/unit/**`, `tests/integration/**` additions |
| **S2 frontend** | `frontend/**` — broadcast composer w/ preview + undo toast, pause states, advance controls w/ confirmation, reorder UI, audit tab, alerts/pulse cards replacing their stubs; participant banner + paused lock |
| **S3 e2e** | `tests/e2e/**` additions (command flows + undo + banner) |

**Gate (repo root; same setup):** `uv run alembic upgrade head && uv run alembic current` · `uv run pytest tests/unit tests/integration -q` · `(cd frontend && pnpm build)` · server up → `pnpm exec playwright test tests/e2e --reporter=line`. Integration tests must cover: undo inside/after the window (`undo_expired`), advance-all creating only missing completions (`source: "facilitator"`), pause blocking complete *and* uncomplete, audit rows for every action, stuck/bottleneck/pulse computed against a seeded 40-participant fixture whose expected alert set is pre-computed (not a trivially-empty fixture).

**How the user tests it:** with a live workshop + a few joined participants: send a markdown broadcast → banner appears on trackers within a poll → **Undo** within 30 s → banner gone. Pause → participant checkboxes lock with a banner. Advance-all on milestone 1 → bars jump → Undo → they revert. Reorder milestones → tracker order updates. Leave one participant idle past the stuck threshold → stuck alert card names them; the pulse card shows pace + projected finish. Open the Audit tab → every action listed who/what/when.

---

## Phase 3 — Lifecycle, Templates & Re-run

**Goal:** Workshops become sessions with a life: created from persistent templates (agenda + join form), ended into a grace period, archived read-only forever, and clonable for the next run.

**Capabilities delivered:** End/grace/archive lifecycle (lazy transitions, read-only archive views) · Clone/re-run · Agenda template library (+ save-as-template) · Join-form templates & custom join fields · Admin Home lifecycle grouping (Live/Upcoming/Ended, `starts_at`).

**Independent slices (parallel):**

| Slice | Owns |
|---|---|
| **S1 backend** | `src/**` (`services/{lifecycle,templates}.py`, admin/facilitator/participant endpoint additions), `tests/**` (py) additions |
| **S2 frontend** | `frontend/**` — template library page + pickers (replacing stubs), end-workshop dialog w/ grace hours, archive read-only styling, clone, join-form custom fields, Admin Home grouping |
| **S3 e2e** | `tests/e2e/**` additions |

**Gate (repo root):** same command sequence as Phase 2. Integration tests must cover: lazy transition on access (set `grace_until` in the past → next request archives), archived rejects every mutation with `workshop_archived` while reads still serve, template edit never mutating an instantiated workshop (snapshot proof), clone = fresh tokens + zero participants, join-form validation against the snapshot.

**How the user tests it:** save the running workshop as a template → create a new workshop from it (milestones pre-filled) → add a custom dropdown join field via a form template → join page shows it → **End workshop** with a 1-hour grace → tracker shows the grace banner, completions still work → **Archive now** → tracker and dashboard flip to read-only archive views; Admin Home shows it under Ended → **Clone** → a fresh Live workshop with the same agenda and new links.

---

## Phase 4 — AI Help-Desk

**Goal:** Help requests are triaged by AI that knows the participant's context and every past resolution: confident → instant badged auto-answer with one-tap human escalation; unsure → draft for facilitator review — fully audited, costed per workshop, per-workshop toggleable, and a zero-error no-op without an API key.

**Capabilities delivered:** AI triage & auto-answer pipeline · Escalation & transparency (AI badge, "Get a human", exact-context disclosure) · Cross-workshop learning corpus (FTS5) · Spend tracking + per-workshop toggle + air-gapped guarantee. Design is fixed in [agent.md](agent.md).

**Independent slices (parallel; S1↔S2 share only the `run_help_desk(help_request_id)` interface fixed in agent.md — no serialization needed):**

| Slice | Owns |
|---|---|
| **S1 ai-pipeline** | `src/helmsman/ai/**` (pipeline, context, corpus, openrouter client, prompts), `tests/integration/ai/**`, corpus migration (`alembic/versions/` addition) |
| **S2 backend-api** | `src/helmsman/api/**` (toggle/spend/escalate endpoints, BackgroundTask hookup in participant help POST), `src/helmsman/services/snapshots.py` (spend + AI fields), `tests/unit/**` + non-AI integration additions |
| **S3 frontend** | `frontend/**` — AI badge + escalate on tracker; draft-review block, context disclosure, spend card, AI toggle (replacing stubs) |
| **S4 e2e** | `tests/e2e/**` additions (AI auto-answer flow, escalation, air-gapped run) |

**Gate (repo root; requires the real `OPENROUTER_API_KEY` in `.env` — the gate is BLOCKED, not skipped, without it):** `uv run alembic upgrade head && uv run alembic current` · `uv run pytest tests/unit tests/integration -q` (now includes `tests/integration/ai` against the **real OpenRouter API**; the similarity fixture seeds 25+ resolved requests across ≥3 workshops with exactly one strong match asserted at rank 1 — per agent.md §Testing) · `(cd frontend && pnpm build)` · server up → `pnpm exec playwright test tests/e2e --reporter=line` (includes the real-key auto-answer journey **and** the keyless air-gapped journey with zero errors and zero AI chrome).

**How the user tests it:** with `OPENROUTER_API_KEY` set: toggle AI on → as a participant, ask something answered by the milestone content → an **AI-badged** answer appears in seconds → tap **Get a human** → request returns to the queue flagged, AI answer still visible → in the queue, expand **Context the AI used** → see progress/milestone/similar-resolutions exactly → ask something ambiguous → a violet **draft** waits in the queue; edit and send it → spend card shows real dollars. Then remove the key, restart: everything works, AI surfaces show a labelled off state, zero errors anywhere.

---

## Phase 5 — Ship It: Docker + CI/CD to GCP

**Goal:** One-command production deploy and an automated path from merge to the VM.

**Capabilities delivered:** Docker Compose packaging (multi-stage image, volume-backed SQLite, migrations on boot) · CI on GitHub Actions (tests on PR; real-key jobs guarded to runners with secrets) · CD to the GCP VM (image build → registry → compose deploy) + `deploy/RUNBOOK.md` (backup/restore of `data/`, TLS proxy note).

**Independent slices (parallel):** **S1 deploy** — `deploy/**` (Dockerfile, docker-compose.yml, RUNBOOK.md) + README deploy section · **S2 ci-cd** — `.github/workflows/**` (ci.yml, deploy.yml).

**Gate (repo root):** `docker compose -f deploy/docker-compose.yml up -d --build` · `curl -fsS http://localhost:8001/api/health` · `pnpm exec playwright test tests/e2e --reporter=line` against the container · `docker compose -f deploy/docker-compose.yml down` (volume persists; re-`up` retains data — verified by the e2e re-run finding the same workshop) · CI workflow green on the PR.

**How the user tests it:** `cp .env.example .env`, set the key(s), `docker compose -f deploy/docker-compose.yml up -d` → open `http://localhost:8001/app/` → run the Phase-1 manual loop → `docker compose restart` mid-session → participants reconnect with nothing lost. Merge a PR → watch Actions deploy it to the VM.

---

## Phase 6 — Public Landing Page & Self-Service Workshop Creation

**Goal:** A stranger lands on `/`, understands the product, and creates and runs their own workshop with full facilitator powers — never touching an access key — while the admin keeps the only cross-workshop view and can see who created what.

**Capabilities delivered:** C5 Public landing page · C6 Self-service workshop creation (keyless, email as the last step before the link reveal, localStorage "your workshops") · C7 Admin oversight of public workshops (origin badge + creator email; console moves to `/app/admin/` with a pretty `/admin`).

**Non-goals for this phase (explicit):** no accounts, no login, no email sending or verification, no rate limiting, no creation cap, no captcha, no reduced facilitator tier for public creators. Accepted risk recorded in [architecture.md](architecture.md) §Auth model.

**Independent slices (all three fan out in parallel — disjoint owned paths, no build dependencies):**

| Slice | Owns (exclusive paths) | Delivers |
|---|---|---|
| **S1 backend** | `src/**`, `alembic/versions/0004_public_creation.py`, `tests/unit/**`, `tests/integration/**` | New `services/workshops.py` creation service extracted from `api/admin.py` (single implementation, both callers); new `api/public.py` with keyless `POST /api/public/workshops`; `creator_email` + `created_via` on the model and on both admin responses; `GET /` serves `frontend/out/index.html` via `FileResponse` (307 fallback when unbuilt) + `GET /admin` → 307 `/app/admin/`; migration `0004` (batch mode) |
| **S2 frontend** | `frontend/**` | Landing page at `frontend/app/page.tsx` (C5); Admin Home relocated to `frontend/app/admin/page.tsx` unchanged in behaviour (C7 badges + email added); new `frontend/app/create/page.tsx` (C6) reusing the composer extracted into `frontend/components/create/` shared by both; `lib/localWorkshops.ts`; `lib/api.ts` gains `createPublicWorkshop` |
| **S3 e2e** | `tests/e2e/**` (whole directory) | New `landing.spec.ts` + `public-creation.spec.ts` (keyless create→join→live journey and the admin-sees-it check); plus the **mechanical URL migration** of the existing specs — `smoke.spec.ts` (`GET /` is now 200 HTML, not a redirect into `/app/`) and every `goto(\`${APP_BASE}/\`)` Admin-Home navigation in `core-loop.spec.ts` and `facilitator-command.spec.ts` → `` `${APP_BASE}/admin/` ``. No build dependency; **runtime dependency on S1+S2 at gate time only** |

> **Assumed:** S3 owns the entire `tests/e2e/` directory this phase, because the Admin-Home relocation and the `/` behaviour change mechanically touch three existing specs (`smoke`, `core-loop`, `facilitator-command`) plus `helpers.ts`. No other slice may edit anything under `tests/e2e/`. These are the **only** permitted changes to existing e2e specs — assertions and journeys stay identical apart from the URL.

**Key surfaces/files** — S1: `src/helmsman/services/workshops.py`, `src/helmsman/api/{public,admin,__init__}.py`, `src/helmsman/db/models.py` (Workshop), `alembic/versions/0004_public_creation.py`, `tests/integration/test_public_creation.py`, `tests/unit/test_creator_email.py`. S2: `frontend/app/{page,admin/page,create/page}.tsx`, `frontend/components/create/WorkshopComposer.tsx`, `frontend/components/landing/*`, `frontend/lib/{api,localWorkshops}.ts`. S3: `tests/e2e/{landing,public-creation}.spec.ts`.

**Gate (exact commands, from repo root; `.env` already has `HELMSMAN_ADMIN_KEY`):**

```bash
uv sync
(cd frontend && pnpm install) && pnpm install && pnpm exec playwright install chromium
uv run alembic upgrade head
uv run alembic current            # MUST print 0004 — blank output or 0003 = gate failed
uv run pytest tests/unit tests/integration -q   # ALL pre-existing tests must still pass
(cd frontend && pnpm build)
test -f frontend/out/index.html                              # landing page is the export root
test -f frontend/out/create/index.html                       # public create route exported
test -f frontend/out/admin/index.html                        # admin console relocated
grep -q '\.flex' frontend/out/_next/static/css/*.css         # styled-render: real utilities present
! grep -q '@source' frontend/out/_next/static/css/*.css      # …and no unexpanded Tailwind directives
uv run python -m src &            # live server on :8001 (leave running)
sleep 3
curl -fsS -o /dev/null -w '%{http_code}\n' http://localhost:8001/ | grep -qx 200   # / is the page, not a 307
curl -fsS http://localhost:8001/ | grep -q 'data-testid="landing-cta"'             # hero CTA present in the served HTML
curl -fsS -o /dev/null -w '%{http_code}\n' http://localhost:8001/admin | grep -qx 307
pnpm exec playwright test tests/e2e --reporter=line          # includes ALL pre-existing specs
kill %1
```

**Gate conditions beyond the commands:** every pre-existing unit and integration test passes with exactly **one** permitted Python edit — `tests/integration/test_redirects.py`, whose parametrized redirect list drops `("/", "/app/")` (no longer a redirect) and gains `("/admin", "/app/admin/")`; the same file gains a `/` case asserting 200 `text/html` when `frontend/out/index.html` exists and the documented 307 `/app/` fallback when it does not. No other Python test may be edited. Every pre-existing e2e spec passes with only the mechanical URL migration described in the S3 row (Admin Home `/app/` → `/app/admin/`, and `GET /` now 200 HTML); no e2e assertion or journey may be weakened or deleted. Integration tests must cover: public create with a valid email → row with `created_via="public"` and the stored email · the same body with a missing / blank / malformed email (`"a@b"`, `"no-at.example.com"`, `" "`) → 422 `validation_error` **and zero rows created** · public create with no `X-Admin-Key` header succeeds while `POST /api/admin/workshops` without it still returns 401 `invalid_admin_key` · a public-created workshop's `admin_token` exercises three facilitator mutations (broadcast, pause, milestone advance) successfully — parity proof · that token returns 404 for a *different* workshop's ids — isolation proof · `GET /api/admin/workshops` returns `created_via` and `creator_email` for both origins · admin create still returns `created_via="admin"`, `creator_email: null` · the email never appears in any facilitator/participant/poll payload (assert on the serialized JSON) · `GET /` returns 200 HTML and `GET /admin` returns 307.

**How the user tests it:** run the build and server commands above, then open **http://localhost:8001/** in a fresh private window — read the marketing page top to bottom (hero, features, how-it-works, FAQ; there is no "Your workshops" section yet and no admin link anywhere). Click **"Create your workshop — free, no signup"** → compose a workshop with 3 milestones including a markdown list and a fenced code block → on the last step enter your email (try a bad one first: it is rejected inline and nothing is created) → **Create workshop** → the success screen shows your dashboard link (with the "this is the only key — save it" warning) and your join link. Copy the join link, open it in a *second* browser, join as "Priya", mark a milestone complete → back in the first browser, open your dashboard: Priya is there and her progress moves within ~2 s. Confirm you have the full toolset — send a broadcast, pause, advance, open the audit tab, export CSV — nothing is locked. Return to **http://localhost:8001/** in the first browser: **Your workshops** now lists it with working quick links. Finally open **http://localhost:8001/admin**, enter your `HELMSMAN_ADMIN_KEY`, and see that same workshop in the full list with a **Public** badge and the email you typed. You never entered an access key at any point before that. **Nothing on this phase is a stub** — every surface it adds is real.

---

## Phase 7 — Helmsman runs on Cloud Run + Cloud SQL (fresh database)

**Goal:** The same product, unchanged, runs in production on Cloud Run against the shared Cloud SQL PostgreSQL instance (own database `helmsman`, empty), deployed by a fully automated, keyless GitHub Actions pipeline with a rollback guard. Reachable at the `*.run.app` URL; `workshops.smalltech.in` and the VM keep serving real traffic untouched.

**Capabilities delivered:** Stateless multi-instance serving (PostgreSQL storage, memo dropped, DB-side `last_seen_at` throttle) · PostgreSQL parity for tests and migrations (Rule 5) · Cloud Run + Cloud SQL deploy pipeline (idempotent provisioning, WIF, migrate job, no-traffic revision, health-checked traffic shift, rollback) · Workshop mode (`min-instances` toggle). Architecture in [architecture.md](architecture.md) §Production topology.

**Non-goals:** no data migration (Phase 8), no domain mapping (Phase 8), no VM changes, no behaviour change, no new UI (nothing in this phase is a stub — there is no UI work; the existing UI is exercised by the existing e2e suite).

**Spec-level behaviour changes (implement exactly):**
1. `services/snapshots.py`: delete `_cache`, `_memoized`, `clear_snapshot_cache`, `SNAPSHOT_TTL_SECONDS`, `_monotonic`; `participant_shared_snapshot` / `dashboard_snapshot` call their builders directly. Leave a comment at the removal site containing the literal sentence: `revisit if load testing shows snapshot build is a bottleneck; key was (workshop_id, state_version)`. `bump_*_version` and the `v == state_version → {"changed": false}` fast path are untouched.
2. `api/participant.py::_touch_last_seen(session, participant_id)` becomes one Core statement: `UPDATE participant SET last_seen_at=:now WHERE id=:id AND last_seen_at < :now - LAST_SEEN_TOUCH_SECONDS` (`now` = app UTC clock, bound as a parameter so it is portable to SQLite). No read-then-write.
3. `db/session.py`: PostgreSQL engine with `pool_size/max_overflow` from `HELMSMAN_DB_POOL_SIZE` (3) / `HELMSMAN_DB_MAX_OVERFLOW` (2), `pool_timeout=10`, `pool_recycle=1800`, `pool_pre_ping=True`; SQLite branch unchanged. `settings.py` normalises `postgres://`/`postgresql://` → `postgresql+psycopg://` and adds the two pool settings. `psycopg[binary]>=3.2` added to `pyproject.toml` and `uv.lock`.
4. `src/__main__.py`: `uvicorn.run(..., proxy_headers=True, forwarded_allow_ips="*")`; `observability/logging.py`: add a `severity` key (mapped from level) to every JSON line.
5. `deploy/entrypoint.sh`: `migrate` subcommand; boot-time `alembic upgrade head` only when `HELMSMAN_MIGRATE_ON_BOOT` is `1`/`true` (default `1`).

**Independent slices** (all fan out concurrently, disjoint exclusive paths; the only true dependency is marked):

| Slice | Owns (exclusive paths) | Delivers |
|---|---|---|
| **S1a db-engine** | `src/helmsman/db/session.py`, `src/helmsman/config/settings.py`, `src/__main__.py`, `src/helmsman/observability/logging.py`, `pyproject.toml`, `uv.lock`, `tests/unit/test_settings.py`, new `tests/unit/test_db_engine.py` | Spec items 3, 4; unit tests for URL normalisation, pool kwargs on PG vs none on SQLite, `severity` key |
| **S1b stateless-serving** | `src/helmsman/services/snapshots.py`, `src/helmsman/api/participant.py`, `tests/unit/test_snapshot_helpers.py`, `tests/unit/test_last_seen_throttle.py`, `tests/integration/test_dashboard_details.py` | Spec items 1, 2; tests rewritten without the cache/clock hooks: two consecutive snapshot builds both see a data change made without a version bump; throttle: poll with `last_seen_at` 30 s old → row unchanged, 90 s old → advanced, two instances' sessions polling at once → exactly one effective update |
| **S1c postgres-test-harness** | `tests/conftest.py`, `alembic/**`, `tests/integration/test_migration.py`, `tests/integration/test_restart_survival.py`, `tests/integration/test_public_creation.py`, `tests/integration/test_intelligence_fixture.py`, `.github/workflows/ci.yml` | `conftest.py`: requires `TEST_DATABASE_URL` (clear error pointing at the README if unset; **refuses any database whose name does not end in `_test`**; no SQLite fallback); session-scoped fixture drops/recreates schema `public` and runs `alembic upgrade head`; per-test autouse `TRUNCATE … RESTART IDENTITY CASCADE` over all app tables; no `clear_snapshot_cache` call. `test_migration.py` runs the same assertions on a scratch database it creates/drops (`<name>_mig_<uuid>`), plus PostgreSQL-specific: `alembic upgrade head` twice is a no-op, `downgrade base` then `upgrade head` round-trips. Other listed tests: replace SQLite-file URLs with `TEST_DATABASE_URL`. `alembic/env.py`/versions fixed if any migration fails on PostgreSQL. `ci.yml`: `postgres:17` service container + `TEST_DATABASE_URL` + e2e job on Postgres (architecture.md §Deploy shape); add `feature/cloud-run-v0.1` to the push branches |
| **S1d postgres-parity-fixes** *(serialized: starts after S1a + S1c land; needs a runnable PG suite)* | `src/helmsman/api/**` **except** `participant.py`, `src/helmsman/services/**` **except** `snapshots.py`, `src/helmsman/db/models.py` | Fix every app defect the PostgreSQL suite exposes (ordering, case-sensitivity, GROUP BY strictness, aware/naive datetimes, boolean/int coercion). Tests are never weakened to pass |
| **S2a provisioning** | `deploy/cloudrun/provision.sh`, `deploy/cloudrun/dbinit.py`, `deploy/cloudrun/workshop-mode.sh` | Idempotent (check-then-create) `provision.sh` for, in order: required APIs (`run`, `artifactregistry`, `secretmanager`, `sqladmin`, `iamcredentials`) · Artifact Registry repo `helmsman` · SAs `helmsman-run`, `helmsman-deployer` · WIF provider `helmsman-github` (+ attribute condition) and `workloadIdentityUser` binding · DB `helmsman` + user `helmsman_app` · secrets `helmsman-database-url`, `helmsman-openrouter-api-key`, `helmsman-admin-key` (stdin only; values from the operator's exported `HELMSMAN_ADMIN_KEY` / `OPENROUTER_API_KEY`, else read from `.env` without echoing; an existing secret is never overwritten unless `--rotate <name>`) · per-secret IAM · dbinit job (schema privilege probe + grant, see architecture.md) · placeholder Cloud Run service `helmsman` created if absent (image `us-docker.pkg.dev/cloudrun/container/hello`, runtime SA `helmsman-run`, min 0 / max 3; an existing service is never modified) · public invoker IAM binding (`allUsers` → `roles/run.invoker` on service `helmsman`) applied by `provision.sh` itself, guarded by an "already bound" check; the **workflow never passes `--allow-unauthenticated`** (the deployer has only `run.developer`, no setIamPolicy) and always takes the no-traffic candidate path (if an org policy blocks `allUsers`, provisioning fails loudly with that cause). Every created thing prints `CREATED <what>`; every pre-existing thing prints `EXISTS <what>`; exit non-zero on any failure; `--dry-run` prints what it would do. Never reads or modifies resources not prefixed/owned `helmsman`. `workshop-mode.sh on|off|status` (status prints `min-instances=<n> max-instances=<n>`) |
| **S2b image** | `deploy/Dockerfile`, `deploy/entrypoint.sh`, `deploy/docker-compose.yml` | Spec item 5; Dockerfile copies `deploy/cloudrun/dbinit.py`; image works for both compose and Cloud Run (listens on `$PORT`). `docker-compose.yml` is today the *Caddy production* compose (requires `HELMSMAN_DOMAIN`/`ACME_EMAIL`): it is rewritten here to the **local-dev** shape — `app` service only, no Caddy service/volumes, no `HELMSMAN_DOMAIN`/`ACME_EMAIL` requirement, `HELMSMAN_BASE_URL` optional, SQLite volume, `HELMSMAN_MIGRATE_ON_BOOT=1`, port `8001:8001` published. (The separate `docker-compose.prod.yml` + `Caddyfile` used by the VM workflow are left untouched until Phase 8.) |
| **S2c workflows** | `.github/workflows/deploy-cloudrun.yml`, `.github/workflows/deploy.yml` | New workflow (below). `deploy.yml` (VM) triggers reduced to `workflow_dispatch` only (so a push to `main` deploys **only** Cloud Run; the VM path is manual-only until Phase 8 deletes it) |
| **S2d docs-env** | `README.md`, `.env.example`, `deploy/RUNBOOK.md` | README: Postgres test setup (`brew install postgresql@17`, `createdb helmsman_test`, `TEST_DATABASE_URL`), every command `uv run`-prefixed with explicit working directory, "Deploying to Cloud Run" + workshop-mode one-liners; `.env.example` gains `TEST_DATABASE_URL`, `HELMSMAN_DB_POOL_SIZE`, `HELMSMAN_DB_MAX_OVERFLOW`, `HELMSMAN_MIGRATE_ON_BOOT`; RUNBOOK gains a top-level "Cloud Run (current production path from Phase 7)" section pointing at provision/deploy/workshop-mode (full rewrite is Phase 8; VM sections stay, marked legacy) |

**`deploy-cloudrun.yml` contract (S2c):** name `Deploy (Cloud Run)`; triggers `push: branches: [main, feature/cloud-run-v0.1]` (the feature branch is a Phase-7-only trigger so the real deploy can be gated before merge; Phase 8 removes it) and `workflow_dispatch` with inputs `min_instances` (choice `""`/`0`/`1`, default unchanged) and `drill_rollback` (boolean, default false); `permissions: {contents: read, id-token: write}`; `concurrency: {group: deploy-cloudrun, cancel-in-progress: false}`; env `PROJECT_ID=ai-agent-boilerplate0`, `REGION=us-central1`, `SERVICE=helmsman`. Jobs in order: **test** (Postgres service container, `uv run pytest tests/unit tests/integration -q`) → **deploy** (`google-github-actions/auth@v2` with the WIF provider `projects/870371939888/locations/global/workloadIdentityPools/github/providers/helmsman-github` + SA `helmsman-deployer@ai-agent-boilerplate0.iam.gserviceaccount.com`; `setup-gcloud`; `gcloud auth configure-docker us-central1-docker.pkg.dev`; docker buildx build+push `…/helmsman/helmsman:${GITHUB_SHA::12}`; capture `PREV` revision; deploy/update job `helmsman-migrate`; `gcloud run jobs execute helmsman-migrate --wait`; `gcloud run deploy helmsman --no-traffic --tag candidate --revision-suffix sha-${GITHUB_SHA::12}` with the sizing, VPC and `--set-secrets` flags from architecture.md and env `HELMSMAN_MIGRATE_ON_BOOT=0`; health-check candidate URL (path `/api/health`, or `/api/health-drill-404` when `drill_rollback`); shift traffic; health-check service URL; `if: failure()` step restores `PREV=100` and removes the `candidate` tag). No stored GCP keys anywhere; no secret values in logs. The real-key tests in the `test` job are skipped when their secrets are absent (guarded), PostgreSQL ones never are.

**Key surfaces/files:** listed per slice above.

**Gate (exact commands; from repo root; operator is `gcloud`- and `gh`-authenticated; `.env` holds `HELMSMAN_ADMIN_KEY` and `OPENROUTER_API_KEY`; never echo them):**

```bash
# --- one-time local prerequisite (PostgreSQL 17, harness Rule 5) ---
brew install postgresql@17 && brew services start postgresql@17
createdb helmsman_test
export TEST_DATABASE_URL="postgresql+psycopg://$USER@localhost:5432/helmsman_test"

# --- backend on PostgreSQL ---
uv sync
uv run python -c "import psycopg"
DATABASE_URL="$TEST_DATABASE_URL" uv run alembic upgrade head
DATABASE_URL="$TEST_DATABASE_URL" uv run alembic current      # MUST print a revision hash (head) — blank = failed
uv run pytest tests/unit tests/integration -q                  # whole suite, on PostgreSQL, zero failures, no test weakened
! grep -nE '_memoized|clear_snapshot_cache|SNAPSHOT_TTL_SECONDS|_cache:' src/helmsman/services/snapshots.py
grep -q 'revisit if load testing shows snapshot build is a bottleneck; key was (workshop_id, state_version)' src/helmsman/services/snapshots.py
! git grep -nE 'helmsman_app:[A-Za-z0-9]{16,}@'                # no committed credentials

# --- frontend + e2e locally on PostgreSQL ---
(cd frontend && pnpm install && pnpm build) && pnpm install && pnpm exec playwright install chromium
DATABASE_URL="$TEST_DATABASE_URL" uv run python -m src &
sleep 3 && pnpm exec playwright test tests/e2e --reporter=line ; kill %1

# --- script hygiene ---
bash -n deploy/cloudrun/provision.sh && bash -n deploy/cloudrun/workshop-mode.sh && (command -v shellcheck >/dev/null && shellcheck deploy/cloudrun/*.sh || true)
docker compose -f deploy/docker-compose.yml config -q          # local compose is valid with no HELMSMAN_DOMAIN/ACME_EMAIL set
! grep -qi caddy deploy/docker-compose.yml

# --- real provisioning, twice (idempotency proof) ---
bash deploy/cloudrun/provision.sh                              # first run creates; may prompt once (no echo) for the shared instance's postgres password
bash deploy/cloudrun/provision.sh | tee /dev/stderr | grep -c '^CREATED' | grep -qx 0   # second run creates nothing

# --- real deploy through the pipeline ---
git push origin HEAD
gh workflow run deploy-cloudrun.yml --ref feature/cloud-run-v0.1
sleep 10; RUN=$(gh run list --workflow=deploy-cloudrun.yml --limit 1 --json databaseId -q '.[0].databaseId')
gh run watch "$RUN" --exit-status
URL=$(gcloud run services describe helmsman --region us-central1 --project ai-agent-boilerplate0 --format='value(status.url)')
curl -fsS "$URL/api/health" | grep -q '"db":"ok"'              # proves VPC egress + TLS + secrets + migrations
set -a; . ./.env; set +a                                       # HELMSMAN_ADMIN_KEY only needs to equal the value provisioned into helmsman-admin-key
BASE_URL="$URL" pnpm exec playwright test tests/e2e --reporter=line   # full e2e journey against the REAL deployment

# --- rollback-guard drill: a failing candidate must leave the old revision serving ---
PREV=$(gcloud run services describe helmsman --region us-central1 --project ai-agent-boilerplate0 --format='value(status.traffic[0].revisionName)')
gh workflow run deploy-cloudrun.yml --ref feature/cloud-run-v0.1 -f drill_rollback=true
sleep 10; RUN=$(gh run list --workflow=deploy-cloudrun.yml --limit 1 --json databaseId -q '.[0].databaseId')
! gh run watch "$RUN" --exit-status                            # run MUST fail
test "$(gcloud run services describe helmsman --region us-central1 --project ai-agent-boilerplate0 --format='value(status.traffic[0].revisionName)')" = "$PREV"
curl -fsS "$URL/api/health" | grep -q '"db":"ok"'              # old revision still serves

# --- workshop mode ---
bash deploy/cloudrun/workshop-mode.sh on  && bash deploy/cloudrun/workshop-mode.sh status | grep -q 'min-instances=1'
bash deploy/cloudrun/workshop-mode.sh off && bash deploy/cloudrun/workshop-mode.sh status | grep -q 'min-instances=0'

# --- VM path must not deploy on push ---
! grep -nE '^\s*push:' .github/workflows/deploy.yml
```

**Gate conditions beyond the commands:** the PostgreSQL suite must include (and S1b/S1c must have written) — the throttle test with 30 s/90 s fixtures and a concurrent double-poll proving a single effective update; snapshot freshness without a version bump; `alembic upgrade head` idempotency and downgrade round-trip on PostgreSQL; a poll-burst integration test (≥ 300 participants seeded, 300 sequential state polls after one completion, all payloads identical in `leaderboard` and `version`, proving the memo-free path is correct at the stated scale — the fixture is large enough that a truncated/sampled leaderboard would be observably different). The e2e journey against the real deployment is the Rule-6 golden path and asserts rendered content.

**How the user tests it:** open the `*.run.app` URL the workflow prints (or `gcloud run services describe helmsman --region us-central1 --project ai-agent-boilerplate0 --format='value(status.url)'`). The very first load after idle may take a few seconds (cold start, `min-instances=0`) — expected, not a bug. Then the normal loop: landing page → **Create your workshop** → 3 milestones → copy the join link → join as "Priya" in a private window → complete a milestone → dashboard moves within ~2 s → help request → answer → join link and personal link shown are `https://…run.app/…` (not `http://`, not `localhost`). Reload and open the personal link in another browser: same state. Open `/admin` with your admin key: the workshop is listed. Stop and re-open the page after a few minutes idle to see scale-to-zero recover with all data intact (it is in Cloud SQL). `workshops.smalltech.in` still shows the old VM — that is intentional until Phase 8. **Labelled stubs: none** (no UI changes this phase). Data created here is throw-away: Phase 8 replaces it.

---

## Phase 8 — Cutover: data import, `workshops.smalltech.in`, retire the VM path

**Goal:** Production traffic and data move from the VM to Cloud Run: the VM's SQLite data is imported into Cloud SQL with verified counts, `workshops.smalltech.in` serves from Cloud Run, the Caddy/VM deploy path is removed from the repo, and docs describe the new reality. The VM itself is left running and untouched until the user decommissions it.

**Capabilities delivered:** SQLite → PostgreSQL data import with per-table verification and sequence reset · Domain mapping with exact DNS instructions (human gate) · VM deploy path retirement + rewritten RUNBOOK/README + rollback plan.

**Independent slices (all concurrent; disjoint paths; the only coupling is at gate time, marked):**

| Slice | Owns (exclusive paths) | Delivers |
|---|---|---|
| **S1 import-script** | `scripts/sqlite_to_postgres.py`, `scripts/make_import_fixture.py`, `tests/integration/test_sqlite_to_postgres.py` | CLI `uv run python scripts/sqlite_to_postgres.py --sqlite PATH [--target-url URL \| env TARGET_DATABASE_URL] [--replace] [--batch-size 500]`. Behaviour: opens the source **read-only** (`file:PATH?mode=ro`, `uri=True`); aborts unless the source's `alembic_version` equals the target's (print how to upgrade the scratch copy); aborts if the target has rows in any app table unless `--replace` (which prints per-table counts it will delete, then `TRUNCATE … RESTART IDENTITY CASCADE`); copies every app table in FK order (`Base.metadata.sorted_tables`) in batches, naive SQLite datetimes interpreted as UTC, ints → bool; in **one transaction** (all-or-nothing); then resets each serial/identity sequence to `max(id)` (`setval(pg_get_serial_sequence(t,'id'), COALESCE(max(id),1), max(id) IS NOT NULL)`); then verifies per-table `COUNT(*)` source vs target and FK orphan checks, prints a table, exits non-zero on any mismatch (and rolls back). Never prints row data (PII). `make_import_fixture.py --out PATH` builds a SQLite DB through the real app: 3 workshops, **≥ 300 participants** in one, ≥ 900 completions, help requests with answers, broadcasts, audit rows — more rows than one batch, so batching/ordering bugs change the counts. Tests (PostgreSQL via `TEST_DATABASE_URL`): counts equal per table; a spot-checked workshop's leaderboard payload from the API over the imported DB equals the same payload over the SQLite source; a fresh insert after import gets an id greater than the max imported id (sequence reset proof); non-empty target without `--replace` aborts and changes nothing; mismatching alembic revision aborts; forced mid-copy failure leaves the target empty (atomicity) |
| **S2 import-tooling** | `deploy/cloudrun/import-data.sh`, `deploy/Dockerfile` | Dockerfile adds `COPY scripts/ ./scripts/`. `import-data.sh --sqlite PATH [--db helmsman] [--replace] [--drop-after]`: (1) creates a temporary private GCS bucket `ai-agent-boilerplate0-helmsman-import-<rand>` (uniform access, deleted on exit via trap) and uploads the SQLite file; (2) creates/updates Cloud Run Job `helmsman-import` from the **currently deployed image** with VPC egress, runtime SA `helmsman-run` (granted `objectViewer` on that bucket only, revoked with the bucket), the bucket mounted read-only at `/import` (`--add-volume type=cloud-storage`), `DATABASE_URL` from `helmsman-database-url` with the database name swapped when `--db` ≠ `helmsman` (for scratch DBs, which the script creates through `helmsman_app` and `--drop-after` removes), command `scripts/sqlite_to_postgres.py --sqlite /import/<file>` (+ `--replace`); (3) executes with `--wait`, streams the verification table from the job logs, exits non-zero on failure; (4) deletes bucket + job. Also `--pull-from-vm`: runs, read-only against the source, `gcloud compute ssh helmsman-c --zone asia-south1-c -- "<online consistent copy>"` where the copy is made with SQLite's backup API against the live volume file `/srv/helmsman/data/helmsman.db` (via `sqlite3 … ".backup /tmp/helmsman-export.db"`, or a throw-away `python:3.12-slim` container mounting the volume read-only if `sqlite3` is absent), then `gcloud compute scp` to a local scratch dir (`mktemp -d`, mode 700, removed on exit). Nothing on the VM is stopped, edited or deleted other than the temp export file it created |
| **S3 domain-mapping** | `deploy/cloudrun/domain-map.sh` | `domain-map.sh [--wait]`: checks `gcloud domains list-user-verified` includes `smalltech.in` (else prints the Search Console TXT verification step and exits 2); creates the mapping if absent (`gcloud beta run domain-mappings create --service helmsman --domain workshops.smalltech.in --region us-central1`); prints the DNS records exactly as returned by `domain-mappings describe` (`resourceRecords`); `--wait` polls (10 s, 90 min cap) until `Ready=True`/`CertificateProvisioned=True`, then `curl -fsS https://workshops.smalltech.in/api/health` |
| **S4 retire-vm-path** | `deploy/docker-compose.prod.yml` (delete), `deploy/Caddyfile` (delete), `.github/workflows/deploy.yml` (delete), `.github/workflows/deploy-cloudrun.yml` | Orchestrator first tags the commit `vm-deploy-final` (so the VM path stays recoverable from git). `deploy-cloudrun.yml`: remove the `feature/cloud-run-v0.1` push trigger; pass `HELMSMAN_BASE_URL=${{ vars.HELMSMAN_BASE_URL }}` (GitHub repository *variable*, unset/empty ⇒ links derive from the request) to the service deploy — a variable rather than a hard-coded value so share links never point at `workshops.smalltech.in` before the DNS flip; the user sets it in cutover step 5 |
| **S5 docs** | `README.md`, `deploy/RUNBOOK.md`, `.env.example` | RUNBOOK rewritten end-to-end for Cloud Run: topology diagram, `provision.sh`, the pipeline, **workshop mode** (before/after one-liners + `workshop-mode.sh`, and the advice to run `on` at least 10 minutes before a workshop and rehearse with the actual participant count), cold-start expectation, logs (`gcloud run services logs read helmsman …`), DB backup (`gcloud sql export sql …`), connection-budget rule (never raise `max-instances` without recomputing), cutover procedure (below), rollback plan, VM decommission checklist (user-owned: snapshot the disk, then delete VM + static IP). README: Cloud Run production section; compose documented as local-only; all commands `uv run`-prefixed with explicit working directories; no mention of Caddy/GHCR as the production path |

**Cutover procedure (documented in RUNBOOK; the human gate):**

1. *Day before:* in GoDaddy lower the TTL of the existing `workshops` record to 600 s. Choose a window with **no live workshop** (the DNS flip and certificate issuance cause a short HTTPS gap, up to ~30–60 min, and writes landing on the VM after the final import are not carried over).
2. `bash deploy/cloudrun/import-data.sh --pull-from-vm --replace` — copies the VM data read-only, imports into Cloud SQL (wiping the throw-away Phase-7 data), prints the verification table; every row must say `OK`.
3. `bash deploy/cloudrun/domain-map.sh` — creates the mapping and prints the records to set.
4. **GoDaddy DNS for `smalltech.in` (manual):** delete the existing `A` record for host `workshops` (`35.200.241.145`) and any `AAAA` for `workshops` (a CNAME cannot coexist with them), then add **`CNAME` · Host `workshops` · Points to `ghs.googlehosted.com` · TTL 600**. If `domain-map.sh` reports the domain is unverified, first add the `TXT` record at host `@` that it prints (`google-site-verification=…`) and re-run it. If `domain-mappings describe` ever shows different `resourceRecords`, those win.
5. `bash deploy/cloudrun/domain-map.sh --wait` until the certificate is provisioned and the HTTPS health check passes. Then `gh variable set HELMSMAN_BASE_URL --body https://workshops.smalltech.in` and `gh workflow run deploy-cloudrun.yml --ref main` (merge the PR first) so share links use the pretty domain.
6. Smoke on the real domain (user test below). **Rollback at any point before step 7:** set the GoDaddy record back to `A workshops 35.200.241.145` (TTL 600); the VM and its SQLite volume were never modified.
7. After a stable period the user decommissions the VM (RUNBOOK checklist). Not automated, not required for this phase to pass.

**Gate (exact commands; repo root; `TEST_DATABASE_URL` as in Phase 7; operator authenticated to `gcloud`/`gh`; the Phase-7 pipeline has deployed the Phase-8 branch so the image contains `scripts/`):**

```bash
uv sync
uv run pytest tests/unit tests/integration -q                                  # whole suite incl. test_sqlite_to_postgres.py, on PostgreSQL
bash -n deploy/cloudrun/import-data.sh && bash -n deploy/cloudrun/domain-map.sh && (command -v shellcheck >/dev/null && shellcheck deploy/cloudrun/*.sh || true)
test ! -e deploy/Caddyfile && test ! -e deploy/docker-compose.prod.yml && test ! -e .github/workflows/deploy.yml
! grep -rnIiE 'ghcr\.io|appleboy|caddy' README.md deploy .github .env.example
grep -q 'ghs.googlehosted.com' deploy/RUNBOOK.md && grep -q 'min-instances' deploy/RUNBOOK.md
! grep -n 'feature/cloud-run-v0.1' .github/workflows/deploy-cloudrun.yml
git ls-files | grep -qx 'deploy/docker-compose.yml'                            # local compose is kept
docker compose -f deploy/docker-compose.yml config -q
# deploy the Phase-8 branch so the image contains scripts/ (Phase 7 is merged, so dispatch on a branch ref works)
git push origin HEAD && gh workflow run deploy-cloudrun.yml --ref "$(git rev-parse --abbrev-ref HEAD)"
sleep 10; RUN=$(gh run list --workflow=deploy-cloudrun.yml --limit 1 --json databaseId -q '.[0].databaseId'); gh run watch "$RUN" --exit-status
# real end-to-end rehearsal of the import path on a SCRATCH database (never touches `helmsman`):
SCRATCH=$(mktemp -d) && uv run python scripts/make_import_fixture.py --out "$SCRATCH/fixture.db"
bash deploy/cloudrun/import-data.sh --sqlite "$SCRATCH/fixture.db" --db helmsman_import_check --drop-after   # must print all tables OK and exit 0
```

(After the automated gate passes, the user runs the cutover procedure above; the phase is accepted only on the user's "Yes" after the smoke test.)

**How the user tests it:** follow the cutover procedure in `deploy/RUNBOOK.md`. After DNS settles, open **https://workshops.smalltech.in/** in a private window: the landing page loads over HTTPS from Cloud Run (response header `server: Google Frontend`; `curl -sI https://workshops.smalltech.in/ | grep -i '^server: Google Frontend'`). Open `/admin` with your admin key: **every workshop that existed on the VM is listed with the same names, statuses and participant counts** you noted before the cutover (the import's verification table printed the same numbers). Open an old facilitator link (`/f/<admin_token>`) and an old personal participant link (`/p/<token>`) saved from before: both open with identical state — tokens survive the migration. Create a new workshop, join it from a second browser, complete a milestone: the dashboard updates within ~2 s and the links shown start with `https://workshops.smalltech.in/`. Before a real workshop run `bash deploy/cloudrun/workshop-mode.sh on`; afterwards `off`. **Nothing is a stub.** Rollback is the one DNS edit in step 6.

---

## Phase-gate constants (every phase)

Working tree clean and pushed · README updated and its commands re-run verbatim · human test-handoff published and approved before the next phase · qa-auditor sign-off per slice · no phase starts while the previous one is red.
