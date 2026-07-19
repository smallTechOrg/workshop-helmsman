# AI Help-Desk — Workshop Helmsman (v0.2)

The AI layer arrives in **Phase 4**, but this design is fixed now: the schema (data-model.md), the API surface (api.md), and this pipeline are designed once so Phase 4 wires — it does not redesign.

## Framework decision: NO agent framework

**A plain structured pipeline — no LangGraph/CrewAI/AutoGen, no tool-use loop.** Per `harness/patterns/agentic-ai.md`: "reach down only when there are no tools… if the task is a fixed transform with no branching, a prompt chain or a single call is correct — don't bolt a loop onto a one-shot." This task is a fixed transform: *deterministically gather context → one LLM call → route on confidence*. There are no open-ended tool decisions for the model to make (the system, not the model, fetches the context), no multi-turn planning, no inter-agent coordination. A framework would add dependency weight, latency, and failure modes to a three-step function.

Patterns used (from the catalogue): **#2 Routing** (confidence-gated auto-answer vs draft), **#13 Human-in-the-Loop** (draft review; one-tap escalation), **#14 Knowledge Retrieval** (FTS5 similarity over past resolutions — keyword RAG, no vector DB), **#9 Learning & Adaptation** (the corpus grows with every facilitator resolution — this replaces canned replies), **#12 Exception Handling** (degrade to manual, never crash), **#18 Guardrails** (schema-validated JSON output, confidence clamps), **#19 Evaluation & Monitoring** (audit rows, structured logs, spend tracking).

## Entry point

```python
# src/helmsman/ai/pipeline.py
def run_help_desk(help_request_id: int) -> None: ...
```

Invoked as a FastAPI `BackgroundTask` after `POST /api/p/{token}/help` commits — the participant's request returns instantly; the AI answer appears via the normal poll. The pipeline opens its own DB session (`create_db_session`), sets `help_request.ai_state = "pending"` first, and is **re-runnable**: if the process restarts mid-pipeline, the request simply remains `open` in the facilitator queue with `ai_state = "pending"` — no data loss, no stuck state (a request is never blocked on the AI; the queue always shows it).

**Preconditions (else `ai_state = "skipped"`, silently manual):** `OPENROUTER_API_KEY` present **and** `workshop.ai_enabled` **and** workshop status in (`live`, `grace`) **and** request status `open` and not `escalated`. Escalated requests never re-enter the pipeline — a human was demanded. With no key, nothing in the product references AI errors anywhere: air-gapped means zero errors, and the facilitator AI toggle renders as a labelled "AI off (no API key)" state.

## Step 1 — Context gathering (deterministic, no LLM)

Collected into the exact structure stored as `help_answer.ai_context_json` (data-model.md) — what is stored is *precisely* what the model saw, so the facilitator's expandable "context the AI used" view is honest by construction:

1. **Participant progress:** completed count / total, titles of completed milestones (most recent 5).
2. **Current milestone:** the request's `milestone_id` — title + `content_md` (first 2000 chars). This is the instruction text the participant is stuck on.
3. **Similar past requests (cross-workshop learning):** top **5** hits from the `help_corpus` FTS5 table — message + final resolution excerpts (≤500 chars each), ranked by BM25. This corpus spans **all workshops ever run** on the instance, so every facilitator resolution teaches future triage.

### Similarity mechanism (realistic for SQLite — no vector DB)

- **Corpus maintenance (app code, no triggers):** when a request reaches `resolved`, or a facilitator answers it, insert one row into `help_corpus` (message, human-visible resolution, milestone title, ids). Draft-only and unanswered requests never enter the corpus. The corpus is derived data — rebuildable from `help_request` + `help_answer` by a maintenance function, so the DB-is-truth rule holds.
- **Query construction:** tokenize the incoming message + current milestone title; drop stopwords and tokens <3 chars; take the top 12 remaining tokens; build an FTS5 `OR` query of **double-quoted** tokens (quoting neutralizes FTS5 operator injection from user text). Rank with `bm25(help_corpus)`, `LIMIT 5`.
- **PostgreSQL note:** on a PostgreSQL `DATABASE_URL`, the equivalent is a plain `help_corpus` table with a generated `tsvector` column + GIN index and `ts_rank` — same interface (`corpus.search(text) -> list[Hit]`), built only if/when a PostgreSQL deployment enables Phase 4. `src/helmsman/ai/corpus.py` isolates the dialect switch.

## Step 2 — One LLM call: triage + answer combined

One call, not two — the triage signal (confidence) and the candidate answer come from the same completion, halving cost and latency.

- **Provider:** OpenRouter `POST /api/v1/chat/completions` via httpx. Model: `HELMSMAN_AI_MODEL` (default `anthropic/claude-sonnet-4-6`). Timeout 30 s; **one retry** on timeout/5xx with 2 s backoff. Request includes `usage: {"include": true}` so the response carries token counts and `usage.cost`.
- **Prompts** live as markdown files in `src/helmsman/ai/prompts/` (`helpdesk_system.md`, `helpdesk_user.md` — user template interpolates the context block). System prompt outline:
  - You are the AI help-desk for a live hands-on technical workshop; a participant is stuck **right now** — be concise, concrete, actionable (≤150 words), markdown with code blocks where useful, formatted code (real newlines/indentation).
  - You are given: their progress, the milestone instructions they are on, and similar past requests with how a human facilitator resolved them. Prefer approaches proven in past resolutions; never invent workshop-specific facts (URLs, credentials, file names) not present in the context.
  - Report honest confidence: high only when the milestone content or a past resolution clearly covers the problem. If the request needs information you don't have (machine-specific state, account issues, anything ambiguous), answer with your best guidance but report low confidence.
  - Output **only** JSON: `{"confidence": 0.0–1.0, "answer_md": "…", "reasoning": "one sentence for the audit log"}`.
- **Output guardrails:** parse strictly (`json.loads` on the extracted JSON object; one re-ask on malformed output with a "return only valid JSON" nudge, then fail). Validate: `confidence` ∈ [0,1] (clamp), `answer_md` non-empty and ≤10000 chars. **Evidence cap:** if the similar-requests list was empty, cap effective confidence at **0.6** — the model cannot claim high certainty without precedent or (per the prompt) explicit grounding in milestone content; this keeps early workshops (empty corpus) human-first while the corpus grows.
- **Spend:** write one `ai_usage` row (purpose `triage_answer`, model, tokens, `cost_usd` from `usage.cost` else 0, latency). Surfaced at `GET /api/f/{t}/spend` and on the dashboard.

## Step 3 — Route on confidence

Threshold: `HELMSMAN_AI_CONFIDENCE` (default **0.75**), compared against post-guardrail confidence.

**Confident (≥ threshold) → auto-answer:**
- Insert `help_answer(source="ai", draft=false, ai_confidence, ai_model, ai_context_json)`; request → `answered`, `ai_state = "answered"`; bump `state_version`.
- Audit row `ai.auto_answer` (actor `ai`) with request id, confidence, reasoning — every AI-sent answer is logged who/what/when.
- Participant sees the answer on next poll, **clearly badged "AI answer"**, with a one-tap **"Get a human"** escalation (`POST …/escalate` → `escalated=true`, status back to `open`, flagged in the queue; the AI answer stays visible — honesty over tidiness).
- Facilitators see every auto-answer in their queue (status `answered`, source badge AI) with the expandable exact context (`ai_context`).

**Unsure (< threshold) → draft for review:**
- Insert `help_answer(source="ai", draft=true, …)`; request **stays `open`**, `ai_state = "draft"`; bump version.
- The queue shows the draft + confidence + context; the facilitator edits and sends via the normal answer endpoint (a new `facilitator` answer row; the draft remains for audit). Audit row `ai.draft`.

**Failure (timeout ×2, HTTP error, invalid output ×2):**
- `ai_state = "failed"`, ERROR log with request id and cause; **no user-visible error anywhere** — the request simply remains `open` in the facilitator queue, indistinguishable from AI-off for the participant. The AI is an accelerant, never a gate.

## Sequence (normative)

```
participant POST /help ──commit──▶ 202-style instant response
        └─ BackgroundTask: run_help_desk(id)
             ├─ preconditions? ──no──▶ ai_state=skipped (manual queue)
             ├─ gather_context(id)                  [context.py — DB only]
             ├─ call_openrouter(context)            [openrouter.py — 30s, 1 retry]
             │     └─ failure ──▶ ai_state=failed, log ERROR (manual queue)
             ├─ guardrails: parse/validate/clamp/evidence-cap
             └─ route:
                  confidence ≥ τ ──▶ answer row (draft=false) → answered → audit ai.auto_answer
                  confidence < τ ──▶ answer row (draft=true)  → open     → audit ai.draft
             then: ai_usage row · state_version bump · structured log ai.* with latency/tokens/cost
```

## Testing (Phase 4 gate — real key, from `.env`)

- `tests/integration/ai/` runs against the **real OpenRouter key** (`pytest.skip` only if genuinely absent — skipped is not passed; the phase gate is BLOCKED without the key).
- **Corpus-size rule (data-processing gate):** the similarity fixture seeds **25+ resolved requests across ≥3 workshops**, exactly one of which is a strong topical match for the query; the test asserts that match is retrieved at rank 1 and appears in `ai_context_json` — a corpus small enough for "any hit = the hit" proves nothing.
- Route tests assert structure, not prose: a request whose answer is verbatim in the milestone content + a matching past resolution → auto-answer path artifacts (answer row `draft=false`, status `answered`, audit row, `ai_usage` row with nonzero tokens); an ambiguous machine-specific request with an empty corpus → draft path (evidence cap enforced).
- **Air-gapped test:** with `OPENROUTER_API_KEY` unset, the full participant + facilitator journey runs with zero errors and zero AI artifacts (`ai_state="skipped"`), and the UI shows the labelled AI-off state.
- Escalation test: auto-answer → escalate → status `open` + `escalated=true` + AI answer still visible + queue flag.
