# Workshop Helmsman

Self-hosted workshop assistant for facilitator-led hands-on technical labs: a facilitator creates a workshop with content-rich milestones, participants join with just a name, and a genuinely live dashboard tracks the whole room — with a built-in help desk.

> **All commands run from the repo root.** Every Python command is prefixed with `uv run` — bare commands will fail.

## Requirements

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Node.js 22 and [pnpm](https://pnpm.io/)

## Setup (once)

```bash
# from the repo root
cp .env.example .env          # then set HELMSMAN_ADMIN_KEY (any strong string, >=16 chars)
uv sync
(cd frontend && pnpm install)
pnpm install                  # root: Playwright for e2e tests
pnpm exec playwright install chromium   # only needed to run the e2e suite
```

## Database

```bash
# from the repo root
uv run alembic upgrade head
uv run alembic current        # MUST print a revision hash — blank output means no migration was applied
```

## Build the UI and run

```bash
# from the repo root
(cd frontend && pnpm build)
uv run python -m src
```

Open **http://localhost:8001/** — the public landing page. From there, **Create your workshop** needs no access key: compose the workshop, give your email at the last step, and you are handed your facilitator dashboard link and the join link to share.

### URLs

| URL | What it is |
|---|---|
| `/` | Public landing page (served from the static export's `index.html`; falls back to a 307 → `/app/` if the frontend has not been built) |
| `/app/create/` | Keyless self-service workshop creation |
| `/admin` → `/app/admin/` | Admin console — enter your `HELMSMAN_ADMIN_KEY` to see **every** workshop, with its origin (`Admin`/`Public`) and the public creator's email. Not linked from the landing page |
| `/j/<slug>` | Join link — share with the room |
| `/p/<token>` | Participant personal link |
| `/f/<token>` | Facilitator dashboard link — the only credential for a workshop; save it |

There are no accounts and no login: a link is the credential. A workshop created from the public flow has the **full** facilitator toolset — it differs from an admin-created one only by its stored creator email and origin flag.

## Tests

```bash
# from the repo root
uv run pytest tests/unit tests/integration -q

# e2e (requires the server running in another terminal: uv run python -m src)
pnpm exec playwright test tests/e2e --reporter=line
```

## Environment variables

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `DATABASE_URL` | no | `sqlite:///data/helmsman.db` | SQLAlchemy URL; PostgreSQL-ready |
| `PORT` | no | `8001` | HTTP port |
| `HELMSMAN_ADMIN_KEY` | **yes** | — | Facilitator access key for Admin Home |
| `HELMSMAN_BASE_URL` | no | derived from request | Absolute base for generated share links |
| `HELMSMAN_LOG_LEVEL` | no | `INFO` | Log level (structlog, JSON to stdout) |
| `OPENROUTER_API_KEY` | no | — | AI help-desk (Phase 4); absent = fully air-gapped |
| `HELMSMAN_AI_MODEL` | no | `anthropic/claude-sonnet-4-6` | OpenRouter model id |
| `HELMSMAN_AI_CONFIDENCE` | no | `0.75` | AI auto-answer confidence threshold |

## Status

Phase 1 — **Core Live Loop**: create workshop → join (cookie auto-resume + personal links) → content-rich milestones → live dashboard → manual help desk. Broadcast, Pause, End workshop, AI help-desk, Spend, stuck/bottleneck/pulse cards, Audit, Templates are visible as clearly-labelled **"Coming in a later phase"** stubs. The spec in `spec/` is the source of truth.
