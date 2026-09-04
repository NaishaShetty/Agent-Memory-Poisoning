# Phase 3.3-H.2 — Canonical Append-Only Event Ledger — Implementation Report

Status: **COMPLETE**. Architectural remediation stage only — no evaluation campaign was run
or modified.

## 1. Files created

All additions. **No existing file was modified.**

| File | Purpose |
|---|---|
| `phase3/evaluation/foundations/canonical_event.py` | `CanonicalEvent` — strict runtime object for `relationship_schema.md` section 3 |
| `phase3/evaluation/foundations/event_ledger.py` | `CanonicalEventLedger` — benchmark-owned, append-only event history, linked to a `CanonicalMemoryLedger` |
| `phase3/evaluation/tests/test_canonical_event_ledger_h2.py` | 42 contract tests covering the mission's 30 test items + 12 invariants |
| `phase3/specification/PHASE3_3_H2_CANONICAL_EVENT_LEDGER.md` | Architecture/design document |
| `phase3/experiments/PHASE3_3_H2_IMPLEMENTATION_REPORT.md` | This report |

## 2. Files modified

**None.** Nothing from H.1 (`canonical.py`, `ledger.py`, `canonical_write.py`) was changed;
`CanonicalEventLedger` consumes H.1's `CanonicalMemoryLedger` as a constructor dependency
without modifying it. No trace module (`foundations/trace.py`, `agent_runtime/trace.py`,
`contracts/trace_artifact.schema.json`) was touched — see design doc section 15 for why
trace reconciliation was investigated but explicitly deferred.

## 3. Event schema

Seven event types, taken verbatim from `relationship_schema.md` section 3:
`created`, `retrieved`, `selected`, `used`, `derived`, `superseded`, `retired`.

`CanonicalEvent` fields: `event_id`, `event_type`, `memory_ids` (tuple, non-empty),
`timestamp`, `actor`, `reason`, `task_id` (required for `retrieved`/`selected`/`used`,
optional otherwise), `previous_state`/`new_state` (required for `created`/`superseded`/
`retired`, forbidden otherwise; validated against H.1's `LIFECYCLE_STATES`),
`foundation_name`/`foundation_memory_id` (optional; the latter requires the former).

## 4. Event storage

`events.jsonl`, one JSON line per successful `append()`, under a `storage_dir` — identical
persistence discipline to H.1's `CanonicalMemoryLedger` (append-mode write, one already-
formed line, `flush()`, `os.fsync()`). Reload is a pure, order-preserving fold over the
file. Single-process/single-writer; no cross-process lock (documented limitation, matches
H.1's own).

## 5. APIs

- `CanonicalEventLedger(storage_dir, memory_ledger)` — constructor requires a
  `CanonicalMemoryLedger` to validate linkage against.
- `append(event) -> APPEND_CREATED | APPEND_IDEMPOTENT` — raises `UnknownCanonicalMemoryError`
  for an unlinked memory id, `CanonicalEventCollisionError` for a differing-payload
  `event_id` re-use.
- `get_event(event_id)`, `events_for_memory(memory_id)`, `events_for_task(task_id)`,
  `events_for_foundation(foundation_name)`, `reconstruct_memory_history(memory_id)`
  (identical to `events_for_memory`), `all_events()`.
- **No** `update_event()`/`delete_event()` — deliberately absent, not merely unused; tested
  as a structural invariant.

## 6. Invariants

All 12 mission invariants implemented and tested — see design doc section 19 for the full
mapping to test names.

## 7. Test count

**New H.2 tests only:** `python -m pytest phase3/evaluation/tests/test_canonical_event_ledger_h2.py -q`
→ **42 passed** in 0.29s.

**Before this stage (== H.1's "after" count):** 1188 passed, 14 skipped.

**After this stage:** 1230 passed, 14 skipped (1188 + 42 new, zero regressions, identical
skip count) — see section 8 for exact timings.

## 8. Regression results

| Run | Result | Duration |
|---|---|---|
| Full suite, before H.2 (== H.1's final state) | 1188 passed, 14 skipped | 365.20s |
| Full suite, after H.2 | 1230 passed, 14 skipped | 374.83s |
| Full suite, after H.2, `-W error` | 1230 passed, 14 skipped | 350.61s |

No warning was promoted to an error anywhere in the suite, including the new H.2 tests.

## 9. Limitations

See design doc section 21 for the full list. Summary: single-process ledger; no trace
reconciliation implemented; no `experiment_reset` event type exists (a genuine gap in
`relationship_schema.md` itself, not fixed here since fixing it would mean changing a
frozen schema document); `actor` is an open string, not a closed enum; no call site wired
to actually emit events yet (H.2 is pure substrate, matching H.1's own deferred-migration
posture).

## 10. Trace integration status

Investigated, not implemented. `FoundationTraceArtifact` could in principle gain an
additive, optional `event_id` field, but every mock/real adapter's `normalize_trace()` call
sits on a path that, for A-MEM, is currently the live 3.3-G.1 execution path — this stage
draws the line at zero files on that import path being touched at all, rather than judging
each candidate change's actual risk case-by-case. `agent_runtime/trace.py`'s trace dict and
`contracts/trace_artifact.schema.json` are pre-existing "protected surface, additive only";
neither was imported or referenced by any H.2 file. Full reasoning: design doc section 15.

## 11. G.1 impact

**The running 3.3-G.1 A-MEM × LongMemEval N=120 campaign was not disturbed.**

Verified via `Get-CimInstance Win32_Process -Filter "Name='python.exe'"` immediately before
starting H.2 and again immediately before running the final regression pass: the same three
worker processes (PIDs 33588/18212/4512 under `h4venv`) were running the identical
`phase3.evaluation.agent_runtime.campaign_formal_runner c_longmemeval_worker {0,1,2} 3`
command line throughout this stage's implementation.

No file on that process's import path was read-written, modified, or deleted. `git status
--short` confirms every change this stage made is a newly-added file; `git diff --stat`
against the working tree shows zero modified tracked files.

## 12. Deferred to H.3

Immutable memory versioning, supersession-chain semantics (beyond `superseded` merely
being a representable, validated event type), and retirement/tombstone workflows (beyond
`retired` being representable). No change was made to `CanonicalMemoryLedger.put()`'s
existing collision-only semantics.

## 13. Git status

```
$ git status --short
?? phase3/evaluation/foundations/canonical_event.py
?? phase3/evaluation/foundations/event_ledger.py
?? phase3/evaluation/tests/test_canonical_event_ledger_h2.py
?? phase3/specification/PHASE3_3_H2_CANONICAL_EVENT_LEDGER.md
?? phase3/experiments/PHASE3_3_H2_IMPLEMENTATION_REPORT.md
(plus H.1's own untracked additions, and pre-existing untracked files from the in-progress
3.3-G/G.1 campaign work, unrelated to and unmodified by this stage)

$ git diff --stat
(empty -- no tracked file was modified)
```

Per the mission's repository-discipline rule, no `git add`/`commit`/`push` was performed.
