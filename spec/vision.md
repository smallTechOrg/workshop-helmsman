# Workshop Helmsman — Vision

## What it is

Workshop Helmsman is a self-hosted, single-VM workshop tracker for running remote AI
workshops. It gives a **facilitator** a live dashboard of where every participant is in
the curriculum and surfaces "I need help" requests in real time, while each
**participant** gets a personal tracker page (progress bar, "mark milestone complete"
buttons, a help form, and a leaderboard of peers).

It is opinionated, no-LLM, air-gapped-friendly, and reusable: the same codebase runs any
number of workshops back-to-back via unique tokens.

## Who it serves

- **Facilitators** running live online workshops who want to see at a glance which
  participants are stuck, in addition to seeing who is keeping pace.
- **Participants** who need a stable URL they can pin on their phone, a clear view of
  "what's left", and a low-friction way to ask for help without disrupting the room.

## Non-goals

- No LLM in the loop. No external API calls. Everything stays on the single VM.
- No multi-tenant SaaS, no auth provider integration beyond the workshop tokens.
- No React/Vue/webpack. Server-rendered Jinja2 + vanilla JS, polling-based sync.
