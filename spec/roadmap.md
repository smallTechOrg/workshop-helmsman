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

## Phase-gate constants (every phase)

Working tree clean and pushed · README updated and its commands re-run verbatim · human test-handoff published and approved before the next phase · qa-auditor sign-off per slice · no phase starts while the previous one is red.
