# Capabilities — Workshop Helmsman (v0.2)

Four core capabilities (C1–C4) carry the product; C5–C7 open it to the public in Phase 6; everything else is deferred to a named phase (§Deferred). API shapes live in [api.md](api.md); schema in [data-model.md](data-model.md); phase plan in [roadmap.md](roadmap.md). This file also carries the UI specification (pages, components, states, stub placements) — there is no separate ui.md.

## Design system (applies to every page)

- Tailwind v4 design tokens in `globals.css` `@theme`: brand **indigo** (`--color-brand-*`), warm neutral scale, semantic colors (success green, warning amber, danger red, AI **violet**), one radius scale (lg cards, md controls), one shadow scale, spacing on the 4px grid. Type: Inter (via `next/font`, system fallback); body ≥16px; `text-sm` only for metadata. Light theme only (vision non-goal).
- Shared primitives in `frontend/components/ui/`: `Button` (primary/secondary/ghost/danger; loading state), `Card`, `Badge` (status pills), `ProgressBar`, `Toast`, `Modal`, `Skeleton`, `EmptyState` (icon + one-line explanation + one action), `Markdown` (react-markdown + gfm + highlight; raw HTML off), `CopyButton` (copies + "Copied" feedback), **`StubBadge`** — the labelled-stub primitive: a muted card/section with a `Coming in a later phase` pill, short description of what will live there, non-interactive. Every future feature surface renders through `StubBadge` so a stub is never mistaken for a bug.
- Every view designs all four states (empty / loading / error / populated) per `harness/patterns/ui-ux.md`. Loading = skeletons with context, never blank. Errors = human sentence + next step, never a stack trace. All interactive elements keyboard-reachable with visible focus; semantic HTML; WCAG AA contrast.
- **Connection indicator:** both live pages show a quiet "reconnecting…" pill after 2 consecutive failed polls, clearing silently on recovery. Never a modal, never data loss (state is in the DB).

---

## C1 — Workshop creation & facilitator access *(Phase 1)*

Facilitators enter once with the instance access key, then create and reach workshops via token links.

**Pages:**
- **Admin Home — `/app/`**: first visit shows a centered access-key card (one password field, "Enter"; wrong key → inline "That key doesn't match this server's `HELMSMAN_ADMIN_KEY`"). Valid key (checked via `GET /api/admin/workshops`) is kept in `localStorage` and sent as `X-Admin-Key`. Then: workshop list grouped **Live / Upcoming / Ended** (Phase 1: everything is Live; Upcoming/Ended groups render as labelled stubs), each card showing name, participant count, open-help count, created date, buttons **Open dashboard** and **Copy join link**. Empty state: "No workshops yet — create your first." Header button **New workshop**. Stub surfaces on this page: **Template library** nav item (StubBadge, Phase 3).
- **Create workshop** (route `/app/` modal or section): name, description (markdown textarea), and a milestone builder — ordered rows of *title + markdown content editor + minutes*, add/remove/move up-down, live markdown preview per milestone (tabs Write/Preview). A **template picker** renders as a labelled stub (Phase 3). Submit → success screen presenting the two links prominently with copy buttons and a plain-language warning: *"The facilitator link is the only key to this dashboard — save it now."*

**Behavior:** `POST /api/admin/workshops`; workshop is `live` immediately; audit row written. Success criteria: create → dashboard reachable via returned `facilitator_url`; join link works; refresh of Admin Home lists the workshop with live counts.

---

## C2 — Frictionless participant identity *(Phase 1)*

Join with a name; never lose your place.

**Pages:**
- **Join — `/app/join/?s=<slug>`** (pretty link `/j/<slug>` on the door): workshop name + description (markdown), milestone count, participant count ("143 people are in"), one **name field** + **Join** button. Instant validation (1–80 chars, trimmed). If `GET /api/join/{slug}` returns `me` (cookie auto-resume), skip the form: "Welcome back, Priya" → auto-forward to the tracker. Errors: unknown slug → friendly "This workshop link isn't valid — check with your facilitator." Archived → "This workshop has ended" with a **Browse archive** link (read-only tracker).
- After join: the tracker shows a dismissible one-time callout: *"This page's link is yours — it works on any device. Save it."* with a copy button for `participant_url`.

**Identity mechanics (architecture.md §Auth):** cookie `helmsman_p_{workshop_id}` (HttpOnly, 30 d) for same-browser auto-resume; the personal link `/p/<token>` is the cross-device credential; the facilitator dashboard's participant table shows a **copy personal link** button per row — the lost-link recovery path ("what's your name? → here's your link"). Reconnect/restart restores exact state on the next poll because all state is in the DB.

**Success criteria:** join in <10 s from link tap; browser restart auto-resumes; the personal link opens the identical state on a second device; a facilitator can recover any participant's link in two clicks.

---

## C3 — Content-rich milestone tracking, live *(Phase 1)*

The heartbeat: participants work milestones; the facilitator watches the room move.

**Participant Tracker — `/app/p/?t=<token>`** (pretty `/p/<token>`):
- Sticky header: workshop name, my **progress bar** with `n / total`, connection indicator.
- **Milestone checklist**: one card per milestone in position order — checkbox + title + minutes chip + collapsible **markdown body** (instructions, links, code snippets with syntax highlighting + copy-code button). Current milestone (lowest incomplete) is auto-expanded and visually accented; completed ones collapse with a green check. **Mark complete** is optimistic (instant check, reconciled by poll); un-mark available via the checkbox ("fixed a mis-click"). Paused workshop (Phase 2) disables checkboxes with a banner — the Phase 1 payload already carries `paused`.
- **Leaderboard panel** (side on desktop, tab on mobile): full ranked list, full names always on, my row highlighted and pinned when off-screen; top-3 subtle medals. Renders all rows (virtualized past 50).
- **Help panel**: C4 below. **Broadcast banner slot**: renders active broadcast (Phase 2 data); in Phase 1 an inline StubBadge in the panel footer notes "Announcements from your facilitator will appear here."
- Data: `state` poll 3 s (visible) / 15 s (hidden) + `content` fetch keyed by `content_version`. Loading = full-page skeleton mirroring the layout.

**Facilitator Dashboard — `/app/f/?t=<admin_token>`** (pretty `/f/<token>`), the mission-control view, 2 s poll:
- **Header**: workshop name, status pill, participant/active counts, **Copy join link**, connection indicator. Stub actions (StubBadge’d in Phase 1): **Broadcast**, **Pause**, **End workshop**, **AI toggle**, **Spend**.
- **Stat row**: participants, active (5 min), finished, median progress, open help — large-number cards.
- **Per-milestone completion**: horizontal bars per milestone (completed_count / participants, percentage), highlighting the milestone where the largest group currently sits.
- **Cohort distribution**: histogram of participants by completed-count (0…total) — the room's shape at a glance.
- **Participant table**: name, progress bar + count, per-milestone dots (done/current/todo), joined/last-seen, open-help badge, **copy personal link**. Client-side sort (progress/name/joined) and name filter. 300 rows: virtualized.
- **Help queue**: C4 below. **Proactive-intelligence rail**: stuck alerts / bottleneck / session pulse render as three labelled stub cards in Phase 1 (fields already `null` in the payload), real in Phase 2. **Audit trail** tab: StubBadge in Phase 1.

**Success criteria:** a completion on a phone is visible on the dashboard within one poll cycle (≤2 s + RTT); per-milestone bars and distribution always sum consistently with the table; 300 participants render without jank; markdown code blocks are highlighted and copyable.

---

## C4 — Help desk *(Phase 1 manual; Phase 4 adds AI in front)*

A participant raises a hand without disrupting the room; help arrives in-page.

**Participant side (tracker help panel):** "Need help?" card — one textarea ("What are you stuck on? Your facilitator sees this immediately"), submit → optimistic entry in **My help requests**: message (plain text, `pre-wrap`), status pill (`open` = amber "Waiting", `answered` = blue "Answered", `resolved` = green), timestamps. Answers render as markdown reply bubbles; a facilitator answer flashes/highlights on arrival via poll. Buttons: **Mark resolved** (own requests). Phase 4 adds: instant AI answers badged **AI** (violet) with **Get a human** escalation; Phase 1 shows no AI chrome at all (nothing to stub on the participant side — absence is the honest state).
- Empty state: "Stuck? Ask here — answers appear right on this page."

**Facilitator side (dashboard help queue):** cards newest-open-first — participant name, their current milestone chip, message (plain text), age ("4 m ago"), status pill, escalated flag (Phase 4). Inline **reply composer** (markdown textarea with preview, "Answer" button) + **Mark resolved**. Answer → participant sees it next poll; request → `answered`; stays visible until participant (or facilitator) resolves. Resolved section collapsed with count. Every answer writes an audit row. Phase 4 adds: AI draft block (violet, confidence %, editable, "Send") and the expandable **"Context the AI used"** disclosure on AI answers.
- Empty state: "No open help requests — the room is cruising."

**Success criteria:** request → visible in queue within one dashboard poll; answer → visible on tracker within one tracker poll; full loop (submit → answer → see → resolve) with zero manual refreshes; markdown answers with code render correctly; every answer audited (who/what/when).

---

## C5 — Public landing page *(Phase 6)*

The instance's front door for a stranger who has never heard of Workshop Helmsman.

**Page — `/` (also reachable at `/app/`; serving mechanism in [architecture.md](architecture.md) §Serving the landing page at `/`):** a real marketing page, not a redirect. It is the first thing a stranger sees, so it carries the same design-system bar as every other surface — same tokens, same primitives, responsive from 360px up, WCAG AA, keyboard-reachable, no layout shift.

Sections, in order:

1. **Hero** — product name + one-sentence promise + a single **primary CTA "Create your workshop — free, no signup"** → `/app/create/`, carrying `data-testid="landing-cta"` (the gate greps the served HTML for it). A secondary "See how it works" anchor-scrolls. No second competing CTA.
2. **Feature sections** — one block each, with a short honest headline and 1–2 sentences: live progress dashboard across 300+ participants · content-rich markdown/code milestones · frictionless name-only joining with cookie auto-resume and personal cross-device links · real-time help desk · broadcast / pause / advance room controls · proactive stuck-and-bottleneck alerts · audit trail · CSV export.
3. **"How it works"** — the facilitator→participant loop in numbered steps: compose milestones → share one join link → the room joins by name → watch the dashboard move → answer help in-page → export the results.
4. **"Your workshops"** — rendered **only** when the browser's `localStorage` holds entries (see C6): a list of `{name, created_at}` with **Open dashboard** and **Copy join link**, plus the line *"Remembered by this browser only — not an account. Keep your dashboard link somewhere safe."* Absent entirely on a fresh browser (no empty state, no teaser).
5. **FAQ** — the honest limits, stated plainly: no account and no login (a link is the credential) · the dashboard link is the *only* way back in — save it · clearing your browser loses the "your workshops" list but not the workshop · participants need only a browser · it is self-hosted and free · your creation email is used only so the operator can contact you, never for mail-outs.
6. **Footer** — repo/licence line. **No link to the admin console** anywhere on the page.

**Constraints (load-bearing, from architecture.md):** static server component — no router hooks, no data fetching except the client-side `localStorage` read in section 4 (which is a small `"use client"` island so the rest stays static); all outbound links are plain `<a href="/app/…">`, never `next/link`.

**Success criteria:** `GET /` returns 200 `text/html` (not 307) and renders the hero, all eight feature blocks, the how-it-works steps and the FAQ · the primary CTA navigates to `/app/create/` · CSS and fonts load (no unstyled flash — real Tailwind utilities present in the served CSS) · no "Your workshops" section on a fresh browser · no admin link present in the DOM · renders without horizontal scroll at 360px and at 1440px.

---

## C6 — Self-service workshop creation *(Phase 6)*

Anyone can create and host a workshop without ever touching an access key. **Same flow the admin already uses** — not a reduced one.

**Page — `/app/create/` (no key gate):** the identical milestone composer used by the admin console — name, description (markdown), ordered milestone rows (title + markdown editor with Write/Preview + minutes + per-milestone completion input config), add/remove/move, join-form fields. The composer is a **shared component** used by both `/app/admin/` and `/app/create/`; it is not copied.

**Final step — email, then reveal.** After the workshop is composed, the last step before anything is created asks for the creator's email: one field, inline format validation, a one-line explanation (*"So we can reach you about your workshop. We never send you mail and never share it."*), and the **Create workshop** button. Submitting calls `POST /api/public/workshops` ([api.md](api.md) §Phase 6) with the composed workshop **and** the email in one request — nothing is persisted before the email is given.

**Success screen (the reveal):** both links shown prominently with copy buttons — the **facilitator dashboard link** first, under the plain-language warning *"This link is the only key to your dashboard. Save it now — there is no account and no password reset."* — then the **join link** to share with the room. A **Open my dashboard** button goes to the facilitator dashboard. On this screen the workshop is written to the browser's `localStorage` list (C5 §4): `{name, facilitator_url, join_url, created_at}`, capped at the 20 most recent.

**Facilitator parity:** the creator lands on the normal facilitator dashboard with **every** facilitator capability — broadcast, pause, advance, reorder, edit/add/delete milestones, undo, help desk, audit tab, CSV export, settings. There is no reduced tier and no surface anywhere that behaves differently because `created_via = "public"`.

**Errors:** invalid/blank email → inline field error from `validation_error`, the composed workshop is preserved in the form (never lost) · network/500 → toast "Couldn't create your workshop — try again", form preserved.

**Success criteria:** a browser that has never sent an admin key can compose and create a workshop from `/` in one sitting · nothing is created until the email is supplied · a malformed email returns `validation_error` and creates no row · the returned facilitator link opens a dashboard with the full facilitator toolset · the join link admits a participant who then appears live on that dashboard · the created row is identical to an admin-created one apart from `creator_email` and `created_via`.

---

## C7 — Admin oversight of public workshops *(Phase 6)*

The admin keeps the only cross-workshop view, and can now see where each workshop came from.

**Page — `/app/admin/` (pretty `/admin`):** the existing Admin Home, **behaviour unchanged**, moved off `/`. The key gate, the `X-Admin-Key` handling, the grouping, the create flow and the template library all work exactly as before. Two additions to each workshop card in the list:

- an **origin badge** — `Public` (brand-tinted) or `Admin` (neutral);
- the **creator email** as metadata on public-created cards (plain text, selectable, `mailto:` link), absent on admin-created ones.

`creator_email` appears here and nowhere else — never on a facilitator, participant or public surface.

**Success criteria:** entering the key at `/admin` lists every workshop including public-created ones · a public-created workshop shows its `Public` badge and the exact email the creator entered · an admin-created workshop shows `Admin` and no email · every pre-existing admin flow still works from the new URL · `/` never exposes the admin console or its link.

---

## Deferred capabilities (schema exists from Phase 1; features arrive at their phase)

| Capability | Phase | One-line scope |
|---|---|---|
| Broadcast announcements | 2 | Markdown composer → pinned participant banner; history; clear; undoable |
| Milestone controls | 2 | Advance all/selected, pause/resume, reorder, edit/add/delete milestones mid-session |
| Undo | 2 | 30 s inverse-operation window for advance-all/selected, pause, broadcast |
| Audit trail UI | 2 | Dashboard tab over `facilitator_action` (every facilitator + AI action, who/what/when) |
| Proactive intelligence | 2 | Stuck-participant alerts (`stuck_minutes`), bottleneck detection, session pulse (pace vs plan, % on track, projected finish) |
| Lifecycle: end / grace / archive | 3 | End workshop → straggler grace window → read-only archive, browsable forever; lazy transitions |
| Clone / re-run | 3 | New workshop from an old one: milestones copied, fresh tokens, zero participants |
| Agenda template library | 3 | CRUD + create-from-template + save-workshop-as-template; instantiation snapshots |
| Join-form templates & custom fields | 3 | Extra join fields (text/dropdown) from persistent form templates; answers on the participant record |
| Admin Home lifecycle grouping | 3 | Live / Upcoming / Ended real; `starts_at` scheduling; archive browsing |
| AI triage & auto-answer | 4 | Context-gathering → confidence-routed auto-answer/draft (see [agent.md](agent.md)) |
| AI escalation & transparency | 4 | "Get a human" one-tap; AI badge; expandable exact-context view in the queue |
| Cross-workshop learning corpus | 4 | FTS5 similarity over all past resolutions — replaces canned replies, improves with use |
| AI spend & toggle & air-gap | 4 | Per-workshop cost from OpenRouter usage; per-workshop enable; keyless = zero AI chrome errors |
| Docker Compose packaging | 5 | One-container deploy, volume-backed SQLite, multi-stage build |
| CI/CD to GCP | 5 | GitHub Actions: tests on PR; image build + VM deploy on main; runbook |
