# Capabilities — Workshop Helmsman (v0.1)

Phased list. Each phase ships behind a Gate command that proves the slice works end-to-end before the next phase begins.

---

## Phase 1 — Core Path (this improvement cycle)

**The single most important user journey:** Facilitator creates workshop from template → shares participant link → participants join and fill form → facilitator watches live dashboard → participants complete milestones → facilitator exports CSV.

**What's being improved over the existing v0.1:**

| Area | Improvement |
|------|-------------|
| **Facilitator Dashboard** | Visual polish: stat cards, status pills, real-time feel with live progress bars, per-milestone completion table, cohort stacked bar, paginated help flags with status chips |
| **Participant Join** | Instant validation on name field, better mobile UX (larger touch targets, proper keyboard types), inline error/success states |
| **Agenda/Milestone Management** | Drag-and-drop reorder (Phase 1: up/down buttons), inline edit title/description, milestone order persisted per workshop |
| **Form Builder** | Visual field editor (add/remove/reorder fields), field types: text/dropdown, required toggle, template picker |
| **Broadcast Messaging** | Facilitator → all participants: pinned banner on tracker with dismiss, Markdown-lite rendering |
| **Milestone Controls** | "Advance all to next", "Advance selected", "Pause workshop" (locks completions), per-participant override |
| **Export** | One-click CSV with all data: participants × milestones + form answers + help requests |

**Clearly-labelled stubs (Phase 2+):**
- Multi-workshop concurrent sessions (dashboard switcher)
- Breakout rooms / multiple facilitators per workshop
- Email/Slack notifications on help flags
- Custom domains per workshop (e.g. `acme.workshop.smalltech.in`)
- Participant messaging (chat between participants)

---

## Phase 1 — Surfaces built

1. `GET /admin/new` → form: workshop name, pick agenda template (or inline milestones), pick form template (or inline fields), TTL hours
2. `POST /admin/new` → creates workshop, returns redirect to `/admin/<token>`
3. `GET /admin/<token>` → **polished dashboard**: stat cards, participant table with progress bars + milestone chips, per-milestone completion stats, cohort stacked bar, help flags with status pills + inline status change, broadcast message composer, milestone controls (advance all, pause, reorder)
4. `GET /w/<slug>` → join page: workshop name + form fields, instant validation, mobile-optimized, submit → cookie + redirect
5. `GET /w/<slug>/me` → participant tracker: milestone checklist with mark-complete, progress bar, leaderboard (top 50 + toggle), **broadcast banner**, my help requests with status pills
6. `GET /w/<slug>/data` → JSON: milestones, my progress, leaderboard, help requests, **broadcast message**, **workshop_paused flag**, form schema
7. `GET /admin/<token>/data` → JSON: all participants + progress, per-milestone stats, cohort bar, help requests, broadcast message, workshop_paused, milestone order
8. `POST /w/<slug>/me/complete/<mid>` → mark milestone done (idempotent; blocked if workshop_paused)
9. `POST /w/<slug>/me/help` → create help request (two-step: preview → commit; LLM suggestion stub returns empty)
10. `POST /admin/<token>/broadcast` → set/clear broadcast message
11. `POST /admin/<token>/pause` → toggle workshop_paused
12. `POST /admin/<token>/advance-all` → advance all participants to next incomplete milestone
13. `POST /admin/<token>/advance-selected` → advance selected participant IDs
14. `POST /admin/<token>/milestones/reorder` → persist new milestone order
15. `GET /admin/<token>/export.csv` → streams full CSV
16. `GET /healthz` → `{"status":"ok","db":"ok"}`

---

## Phase 2 — Template Library & Multi-Session (future)

- `/admin/templates` — list/create/edit/delete agenda templates & form templates
- `/admin/new` and `/admin/<token>/edit` include template pickers
- Editing a template never mutates existing workshops (snapshots on create)
- `/workshops` archive page with search/filter, per-session drill-down
- Cohort comparison across sessions of same template

---

## Phase 3 — AI Assist & Notifications (future)

- Optional Gemini via OpenRouter for help-desk pre-resolution
- Facilitator clicks "suggest reply" on help flag → LLM returns short actionable fix → facilitator edits/sends
- Email/Slack webhook notifications when help flags accumulate
- Graceful degradation: no API key = feature silently disabled

---

## Phase 4 — Scale & Multi-tenancy (future)

- PostgreSQL backend (swap SQLite via `DATABASE_URL`)
- Multiple concurrent workshops
- Per-workshop facilitator tokens (rotate, revoke)
- Custom domains / subdomains
- Team/organization grouping

---

## Always-on cross-cutting concerns (any phase)

- Platform-agnostic URLs (no hardcoded host/port)
- Mobile-responsive CSS (grid/flex + viewport meta)
- Health probe at `/healthz` returning JSON
- No secrets required to boot (`.env.example` intentionally empty for core flow)
- Single CSS file, single JS file, no bundler, no node_modules
- Audit trail: every milestone completion, help request, facilitator action timestamped