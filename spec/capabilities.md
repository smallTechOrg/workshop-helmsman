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

## Phase 2 — Workshop config + export (this build)

- ✅ Edit milestones post-creation (`GET/POST /admin/<token>/edit`): form
  pre-filled with current name, milestone list (`title: description` textarea),
  and TTL in hours. POST writes `workshop.name`, `workshop.milestone_config`
  (JSON), and `workshop.expires_at`. Existing `milestone_completion.milestone_title`
  rows are preserved unchanged.
- ✅ Real CSV export (`GET /admin/<token>/export.csv`): `Content-Type: text/csv`,
  `Content-Disposition: attachment; filename="workshop-<name>-<ts>.csv"`. Columns:
  `participant_name, joined_at, milestone_title, completed_at, help_message,
  help_created_at`. Left-join all four tables. Header row always present.
  Participants with no completions produce a row with only name/timestamp.
- ✅ Clone-this-workshop (`POST /admin/<token>/clone`): copies `milestone_config`,
  issues fresh `admin_token` + `participant_slug`, sets TTL to 8 h from now.
  Redirects 303 to the new admin dashboard.
- ✅ Copy-to-clipboard on admin dashboard: participant URL shown with a
  "Copy link" button; writes full URL to clipboard and gives 2 s "Copied!"
  feedback. Graceful fallback to text selection.

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
