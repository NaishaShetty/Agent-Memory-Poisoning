# Phase 3.3-H.3-R — Versioning Fix for Multi-Memory `derived` Events — Implementation Report

Status: **COMPLETE**.

Unlike every H.4-* stage that preceded it, this mission corrects a genuine defect inside a
previously-frozen file (`memory_versioning.py`, H.3), following the H.2-R/H.2-R2 precedent
for a reviewed, named remediation stage with full before/after regression proof — never a
silent patch.

## 1. Root cause — confirmed exactly as described

`event_ledger.py::events_for_memory(memory_id)` returns every event where `memory_id`
appears anywhere in `event.memory_ids` — correct, general-purpose behavior for
traceability/observability. `memory_versioning.py::reconstruct_version_history()` filters
this by `event_type in _LIFECYCLE_EVENT_TYPES` — a list that includes `EVENT_DERIVED`, the
one member that is not single-memory-scoped (a `derived` event's `memory_ids` legitimately
equals `set(source_memory_ids) | {target_memory_id}`). For a memory `P` that is only a
source/parent of some other memory's derivation (never itself that event's
`target_memory_id`), that `derived` event was incorrectly admitted into `P`'s OWN lifecycle
history. Since `derived` events are not state-changing (`canonical_event.py`'s
`_STATE_CHANGING_EVENT_TYPES` excludes `EVENT_DERIVED`), `new_state` is always `None` on
such an event — and `CanonicalMemoryVersion.__post_init__` correctly rejects `lifecycle_
state=None`, raising `MemoryVersioningError` for a perfectly healthy memory `P` that never
did anything wrong. Confirmed directly, before writing the fix, by reproducing the crash
against a minimal two-source, one-target derivation.

## 2. The fix — exactly the one condition specified, nowhere else

`memory_versioning.py::reconstruct_version_history()`'s event filter now additionally
requires, for `derived` events specifically, that `memory_id == e.target_memory_id`:

```python
lifecycle_events: List[CanonicalEvent] = [
    e
    for e in event_ledger.events_for_memory(memory_id)
    if e.event_type in _LIFECYCLE_EVENT_TYPES
    and (e.event_type != EVENT_DERIVED or e.target_memory_id == memory_id)
]
```

No other line of `memory_versioning.py` changed. `event_ledger.py` and `canonical_event.py`
were not touched at all — `events_for_memory()`'s own general-purpose semantics remain
exactly as they were, so every other caller (traceability queries, `events_for_task()`,
`events_for_foundation()`) is unaffected by construction (no code path in either file was
modified).

## 3. `get_current_version()`/`get_version()` — no separate fix needed, confirmed

Both are pure derivations of `reconstruct_version_history()`'s own output. Verified directly:
a pure-source memory's `get_current_version()` now returns its own genuine `CREATED` (or
later, correctly-tracked `RETIRED`) state, with no code change to either function.

## 4. A second, DIFFERENT, pre-existing bug was found — documented, not fixed

While testing the fix, `reconstruct_version_history()` was also run on the *target* of a
derivation (the memory legitimately created by that `derived` event, where `target_memory_id
== memory_id`). This **still raises** `MemoryVersioningError`, identically before and after
the H.3-R fix: a `derived`-type memory's own creation event has `new_state=None`
unconditionally (it is never state-changing, per `canonical_event.py`), so the very first
entry in that memory's own lifecycle history has no valid `lifecycle_state` — completely
independent of the source-contamination bug this mission was scoped to fix. This is a
**different, orthogonal defect**, out of this mission's explicit scope (section 5: "do not
attempt to fix any other latent gap... document it the same honest way H.4-D/G did"). It is
named here, reproduced directly
(`test_h3_r_target_memorys_own_derived_creation_is_a_documented_separate_gap`), and left
unrepaired. **Practical consequence**: H.4-G's own finding — "every genuine taint
descendant is structurally derivation-touched, so `lifecycle_status` realistically reports
`UNKNOWN_VERSIONING_GAP` for every genuinely-tainted id today" — remains fully true after
this fix, but for a more precise reason than previously stated: every taint descendant has
non-empty own `parent_ids` (making it itself the *target* of a `derived` event), which hits
*this* orthogonal, still-open bug, not the one H.3-R closes.

## 5. Regression evidence (mission section 4)

**Item 1 — existing `test_h3_versioning.py` unchanged**: all 52 pre-existing tests pass with
zero modification to any existing test's expected outcome — run once before writing any new
test, confirming H.4-D's own prediction ("H.3's own test suite never exercises this — it
only ever seeds via `created`") held exactly as stated.

**Item 2 — new tests added to `test_h3_versioning.py`** (5 new tests, appended in a new
"Phase 3.3-H.3-R" section, following H.2-R/H.2-R2's own precedent of extending the
remediated stage's own test file):
- A pure-source memory's reconstruction no longer crashes and reflects only its own
  `created` history (`test_h3_r_pure_source_memory_reconstruction_no_longer_crashes`),
  verified by asserting the sole surviving version's `established_by_event_id` is the
  source's own `created` event, never the derivation event.
- `get_current_version()` for a pure source resolves correctly
  (`test_h3_r_pure_source_memory_current_version_is_its_own_created_state`).
- A source's own LATER, genuine retirement is still correctly tracked — proving the fix
  removes only the spurious cross-memory entry, not any of the memory's own real history
  (`test_h3_r_source_memorys_own_later_retirement_is_still_correctly_tracked`).
- The orthogonal, separate, NOT-fixed target-side bug is reproduced and documented directly
  (`test_h3_r_target_memorys_own_derived_creation_is_a_documented_separate_gap`), per
  section 4 of this report.
- A three-source, one-target derivation confirms every source reconstructs cleanly with no
  cross-contamination between siblings
  (`test_h3_r_multi_source_derivation_all_sources_reconstruct_cleanly`).

**Item 3 — `test_qualification_h4_d.py` re-run in full**: all 74 tests pass, identical to
the H.4-D baseline. H.4-D's own `_derivation_touched_ids()` skip logic is unmodified by this
mission and remains harmless — it now conservatively skips some ids (foundation-type
memories that are ONLY a source, never themselves derived) that would, after this fix,
actually resolve correctly via `get_current_version()` — but since H.4-D's own code was not
touched, its qualification results are byte-for-byte unchanged (confirmed by the full
re-run, not assumed).

**Item 4 — `test_taint_propagation.py` re-run in full**: all 19 tests pass, identical
`tainted_memory_ids` sets (reachability is untouched by this fix — it operates purely on
`parent_ids`, never events). **H.4-G's `_is_derivation_touched()` predicate was read
directly, as instructed, rather than assumed**: it is a two-clause OR — `(a)` the memory
itself has non-empty `parent_ids` (i.e., it is itself `derived`-shaped) `OR` `(b)` it is
referenced as a parent by some other memory in the snapshot. Clause `(a)` alone already
covers every genuine taint descendant (section 4's finding: every descendant is, by
construction, `derived`-shaped) — so clause `(b)` is **provably dead code for
`taint_propagation.py`'s actual call pattern** (it only ever evaluates the predicate against
`tainted_memory_ids`, which are always non-empty-`parent_ids` already). **Conclusion: H.4-G's
predicate is over-broad in principle (clause `(b)` would incorrectly skip a pure-source,
non-derived id if one were ever checked), but this over-broadness has zero observable effect
on any of H.4-G's own current results**, confirmed by the identical-results re-run.

**Item 5 — full repository regression suite**:

| | Passed | Failed | Skipped | Wall time |
|---|---|---|---|---|
| Before H.3-R | 1567 | 1 (pre-existing) | 17 | 257.48s |
| After H.3-R | 1572 | 1 (same, pre-existing) | 17 | 288.50s |

Exactly `1567 + 5` new tests, zero regressions, identical failure (the same unrelated
`test_candidate_memoryarena.py` dataset-fingerprint drift reported in every prior report
this session) and skip counts.

## 6. Recommendation on the H.4-D/G skip-logic cleanup (mission section 5)

**Not performed in this mission, as instructed.** Recommended as a small, low-risk, optional
future stage: both `qualification_harness.py::_derivation_touched_ids()` and
`taint_propagation.py::_is_derivation_touched()` could narrow their skip condition from "has
non-empty own `parent_ids` OR is referenced as a parent by another memory" to just "has
non-empty own `parent_ids`" (dropping the now-partially-unnecessary second clause) — for
H.4-D, this would let currently-conservatively-skipped, pure-source (foundation-type,
never-derived) memories' real lifecycle status be reported instead of silently omitted in
`compute_expected_graph()`'s comparison. For H.4-G, this cleanup would have **zero
behavioral effect** given the current finding that clause `(b)` is dead code for its actual
call pattern — so it is purely a documentation/clarity improvement there, not a functional
one. Neither cleanup is required for correctness (conservatism is not a bug, per this
mission's own section 5), and the section 4 finding (a *different*, still-open bug makes
every genuine taint descendant unresolvable regardless) means the H.4-G cleanup specifically
would not change any real analysis outcome today. Recommend deferring both until (a) the
section-4 target-side bug is separately triaged/fixed (which would make the H.4-G cleanup
actually consequential), or (b) a concrete H.4-D caller needs a pure-source memory's real
lifecycle status.

## 7. Files touched

- `phase3/evaluation/foundations/memory_versioning.py` — the one, narrow, additive-in-effect
  condition described in section 2. No other line changed.
- `phase3/evaluation/tests/test_h3_versioning.py` — 5 new tests appended in a new "Phase
  3.3-H.3-R" section; zero existing tests modified.

**No modification to** `canonical.py`, `ledger.py`, `canonical_write.py` (H.1),
`canonical_event.py`, or `event_ledger.py` (H.2) — confirmed via `git diff --stat`, all
empty for this stage.

## 8. Definition of done — checklist

- [x] The one-condition fix is in place in `reconstruct_version_history()`, nowhere else.
- [x] Every existing `test_h3_versioning.py` test passes unchanged (52/52, verified before
      any new test was written).
- [x] New tests prove a pure-source memory's version history no longer crashes and reflects
      only its own genuine transitions (5 new tests, all passing).
- [x] `test_qualification_h4_d.py` (74/74) and `test_taint_propagation.py` (19/19) both
      re-run in full with identical substantive results.
- [x] Full regression suite: 1567→1572 passed, same 1 pre-existing unrelated failure, same
      17 skipped — zero unexpected regressions.
- [x] This report honestly states the H.4-D/G skip-logic follow-up recommendation (section
      6) without performing it, and separately documents the orthogonal target-side bug
      found during implementation (section 4) without fixing it.

This closes the last open item flagged after H.4-G, ahead of re-evaluating the readiness
rubric in `MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md` §11.
