# Data Model — Workshop Helmsman (v0.2)

SQLAlchemy 2.x declarative models in `src/helmsman/db/models.py`; schema managed by Alembic (the `0001_initial` migration creates the **full v0.2 schema below**, even though later phases activate some tables). All state lives here — never only in process memory (resilience rule). All `DateTime` columns are timezone-aware UTC. JSON payloads are stored as `Text` (portable across SQLite/PostgreSQL).

**Phase activation:** the "Phase" column says when the app first *writes/uses* the field — the schema itself exists from Phase 1 so later phases never migrate-and-backfill mid-season.

Conventions: integer autoincrement PKs; `created_at` default now; `updated_at` onupdate now where noted; FK columns always indexed.

---

## workshop

The unit of a live session. One row per run.

| Column | Type | Constraints | Phase | Notes |
|---|---|---|---|---|
| id | Integer | PK | 1 | |
| name | String(120) | not null | 1 | |
| description_md | Text | not null, default `''` | 1 | Shown on join page; markdown |
| admin_token | String(64) | not null, **unique, indexed** | 1 | `token_urlsafe(32)` |
| join_slug | String(16) | not null, **unique, indexed** | 1 | `token_urlsafe(6)` |
| status | String(16) | not null, default `'live'` | 1 (`live`), 3 (rest) | `upcoming` \| `live` \| `grace` \| `archived` |
| starts_at | DateTime | nullable | 3 | Set → `upcoming` until reached (lazy transition) |
| ended_at | DateTime | nullable | 3 | Facilitator pressed "End workshop" |
| grace_until | DateTime | nullable | 3 | End of straggler window; passed → `archived` (lazy) |
| grace_hours | Integer | not null, default `24` | 3 | Chosen at end time |
| paused | Boolean | not null, default false | 2 | Blocks milestone completions |
| state_version | Integer | not null, default `0` | 1 | Bumped (same transaction) on ANY change a poller can see |
| content_version | Integer | not null, default `0` | 1 | Bumped only on milestone content/order changes |
| ai_enabled | Boolean | not null, default `false` | 4 | Per-workshop AI toggle |
| join_form_json | Text | not null, default `'[]'` | 3 | Snapshot of extra join fields (see JSON shapes) |
| stuck_minutes | Integer | not null, default `10` | 2 | Stuck-alert threshold (per workshop) |
| cloned_from_id | Integer | FK workshop.id, nullable | 3 | Provenance of a clone |
| agenda_template_id | Integer | FK agenda_template.id (SET NULL), nullable | 3 | Which template instantiated it |
| created_at | DateTime | not null | 1 | |
| updated_at | DateTime | not null, onupdate | 1 | |

Indexes: unique(admin_token), unique(join_slug), ix(status).

**Status lifecycle (Phase 3):** `upcoming` → (starts_at reached) → `live` → (End workshop) → `grace` → (grace_until passed or Archive-now) → `archived`. Transitions are applied lazily inside any workshop-scoped request; `archived` is terminal and read-only (every mutation returns `workshop_archived`). Phase 1–2 workshops are created directly `live` and stay `live`.

---

## milestone

A real table (not JSON): per-milestone stats over 300 participants need indexed GROUP BYs, and the AI phase needs per-milestone content lookup.

| Column | Type | Constraints | Phase | Notes |
|---|---|---|---|---|
| id | Integer | PK | 1 | |
| workshop_id | Integer | FK workshop.id CASCADE, not null | 1 | |
| position | Integer | not null | 1 | 0-based display order; reordering rewrites positions |
| title | String(200) | not null | 1 | |
| content_md | Text | not null, default `''` | 1 | Rich markdown: instructions, links, code snippets. ≤20,000 chars |
| minutes | Integer | nullable | 1 | Facilitator's time estimate; feeds pulse/projection (Phase 2) |
| created_at | DateTime | not null | 1 | |
| updated_at | DateTime | not null, onupdate | 1 | |

Indexes: ix(workshop_id, position).

**Semantics:** checklist, any order — participants may complete milestones in any sequence (no gating). A participant's **current milestone** = lowest-position incomplete milestone (used for help context, bottleneck detection). **Progress** = completed ÷ total milestones.

---

## participant

| Column | Type | Constraints | Phase | Notes |
|---|---|---|---|---|
| id | Integer | PK | 1 | |
| workshop_id | Integer | FK workshop.id CASCADE, not null | 1 | |
| name | String(80) | not null | 1 | Trimmed; duplicates allowed (disambiguated by join time in UI) |
| token | String(32) | not null, **unique, indexed** | 1 | `token_urlsafe(16)` — personal link + cookie value |
| answers_json | Text | not null, default `'{}'` | 3 | Custom join-form answers `{field_key: value}` |
| joined_at | DateTime | not null | 1 | |
| last_seen_at | DateTime | not null | 1 (write), 2 (read) | Touched by polls, throttled to once/60s; feeds presence + stuck alerts |

Indexes: unique(token), ix(workshop_id).

---

## milestone_completion

| Column | Type | Constraints | Phase | Notes |
|---|---|---|---|---|
| id | Integer | PK | 1 | |
| participant_id | Integer | FK participant.id CASCADE, not null | 1 | |
| milestone_id | Integer | FK milestone.id CASCADE, not null | 1 | |
| source | String(16) | not null, default `'participant'` | 1 (`participant`), 2 (`facilitator`) | Who marked it (advance-all/selected writes `facilitator`) |
| completed_at | DateTime | not null | 1 | |

Indexes: **unique(participant_id, milestone_id)** (idempotent completes), ix(milestone_id) (per-milestone stats), ix(participant_id).

Un-marking deletes the row (participants may fix a mis-click; history of the fix lives in the log stream, not the table).

---

## help_request

| Column | Type | Constraints | Phase | Notes |
|---|---|---|---|---|
| id | Integer | PK | 1 | |
| workshop_id | Integer | FK workshop.id CASCADE, not null | 1 | Denormalized for queue + cross-workshop learning queries |
| participant_id | Integer | FK participant.id CASCADE, not null | 1 | |
| milestone_id | Integer | FK milestone.id (SET NULL), nullable | 1 | The participant's current milestone at submit time |
| message | Text | not null | 1 | 1–4000 chars; participant-authored → rendered as plain text |
| status | String(16) | not null, default `'open'` | 1 | `open` \| `answered` \| `resolved` |
| escalated | Boolean | not null, default false | 4 | Participant tapped "get a human" after an AI answer → back to `open`, flagged |
| ai_state | String(16) | nullable | 4 | `pending` \| `answered` \| `draft` \| `failed` \| `skipped` — pipeline observability |
| created_at | DateTime | not null | 1 | |
| updated_at | DateTime | not null, onupdate | 1 | |

Indexes: ix(workshop_id, status, created_at) (queue), ix(participant_id).

**Status semantics:** `open` = awaiting an answer (facilitator queue). `answered` = an answer is visible to the participant (AI auto-answer or facilitator reply) — stays that way until the **participant** marks `resolved` (or the facilitator closes it). `escalated=true` returns status to `open` with the flag set; prior AI answers remain visible.

---

## help_answer

One request can accumulate answers (AI draft → AI answer → facilitator follow-up), so answers are rows, not columns.

| Column | Type | Constraints | Phase | Notes |
|---|---|---|---|---|
| id | Integer | PK | 1 | |
| help_request_id | Integer | FK help_request.id CASCADE, not null | 1 | |
| source | String(16) | not null | 1 (`facilitator`), 4 (`ai`) | `facilitator` \| `ai` |
| answer_md | Text | not null | 1 | Markdown; rendered with code blocks |
| draft | Boolean | not null, default false | 4 | true = AI draft awaiting facilitator review — never shown to the participant |
| ai_confidence | Numeric(4,3) | nullable | 4 | Model-reported, post-guardrail (0–1) |
| ai_model | String(120) | nullable | 4 | OpenRouter model id used |
| ai_context_json | Text | nullable | 4 | Exact context the AI used (see JSON shapes) — expandable in the queue |
| created_at | DateTime | not null | 1 | |

Indexes: ix(help_request_id, created_at).

---

## broadcast

| Column | Type | Constraints | Phase | Notes |
|---|---|---|---|---|
| id | Integer | PK | 2 | |
| workshop_id | Integer | FK workshop.id CASCADE, not null | 2 | |
| message_md | Text | not null | 2 | Markdown; ≤4000 chars |
| created_at | DateTime | not null | 2 | |
| cleared_at | DateTime | nullable | 2 | null = the active pinned banner (at most one: sending a new one clears the previous) |

Indexes: ix(workshop_id, cleared_at).

---

## facilitator_action — audit trail + undo + AI answer log

Every facilitator action and every AI-sent answer, forever.

| Column | Type | Constraints | Phase | Notes |
|---|---|---|---|---|
| id | Integer | PK | 1 | |
| workshop_id | Integer | FK workshop.id CASCADE, nullable | 1 | null for instance-level actions (workshop.create logs on the new row) |
| actor | String(16) | not null | 1 | `facilitator` \| `ai` \| `system` |
| action | String(48) | not null | 1 | Code, e.g. `workshop.create`, `help.answer`, `help.resolve`, `broadcast.send`, `workshop.pause`, `workshop.resume`, `milestone.advance_all`, `milestone.advance_selected`, `milestone.reorder`, `milestone.edit`, `workshop.end`, `workshop.archive`, `workshop.clone`, `ai.auto_answer`, `ai.draft`, `ai.toggle`, `undo.apply` |
| detail_json | Text | not null, default `'{}'` | 1 | Human-renderable specifics (who/what: participant ids, milestone ids, message excerpt ≤200 chars) |
| undo_data_json | Text | nullable | 2 | Inverse-operation data for undoable actions (see below) |
| undone_at | DateTime | nullable | 2 | Set when undone; undoable within 30 s of created_at |
| created_at | DateTime | not null, **indexed** | 1 | |

Indexes: ix(workshop_id, created_at).

**Undo (Phase 2):** undoable actions = `broadcast.send` (undo_data: previous active broadcast id or null), `workshop.pause`/`workshop.resume` (previous paused state), `milestone.advance_all`/`milestone.advance_selected` (list of created milestone_completion ids → deleted on undo). Undo applies the inverse in one transaction, sets `undone_at`, logs `undo.apply`, bumps `state_version`. Window: 30 seconds, enforced server-side.

Phase 1 writes audit rows for `workshop.create`, `help.answer`, `help.resolve` (the actions that exist); the audit-trail UI arrives in Phase 2.

---

## agenda_template + agenda_template_milestone (Phase 3)

Templates persist forever, independent of workshops. Instantiation **snapshots** milestones into the workshop — later template edits never mutate past or running sessions.

**agenda_template:** id (PK) · name String(120) not null · description_md Text default `''` · created_at · updated_at.

**agenda_template_milestone:** id (PK) · template_id (FK agenda_template.id CASCADE, not null) · position Integer not null · title String(200) not null · content_md Text not null default `''` · minutes Integer nullable. Index: ix(template_id, position).

"Save current workshop as template" copies the workshop's milestones into a new template.

---

## join_form_template (Phase 3)

**join_form_template:** id (PK) · name String(120) not null · fields_json Text not null default `'[]'` · created_at · updated_at.

Fields stay JSON (low query need; schema in JSON shapes below). Creating a workshop from a form template snapshots `fields_json` into `workshop.join_form_json`. Phase 1–2 join collects **name only** (`join_form_json = '[]'`).

---

## ai_usage (Phase 4)

One row per OpenRouter call. Per-workshop spend = `SUM(cost_usd)`.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | Integer | PK | |
| workshop_id | Integer | FK workshop.id CASCADE, not null | |
| help_request_id | Integer | FK help_request.id (SET NULL), nullable | |
| purpose | String(16) | not null | `triage_answer` (single combined call; see agent.md) |
| model | String(120) | not null | |
| prompt_tokens | Integer | not null, default 0 | |
| completion_tokens | Integer | not null, default 0 | |
| cost_usd | Numeric(10,6) | not null, default 0 | From OpenRouter `usage.cost` (`usage: {include: true}`); 0 if unavailable, tokens still recorded |
| latency_ms | Integer | not null, default 0 | |
| created_at | DateTime | not null | |

Indexes: ix(workshop_id, created_at).

---

## help_corpus (Phase 4 — SQLite FTS5 virtual table)

The cross-workshop learning corpus for similarity retrieval (see agent.md). **Not** a SQLAlchemy model — created by an Alembic migration guarded by `dialect == "sqlite"`; maintained by application code (no triggers), rebuildable at any time from `help_request` + `help_answer` (it is derived data, so the resilience rule holds).

```sql
CREATE VIRTUAL TABLE help_corpus USING fts5(
  message,              -- participant's help text
  resolution,           -- the final human-visible answer (facilitator-sent, or AI answer the participant resolved)
  milestone_title,      -- indexed: milestone titles carry strong topical signal
  help_request_id UNINDEXED,
  workshop_id UNINDEXED
);
```

A row is inserted when a request reaches `resolved`, or `answered` by a facilitator (facilitator answers are trusted resolutions). PostgreSQL deployments: the equivalent is a `tsvector` GIN index on the same derived table — documented in agent.md, built only if/when a PostgreSQL deployment needs Phase 4.

---

## JSON shapes (stored in Text columns)

**workshop.join_form_json / join_form_template.fields_json** — array of:
```json
{"key": "role", "type": "text|dropdown", "label": "Your role", "required": false, "options": ["Student", "Engineer"]}
```
(`options` only for `dropdown`; `key` is `^[a-z][a-z0-9_]{0,39}$`.)

**participant.answers_json** — `{"role": "Engineer"}` (keys from the workshop's join form).

**help_answer.ai_context_json** — exactly what the AI saw (see agent.md §Context):
```json
{
  "progress": {"completed_count": 3, "total": 8, "completed_titles": ["…"]},
  "milestone": {"id": 12, "title": "Configure the API key", "content_excerpt": "first 2000 chars…"},
  "similar": [{"help_request_id": 41, "workshop_id": 2, "message_excerpt": "…", "resolution_excerpt": "…", "rank": 1}]
}
```

**facilitator_action.detail_json** — action-specific, human-renderable, e.g. `{"help_request_id": 7, "participant_name": "Priya", "excerpt": "Answered: check your .env…"}`.

**facilitator_action.undo_data_json** — inverse-op data, e.g. `{"completion_ids": [911, 912, 913]}`.

---

## Version-bump rules (the contract every write follows)

Bump `workshop.state_version` (same transaction) on: participant join, completion create/delete, help request create/answer/resolve/escalate, broadcast send/clear, pause/resume, advance, reorder, milestone edit, AI answer/draft, undo, status transition, ai toggle. Additionally bump `content_version` on: milestone create/edit/delete/reorder (and workshop name/description edit). Nothing else writes these counters.

## Indexing strategy for 300-participant polling

- Poll hot path: single point-read of `workshop` by unique token (admin_token/join_slug) or `participant` by unique token → covered by the unique indexes.
- Snapshot build (per version change, coalesced): `milestone_completion` GROUP BY milestone_id filtered via ix(milestone_id) join on workshop's milestones; leaderboard from ix(workshop_id) participants + their completion counts; help queue via ix(workshop_id, status, created_at).
- "Me" section per poll: unique(token) point-read + ix(participant_id) on completions + ix(participant_id) on help_requests — 2–3 sub-ms indexed queries.
- No composite index tuning beyond the above is warranted at ≤1000 rows/table/session scale; the unique constraints double as the lookup indexes.
