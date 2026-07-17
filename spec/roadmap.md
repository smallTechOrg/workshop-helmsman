# Roadmap — Workshop Helmsman

## Phase 1 — Single-workshop happy path ✅

**Goal.** A facilitator can stand up a workshop, share two links, see
participants join and complete milestones in real time, spot stuck
participants, and not have to think about auth or external services.

**Slices (vertical, built in parallel).**
- Backend: all routes — landing, create, dashboard, join, tracker, helper
  routes, expiry handling. SQLAlchemy models + DB bootstrap. Token/slug
  generators. Phase 1 stubs for edit / export / clone (render "Coming in
  Phase 2" page, do not 404 silently).
- Frontend: Jinja2 templates + one CSS file + one JS file (live-poll loop).
  Mobile-responsive. No bundler. No node_modules.
- Deploy: `Dockerfile` + `docker-compose.yml` + a systemd unit file.
- Harness: `harness/skills/workshop-helmsman/SKILL.md` — operational cheat
  sheet (boot, DB inspection, phase notes).

**Key surfaces / files.**
- `src/main.py`        — all FastAPI routes
- `src/models.py`      — four-table schema
- `src/db.py` · `src/security.py`
- `frontend/templates/`
- `frontend/static/style.css`, `frontend/static/app.js`
- `spec/{vision,capabilities,architecture,data-model,agent,roadmap}.md`
- `Dockerfile`, `deploy/`, `harness/skills/workshop-helmsman/SKILL.md`

**Runnable Gate.**
```sh
cd /Users/sai/workshop-helmsman
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python -m src                  # http://localhost:8001
curl -sf http://localhost:8001/healthz  # {"status":"ok","db":"ok"}
```

**How the user tests it.**
1. Open `http://localhost:8001/` → click "Open demo dashboard" or
   "Create new workshop".
2. In another tab, open the participant URL → enter a name → land on the
   tracker. Click "Mark complete" on milestones; watch the progress bar
   fill.
3. Verify the leaderboard updates every ~4 s (open a third tab as a different
   name, mark a milestone → first tab's leaderboard refreshes within 4 s).
4. Test the help flag: type a help message on the participant tab; within
   one polling tick it appears in the admin dashboard's "Help flags" card.
5. Hit stub routes — `/admin/<token>/edit`, `/admin/<token>/export.csv`,
   `/admin/<token>/clone` — each shows the "Coming in Phase 2" page.

---

## Phase 2 — Workshop config + export ✅

**Goal.** Facilitators can iterate on a workshop without losing it:
edit milestones after launch, export a full audit CSV, and spin up
next-session clones from a previous workshop's config.

**Slices.**
- Edit-after-create: `GET/POST /admin/<token>/edit` pre-fills name,
  milestones (as `title: description` textarea), and TTL. POST writes
  `workshop.name`, `workshop.milestone_config` (JSON), `workshop.expires_at`.
  Existing `milestone_completion.milestone_title` rows are preserved.
  Redirects 303 → `/admin/<token>`.
- Real `GET /admin/<token>/export.csv`: `Content-Type: text/csv`,
  `Content-Disposition: attachment; filename="workshop-<name>-<ts>.csv"`.
  Columns: `participant_name, joined_at, milestone_title, completed_at,
  help_message, help_created_at`. Left-join all four tables. Header row always
  present.
- Clone: `POST /admin/<token>/clone` creates a new workshop with the same
  milestone_config, new admin_token + participant_slug, 8 h TTL from now.
  Redirects 303 → `/admin/<new_token>`.
- Copy-to-clipboard on the admin dashboard: participant URL displayed with
  a "Copy link" button that writes the full origin+slug URL to clipboard and
  shows a 2 s "Copied!" feedback. Graceful fallback to text selection.

**Gate.** Same boot. Smoke: edit writes through, export downloads a non-empty
CSV with header row, clone returns 303 to a new dashboard URL with the same
milestone list.

---

## Phase 3 — Archive view + cohort polish

**Goal.** The landing page surfaces a usable archive of past workshops so
facilitators can find an old session, compare cohorts, or hand the link to
a colleague who joined late.

**Slices.**
- `/workshops` becomes a full archive table with status / search / "open"
  actions (was a read-only stub in Phase 1).
- Per-participant drill-down from the dashboard (`/admin/<token>/p/<pid>`).
- Cohort progress chart (just a horizontal stacked bar per workshop — no
  charting library).
- Polish: empty-state copy, soft-delete action on the dashboard
  (`/admin/<token>/archive` → sets `archived=1`).

**Gate.** Same boot. Smoke: archive page lists ≥ 3 previous workshops from
test data; per-participant drill-down renders their full completion timeline.
