# Capabilities

Phased list. Each phase ships behind a Gate command that proves the slice works
end-to-end before the next phase begins.

## Phase 1 — Single-workshop happy path (this build)

- Landing page with two entry points: "Facilitator: create a new workshop" and
  "Workshop admin: enter admin token".
- `POST /admin/new` creates a workshop, stores `admin_token` + `participant_slug`,
  redirects the facilitator to the dashboard.
- Admin dashboard is **read-only** in this phase but already shows:
  - participant grid (name, % complete, last activity, help-needed badge),
  - live help-requests panel,
  - workshop metadata (name, expiry, milestones).
- A seeded **DEMO** workshop is created on first boot so a tester can click straight in.
- Participants join via `/w/<participant_slug>`, are prompted for a name on first visit,
  then land on their tracker.
- Participants can complete milestones and submit help requests.
- Live refresh: `/w/<participant_slug>/data?since=<ts>` returns a JSON snapshot used by
  the tracker for leaderboard updates and by the admin dashboard for participant
  refresh. Polled every 3s.
- Real expiry enforcement: if `expires_at < now()` and `archive_after_expiry` is on, the
  participant page renders a friendly "this workshop has ended" page. The admin route
  always works until a future archive feature deletes the row.
- **Clearly-labelled stubs** (not silent failures):
  - `GET /admin/<token>/export.csv` → returns `text/plain` body "Coming in Phase 2".
  - `POST /admin/<token>/clone` → returns `text/plain` body "Coming in Phase 2".
  - `GET /admin/<token>/edit` → returns `text/plain` body "Coming in Phase 2".

## Phase 2

- Edit milestones post-creation (replace milestone_config JSON via the edit page).
- Real CSV export of the full audit (workshop meta, participants, completions,
  help requests).
- Clone-this-workshop wired up: copies milestones + expiry offset and issues fresh
  tokens; redirects to the new admin dashboard.
- A "share this URL" affordance on the dashboard (short-link friendly slug displayed
  prominently, copy-to-clipboard button).

## Phase 3

- Multi-workshop archive view on the landing page (list of past + active workshops).
- Per-cohort grouping / filtering on the archive view.
- Finer-grained admin permissions (per-workshop token rotation, archival, restore).
- UI polish, tests, CI.

## Always-on cross-cutting concerns (any phase)

- Platform-agnostic URLs.
- Mobile-responsive CSS (grid/flex + viewport meta).
- Health probe at `/healthz` returning JSON.
- No secrets required to boot (`.env.example` is intentionally empty).
