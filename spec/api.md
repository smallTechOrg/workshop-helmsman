# API Contract — Workshop Helmsman (v0.2)

This is the contract both generators build against **in parallel** — the backend implements it exactly; the frontend consumes it exactly. Nothing here is aspirational: field names, casing, and shapes are normative.

## Conventions (normative)

- All endpoints are under `/api/`. All bodies and responses are JSON (UTF-8). All field names are `snake_case`.
- **Timestamps:** ISO 8601 UTC with `Z`, seconds precision — `"2026-07-20T14:03:22Z"`.
- **IDs** are integers. **Tokens/slugs** are strings.
- **Success envelope:** HTTP 200 → `{"data": <payload>, "error": null}`.
- **Error envelope:** HTTP 4xx/5xx → `{"detail": {"code": "<machine_code>", "message": "<human sentence>"}}`. Pydantic validation failures are converted by an exception handler into this same shape (`code: "validation_error"`, message = first human-readable error) — the raw FastAPI 422 array shape never reaches clients.
- **Auth:** three schemes — `X-Admin-Key` header (admin surface), `admin_token` path segment (facilitator surface), `participant_token` path segment (participant surface). See architecture.md §Auth.
- **Versioned polling:** poll endpoints take `?v=<int>` (last-seen `state_version`; default `-1` = always changed). Unchanged → `{"changed": false, "version": N, "content_version": M}`. The content endpoint uses `?cv=<int>` against `content_version` the same way. Every mutation response includes `"version"` (the new `state_version`) so clients re-poll immediately.
- **URL fields** (`join_url`, `facilitator_url`, `participant_url`) are absolute, built from `HELMSMAN_BASE_URL` (or the request origin) + the pretty paths `/j/{slug}`, `/f/{admin_token}`, `/p/{participant_token}`.
- **Draft AI answers (`draft: true`) appear only in facilitator payloads — never in participant payloads.** `ai_context` appears only in facilitator payloads.

### Error code catalogue

| HTTP | `code` | When |
|---|---|---|
| 401 | `invalid_admin_key` | Missing/wrong `X-Admin-Key` |
| 404 | `not_found` | Unknown token/slug, or an id not in the token's scope (never distinguish wrong vs missing) |
| 409 | `workshop_paused` | Completion mark/unmark while paused (Phase 2+) |
| 409 | `workshop_not_started` | Join before `starts_at` (Phase 3) |
| 409 | `undo_expired` | Undo requested after the 30 s window (Phase 2) |
| 410 | `workshop_archived` | Any mutation on an archived workshop (Phase 3) |
| 422 | `validation_error` | Body/param validation failure |
| 500 | `internal_error` | Unexpected; logged with `request_id` |

### Pretty redirect routes (not JSON API)

`GET /` → `/app/` · `GET /j/{join_slug}` → `/app/join/?s=…` · `GET /p/{participant_token}` → `/app/p/?t=…` · `GET /f/{admin_token}` → `/app/f/?t=…` — all 307. **Phase 1.**

---

# Phase 1 endpoints

## Health

### `GET /api/health` — no auth
`{"data": {"status": "ok", "db": "ok"}, "error": null}` — `db` is `"ok"` after a real `SELECT 1`, else 500 `internal_error`.

## Admin surface (header `X-Admin-Key`)

### `GET /api/admin/workshops`
Lists all workshops (also serves as key validation for the Admin Home login). Sorted `created_at` desc.

```json
{"data": {"workshops": [{
  "id": 1, "name": "LangGraph Lab — July", "status": "live",
  "participant_count": 143, "open_help_count": 2,
  "created_at": "2026-07-20T09:00:00Z",
  "join_slug": "Ab3dEfGh", "join_url": "http://localhost:8001/j/Ab3dEfGh",
  "facilitator_url": "http://localhost:8001/f/<admin_token>"
}]}, "error": null}
```
Errors: `invalid_admin_key`.

### `POST /api/admin/workshops`
```json
{"name": "LangGraph Lab — July", "description_md": "Welcome!…",
 "milestones": [{"title": "Set up your environment", "content_md": "```bash\nuv sync\n```", "minutes": 30}]}
```
Validation: `name` 1–120 (trimmed); `description_md` ≤10000; `milestones` 1–50 items in given order; `title` 1–200; `content_md` ≤20000; `minutes` null or 1–480.
*(Phase 3 adds optional `agenda_template_id`, `join_form_template_id`, `starts_at`.)*

Response — the full workshop:
```json
{"data": {"workshop": {
  "id": 1, "name": "…", "description_md": "…", "status": "live", "paused": false, "ai_enabled": false,
  "admin_token": "<43 chars>", "join_slug": "Ab3dEfGh",
  "join_url": "…/j/Ab3dEfGh", "facilitator_url": "…/f/<admin_token>",
  "created_at": "2026-07-20T09:00:00Z"
}}, "error": null}
```
Side effects: audit row `workshop.create`. Errors: `invalid_admin_key`, `validation_error`.

## Facilitator surface (path `admin_token`)

### `GET /api/f/{admin_token}/workshop`
Initial dashboard load + milestone bodies (re-fetched when the dashboard poll reports a new `content_version`).
```json
{"data": {
  "content_version": 3,
  "workshop": {"id": 1, "name": "…", "description_md": "…", "status": "live", "paused": false,
               "ai_enabled": false, "join_slug": "Ab3dEfGh", "join_url": "…", "facilitator_url": "…",
               "created_at": "…"},
  "milestones": [{"id": 11, "position": 0, "title": "…", "content_md": "…", "minutes": 30}]
}, "error": null}
```

### `GET /api/f/{admin_token}/dashboard?v={int}` — poll (2 s)
Unchanged → `{"data": {"changed": false, "version": 42, "content_version": 3}, "error": null}`.
Changed:
```json
{"data": {
  "changed": true, "version": 42, "content_version": 3,
  "workshop": {"id": 1, "name": "…", "status": "live", "paused": false, "ai_enabled": false},
  "stats": {"participant_count": 143, "active_count": 121, "finished_count": 12,
            "median_progress_pct": 40.0, "open_help_count": 3, "answered_help_count": 5,
            "resolved_help_count": 17},
  "milestone_stats": [{"milestone_id": 11, "position": 0, "title": "…",
                        "completed_count": 130, "completed_pct": 90.9}],
  "distribution": [{"completed_count": 0, "participants": 5}, {"completed_count": 1, "participants": 20}],
  "participants": [{"id": 7, "name": "Priya", "joined_at": "…", "last_seen_at": "…",
                    "completed_milestone_ids": [11, 12], "completed_count": 2, "progress_pct": 25.0,
                    "current_milestone_id": 13, "open_help_count": 1,
                    "participant_url": "…/p/<participant_token>"}],
  "help_queue": [{"id": 9, "participant_id": 7, "participant_name": "Priya",
                  "milestone_id": 13, "milestone_title": "Configure the API key",
                  "message": "getting a 401 from…", "status": "open", "escalated": false,
                  "created_at": "…", "updated_at": "…",
                  "answers": [{"id": 3, "source": "facilitator", "answer_md": "Check `.env`…",
                                "draft": false, "created_at": "…",
                                "ai_confidence": null, "ai_model": null, "ai_context": null}]}],
  "broadcast": null,
  "alerts": null,
  "pulse": null,
  "spend": null
}, "error": null}
```
Semantics: `active_count` = participants with `last_seen_at` within 5 min. `distribution` covers every completed-count 0…total (zeros included). `participants` sorted `joined_at` asc (client re-sorts). `help_queue` = all `open` + `answered` requests (newest first within status, `open` block first) plus the 50 most recent `resolved`; totals live in `stats`. `broadcast`/`alerts`/`pulse` are `null` until Phase 2, `spend` `null` until Phase 4 — the frontend renders labelled stubs for them from day one.

### `POST /api/f/{admin_token}/help/{help_request_id}/answer`
Body: `{"answer_md": "…"}` (1–10000). Effect: append `help_answer(source="facilitator")`, request → `answered`, audit `help.answer`, bump version.
Response: `{"data": {"help_request": <help_queue row shape>, "version": 43}, "error": null}`.
Errors: `not_found` (id not in this workshop), `validation_error`. Answering a `resolved` request re-opens nothing — it appends the answer and leaves status `resolved`.

### `POST /api/f/{admin_token}/help/{help_request_id}/resolve`
Facilitator closes a request. Idempotent. Audit `help.resolve`.
Response: `{"data": {"help_request": <row>, "version": 44}, "error": null}`.

## Participant surface

### `GET /api/join/{join_slug}` — no auth; reads auto-resume cookie
```json
{"data": {
  "workshop": {"name": "…", "description_md": "…", "status": "live",
               "milestone_count": 8, "participant_count": 143},
  "me": null
}, "error": null}
```
If the browser carries a valid `helmsman_p_{workshop_id}` cookie, `"me": {"participant_token": "<22 chars>", "name": "Priya"}` — the page then forwards to the tracker without re-joining. Errors: `not_found`.

### `POST /api/join/{join_slug}`
Body: `{"name": "Priya"}` (1–80 trimmed; duplicates allowed). *(Phase 3 adds `"answers": {…}` for custom join fields.)*
Effect: create participant; **set cookie** `helmsman_p_{workshop_id}=<participant_token>; HttpOnly; SameSite=Lax; Path=/; Max-Age=2592000`; bump version.
```json
{"data": {"participant_token": "<22 chars>", "participant_url": "…/p/<token>", "name": "Priya"}, "error": null}
```
Errors: `validation_error`, `workshop_archived`, `workshop_not_started` (Phase 3).

### `GET /api/p/{participant_token}/state?v={int}` — poll (3 s)
Unchanged → `{"data": {"changed": false, "version": 42, "content_version": 3}, "error": null}`.
Changed:
```json
{"data": {
  "changed": true, "version": 42, "content_version": 3,
  "workshop": {"name": "…", "status": "live", "paused": false},
  "milestones": [{"id": 11, "position": 0, "title": "…", "minutes": 30}],
  "me": {"id": 7, "name": "Priya", "completed_milestone_ids": [11],
         "completed_count": 1, "total_count": 8, "progress_pct": 12.5, "rank": 37},
  "leaderboard": [{"rank": 1, "name": "Arun", "completed_count": 6, "progress_pct": 75.0, "is_me": false}],
  "broadcast": null,
  "help_requests": [{"id": 9, "message": "getting a 401…", "status": "answered", "escalated": false,
                     "milestone_id": 13, "created_at": "…",
                     "answers": [{"id": 3, "source": "facilitator", "answer_md": "Check `.env`…",
                                   "created_at": "…"}]}]
}, "error": null}
```
Semantics: `milestones` **excludes** `content_md` (bodies come from the content endpoint). `leaderboard` is the **full** ranked list (full names, always on). Ranking order: `completed_count` desc → earliest timestamp of reaching that count asc → `joined_at` asc; `rank` is the 1-based position (no tie-sharing). `help_requests` = mine only, newest first; never includes drafts or `ai_context`. Side effect: throttled `last_seen_at` touch (≥60 s since last).
Errors: `not_found`. Archived workshops still return state (read-only archive view; `workshop.status` = `"archived"`).

### `GET /api/p/{participant_token}/content?cv={int}`
Unchanged → `{"data": {"changed": false, "content_version": 3}, "error": null}`.
Changed:
```json
{"data": {"changed": true, "content_version": 3,
  "workshop": {"name": "…", "description_md": "…"},
  "milestones": [{"id": 11, "position": 0, "title": "…", "content_md": "…", "minutes": 30}]
}, "error": null}
```

### `POST /api/p/{participant_token}/milestones/{milestone_id}/complete`
Idempotent (unique constraint; re-complete is a no-op success). Blocked while paused/archived.
Response: `{"data": {"completed_milestone_ids": [11, 13], "completed_count": 2, "progress_pct": 25.0, "version": 43}, "error": null}`.
Errors: `not_found` (milestone not in my workshop), `workshop_paused`, `workshop_archived`.

### `POST /api/p/{participant_token}/milestones/{milestone_id}/uncomplete`
Deletes my completion if present (idempotent). Same response shape and errors as complete.

### `POST /api/p/{participant_token}/help`
Body: `{"message": "…"}` (1–4000; rendered as plain text everywhere). Effect: create request with `milestone_id` = my current milestone (lowest-position incomplete; null if finished); bump version. *(Phase 4: additionally triggers the AI pipeline as a background task when enabled.)*
Response: `{"data": {"help_request": <tracker row shape>, "version": 43}, "error": null}`.
Errors: `validation_error`, `workshop_archived`.

### `POST /api/p/{participant_token}/help/{help_request_id}/resolve`
Participant marks their own request resolved. Idempotent. Errors: `not_found` (not mine).
Response: `{"data": {"help_request": <row>, "version": 44}, "error": null}`.

---

# Phase 2 endpoints — Facilitator command & proactive intelligence

All under `/api/f/{admin_token}/…`; all bump `state_version`, write an audit row, and (where noted) record undo data. Undoable actions return `"undoable_action_id"`.

| Endpoint | Body → Effect |
|---|---|
| `POST …/broadcast` | `{"message_md": "…"}` (1–4000) → new active broadcast (previous one cleared). Undoable (restores previous). Response: `{"broadcast": {...}, "version": N, "undoable_action_id": 77}` |
| `POST …/broadcast/clear` | `{}` → active broadcast `cleared_at` = now |
| `POST …/pause` | `{"paused": true|false}` → freeze/unfreeze completions. Undoable |
| `POST …/milestones/advance` | `{"milestone_id": 13, "participant_ids": [7, 9]}` or `"participant_ids": null` (= all) → create missing completions with `source: "facilitator"`. Undoable (deletes created rows). Response includes `"affected_count"` |
| `POST …/milestones/reorder` | `{"milestone_ids": [12, 11, 13]}` (exact permutation) → rewrite positions; bumps `content_version` too |
| `POST …/milestones` | `{"title", "content_md", "minutes"}` → append milestone; bumps `content_version` |
| `PATCH …/milestones/{id}` | any of `{"title", "content_md", "minutes"}` → edit; bumps `content_version` |
| `DELETE …/milestones/{id}` | removes milestone + its completions (confirmation is a UI concern); bumps both versions |
| `POST …/undo/{action_id}` | `{}` → apply inverse within 30 s. Errors: `undo_expired`, `not_found` |
| `GET …/audit?before_id={int}&limit={int≤100}` | → `{"actions": [{"id", "actor", "action", "detail": {…}, "created_at", "undone_at"}], "has_more": true}` newest first |
| `PATCH …/settings` | `{"stuck_minutes": 10}` (2–120) |

Phase 2 also **activates** these dashboard-poll fields (shapes normative now):
```json
"broadcast": {"id": 5, "message_md": "…", "created_at": "…"},
"alerts": {"stuck": [{"participant_id": 7, "name": "Priya", "minutes_inactive": 14,
                       "current_milestone_id": 13}],
           "bottleneck": {"milestone_id": 13, "title": "Configure the API key", "waiting_count": 96}},
"pulse": {"pace_ratio": 0.82, "on_track_pct": 61.0, "open_help_count": 3,
          "projected_finish_at": "2026-07-20T17:40:00Z"}
```
The participant poll's `broadcast` field activates with the same shape. Definitions: *stuck* = live, not paused, not finished, no completion and no help activity for ≥ `stuck_minutes`. *Bottleneck* = the milestone that is the current milestone of the largest participant group (≥25% of active participants, else null). *pace_ratio* = median actual minutes-per-milestone ÷ planned `minutes` (1.0 = on plan; >1 = slower). *on_track_pct* = % of participants whose progress ≥ elapsed-time-proportional expectation. *projected_finish_at* = now + (median remaining planned minutes × pace_ratio).

---

# Phase 3 endpoints — Lifecycle, templates & re-run

| Endpoint | Auth | Body → Effect |
|---|---|---|
| `POST /api/f/{t}/end` | token | `{"grace_hours": 24}` (0–168) → status `grace`, `ended_at`=now, `grace_until`=now+h. `0` archives immediately |
| `POST /api/f/{t}/archive` | token | `{}` → status `archived` now (terminal, read-only) |
| `POST /api/f/{t}/reopen` | token | `{}` → `grace` → `live` (mistake recovery; not allowed from `archived`) |
| `POST /api/f/{t}/clone` | token | `{"name": "…"}` → new `live` workshop, milestones copied, fresh tokens, zero participants. Response: new workshop object |
| `POST /api/f/{t}/save-as-template` | token | `{"name": "…"}` → agenda template from current milestones |
| `GET /api/admin/templates` | key | → `{"agenda_templates": [{"id","name","description_md","milestone_count","created_at","updated_at"}], "join_form_templates": [{"id","name","field_count","created_at","updated_at"}]}` |
| `POST /api/admin/templates/agenda` | key | `{"name", "description_md", "milestones": [{"title","content_md","minutes"}]}` |
| `GET /api/admin/templates/agenda/{id}` | key | full template incl. milestones |
| `PATCH /api/admin/templates/agenda/{id}` / `DELETE` | key | edit / delete (never affects existing workshops — snapshots) |
| `POST /api/admin/templates/forms` + `GET/PATCH/DELETE …/forms/{id}` | key | same pattern; body `{"name", "fields": [<join-field shape, data-model.md>]}` |

`POST /api/admin/workshops` gains optional `agenda_template_id`, `join_form_template_id`, `starts_at`. `GET /api/join/{slug}` gains `"join_form": [<field>]` and `"starts_at"`; `POST /api/join/{slug}` gains `"answers": {…}` validated against the snapshot. Admin Home list gains `ended_at`/`starts_at` for Live/Upcoming/Ended grouping and an archived workshop's dashboard/tracker render read-only.

---

# Phase 4 endpoints — AI help-desk

| Endpoint | Auth | Body → Effect |
|---|---|---|
| `POST /api/f/{t}/ai` | token | `{"enabled": true|false}` → toggle; audit `ai.toggle`. When no `OPENROUTER_API_KEY` is configured, responds 200 with `{"enabled": false, "available": false}` — never an error (air-gapped) |
| `GET /api/f/{t}/spend` | token | → `{"total_cost_usd": 0.4312, "call_count": 57, "prompt_tokens": 91234, "completion_tokens": 18022, "by_purpose": [{"purpose": "triage_answer", "cost_usd": 0.4312, "count": 57}]}` |
| `POST /api/p/{token}/help/{id}/escalate` | token | `{}` → `escalated=true`, status → `open` (AI answers stay visible); bump version. Idempotent |

Phase 4 **activates** (shapes normative now): dashboard `"spend": {"total_cost_usd": 0.43}`; help-queue answers carry real `ai_confidence`, `ai_model`, and `ai_context` (shape = `help_answer.ai_context_json`, data-model.md) plus `draft: true` rows for review; the workshop objects' `ai_enabled` goes live; tracker answers with `"source": "ai"` are badged AI client-side with the escalate action. Facilitator sending a reviewed draft uses the existing `POST …/help/{id}/answer` (the draft row stays for audit; the sent answer is a new `facilitator` row).

---

*Phase 5 (deploy) adds no API surface.*
