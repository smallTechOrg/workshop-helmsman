# Architecture

## Stack

- **Language:** Python 3.11
- **Web framework:** FastAPI (with Jinja2Templates for server-rendered HTML)
- **Database:** SQLite via raw `sqlite3` (one file, no migrations framework in Phase 1)
- **Templates:** Jinja2
- **Frontend JS:** vanilla (one file: `frontend/static/js/app.js`), polling every 3s
- **Styling:** one CSS file: `frontend/static/css/styles.css` (no preprocessor)
- **No bundler, no node_modules, no React/Vue.**
- **No LLM, no external API calls.**
- **Process model:** `python -m src` boots uvicorn on `0.0.0.0:8001`.

## Repo layout

```
workshop-helmsman/
├── backend/                  # reserved for future split-out; intentionally empty in Phase 1
├── frontend/
│   ├── templates/            # Jinja2 templates
│   └── static/
│       ├── css/styles.css
│       └── js/app.js
├── deploy/
│   ├── workshop-helmsman.service   # systemd unit
│   └── docker-compose.yml          # alt local boot
├── harness/                  # smoke / acceptance scripts
├── spec/                     # what you are reading now + the rest
├── src/                      # FastAPI app package
│   ├── __init__.py
│   ├── __main__.py           # entrypoint: python -m src
│   ├── app.py                # FastAPI app factory + route imports
│   ├── db.py                 # sqlite connection + schema bootstrap
│   ├── models.py             # domain helpers (CRUD)
│   ├── auth.py               # token generation, slug dedup
│   ├── routes/
│   │   ├── landing.py
│   │   ├── admin.py
│   │   ├── participant.py
│   │   └── api.py            # JSON polling + healthz
│   └── time_utils.py         # expiry helper
├── data/                     # sqlite file lives here at runtime (created on first boot)
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

## Request flow (Phase 1)

1. Facilitator visits `/` → clicks "Create a new workshop".
2. Browser `GET /admin/new` → facilitator fills the form (name, milestones one per line
   as `title: description`, optional expiry days).
3. Browser `POST /admin/new`. Server creates a row in `workshop`, generates
   `admin_token` (32-hex) and `participant_slug` (8-char URL-safe), records the
   milestone config as JSON, and redirects to `/admin/<admin_token>`.
4. Facilitator shares `/w/<participant_slug>` to participants.
5. Participant opens `/w/<participant_slug>`: if they have no `participant_id` cookie,
  they're shown the name-entry form. `POST /w/<slug>` saves the participant row, sets
  the cookie, and redirects to `/w/<slug>/me`.
6. Participant tracker polls `GET /w/<slug>/data?since=<ts>` every 3s and renders the
   leaderboard; admin dashboard polls the same JSON endpoint family via
   `/admin/<token>/data?...` for its own view (Phase 1 reuses the participant-shaped
   JSON; later phases widen it).
7. `POST /w/<slug>/me/complete/<milestone_id>` inserts a `milestone_completion` row.
8. `POST /w/<slug>/me/help` inserts a `help_request` row (instantly visible on the
   admin dashboard's help panel).

## Bootstrap modes

- `python -m src` → production-style boot on `:8001`.
- On every boot, the demo seeder runs **only if there are zero workshops**, so first
  install is one-click testable and subsequent boots are idempotent.
- `archive_after_expiry` defaults to true.

## Data sovereignty

- All state is in `data/workshop.db`. The directory is excluded from git (`data/` in
  `.gitignore`).
- No outbound network calls. No tokens leave the host.
