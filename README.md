# Workshop Helmsman

A self-hosted workshop tracker for remote sessions. Facilitators stand up a
workshop, get a participant link (slug) and a separate admin link (token),
and watch participants move through milestones in real time.

Phase 1 ships the full single-workshop happy path on a single VM with no
external services. No LLM, no external APIs — everything is local SQLite.

## Stack

- Python 3.11 / FastAPI / Uvicorn
- SQLite via SQLAlchemy 2.x
- Jinja2 templates, vanilla JS, one CSS file
- Polling-based live updates (4 s)

## Run locally

```sh
cd /Users/sai/workshop-helmsman
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python -m src        # serves on http://localhost:8001
```

The first boot creates `./data/helmsman.db` automatically.

## Endpoints (Phase 1)

| Route                                  | Purpose                                      |
| -------------------------------------- | -------------------------------------------- |
| `GET /`                                | Landing page                                 |
| `GET /admin/new` · `POST /admin/new`   | Facilitator creates a workshop               |
| `GET /admin/<admin_token>`             | Live facilitator dashboard                   |
| `GET /w/<participant_slug>`            | Participant join (asks for their name)       |
| `GET /w/<participant_slug>/me`         | Personal progress tracker + leaderboard     |
| `GET /w/<participant_slug>/data?since=`| JSON poll feed (used by the participant UI)  |
| `GET /healthz`                         | `{"status":"ok","db":"ok"}` liveness probe   |

## Phase 1 stubs (clearly labelled)

- `GET /admin/<token>/edit`         → "Coming in Phase 2"
- `GET /admin/<token>/export.csv`   → "Coming in Phase 2"
- `POST /admin/<token>/clone`       → "Coming in Phase 2"
- `GET /workshops`                  → read-only archive (no admin actions)

## Deploy

`deploy/systemd/workshop-helmsman.service` and `deploy/docker-compose.yml`
are both scaffolded. Pick one. The Phase-1 VM target is
`workshop.smalltech.in`; this repo boots cleanly on `:8001` for local
testing with no extra config.
