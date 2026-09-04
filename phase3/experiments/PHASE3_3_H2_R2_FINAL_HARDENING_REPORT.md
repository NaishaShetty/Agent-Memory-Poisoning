# Phase 3.3-H.2-R2 — Final H.2 Hardening Pass — Report

Status: **COMPLETE**.

## 1. STATUS

COMPLETE.

## 2. Issue investigated

Four areas per the mission brief: (A) event identity semantics, (B) identifier namespace
enforcement, (C) experiment-boundary-ledger concurrency/ownership, (D) integration-API
readiness. A fifth, independent gap was found while investigating (A) — see section 3.

## 3. Evidence

- **A:** `memory_schema.json` models `creation_event`, `superseded_by`, and
  `lifecycle_state` as SINGULAR per-memory fields. Nothing in H.2/H.2-R prevented two
  different `created`/`derived`/`superseded`/`retired` events from being appended for the
  same memory — a genuine data-integrity gap distinct from (and in addition to) the
  identical-content-duplicate question the mission explicitly asked about.
- **B:** every pre-existing H.2/H.2-R test fixture uses plain, non-`EVT-`-prefixed
  `event_id` values (`"evt-001"`, `"e1"`-`"e9"`, etc.) — direct evidence that mandatory
  prefix enforcement would break historical fixtures for a cosmetic reason.
- **C:** `campaign_formal_runner.py`'s own module docstring: "each worker writes to its OWN
  checkpoint file... merged only after all workers finish a batch, by
  `merge_longmemeval_worker_checkpoints()`" — direct repository evidence for the
  already-established multi-worker concurrency pattern (per-worker isolation + merge, not
  shared-file locking). Confirmed the G.1 campaign genuinely runs 3 concurrent worker
  processes (PIDs 33588/18212/4512) throughout this stage.
- **D:** `campaign_formal_runner.py` (and every other live-runtime file) contains zero
  reference to any H.2/H.2-R/H.2-R2 module — confirmed by direct source inspection, not
  assumed.

## 4. Decision

| Area | Decision |
|---|---|
| A — identity semantics | Identical content = same historical fact (formalized as documented invariant, already implicit in H.2-R's content-derived id design) |
| A — single-occurrence gap | Real correctness issue; implemented `len(memory_ids)==1` constraint for `created`/`superseded`/`retired` + ledger-level `SingleOccurrenceViolationError` |
| B — namespace format | Do NOT enforce `EVT-`/`BND-` as mandatory; namespace separation is already structural (separate classes/files) and stronger than any format check could be |
| C — concurrency | Retain single-writer `ExperimentBoundaryLedger`; add `merge_experiment_boundary_ledgers()` mirroring the repository's own established checkpoint-merge pattern |
| D — integration | Add `build_canonical_event()`/`build_reset_boundary()` as the one documented construction surface per type, without removing or deprecating the low-level constructors |

## 5. Implementation

- `phase3/evaluation/foundations/canonical_event.py`: added `_SINGLE_MEMORY_EVENT_TYPES`
  validation (`created`/`superseded`/`retired` require exactly one `memory_id`).
- `phase3/evaluation/foundations/event_ledger.py`: added `SingleOccurrenceViolationError`
  and `_check_single_occurrence()`, invoked from `append()` after the existing
  idempotency/collision check and before any write; extended module docstring with the
  formal identity-semantics decision.
- `phase3/evaluation/foundations/event_identity.py`: added `build_canonical_event()`.
- `phase3/evaluation/foundations/experiment_boundary.py`: added `generate_boundary_id()`,
  `looks_like_generated_boundary_id()`, `build_reset_boundary()`, and
  `merge_experiment_boundary_ledgers()`.
- `phase3/specification/PHASE3_3_H2_CANONICAL_EVENT_LEDGER.md`: appended sections 30-36
  documenting all of the above. Sections 1-29 unchanged.

**No file was deleted or had an existing field/default changed.** Every change is a new
module, a new function in an existing module, or a new validation branch that only
rejects inputs that were never legitimately accepted before (see section 8).

## 6. Tests

New file: `phase3/evaluation/tests/test_h2_r2_hardening.py` — 36 tests covering all 30
mission test items plus 6 additional invariant/single-occurrence tests. One test
(`test_invariant_event_id_generation_remains_benchmark_owned`) was corrected mid-development
after its first draft accidentally matched its own docstring text rather than the
function's actual signature/behavior — fixed to inspect the real call signature instead.

## 7. Regression

| Run | Result | Duration |
|---|---|---|
| Full suite, before H.2-R2 (== H.2-R's final state) | 1262 passed, 14 skipped | 236.69s |
| Full suite, after H.2-R2 | 1298 passed, 14 skipped (1262 + 36 new, zero regressions) | 233.44s |
| Full suite, after H.2-R2, `-W error` | 1298 passed, 14 skipped, no warning promoted to error | 238.05s |

Dedicated suites: `test_canonical_event_ledger_h2.py` (42), `test_h2_remediation.py` (32),
`test_canonical_memory_ledger_h1.py` (29) — all still pass unmodified (103 total) after the
`len(memory_ids)==1` constraint was added, confirmed by direct re-run before proceeding to
the full suite.

## 8. Backward compatibility

Full. Both new validation paths (the `len(memory_ids)==1` constraint and the
single-occurrence ledger check) only reject inputs that were EITHER already
schema-violating (per `memory_schema.json`'s singular fields) or already a genuine
data-integrity conflict — no previously-legitimate H.2/H.2-R construction or append
becomes rejected. Verified directly: every existing `created`/`superseded`/`retired`
fixture in `test_canonical_event_ledger_h2.py`/`test_h2_remediation.py` already used
exactly one `memory_id`, and no existing test appends two conflicting single-occurrence
events for the same memory.

## 9. G.1 protection verification

Confirmed via `Get-CimInstance Win32_Process -Filter "Name='python.exe'"`:

- **Before starting H.2-R2:** PIDs 33588/18212/4512 running
  `phase3.evaluation.agent_runtime.campaign_formal_runner c_longmemeval_worker {0,1,2} 3`.
- **After completing H.2-R2** (immediately before the final regression run): the identical
  three PIDs, running the identical command line.

`campaign_formal_runner.py` was not modified, and contains zero reference to any
H.2/H.2-R/H.2-R2 module (tested directly:
`test_24_no_automatic_runtime_wiring`). No checkpoint/manifest/result file was touched.

## 10. Files changed

**New:**

| File | Purpose |
|---|---|
| `phase3/evaluation/tests/test_h2_r2_hardening.py` | 36 tests for all four H.2-R2 areas |
| `phase3/experiments/PHASE3_3_H2_R2_FINAL_HARDENING_REPORT.md` | This report |

**Modified (additive only — see section 8):**

| File | Change |
|---|---|
| `phase3/evaluation/foundations/canonical_event.py` | `len(memory_ids)==1` constraint for `created`/`superseded`/`retired` |
| `phase3/evaluation/foundations/event_ledger.py` | `SingleOccurrenceViolationError` + `_check_single_occurrence()`; docstring additions |
| `phase3/evaluation/foundations/event_identity.py` | `build_canonical_event()` added |
| `phase3/evaluation/foundations/experiment_boundary.py` | `generate_boundary_id()`, `looks_like_generated_boundary_id()`, `build_reset_boundary()`, `merge_experiment_boundary_ledgers()` added |
| `phase3/specification/PHASE3_3_H2_CANONICAL_EVENT_LEDGER.md` | Sections 30-36 appended |

**Not modified:** `canonical.py`, `ledger.py`, `canonical_write.py`,
`test_canonical_event_ledger_h2.py`, `test_h2_remediation.py`,
`PHASE3_3_H2_IMPLEMENTATION_REPORT.md`, `PHASE3_3_H2_REMEDIATION_REPORT.md`. No file on the
live G.1 import path.

## 11. Remaining accepted limitations

- No `merge_*` utility exists for `CanonicalEventLedger` (only `ExperimentBoundaryLedger`)
  — Area C's mission scope was the boundary ledger specifically; the identical pattern
  would generalize if/when needed.
- `EVT-`/`BND-` remain advisory, unenforced prefixes (deliberate decision, section 31 of
  the design doc).
- No runtime call site constructs a real event/boundary from live behavior yet — H.2 in
  its entirety remains integration-ready, not integrated.
- The single-occurrence check is scoped to one ledger instance's own recorded state, not a
  cross-ledger/cross-process global uniqueness claim (mirrors every other guarantee in this
  framework).

## 12. Explicit H.3 boundary

No memory version identity, version chains, supersession POLICY (as opposed to the
single-occurrence DATA-INTEGRITY check added here), retirement/tombstone workflow, or
version-aware retrieval was implemented. `CanonicalMemoryLedger.put()`'s existing
collision-only semantics are unchanged. The single-occurrence enforcement added in this
stage decides nothing about WHEN a `superseded`/`retired` event should be emitted — only
that, once one is recorded, it is the sole one for that memory. That "when" decision
remains H.3's.

## 13. H.2 freeze recommendation

**H.2 (base + H.2-R + H.2-R2) is ready to be declared FROZEN**, pending human review of
this report and its two predecessors. All identified gaps — experiment/run boundary
representation, benchmark-owned event ID authority, multi-memory lineage roles, event
identity semantics, namespace separation, boundary-ledger ownership, and integration-API
readiness — have been investigated and either resolved or explicitly, evidence-backed
declared not-a-defect. 1298 tests pass (up from H.2's original 1230), zero regressions
across three successive hardening passes, `-W error` clean throughout, and the live 3.3-G.1
campaign was never touched.

## 14. Git status

```
$ git status --short --porcelain | awk '{print $1}' | sort | uniq -c
     50 ??

$ git diff --stat
(empty -- zero tracked files modified across H.1, H.2, H.2-R, and H.2-R2)
```

Per the mission's repository-discipline rule, no `git add`/`commit`/`push` was performed.
