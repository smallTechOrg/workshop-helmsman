# Vision — Workshop Helmsman (v0.1)

## What it is

Workshop Helmsman is a self-hosted workshop tracker for **remote, facilitator-led sessions with 100+ participants**. It gives a **facilitator** a live dashboard of where every participant is in the curriculum and surfaces "I need help" requests in real time, while each **participant** gets a personal tracker page (progress bar, "mark milestone complete" buttons, a help form, a leaderboard of peers, and facilitator announcements).

It is opinionated, no-LLM-required, air-gap-friendly, and reusable: the same codebase runs any number of workshops back-to-back via unique tokens.

## Who it serves

- **Facilitators** running live online workshops who want to see at a glance which participants are stuck, in addition to seeing who is keeping pace. They need to intervene — broadcast announcements, advance milestones, pause the room, send targeted hints.
- **Participants** who need a stable URL they can pin on their phone, a clear view of "what's left", a low-friction way to ask for help without disrupting the room, and a sense of progress alongside peers.

## Non-goals

- No LLM in the core loop. No external API calls required. Everything stays on the single VM.
- No multi-tenant SaaS, no auth provider integration beyond the workshop tokens.
- No React/Vue/webpack. Server-rendered Jinja2 + vanilla JS, polling-based sync.
- No breakout rooms, no participant-to-participant chat (Phase 2+).

## Core interaction model

- **Session shape:** Facilitator creates a *new workshop per session* from a reusable template. Participants join that session's unique link. Workshop has TTL (default 8h).
- **Memory/state:** Workshop templates (agenda + form schema) persist forever. Each session gets its own snapshot. Participant progress, form answers, and help requests persist *within a session*. Templates carry across sessions; session data does not.
- **Multi-item:** Facilitator manages a library of agenda templates and form templates. Can pick one of each when creating a new session. Can also edit the session's snapshot without affecting the template.
- **Error handling:** Participant join validates name instantly. Help requests go through 2-step preview (optional LLM suggestion) then commit. Facilitator actions (advance, broadcast, pause) are immediate with optimistic UI — next poll (≤4s) confirms.

## Technical stack

- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2.x, SQLite (dev) / PostgreSQL (prod)
- **Frontend:** Jinja2 templates, vanilla JS (single `app.js`), one CSS file (`style.css`). Mobile-responsive participant view.
- **Auth:** Token-based (admin_token in URL, participant_slug in URL). HttpOnly cookie for participant session.
- **Real-time:** Short polling (4s) — no WebSockets. Single `/data` endpoint serves both participant tracker and admin dashboard (different shapes via query param).
- **Deploy:** Docker Compose + systemd unit. Runs on single VM.
- **LLM:** Optional — Google Gemini via OpenRouter (`OPENROUTER_API_KEY` in `.env`). Phase 3 help-desk pre-resolution only. Graceful fallback if unavailable.