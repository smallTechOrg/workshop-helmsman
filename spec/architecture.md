# Architecture — Workshop Helmsman (v0.2)

## Stack

| Layer | Choice | Version / notes |
|-------|--------|-----------------|
| Language (backend) | Python | 3.12+ |
| Package manager (Python) | uv | all commands `uv run …` from repo root |
| Web framework | FastAPI | ≥0.115 |
| ASGI server | uvicorn | single process, single worker (see Process model) |
| ORM | SQLAlchemy | 2.x, sync engine, `Mapped`/`mapped_column` declarative |
| Migrations | Alembic | ≥1.13, `render_as_batch=True` for SQLite ALTER support |
| Database | SQLite (WAL) | file `data/helmsman.db`; PostgreSQL-ready via `DATABASE_URL` override — no SQLite-only SQL in app code (FTS5 corpus is the one documented exception, with a PostgreSQL note in agent.md) |
| Settings | pydantic-settings | v2, loads `.env` |
| Logging | structlog | JSON to stdout |
| HTTP client (LLM) | httpx | OpenRouter REST, 30s timeout |
| Frontend framework | Next.js | 15.x, App Router, **static export** (`output: 'export'`, `basePath: '/app'`) |
| UI library | React | 19.x |
| Language (frontend) | TypeScript | 5.x, strict |
| Styling | Tailwind CSS | v4 (via `@tailwindcss/postcss` + `@source "../";` in globals.css — never removed). Chosen for the polish bar: design tokens via `@theme`, consistent spacing/type scales, zero runtime cost in a static export |
| Markdown | react-markdown + remark-gfm + rehype-highlight | raw HTML disabled (no rehype-raw) — see Security |
| Package manager (frontend) | pnpm | frontend deps in `frontend/`, e2e deps in root `package.json` |
| E2E testing | Playwright | `@playwright/test`, chromium, config at repo root, tests in `tests/e2e/` |
| Backend testing | pytest | `tests/unit/`, `tests/integration/` |
| LLM provider | OpenRouter | key: `OPENROUTER_API_KEY` (exact name — project convention); default model `anthropic/claude-sonnet-4-6` via `HELMSMAN_AI_MODEL` |
| Deploy | Docker Compose on a VM; GitHub Actions CI/CD to GCP | Phase 5 — never blocks earlier phases |

> **Assumed:** Node LTS (22.x) pinned via `frontend/.nvmrc` and `engines`; all frontend `dev`/`build` scripts carry `NODE_OPTIONS=--no-experimental-webstorage` (harness Node ≥25 safety rule).

## Repo layout

```
workshop-helmsman/                  ← repo root IS the project; all commands run from here
├── src/
│   ├── __init__.py
│   ├── __main__.py                 ← boots uvicorn on 0.0.0.0:$PORT (default 8001)
│   └── helmsman/
│       ├── __init__.py             ← __version__ = "0.2.0"
│       ├── config/settings.py      ← pydantic-settings; reads .env
│       ├── security.py             ← token generation + auth dependencies
│       ├── db/
│       │   ├── models.py           ← all SQLAlchemy models (spec/data-model.md)
│       │   └── session.py          ← engine, SQLite pragmas, session dependency
│       ├── api/
│       │   ├── __init__.py         ← create_app(): routers, static mount, pretty-link redirects
│       │   ├── _common.py          ← ok(), api_error()
│       │   ├── health.py           ← GET /api/health
│       │   ├── admin.py            ← admin-key surface (create/list workshops, templates)
│       │   ├── facilitator.py      ← /api/f/{admin_token}/… surface
│       │   └── participant.py      ← /api/join/…, /api/p/{token}/… surface
│       ├── services/
│       │   ├── snapshots.py        ← versioned poll-payload builders + in-process cache
│       │   ├── lifecycle.py        ← lazy status transitions (Phase 3)
│       │   ├── intelligence.py     ← stuck / bottleneck / pulse computation (Phase 2)
│       │   ├── undo.py             ← undoable-action record/replay (Phase 2)
│       │   └── templates.py        ← template instantiate/save-as (Phase 3)
│       ├── ai/                     ← AI help-desk pipeline (Phase 4; see spec/agent.md)
│       │   ├── pipeline.py         ← run_help_desk(help_request_id)
│       │   ├── context.py          ← context gathering
│       │   ├── corpus.py           ← FTS5 corpus maintenance + similarity search
│       │   ├── openrouter.py       ← httpx client, usage/cost capture
│       │   └── prompts/            ← *.md prompt templates
│       └── observability/
│           └── logging.py          ← structlog config + request-logging middleware
├── frontend/
│   ├── package.json                ← pnpm; NODE_OPTIONS safety in scripts
│   ├── next.config.ts              ← output: 'export', basePath: '/app', trailingSlash: true
│   ├── postcss.config.mjs          ← @tailwindcss/postcss (never removed)
│   ├── tsconfig.json
│   ├── app/
│   │   ├── layout.tsx              ← fonts, shell
│   │   ├── globals.css             ← Tailwind v4 + @source "../"; + design tokens (@theme)
│   │   ├── page.tsx                ← Admin Home (facilitator access key + workshop list/create)
│   │   ├── f/page.tsx              ← Facilitator Dashboard   (?t=<admin_token>)
│   │   ├── join/page.tsx           ← Participant Join        (?s=<join_slug>)
│   │   └── p/page.tsx              ← Participant Tracker     (?t=<participant_token>)
│   ├── components/
│   │   ├── ui/                     ← shared primitives (Button, Card, Badge, Toast, Modal, Markdown, Skeleton, StubBadge)
│   │   ├── facilitator/            ← dashboard components
│   │   └── participant/            ← tracker/join components
│   └── lib/
│       ├── api.ts                  ← typed API client (contract: spec/api.md)
│       └── poll.ts                 ← versioned polling hook (visibility-aware)
├── alembic/                        ← env.py, script.py.mako, versions/
├── tests/
│   ├── conftest.py
│   ├── unit/                       ← pytest, no network
│   ├── integration/                ← pytest, real HTTP (TestClient) + real DB file; Phase 4: tests/integration/ai against real OpenRouter key
│   └── e2e/                        ← Playwright specs (TypeScript)
├── playwright.config.ts            ← baseURL http://localhost:8001/app
├── package.json                    ← root: @playwright/test only
├── pyproject.toml                  ← uv-managed; testpaths = ["tests"]
├── alembic.ini
├── .env.example
├── data/                           ← SQLite file at runtime (gitignored)
├── deploy/                         ← Phase 5: Dockerfile, docker-compose.yml, runbook
└── .github/workflows/              ← Phase 5: CI/CD
```

Import convention: the application package is `src.helmsman.*` (the `src` package exists so `uv run python -m src` boots — harness contract).

## Process model & single-origin serving

**One process serves everything.** `uv run python -m src` starts one uvicorn worker on port **8001**:

- `/api/*` — JSON API (FastAPI routers, sync `def` handlers on the threadpool).
- `/app/*` — the built Next.js static export (`frontend/out/`), mounted with `StaticFiles(html=True)`. The canonical URL is `http://localhost:8001/app/`.
- **Pretty share links** (tiny FastAPI redirect routes, because a static export cannot serve dynamic path segments):
  - `GET /j/{join_slug}` → 307 → `/app/join/?s={join_slug}` (the link on the door)
  - `GET /p/{participant_token}` → 307 → `/app/p/?t={participant_token}` (personal link)
  - `GET /f/{admin_token}` → 307 → `/app/f/?t={admin_token}` (facilitator link)
  - `GET /` → 307 → `/app/`
- No separate Node server in production. `pnpm dev` (port 3000) is inner-loop only and is never the documented test path.

**Single worker is a deliberate choice**, not an accident: it makes the in-process snapshot cache correct without Redis, and the load profile (below) fits comfortably in one asyncio process + threadpool. If the app ever outgrows one worker, the cache moves behind the DB (the DB is already the source of truth, so nothing breaks — the cache is only an optimization).

## Live-update mechanism: versioned coalesced polling (decision + justification)

**Decision: short polling with per-workshop version counters and an in-process snapshot cache. No SSE, no WebSockets.**

Load profile: 300+ participants + 1–3 facilitator dashboards on 2 vCPU / 2–4 GB, SQLite storage, and a hard resilience rule (reconnect/restart must recover purely from the DB).

Why polling beats SSE here:

1. **Resilience is free.** Polling is stateless — after a server restart, every client's next poll simply succeeds with full state. SSE requires reconnect logic, `Last-Event-ID` replay, server-side fan-out state, and produces a thundering-herd reconnect after every restart or deploy. The resilience requirement ("restart loses nothing, reconnect restores exact state") is the polling model's native behavior.
2. **The arithmetic is trivial.** 300 participants polling every 3 s = 100 req/s. Each poll does **one indexed point-read** (the workshop's version row) and, when nothing changed (the overwhelming steady state), returns a ~60-byte `{"changed": false}` response. SQLite in WAL mode serves tens of thousands of point-reads/s; uvicorn serves 100 req/s of this without noticing. SSE's 300 idle connections would also fit in memory — but buys nothing over this, at real complexity cost (proxy buffering config, keepalive pings, per-event fan-out code).
3. **SQLite write contention stays negligible.** Peak write load is a completion burst (~5–10 writes/s) plus joins and help requests. WAL readers never block the writer; each write is a short transaction that also bumps the workshop's version counter. Polling adds *zero* writes (the `last_seen_at` touch is throttled to once per 60 s per participant ≈ 5 writes/s at 300 participants).
4. **Bandwidth is controlled by two version counters.** Each workshop row carries:
   - `state_version` — bumped on any activity change (join, completion, help, answer, broadcast, pause, advance, reorder…)
   - `content_version` — bumped only when milestone content/order changes.
   Clients send their last-seen `state_version`; unchanged → tiny response. Changed → the poll payload (**without** milestone `content_md` — leaderboard, progress, help state; ~10–15 KB at 300 participants). Milestone bodies are fetched from a separate content endpoint only when `content_version` changes. Worst-case burst (a completion every second, all 300 clients refreshing full payloads) ≈ 1–1.5 MB/s — comfortably inside a modest VM's budget; steady state is ~10 KB/s total.
5. **Coalescing caps DB work independent of participant count.** The changed-payload for a given `(workshop_id, state_version)` is built once and memoized in-process (dict, TTL 2 s as a safety net); 300 pollers hitting the same version share one snapshot build. Per-request personal data ("me": my completions, my help requests) is 2–3 indexed point-queries per poll — ~250 cheap queries/s at burst, trivial for WAL SQLite.

Poll intervals (client, via the `lib/poll.ts` hook): participant tracker **3 s** visible / **15 s** hidden (Page Visibility API); facilitator dashboard **2 s** visible / **10 s** hidden. Every mutation response includes the new `state_version`, and the client polls immediately after any of its own mutations, so the actor always sees their effect within one round-trip (plus optimistic UI, see Error handling).

## Auth model

No accounts anywhere. Three credentials, all generated with `secrets`:

| Credential | Format | Entropy | Carried in | Grants |
|---|---|---|---|---|
| Facilitator access key | operator-chosen string in `.env` (`HELMSMAN_ADMIN_KEY`, recommend ≥16 chars) | n/a | `X-Admin-Key` request header (entered once on Admin Home, kept in `localStorage`) | Admin Home: list/create workshops, template library |
| Workshop admin token | `secrets.token_urlsafe(32)` → 43 chars | 256 bits | URL path (`/f/{token}`, `/api/f/{token}/…`) | Full facilitator control of one workshop; shareable to co-facilitators |
| Participant token | `secrets.token_urlsafe(16)` → 22 chars | 128 bits | URL path (`/p/{token}`, `/api/p/{token}/…`) **and** cookie | One participant's identity, cross-device |
| Join slug | `secrets.token_urlsafe(6)` → 8 chars | 48 bits (public, not a secret) | URL (`/j/{slug}`) | The join page only |

- Key comparison uses `secrets.compare_digest`. Unknown token/key → 404 (`not_found`) for workshop tokens, 401 (`invalid_admin_key`) for the admin key — never distinguish "wrong" from "missing" for tokens.
- **Participant cookie (auto-resume):** on join, the server sets `helmsman_p_{workshop_id}={participant_token}`; `HttpOnly; SameSite=Lax; Path=/; Max-Age=2592000` (30 days). `GET /api/join/{slug}` reads it server-side and returns the participant's token if recognized, so the join page silently forwards a returning browser to its tracker. The personal link `/p/{token}` needs no cookie — it *is* the cross-device credential. The facilitator dashboard shows each participant's personal link (copy button) — the lost-link recovery path.
- Structured logs mask all tokens to their first 6 characters.

## Error-handling strategy

- **Envelope (exact, both directions in spec/api.md):** success → HTTP 200, `{"data": …, "error": null}`. Failure → HTTP 4xx/5xx, `{"detail": {"code": "<machine_code>", "message": "<human sentence>"}}` (FastAPI `HTTPException` shape via `api_error()`). One catalogue of `code` values lives in api.md.
- **Fail fast at the boundary.** Request bodies are validated by Pydantic models; domain validation (lengths, state rules like "workshop is archived") raises `api_error` with a specific code. Invalid data never propagates.
- **Optimistic UI with reconciliation.** Mutations (mark complete, send answer) update the UI immediately, fire the request, and reconcile on the response + next poll. On failure: the UI reverts and shows a toast naming the cause and next step ("Couldn't save — retrying in 3 s" / "This workshop is paused").
- **The poll loop is self-healing.** A failed poll (server restarting, network blip) shows a quiet "reconnecting…" indicator after 2 consecutive failures, backs off (3 s → 6 s → 12 s, cap 30 s), and recovers automatically — full state comes from the DB on the first successful poll. No data is ever lost because no data lives only in the client or the process.
- **Startup fails hard** on unrecoverable config (missing `HELMSMAN_ADMIN_KEY`, unreadable `DATABASE_URL`) with a clear message. A missing `OPENROUTER_API_KEY` is *not* an error — the AI surface reports "AI off (no API key)" and everything else runs (air-gapped guarantee).
- **AI failures degrade to manual.** Any AI-pipeline failure (timeout, 5xx, malformed output) logs ERROR and leaves the help request in the normal facilitator queue — the participant experience is identical to AI-off (see agent.md).

## Observability (wired in Phase 1, never deferred)

- **structlog → JSON on stdout.** Every line: `timestamp`, `level`, `event`, `request_id`, plus context.
- **Request middleware:** method, token-masked path, status, `duration_ms`, `request_id` for every API request (poll endpoints log at DEBUG to keep INFO readable).
- **Domain events at INFO:** `workshop.created`, `participant.joined`, `milestone.completed`, `help.created`, `help.answered`, `broadcast.sent`, `workshop.paused`, `undo.applied`, `ai.triage`, `ai.auto_answered`, `ai.draft_created`, `ai.failed` — each with ids and (for AI) latency, token counts, cost.
- **No metrics endpoint, no ops UI** (vision non-goal). `GET /api/health` returns `{"status":"ok","db":"ok"}` for machines.

## Database configuration

- SQLite engine (default `sqlite:///data/helmsman.db`), applied per-connection via an `connect` event listener:
  `PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA busy_timeout=5000; PRAGMA foreign_keys=ON;`
- SQLAlchemy: sync engine, `pool_pre_ping=True`; for SQLite `connect_args={"check_same_thread": False}`.
- `DATABASE_URL` may point at PostgreSQL; models use portable types only (Integer/Text/Boolean/DateTime/Numeric + JSON as Text). Alembic runs with `render_as_batch=True` so SQLite ALTERs work. The FTS5 help corpus (Phase 4) is created only when the dialect is SQLite; agent.md documents the PostgreSQL alternative.
- All timestamps stored UTC; serialized as ISO 8601 `Z` (`2026-07-20T14:03:22Z`).
- Transactions are short: one request = one transaction (commit in the session dependency). Any state-changing write bumps the workshop's `state_version` in the same transaction.
- **Lazy lifecycle transitions (Phase 3):** no cron/background scheduler. Every workshop-scoped request first applies due transitions (`grace_until` passed → `archived`) inside the request transaction — restart-proof by construction.

## Security notes

- **XSS:** all facilitator/AI-authored markdown (milestones, broadcasts, answers) renders through react-markdown with **raw HTML disabled** — HTML in markdown source is not injected. Participant-authored text (names, help messages) is rendered as **plain text** (React text nodes, `whitespace-pre-wrap`), never as markdown or HTML.
- **SQL injection:** SQLAlchemy ORM/parameterized queries only. The FTS5 `MATCH` query string is built from sanitized, quoted tokens (see agent.md).
- **CSRF:** state-changing endpoints are authenticated by unguessable URL tokens or the `X-Admin-Key` header — not by cookies — so cross-site form posts cannot forge them. The participant cookie is only ever *read* to resolve auto-resume on `GET /api/join/{slug}`.
- **Secrets:** only in `.env` (gitignored). Logs and API responses never contain `OPENROUTER_API_KEY` or `HELMSMAN_ADMIN_KEY`; key presence is logged as a boolean.
- **Rate limiting:** none in v0.2 (self-hosted, unguessable tokens, trusted room). > **Assumed:** acceptable for a single-team instance; revisit if ever exposed as SaaS.

## Environment variables (complete list)

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `DATABASE_URL` | no | `sqlite:///data/helmsman.db` | SQLAlchemy URL; PostgreSQL-ready |
| `PORT` | no | `8001` | HTTP port |
| `HELMSMAN_ADMIN_KEY` | **yes** | — | Facilitator access key for Admin Home |
| `HELMSMAN_BASE_URL` | no | derived from request | Absolute base for generated share links (set behind a proxy) |
| `HELMSMAN_LOG_LEVEL` | no | `INFO` | structlog level |
| `OPENROUTER_API_KEY` | no | — | AI help-desk; absent → fully air-gapped, zero errors |
| `HELMSMAN_AI_MODEL` | no | `anthropic/claude-sonnet-4-6` | OpenRouter model id |
| `HELMSMAN_AI_CONFIDENCE` | no | `0.75` | Auto-answer confidence threshold (see agent.md) |

## Deploy shape (Phase 5)

- `deploy/Dockerfile` — multi-stage: (1) Node stage builds the frontend export, (2) Python stage with uv installs the app and copies `frontend/out/`; runs `alembic upgrade head` then `python -m src`.
- `deploy/docker-compose.yml` — one service, one named volume for `data/` (SQLite + WAL files), `env_file: .env`, port 8001. Optional Caddy/nginx TLS proxy is documented, not shipped.
- `.github/workflows/ci.yml` — on PR: `uv run pytest tests/unit -q` + `pnpm build` + lint. Real-key integration tests run only where secrets exist (guarded skip).
- `.github/workflows/deploy.yml` — on main: build image, push to Artifact Registry, SSH-deploy compose to the GCP VM.
- Backup = copy the `data/` volume (documented in `deploy/RUNBOOK.md`).

## Key architectural decisions (summary)

| Decision | Rationale |
|---|---|
| Versioned coalesced polling, no SSE | Restart/reconnect resilience for free; ~100 req/s of point-reads is trivial; no fan-out state, no proxy pitfalls |
| Two version counters (`state_version` / `content_version`) | Keeps steady-state polls at ~60 bytes and burst payloads ~10–15 KB; milestone bodies transfer only when edited |
| Single uvicorn worker + in-process snapshot cache | Correct coalescing without Redis; load fits one process; DB remains sole source of truth |
| Milestones as a real table (not JSON blob) | Per-milestone stats for 300 participants via indexed GROUP BY; FTS/context queries for the AI phase |
| Static Next.js export served by FastAPI at `/app/` + pretty-link redirects | Single origin, one process, harness gate path; dynamic tokens carried in query params where the static router needs them, pretty in shared URLs |
| Lazy lifecycle transitions on access | No scheduler process to crash or restart; correctness derives from the DB clock check |
| Audit + undo share one table (`facilitator_action`) | One write per action serves the audit trail, the undo window, and AI-answer logging |
