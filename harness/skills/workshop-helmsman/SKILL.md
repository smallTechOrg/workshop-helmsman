---
name: workshop-helmsman
description: Operate the Workshop Helmsman tracker server — boot it, inspect state, archive workshops, or rebuild the DB.
---

# Workshop Helmsman Skill

Local, self-hosted milestone tracker for remote workshops. Intended deployment
at `workshop.smalltech.in`.

## When to load

- Starting / restarting / debugging the server
- Inspecting workshop state in SQLite
- Snapshotting or archiving a workshop
- Resolving a Phase annotation question

## Boot (local dev)

```sh
cd /Users/sai/workshop-helmsman
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python -m src          # http://localhost:8001
```

Background: `nohup venv/bin/python -m src > /tmp/ws.log 2>&1 &`.
Stop: `pkill -f 'python -m src'`.

## Inspect DB

```sh
sqlite3 /Users/sai/workshop-helmsman/data/helmsman.db
.tables
.headers on
SELECT id, name, admin_token, participant_slug, archived, expires_at FROM workshop;
```

## Routes cheat-sheet

- `GET /`                              landing (auto-seeds demo workshop)
- `GET /admin/new` · `POST /admin/new` create a workshop
- `GET /admin/<admin_token>`           facilitator dashboard
- `GET /w/<participant_slug>`          participant join form
- `GET /w/<participant_slug>/me`       participant tracker (live leaderboard)
- `GET /w/<participant_slug>/data`     JSON poll feed (used by `static/app.js`)
- `GET /healthz`                       `{"status":"ok","db":"ok"}`

## Phase notes

- Phase 1 real landing/admin/participant/help/expiry.
- Phase 1 stubs: `/admin/<token>/edit`, `/admin/<token>/export.csv`, `/admin/<token>/clone`, `/workshops` (archive index — read-only listing only).
