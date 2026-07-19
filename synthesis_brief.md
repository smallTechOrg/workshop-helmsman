# Synthesis Brief — Improved Workshop Helmsman

## What the agent does & who uses it
A self-hosted workshop tracker for **remote, facilitator-led sessions with 100+ participants**. Facilitators create a workshop (agenda + milestones + custom join form), get a participant link and admin token, and run the session in real time. Participants join via slug, fill the onboarding form, and progress through milestones. The facilitator watches a live dashboard with per-participant progress, cohort completion bars, and real-time help requests — and can advance milestones, broadcast announcements, or send targeted hints. After the session, data exports as CSV/JSON.

**Primary users:** Facilitators running multi-session workshops (same template, new cohort each time). Participants join via browser, no accounts needed.

## Core interaction model
- **Session model:** Facilitator creates a *new workshop per session* from a reusable template. Participants join that session's unique link. Multiple sessions from the same template can run in parallel (different groups).
- **Memory/state:** Workshop templates (agenda + form schema) persist forever. Each session gets its own snapshot. Participant progress + help requests + form answers persist *within a session*. Templates carry across sessions; session data does not.
- **Multi-item:** Facilitator manages a library of agenda templates and form templates. Can pick one of each when creating a new session. Can also edit the session's snapshot without affecting the template.
- **Error/ambiguity handling:** Participant help requests appear in facilitator dashboard in real time. Facilitator can respond with hints/announcements. If LLM (Gemini) is configured, it pre-suggests a resolution before the facilitator sends it — but the facilitator always approves/edits before the participant sees it.

## Key capabilities & features
| Capability | Detail |
|------------|--------|
| **Agenda builder** | Ordered milestones with title + description. Defined in template, instantiated per session. |
| **Milestone tracking** | Participant marks completion; facilitator sees live % and per-milestone counts. |
| **Participant roster** | Auto-created on join. Custom form fields (text, dropdown, required). "Display name" field guaranteed. |
| **Facilitator controls** | Advance/pause milestones globally or per-participant. Broadcast announcement to all. Send targeted hint to one participant (with optional LLM pre-draft). |
| **Live dashboard** | Table: name, joined, progress %, current milestone, help status. Cohort stacked-bar: how many at 0/1/2… done. Per-milestone completion stats. Paginated help requests with status pills (open/on_hold/resolved). |
| **Participant view** | Personal tracker: my milestones (checklist), my form answers (read-only), my help requests, announcements banner. Polls `/w/<slug>/data` every ~4s. |
| **Exports** | CSV: one row per (participant, milestone) with form answers as columns. JSON: full session dump. |
| **Templates library** | Save/load agenda templates and form templates. Edit template → new sessions pick it up; existing sessions keep their snapshot. |
| **AI assist (optional)** | When facilitator clicks "suggest reply" on a help request, call Gemini with context (milestones, help tips, participant's message) → returns one short actionable suggestion. Facilitator edits/sends. Never auto-sends. |

## Hard constraints
- **Scale:** 100+ participants per session, single session at a time (but template reuse means many sessions over time). Efficient polling, indexed DB queries, no N+1.
- **Privacy:** Full cloud deployment OK with standard encryption. Participant PII = name + custom form fields. No data leaves the server unless facilitator exports.
- **Reliability:** Production-ready. Audit trail: every milestone completion, help request, and facilitator action timestamped. No "prototype" tolerances.
- **No LLM required for core loop:** Core facilitation works 100% offline. Gemini is purely a *facilitator-time saver* for help replies.

## Technical stack & access model
- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2.x, SQLite (dev) / PostgreSQL (prod via `DATABASE_URL`).
- **Frontend:** Jinja2 templates + vanilla JS (polling), one CSS file. Mobile-friendly participant view.
- **Auth:** Workshop-scoped tokens. Admin token in URL (`/admin/<token>`). Participant slug in URL (`/w/<slug>`). Participant cookie for return visits.
- **LLM:** Google Gemini (via `GEMINI_API_KEY` in `.env`). Model: `gemini-1.5-flash` (cheap, fast). If key missing, AI assist silently disabled — no degradation.
- **Access:** Web UI for both facilitator and participants. No CLI, no separate API surface needed (poll endpoint is the API).

## Phase 1 — Core Path (smallest user-testable win)
**Goal:** Facilitator creates a workshop from a template (or blank), gets two links. Participants join, fill name + one custom field, see milestone checklist. Facilitator sees live dashboard with progress bars. No AI, no templates library, no exports, no announcements — just the happy path.

**Surfaces built in Phase 1:**
1. `GET /admin/new` → form: workshop name, pick agenda template (or inline milestones), pick form template (or inline fields), TTL hours.
2. `POST /admin/new` → creates workshop, returns redirect to `/admin/<token>`.
3. `GET /admin/<token>` → dashboard: participant table (name, progress %, current milestone), per-milestone counts, cohort bar. Polls `/admin/<token>/data` every 4s.
4. `GET /w/<slug>` → join page: shows workshop name + form fields. On submit, creates participant, sets cookie, redirects to `/w/<slug>/me`.
5. `GET /w/<slug>/me` → participant tracker: milestone checklist (click to mark done), my form answers (read-only). Polls `/w/<slug>/data`.
6. `GET /w/<slug>/data` → JSON: milestones, my progress, leaderboard (top 50), announcements (empty in Phase 1).
7. `GET /admin/<token>/data` → JSON: all participants + progress, per-milestone stats, cohort bar, help requests (empty in Phase 1).
8. `POST /w/<slug>/me/complete/<mid>` → mark milestone done (idempotent).
9. `POST /w/<slug>/me/help` → create help request (Phase 1: just stores it; dashboard shows it).
10. Health endpoint `/healthz`.

**Clearly-labelled stubs (Phase 2+):** Template library (`/admin/templates/*`), agenda template picker, form template picker, announcements, AI assist, CSV/JSON export, clone workshop, archive workshop, per-participant drill-down, facilitator milestone advance controls.