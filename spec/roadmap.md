# Roadmap — Workshop Helmsman (v0.1)

## Phase 1 — Core Path (current improvement cycle)

**Goal:** Facilitator creates workshop from template → shares participant link → participants join and fill form → facilitator watches live dashboard → participants complete milestones → facilitator exports CSV.

**Surfaces built in Phase 1:**

| # | Surface | Route | Notes |
|---|---------|-------|-------|
| 1 | Create workshop | `GET/POST /admin/new` | Name, agenda template picker, form template picker, TTL |
| 2 | Admin dashboard | `GET /admin/<token>` | **Polished**: stat cards, participant table with progress bars + milestone chips, per-milestone stats, cohort stacked bar, help flags with status pills, broadcast composer, milestone controls |
| 3 | Participant join | `GET/POST /w/<slug>` | Instant validation, mobile-optimized, accessible |
| 4 | Participant tracker | `GET /w/<slug>/me` | Milestone checklist, progress bar, leaderboard, broadcast banner, my help flags |
| 5 | Participant poll data | `GET /w/<slug>/data` | JSON: milestones, my progress, leaderboard, help requests, broadcast message, workshop_paused, form schema |
| 6 | Admin poll data | `GET /admin/<token>/data` | JSON: all participants, stats, cohort bar, help requests, broadcast, workshop_paused, milestone order |
| 7 | Mark milestone complete | `POST /w/<slug>/me/complete/<mid>` | Idempotent, blocked if workshop_paused |
| 8 | Help flag (2-step) | `POST /w/<slug>/me/help` | Preview (with LLM suggestion stub) → commit |
| 9 | Broadcast message | `POST /admin/<token>/broadcast` | Set/clear pinned announcement |
| 10 | Pause workshop | `POST /admin/<token>/pause` | Toggle workshop_paused (locks completions) |
| 11 | Advance all | `POST /admin/<token>/advance-all` | Move all participants to next incomplete milestone |
| 12 | Advance selected | `POST /admin/<token>/advance-selected` | Move selected participant IDs to next milestone |
| 13 | Reorder milestones | `POST /admin/<token>/milestones/reorder` | Persist drag-drop order |
| 14 | Export CSV | `GET /admin/<token>/export.csv` | Streamed: participants × milestones + form answers + help |
| 15 | Health | `GET /healthz` | `{"status":"ok","db":"ok"}` |

**Stubs (Phase 2+):**
- `GET /admin/templates` — template library CRUD
- `GET /workshops` — archive with search/filter
- `POST /admin/<token>/clone` — clone workshop
- `POST /admin/<token>/archive` — soft delete

---

## Phase 2 — Template Library & Multi-Session

- `/admin/templates` — list, create, edit, delete agenda templates & form templates
- Template pickers on `/admin/new` and `/admin/<token>/edit`
- Template edits never mutate existing workshops (snapshot-on-create)
- `/workshops` archive page: list all workshops, search by name, filter by status (live/expired/archived), per-session participant count
- Cohort comparison: select multiple sessions of same template → side-by-side completion rates
- Per-participant drill-down: `/admin/<token>/participant/<pid>` — timeline of completions + help requests + form answers

---

## Phase 3 — AI Assist & Notifications

- Optional LLM (Gemini via OpenRouter) for help-desk pre-resolution
- Facilitator clicks "Suggest reply" on help flag → LLM returns one short actionable paragraph → facilitator edits/sends
- Context injected: workshop milestones, facilitator help tips (`help_tips_json`), participant's message
- Email/Slack webhook on new help flags (configurable per workshop)
- Mobile-first participant tracker polish (touch targets, gesture-friendly)
- Accessibility audit (WCAG AA)

---

## Phase 4 — Scale & Multi-tenancy

- PostgreSQL backend (swap via `DATABASE_URL`)
- Multiple concurrent workshops (dashboard switcher)
- Per-workshop facilitator tokens (rotate, revoke, multiple per workshop)
- Custom domains / subdomains per workshop
- Team/organization grouping (multi-tenant)
- Webhooks for external integrations (completion webhook, help-flag webhook)
- Structured logging + metrics endpoint (`/metrics` for Prometheus)
- Load test: 200+ participants, 4s poll, <200ms p99

---

## Cross-cutting (every phase)

- Platform-agnostic URLs (no hardcoded host/port)
- Mobile-responsive CSS (grid/flex + viewport meta)
- Health probes: `/healthz` (liveness), `/healthz/ready` (readiness)
- No secrets required to boot (`.env.example` empty for core flow)
- Single CSS file, single JS file, no bundler, no `node_modules`
- Audit trail: every milestone completion, help request, facilitator action timestamped
- SQLite `data/helmsman.db` excluded from git