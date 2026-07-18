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
   tracker. Click "Mark complete" on milestones; watch the progress bar fill.
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
- Edit-after-create: form on `/admin/<token>/edit` rewrites
  `workshop.milestone_config` and/or `expires_at`. Existing
  `milestone_completion.milestone_title` rows keep their old title (audit
  fidelity); future completions use the new title.
- Real `/admin/<token>/export.csv`: streams a `workshop`, `participant`,
  `milestone_completion`, `help_request` CSV dump joined by ID.
- Clone: `POST /admin/<token>/clone` creates a new workshop with the
  same milestones + a new TTL, redirects to its dashboard.

**Gate.** Same boot command. Smoke: edit writes through, export downloads a
non-empty CSV with header row, clone returns 303 to a new dashboard URL with
the same milestone list.

---

## Phase 3 — Archive view + cohort polish ✅

**Goal.** The landing page surfaces a usable archive of past workshops so
facilitators can find an old session, compare cohorts, or hand the link to
a colleague who joined late.

**Slices.**
- `/workshops` — full archive table with name, created_at, participant count,
  status badge, action pills (dashboard/participant link). Client-side search
  filter by workshop name.
- Per-participant drill-down: `GET /admin/<token>/participant/<pid>` renders
  the participant's full timeline — joined_at, sorted completions, sorted
  help requests. Linked from participant name in the admin table.
- Cohort progress stacked bar: CSS-only horizontal stacked bar in the Stats
  card showing how many participants are at each completion level (0 done,
  1 done, 2 done, …). No charting library.
- Archive action: `POST /admin/<token>/archive` sets `archived=True`.
  Archived workshops show a friendly "archived" page to participants and a
  badge on `/workshops`. Admin dashboard always works.

**Gate.** Same boot. Smoke: archive page lists workshops with counts and
search filter; drill-down renders full timeline; archive POST → subsequent
`/w/<slug>` returns friendly "archived" page.

---

## Phase 4 — Future (optional)

- AI help-desk sub-agent: when a participant submits a help request, an LLM
  (optional, requires `AGENT_*_API_KEY`) drafts a suggested fix before the
  facilitator sees it
- Email/Slack notifications: facilitator gets a digest when N help flags accumulate
- Custom domain per workshop (e.g. `acme.workshop.smalltech.in`)
- Participant messaging: facilitator sends a broadcast message to all participants