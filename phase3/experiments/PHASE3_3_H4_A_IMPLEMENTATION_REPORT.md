# Phase 3.3-H.4-A — Counterfactual Influence Measurement — Implementation Report

Status: **COMPLETE**.

This mission implements `counterfactually_influential`, not `used_causal` — every result
this mechanism produces is scoped strictly to "masking this memory changed the specified
observable under the frozen intervention protocol." Nothing here is reported, logged, or
documented as proving a memory was "the" cause of an answer.

## 1. Single-retrieval design correction — confirmed followed

Direct inspection of `runner.py::run_agent_task()` confirmed the mission's own suspected
confound: a naive "re-run the whole pipeline" reading would call `foundation.retrieve()`
a second time for the masked run. `run_counterfactual_mask()` does not. It has **no
`foundation` parameter at all** — the masked context is built purely from
`baseline.agent_visible_context` (a deep copy with one `memory_content` entry removed), and
`foundation.retrieve()`/`foundation.inspect_memory()` are never called anywhere in the new
module. This is verified by an AST-based test
(`test_module_never_calls_foundation_methods`) that walks the module's parsed syntax tree
for any `Call` node whose attribute is `retrieve`/`inspect_memory` — not a raw substring
scan, since the module's own docstring legitimately *discusses* those method names in
prose. This is a stronger reproducibility guarantee than the plan's literal wording implies
(retrieval happens exactly once, full stop, eliminating any confound from a foundation
whose `retrieve()` is not perfectly deterministic), stated explicitly here rather than
silently substituted.

## 2. `run_agent_task()` — one small, additive refactor, no behavior change

`runner.py` needed exactly one change: the inline generation-retry loop (previously lines
~292–317) was extracted into a new, additive function, `generate_with_retries(messages,
config) -> (Optional[str], Tuple[GenerationAttempt, ...])`. `run_agent_task()` now calls
this helper instead of inlining the loop; `agent_runtime/counterfactual.py`'s masked run
calls the exact same helper, so the masked run's retry/attempt-recording behavior is
byte-for-byte identical to the baseline's own, never a second, divergent reimplementation.
No signature changed, no existing caller was touched, and every pre-existing test in
`test_agent_runtime.py`/`test_trace_identity_integration.py` passes unchanged (19/19,
verified before writing any new code, confirming the refactor is purely mechanical).

## 3. Deliverable 1 — `run_counterfactual_mask()` / `CounterfactualRunOutcome`

New module: `phase3/evaluation/agent_runtime/counterfactual.py`. Validates
`masked_memory_id` is in `baseline.selected_memory_ids` (raises
`CounterfactualMaskingError` otherwise — never silently no-ops). Deep-copies
`baseline.agent_visible_context`, removes the one matching `memory_content` entry,
re-validates the masked context through `boundary.validate_agent_visible()` and
`security.leakage.validate_no_leakage()` (the SAME two checks the baseline context already
passed) before proceeding — raising, not assuming, if either somehow fails. Renders and
generates via `render_messages()`/`generate_with_retries()`, reusing `config` unchanged.
`CounterfactualRunOutcome` carries no `generation_config_fingerprint` field of its own —
the baseline's own, unchanged value already IS the masked run's value, by construction
(never recomputed).

## 4. Deliverable 2 — diff criterion

`DIFF_CRITERION_EXACT_NORMALIZED_MATCH` (the only criterion shipped, per mission section
4's explicit non-goal on semantic/LLM-judge matching): strip leading/trailing whitespace,
collapse internal whitespace runs to a single space, **no case-folding, no punctuation
stripping**. Tested directly: a trailing-whitespace-only difference and an internal-
whitespace-run difference are both `NOT_COUNTERFACTUALLY_INFLUENTIAL`; a case-only
difference (`"Paris"` vs `"paris"`) is `COUNTERFACTUALLY_INFLUENTIAL` — the documented,
deliberate precision/recall tradeoff the mission requires. `diff_criterion` is a named,
swappable string parameter on `compare_counterfactual_run()`; an unrecognized value raises
`ValueError` rather than silently falling back to a default.

## 5. Deliverable 3 — `CounterfactualComparisonResult` and status vocabulary

Four-way closed status set: `COUNTERFACTUALLY_INFLUENTIAL`,
`NOT_COUNTERFACTUALLY_INFLUENTIAL`, `INCONCLUSIVE_BASELINE_FAILURE`,
`INCONCLUSIVE_GENERATION_FAILURE` — enforced in `__post_init__`. A `None` answer on either
side is routed to an `INCONCLUSIVE_*` status *before* any diff attempt; never diffed
against real content. `baseline_answer_hash`/`masked_answer_hash` use
`security.reproducibility.fingerprint()` — H.4-F's/`event_identity.py`'s established
hashing authority, no second scheme.

## 6. Deliverable 4 — `canonical_event.py`, additive

Added `EVENT_COUNTERFACTUALLY_INFLUENTIAL = "counterfactually_influential"` to
`EVENT_TYPES` (additive, exactly mirroring H.4-BC's `rejected`/`relationship_detected`
precedent). Scoped like `retrieved`/`selected`, not like `rejected`/`relationship_detected`:
added to `_CONFIG_SCOPED_EVENT_TYPES` (requires non-empty `config_fingerprint`), to
`_TASK_SCOPED_EVENT_TYPES` (requires non-empty `task_id`), and to
`_SINGLE_MEMORY_EVENT_TYPES` (exactly one `memory_id` — the masked one). Four new fields
added to `CanonicalEvent`: `counterfactual_answer_hash`, `baseline_answer_hash`,
`diff_criterion`, `masking_method` — all required (non-empty/valid) for
`counterfactually_influential`, all forbidden (`None`) for every other event type, mirroring
the exact `__post_init__` if/else pattern H.4-BC/H.4-F both used. `masking_method` is
validated against a new closed enum, `MASKING_METHODS = (MASKING_METHOD_SELECTED_SET_
REMOVAL,)`, extendable only via the same review discipline as `REJECTED_REASONS`.
`to_dict()`/`from_dict()`/`identity_fields()` updated in the same enumerated style as every
prior addition (no `**kwargs`/reflection shortcut). Every existing event type, field, and
validation rule H.2/H.4-BC/H.4-D/H.4-F/H.4-G established is unchanged — confirmed by running
all eight pre-existing `canonical_event.py`-dependent test files (320 tests) before writing
any new test, all passing unmodified.

**Event-logging integration (§6) was NOT wired into any live pipeline.** The schema/
validation addition to `canonical_event.py` is complete and tested, but no caller in this
mission actually constructs and appends a `counterfactually_influential`
`CanonicalEvent` from a real `CounterfactualComparisonResult` — that wiring is deferred, per
the mission's own explicit permission ("this deliverable is explicitly optional... state
clearly whether completed or deferred").

## 7. Deliverable 7 — sampling strategy

`select_counterfactual_pairs(outcomes, sample_size=None, rng_seed=None)`. Default
(`sample_size=None`): every `(task_id, memory_id)` pair for every selected memory, in
outcome/selection order (exhaustive — appropriate for LoCoMo's "full battery" per the
revised plan's own dataset table). `sample_size` given: uniform sampling without
replacement via `random.Random(rng_seed)` — `rng_seed` is **required** whenever
`sample_size` is given (raises `ValueError` otherwise; never an unseeded sample).
`sample_size` exceeding the available pair count returns all available pairs, capped, not
an error (tested directly). No fixed LongMemEval budget is hardcoded anywhere — that
remains a per-campaign decision, per the mission's own explicit non-scope.

## 8. Explicit non-scope / deferred, stated per mission section 11

- **No modification to H.1/H.2/H.3 canonical files, `messages.py`, `boundary.py`, or
  `leakage.py`** — confirmed via `git diff --stat`, all empty for this stage.
- **No real (non-mock) counterfactual execution was performed.** Every test in
  `test_counterfactual.py` runs against `MockMem0Adapter` and an in-file fake `LLMProvider`
  (mirroring `test_agent_runtime.py`'s own established fixture style) — no real Mem0/A-MEM/
  LoCoMo/LongMemEval/network/LLM call anywhere.
- **No wiring into `campaign_formal_runner.py`.** `run_counterfactual_mask()`/
  `select_counterfactual_pairs()` are standalone, callable functions; automatic
  post-processing wiring into any campaign runner was not attempted.
- Causal attribution in the stronger sense (`used_causal`) — not implemented, not
  approximated.
- Semantic/paraphrase-aware diffing — not implemented (§4).
- A fixed LongMemEval sampling budget — not chosen (§7).
- The H.3/H.4-D/H.4-G versioning gap — untouched and irrelevant here; this mechanism never
  calls `memory_versioning` at all.

## 9. Files touched

- `phase3/evaluation/agent_runtime/counterfactual.py` — new module: `run_counterfactual_
  mask()`, `CounterfactualRunOutcome`, `compare_counterfactual_run()`,
  `CounterfactualComparisonResult`, `select_counterfactual_pairs()`, the diff-criterion
  implementation.
- `phase3/evaluation/agent_runtime/runner.py` — additive: `generate_with_retries()`
  extracted from `run_agent_task()`'s own inline loop; `run_agent_task()`'s call site
  updated to use it; `__all__` updated. No signature or observable behavior changed for any
  existing caller.
- `phase3/evaluation/foundations/canonical_event.py` — additive: `EVENT_COUNTERFACTUALLY_
  INFLUENTIAL`, `MASKING_METHOD_SELECTED_SET_REMOVAL`/`MASKING_METHODS`, four new optional
  fields, their `__post_init__` validation, and `to_dict()`/`from_dict()`/
  `identity_fields()` updates.
- `phase3/evaluation/tests/test_counterfactual.py` — new, 30 tests covering mission
  sections 8 and 9.

**Frozen/existing-untouched files — verified unmodified (empty diff):** `canonical.py`,
`ledger.py`, `canonical_write.py` (H.1); `event_ledger.py` (H.2, not touched this stage —
its existing `_CONFIG_SCOPED_EVENT_TYPES`-equivalent logic lives in `canonical_event.py`,
which IS additively extended, as authorized); `memory_versioning.py` (H.3);
`agent_runtime/messages.py`; `contracts/boundary.py`; `security/leakage.py`.

## 10. Tests

**Before H.4-A (this session's own baseline, carried over from the H.4-G report):**
`python -m pytest phase3/evaluation/tests/ -q` → **1537 passed, 1 failed, 17 skipped**
(404.18s). The one failure is the same pre-existing, unrelated dataset-fingerprint drift
reported in every prior H.4 report this session.

**After H.4-A:** **1567 passed, 1 failed (the same pre-existing failure), 17 skipped**
(257.48s) — exactly `1537 + 30` new tests, zero regressions, identical failure and skip
counts.

**New H.4-A tests only:**
`python -m pytest phase3/evaluation/tests/test_counterfactual.py -q` →
**30 passed** (0.20s).

## 11. Definition of done — checklist

- [x] The masked re-run mechanism works without re-invoking retrieval (AST-verified).
- [x] Diff criterion is exact-normalized-match as specified; inconclusive states never
      folded into a positive/negative influence verdict.
- [x] The four-way status vocabulary is enforced (`__post_init__` rejects any fifth value).
- [x] The sampling mechanism is deterministic (seeded) and budget-aware (capped at
      available pairs).
- [x] `counterfactually_influential` added additively to `canonical_event.py` with correct
      `config_fingerprint`/task/single-memory scoping.
- [x] All invariants (section 8) and adversarial cases (section 9) pass.
- [x] Regression suite shows zero regressions (1537→1567 passed, same 1 pre-existing
      unrelated failure, same 17 skipped).
- [x] This report states: `run_agent_task()` needed one additive refactor
      (`generate_with_retries()` extraction, no behavior change); event-logging
      integration (§6) was deferred; no real (non-mock) execution was performed; the
      single-retrieval design correction (§1) was followed and is AST-verified.
- [x] No modification to H.1/H.2/H.3 canonical files, `messages.py`, `boundary.py`, or
      `leakage.py`.

Completion of this mission completes all seven initiatives (A, B, C, D, E, F, G) of
`MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md`. Remaining work, per that document's own
close-out: (1) deciding whether/how to run real counterfactual campaigns, (2) the separate
H.3 versioning-gap remediation flagged after H.4-G, and (3) re-evaluating the readiness
rubric §11 against the now-complete instrumentation.
