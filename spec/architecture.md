# Architecture — Workshop Helmsman (v0.1)

## Stack

- **Language:** Python 3.11
- **Web framework:** FastAPI (with Jinja2Templates for server-rendered HTML)
- **Database:** SQLite via SQLAlchemy 2.x (dev) / PostgreSQL via `DATABASE_URL` (prod)
- **Templates:** Jinja2 (`frontend/templates/`)
- **Frontend JS:** vanilla (single file: `frontend/static/app.js`), polling every 4s
- **Styling:** single CSS file (`frontend/static/style.css`), CSS custom properties, mobile-first
- **Auth:** token-based (admin_token in URL, participant_slug in URL), HttpOnly cookie for participant session
- **Real-time:** short polling (4s) — no WebSockets. Single `/data` endpoint serves both participant tracker and admin dashboard (different shapes via query param).
- **Deploy:** Docker Compose + systemd unit. Runs on single VM (workshop.smalltech.in).
- **LLM:** Gemini via OpenRouter (`OPENROUTER_API_KEY` in `.env`). Optional — Phase 3 help-desk pre-resolution only. Graceful fallback if unavailable.

## Repo layout

```
workshop-helmsman/
├── src/                      # FastAPI app package
│   ├── __init__.py
│   ├── __main__.py           # entrypoint: python -m src
│   ├── main.py               # all routes (Phases 1-6 consolidated)
│   ├── models.py             # SQLAlchemy models
│   ├── db.py                 # engine, session, init_db
│   └── security.py           # token/slug generators, auth dependencies
├── frontend/
│   ├── templates/            # Jinja2 templates
│   │   ├── base.html
│   │   ├── landing.html
│   │   ├── admin_new.html
│   │   ├── admin_edit.html
│   │   ├── admin_dashboard.html
│   │   ├── admin_templates.html
│   │   ├── admin_template_edit.html
│   │   ├── admin_form.html
│   │   ├── admin_form_template.html
│   │   ├── participant_join.html
│   │   ├── participant_tracker.html
│   │   ├── participant_drilldown.html
│   │   ├── workshops_index.html
│   │   ├── workshop_archived.html
│   │   ├── workshop_expired.html
│   │   ├── _stubs.html
│   │   └── _form_field_row.html
│   └── static/
│       ├── style.css         # single stylesheet
│       ├── app.js            # participant polling + UI
│       ├── help_status.js    # inline help-status buttons (admin + participant)
│       └── form_editor.js    # form builder drag/drop/inline edit
├── spec/                     # this directory
├── data/                     # sqlite file at runtime (gitignored)
├── .env.example
├── .env                      # local overrides (gitignored)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── deploy/
    └── workshop-helmsman.service
```

## Request flow (Phase 1 Core Path)

1. Facilitator visits `/` → clicks "Create new workshop"
2. Browser `GET /admin/new` → form with agenda template picker, form template picker, inline editors
3. Browser `POST /admin/new` → server creates `Workshop` row, generates `admin_token` + `participant_slug`, snapshots milestones + form schema, redirects to `/admin/<admin_token>`
4. Facilitator shares `/w/<participant_slug>` with participants
5. Participant opens `/w/<slug>`: if no `participant_id` cookie → join form (name + custom fields). `POST /w/<slug>` creates `Participant`, sets HttpOnly cookie, redirects to `/w/<slug>/me`
6. Participant tracker (`/w/<slug>/me`) polls `GET /w/<slug>/data?since=<ts>` every 4s → renders leaderboard, help flags, **broadcast banner**, **workshop_paused state**, milestone checklist
7. Admin dashboard (`/admin/<token>`) polls `GET /admin/<token>/data?since=<ts>` every 4s → renders participant table, stats, cohort bar, help flags, broadcast composer, milestone controls
8. Participant clicks "Mark complete" → `POST /w/<slug>/me/complete/<mid>` → inserts `MilestoneCompletion` (blocked if `workshop_paused=true`)
9. Participant submits help → `POST /w/<slug>/me/help` (two-step: preview with LLM suggestion → commit) → inserts `HelpRequest`
10. Facilitator actions (broadcast, pause, advance, reorder) → POST to admin endpoints → immediate effect, next poll reflects change

## Bootstrap modes

- `python -m src` → production-style boot on `0.0.0.0:8001`
- On every boot, demo seeder runs **only if zero workshops exist** → first install is one-click testable, subsequent boots idempotent

## Data sovereignty

- All state in `data/helmsman.db` (SQLite) or PostgreSQL via `DATABASE_URL`
- `data/` directory excluded from git (`.gitignore`)
- No outbound network calls in core loop. LLM call (OpenRouter) only on facilitator "suggest reply" click — optional, never blocks.

## Key architectural decisions

| Decision | Rationale |
|----------|-----------|
| Server-rendered Jinja2 + polling | Zero JS build step, works on any browser, easy to audit, fast initial paint |
| Single `/data` JSON endpoint | One polling loop serves both participant and admin views; conditional fields via `?view=admin\|participant` |
| Workshop-scoped tokens in URL | No auth provider, no cookies for admin, shareable links, revocable by archive |
| Snapshot milestones/form on workshop create | Template edits never mutate historical sessions |
| `workshop_paused` + `broadcast_message` on Workshop row | Simple, no extra tables; atomic toggle; visible on next poll (≤4s) |
| Milestone order stored as JSON array of IDs | Drag-drop reorder without schema migration; stable IDs (`m0`, `m1`...) |
| CSV streaming via `StreamingResponse` | Handles 100+ participants × 10 milestones without memory spike |

## Security notes

- `admin_token` = 32-char URL-safe secret (256 bits entropy). Treat as password.
- `participant_slug` = 8-char URL-safe (not secret; public join link).
- Participant cookie: HttpOnly, SameSite=Lax, path-scoped to `/w/<slug>`, 12h TTL.
- No password hashing (no passwords). No session table (stateless tokens).
- SQL injection: SQLAlchemy ORM + parameterized queries only.
- XSS: Jinja2 auto-escape + `escapeHtml` in JS for dynamic inserts.
- CSRF: not needed for token-in-URL flows; participant cookie is read-only for GET, POSTs are same-origin form submits.