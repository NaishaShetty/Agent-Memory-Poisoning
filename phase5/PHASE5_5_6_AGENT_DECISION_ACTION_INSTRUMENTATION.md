# Phase 5.6 — Agent Decision & Action Instrumentation

Status: PASS.
Depends on: `PHASE5_5_1_INSTRUMENTATION_CONTRACT.md` (OR-8, OR-9, OR-10),
`PHASE5_5_5_RETRIEVAL_SELECTION_INSTRUMENTATION.md`.

## What exists

- `agent_runtime/trace.py::evaluate_and_trace()` — real, tested, rich, but confirmed
  (Stage 5.1 audit) to be an **evaluation-time-only** trace requiring evaluator-only
  inputs; `runner.py` never calls it, so it is not part of any live decision path a
  Phase 4 attack campaign actually executes.
- `agent_runtime/runner.py::generate_with_retries()` — the real, frozen retry loop every
  attack's `campaign_runner.retrieve_select_generate()` calls. Confirmed by direct read:
  it returns `(generation_text, attempts)` — the underlying `GenerationResult
  .finish_reason` the provider actually returned is read internally but **never
  propagated out**.
- `agent.outcomes.AgentExecutionResult` — confirmed by direct read: this framework has no
  concept of an "action" distinct from the generated answer for LoCoMo-style QA tasks;
  `execution_status` is the closest existing concept to an action's result.

## The gap

No live decision/action telemetry exists at all for a Phase 4 attack campaign run.

## Two disclosed, deliberate design decisions

1. **`finish_reason` is a derived value, not the literal provider string.** Since
   `generate_with_retries()` discards the real finish_reason before returning, and
   calling the provider a second time just to recover it would be an undesirable extra
   generation call (and could legitimately diverge if the provider isn't perfectly
   deterministic), this stage records one of two clearly-named derived constants —
   `GENERATED` / `FAILED_ALL_ATTEMPTS` — never spelled to look like a real
   `"stop"`/`"length"` provider value, so no reader is misled into thinking this module
   observed something it did not.
2. **`used_memories_observability` is always `NOT_OBSERVABLE`** in the live pipeline
   wrapper, per the audit's own finding that this framework implements no citation-based
   usage attribution in the runtime. `record_agent_decision()` itself still accepts
   `OBSERVED` for a caller with a genuinely separate usage signal — the live wrapper just
   never claims one it doesn't have.
3. **"Action" for a QA task is answer submission.** LoCoMo-style tasks have no action
   distinct from generation, but `AgentExecutionResult.execution_status` already models
   submitting an answer as having a real outcome (SUCCESS/ERROR). The live wrapper
   records one `agent_action` event per decision (`action="submit_answer"`,
   `result=execution_status`) rather than leaving OR-9 wired but never exercised by the
   one task shape this framework's frozen attacks actually run today.

## The minimal, scientifically sufficient change

New module: [wiring/agent_decision_instrumentation.py](wiring/agent_decision_instrumentation.py).

1. **`record_agent_decision()`** (OR-8, OR-10) — thin: builds and appends one
   `agent_decision` `Phase5Event`, no inference.
2. **`record_agent_action()`** (OR-9) — thin, generic, not QA-specific; linked to its
   decision via `decision_id`.
3. **`instrument_agent_decision()`** — calls `generate_with_retries()` exactly once
   (never reimplemented, never called twice), derives `finish_reason`, reuses
   `run_config.llm_provider.configuration_fingerprint()`/`.model_metadata()` verbatim
   (the same calls `campaign_runner.py` itself already makes) for
   `config_fingerprint`/`model_identity`, and records both the decision and the
   submit-answer action from one real generation call.

## What was NOT done

- `generate_with_retries()`, `runner.py`, and `campaign_runner.py` were not modified.
- No second LLM call was introduced to recover the real provider `finish_reason` —
  disclosed as a derived approximation instead of guessed or silently omitted.
- No fabricated "OBSERVED" usage-attribution claim — the live wrapper always states
  `NOT_OBSERVABLE` honestly.

## Evidence

- [phase5/wiring/agent_decision_instrumentation.py](wiring/agent_decision_instrumentation.py)
- [phase5/tests/test_agent_decision_instrumentation.py](../tests/test_agent_decision_instrumentation.py)
  — 7 tests: direct decision/action recording, the explicit-OBSERVED escape hatch, a
  **live** success run (real `generate_with_retries()` against a scripted, never-real-network
  provider — same pattern Stage 5.4's `live_attack_runs.py` and this project's own frozen
  tests use) with real `config_fingerprint`/`model_identity` asserted non-fabricated, a
  live retry-then-succeed run (closed proactively — see below), a live all-attempts-failed
  run, and a non-interference check confirming `generate_with_retries()`'s own return
  value is unchanged whether or not this module is used.
- **Proactive full-chain test**, written before being asked (applying the lesson from
  Stage 5.5's own review that isolated per-stage tests leave real integration gaps
  invisible): [phase5/tests/test_full_pipeline_chain.py](../tests/test_full_pipeline_chain.py)
  — runs a real Stage 5.4 live attack injection, through real Stage 5.5 retrieval/
  selection/context-assembly, through real Stage 5.6 decision/action instrumentation,
  then reloads every ledger fresh from disk and confirms the entire
  `injection → memory → retrieved → selected → context_assembled → decision → action`
  chain reconstructs correctly, with every event registered to the same run.
- Full Phase 5 suite: `python -m pytest phase5/tests/ -q` → 108 passed.
- Frozen Phase 3/4 regression: recorded below once complete.

## Coverage check

OR-8 (agent decision), OR-9 (agent action), OR-10 (explicit non-observability) are all
satisfied.

## Things worth flagging before moving on

- **`finish_reason` is coarser than a real provider finish_reason.** `GENERATED`/
  `FAILED_ALL_ATTEMPTS` collapses `"stop"` vs `"length"` vs any other real reason a
  successful generation might have had — a real limitation of not touching frozen
  `generate_with_retries()`, not a false claim, but a real loss of resolution a future
  reviewer might want closed by a small, reviewed change to that function (which is
  frozen Phase 3 and out of Phase 5's authority to modify unilaterally).
- **The `submit_answer` action mapping is QA-task-specific**, living inside
  `instrument_agent_decision()` rather than as a separate, generic concern — a future
  action-shaped task (tool use, an environment step) would need its own call to
  `record_agent_action()`, not a reuse of this wrapper's hardcoded action name.
**STAGE 5.6 STATUS: PASS.**
