# Vision — Workshop Helmsman (v0.2)

> This spec supersedes v0.1 entirely, including all v0.1 non-goals (notably "no React / no build step" — v0.2 is a Next.js frontend by explicit user choice). The v0.1 code in `src/` and `frontend/` is removed at scaffold; v0.2 is built fresh from this spec.

## What it is

Workshop Helmsman is a **self-hosted workshop assistant for facilitator-led, hands-on technical labs**. A facilitator creates a workshop, shares one join link, and 100–300+ participants work through a checklist of **content-rich milestones** (full markdown instructions, links, code snippets) on their own devices. The facilitator watches a **genuinely live dashboard** — per-milestone completion, cohort distribution, a help queue — and intervenes with broadcasts, milestone controls, and answers. An **AI help-desk** (OpenRouter) triages help requests: it gathers the participant's context and past resolutions, auto-answers when confident (clearly badged, one tap to escalate to a human), and drafts a reply for facilitator review when unsure. Without an API key, the entire product works air-gapped with zero errors.

It is production-grade from day one: real workshops with external participants depend on it, so polish, resilience, and first-time-right behavior are the bar — not aspirations.

## Who it serves

- **Facilitators** (a small team, co-facilitating the same live workshop) who need to know *right now* which milestone the room is piled up on, who is stuck, and which help requests are open — and to act on it: broadcast, advance, pause, answer, undo a fat-fingered action. No accounts: unguessable token links.
- **Participants** (100–300+ per session, including external attendees) who join with near-zero friction (name at the door), get a personal link that survives device switches and browser restarts, see rich instructions per milestone, mark progress, watch a leaderboard, and get help fast — from the AI instantly when it's confident, from a human otherwise.

## Session lifecycle

Workshops are created fresh per session — from scratch or from a persistent **template library** (agenda templates + join-form templates). A live workshop ends into a **grace period** for stragglers, then becomes a **read-only archive**, browsable forever. Workshops are clonable/re-runnable. Full session archives persist indefinitely.

## Quality bar

- **First-time-right.** Every phase's tested path works the first time the user tests it. Zero rough edges on the tested path; stubs for future features are clearly labelled and never read as bugs.
- **Resilient by construction.** All state lives in the database, never only in memory. A participant who reconnects gets their exact state back. A server restart mid-session loses nothing — every client recovers on its next poll with no user action.
- **Live at scale on modest hardware.** 300+ concurrent participants on a 2 vCPU / 2–4 GB VM, near-zero running cost (see [architecture.md](architecture.md) for the coalesced-polling design that achieves this).
- **Visually excellent.** A modern, polished UI with a consistent design system — this is the product's face to external participants. Every view designs its empty, loading, error, and populated states.
- **Honest AI.** AI answers are always badged as AI, always escapable to a human, always audited with the exact context the AI used, and always costed (per-workshop spend visible).

## Explicit non-goals (v0.2)

- **No participant accounts, no facilitator accounts, no auth-provider integration.** Access is via unguessable token links plus a single instance-level facilitator access key.
- **No separate concurrent-workshop isolation model.** Multiple facilitators co-run the *same* workshop; running several workshops at once is possible but not a designed-for isolation boundary (one team, one instance).
- **No lecture mode or multi-day cohort mode** — future versions, not v0.2.
- **No external integrations** (no Slack/email/webhooks/calendar). Standalone.
- **No participant-to-participant chat, no breakout rooms.**
- **No WebSockets/SSE** — live updates are versioned coalesced polling (a deliberate architecture decision, see architecture.md).
- **No dark mode in v0.2** — one polished light theme; design tokens are structured so dark mode can be added later without rework.
- **No health/ops chrome in the UI** — a plain `/api/health` endpoint exists for machines; the UI stays clean.
- **No vector database** — help-request similarity uses SQLite FTS5 keyword search (see [agent.md](agent.md)).

## The one-line test

A facilitator with a fresh VM can go from `docker compose up` (or `uv run python -m src`) to a live workshop with 300 external participants tracking milestones and getting help — without reading anything beyond the join link they share.
