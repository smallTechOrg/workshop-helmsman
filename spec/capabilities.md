# Capabilities — Workshop Helmsman (v0.1)

Phased list. Each phase ships behind a Gate that proves the slice works end-to-end.

## Phase 1 — Core Path ✅
**Goal:** Facilitator creates workshop from template → shares participant link → participants join and fill form → facilitator watches live dashboard → participants complete milestones → facilitator exports CSV.

### Phase 1 — UX Polish (this improvement cycle) ✅
**Goal:** Polish the Phase 1 happy path with modern visual design, better mobile UX, instant validation, and facilitator controls that feel real-time.

| Capability | Detail |
|---|---|
| **Facilitator dashboard polish** | Cards with elevation, status pills (live/expired/archived), progress bars with smooth animations, milestone chips, cohort stacked bar with legend, per-milestone stats, responsive grid |
| **Participant join form** | Cleaner card layout, workshop name prominent, instant inline validation (required fields, dropdown required selection), better mobile input sizing, touch-friendly targets (44px min) |
| **Participant tracker** | Milestone checklist with check animations (CSS transition), broadcast announcement banner (dismissible), "My answers" panel (read-only form responses), help request 2-step preview (LLM suggestion → confirm), smooth progress bar animation |
| **CSS: Modern visual system** | Design tokens (spacing scale --space-1..8, color tokens, elevation shadows, border-radius scale), fluid typography with clamp(), responsive breakpoints (480, 720, 1024), elevation system (surface/raised/overlay), focus-visible states, reduced-motion support |
| **JS: Smooth polling & interactions** | Single poll loop with requestAnimationFrame scheduling, broadcast message handling (banner + auto-dismiss), milestone advance controls (facilitator: "Advance all to next"), optimistic UI for milestone complete, help request 2-step flow in JS |

### Clearly-labelled stubs (Phase 2+)
- Multi-workshop concurrent sessions (dashboard switcher)
- Breakout rooms / multiple facilitators per session
- Email/Slack/webhook notifications on help flags
- Custom domains per workshop (CNAME mapping)
- Participant-to-participant messaging (chat)
- Webhooks / REST API for external integrations

## Phase 2 — Template Library & Multi-Session (planned)
- `/admin/templates` — CRUD for agenda templates + form templates
- Workshop cloning with template reference preserved
- `/workshops` archive page with search/filter, cohort comparison
- Per-participant drill-down page (`/admin/<token>/participant/<pid>`)

## Phase 3 — AI Assist & Polish (planned)
- LLM suggestion on help flags (OpenRouter/Gemini, optional key)
- Facilitator "help tips" (FAQ) injected into LLM context
- Mobile-first participant tracker polish
- Accessibility audit (WCAG AA)

## Phase 4 — Scale & Ops (planned)
- 100+ participant load testing, query optimization
- PostgreSQL production config, migrations
- Docker Compose + systemd unit + health checks
- Structured logging, metrics endpoint