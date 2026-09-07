# Phase 3.3-H4-CONTENT-LEAKAGE-WIRE — Implementation Report

Status: **COMPLETE**. Closes the gap flagged in the Phase 3 completion audit (§15):
`content_leakage.py`'s fail-closed content-level scan was wired into
`integration/pipeline.py::evaluate_case()` (H.4-E) but never into
`campaign_formal_runner.py`, the actual harness that produced every real result this
session (and the original frozen 3.3-G-formal campaign). Structural leakage checks
(`boundary.py`/`leakage.py`) were already live there via `run_agent_task()` itself; the
content-level scan was the one layer missing from the real execution path.

## 1. What was added

Both `run_condition_b_mem0()` and `run_condition_c_amem()` now run the identical two-scan
pattern `integration/pipeline.py::evaluate_case()` already established (same field
scoping, same rationale): a `gold_answer` scan over the context with `memory_content`
removed, and a `gold_evidence_ids` scan over the context with only each memory's own
`memory_id` key removed (so a selected memory's `memory_id` legitimately equaling a gold
evidence id — the expected shape of correct evidence exposure — is never flagged, exactly
as `content_leakage.py`'s own design requires).

Placed immediately after `run_agent_task()` returns and *before* `evaluate_and_trace()`/
`evaluate_and_trace_with_identity()` — a detected leak stops the task before any further
processing, not merely a diagnostic afterthought. **Deliberately not wrapped in its own
try/except** (unlike the canonical-event wiring, which is optional instrumentation) — a
`ContentLeakageDetectedError` is allowed to propagate to the existing, pre-existing
per-task `except Exception` handler, marking that task `EXECUTION_FAILURE`. This matches
the leakage contract's own "no experimental exceptions" severity: a leak should stop the
task, not be swallowed as a soft warning.

The wiring is duplicated across both conditions (not factored into a shared helper), to
match this module's own existing convention (Condition B and C each already inline their
own logic independently) and keep each condition's diff separately reviewable.

## 2. Safety verification

New test file, `test_campaign_formal_runner_content_leakage_wire.py`, 5 tests, proving
both directions — not just "it doesn't crash":

1. **Legitimate operation is not flagged** (both conditions) — a gold answer restated
   inside correctly-exposed evidence content produces `SUCCESSFUL_EVALUATION`, exactly as
   before this wiring.
2. **A genuine leak is actually caught** (both conditions) — a gold answer injected
   directly into the task prompt (a surface the `gold_answer` scan does *not* exclude)
   produces `EXECUTION_FAILURE` with the leakage error visible in the result.
3. **A leaked gold evidence ID inside memory content text** (Condition B) — an id
   appearing somewhere other than its own legitimate `memory_id` field is caught.

All pre-existing wiring test suites (`test_campaign_formal_runner_h4_wire.py`,
`test_campaign_formal_runner_h4_wire_c.py`, `test_campaign_formal_checkpoint.py` — 24
tests total) pass unchanged, confirming no false positives were introduced into any
already-validated scenario.

## 3. Regression

Full suite: **1601 passed**, 14 skipped (llama-server not running for this check),
same single pre-existing unrelated memoryarena fingerprint-drift failure. Zero
unexpected regressions.

## 4. What this does not change

- `boundary.py`, `leakage.py`, `content_leakage.py` themselves — untouched, reused
  exactly as built.
- `integration/pipeline.py` — untouched; its own wiring remains as H.4-E left it.
- The structural checks already live via `run_agent_task()` — unaffected; this adds a
  third, independent layer, not a replacement for the first two.
- No real campaign was re-run against this wiring as part of this stage — the next real
  Mem0/A-MEM run (this session already produced several) will be the first to exercise it
  for real; nothing in this repository's real evidence to date has been re-validated
  against it retroactively.

## 5. Compatibility and freeze status

Only `campaign_formal_runner.py` (additive) and one new test file were touched. Not a
frozen decision — a completed wiring stage closing an audit-identified gap.
