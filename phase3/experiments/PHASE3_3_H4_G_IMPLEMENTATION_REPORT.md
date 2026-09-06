# Phase 3.3-H.4-G — `tainted_by` Attack-Propagation Query — Implementation Report

Status: **COMPLETE**.

## 1. Scope confirmed narrow, per mission's own corrected understanding

`metrics/provenance.py::descendants()` already provides exactly the traversal this mission
needs — transitive `parent_ids` (i.e. `derived_from`) reachability, cycle-safe, already
tested against `fixtures/lineage/*.json`. This stage's actual work was: build a live
canonical-ledger snapshot for it to run against, run it once per confirmed-attack id and
union the results while preserving per-attack attribution, cross-reference current
lifecycle state, and wrap all of it in one documented function. No graph traversal logic
was reimplemented.

## 2. Module placement — `foundations/taint_propagation.py`, and why

Placed under `phase3/evaluation/foundations/`, not `metrics/`. `metrics/provenance.py` is a
package of pure functions over plain, caller-supplied mappings with no concept of a
`CanonicalMemoryLedger` or `memory_versioning`'s lifecycle machinery — the mission's own
§3 explicitly forbids giving it one. This module is the opposite: it is entirely *about*
canonical-ledger/lifecycle infrastructure (it builds a snapshot from
`CanonicalMemoryLedger.list_records()` and calls `memory_versioning.get_current_version()`)
and only *delegates* the actual traversal to `provenance.descendants()`, reused verbatim.
Every other H.1/H.2/H.3-adjacent query module that consumes `CanonicalMemoryLedger`/
`memory_versioning` directly (`memory_versioning.py` itself, H.4-D's
`qualification_harness.py`) already lives under `foundations/`/`foundations_real/` — this
follows that same placement convention.

## 3. No event-ledger replay

Confirmed, and verifiable by inspection: this module has zero dependency on
`canonical_event.py`/`event_ledger.py` for the traversal itself. `parent_ids` already lives
directly on `CanonicalMemoryRecord` (H.1); reading the ledger's own records answers the
lineage-reachability question without replaying any `derived` event. (`event_ledger`/
`supersession_ledger` are accepted as *optional* parameters purely for the separate,
optional lifecycle-status cross-reference — see section 4.)

## 4. The H.3/H.4-D versioning gap — worked around again, not repaired, and a further
honest finding

`_is_derivation_touched()` replicates (does not import — that name is private, underscore-
prefixed, in `qualification_harness.py`, per the mission's own instruction not to reach
into another module's internals) H.4-D's exact narrow check: is a memory itself
`derived`-shaped (non-empty `parent_ids`), or is it referenced as a parent by some other
memory? Either shape triggers the frozen `memory_versioning.reconstruct_version_history()`
bug (a `derived` event's `new_state=None` slips into a memory's own version history via
`events_for_memory()`'s "matches on any appearance in `memory_ids`" property). A
derivation-touched tainted id is reported as `LIFECYCLE_STATUS_UNKNOWN_VERSIONING_GAP` and
`get_current_version()` is never called on it.

**A further finding, discovered during testing, stated honestly in the module docstring**:
every GENUINE taint descendant is, by construction, a `derived`-type memory — non-empty
`parent_ids` is exactly what connects it to its ancestor via `derived_from` — so it always
satisfies `_is_derivation_touched()`'s own "has non-empty parent_ids" clause on its own
account. Given the current H.3 gap, this means `lifecycle_status` realistically reports
`LIFECYCLE_STATUS_UNKNOWN_VERSIONING_GAP` for **every** genuinely-tainted id today;
`get_current_version()` is not actually reachable for a real taint result under the present
frozen H.3 behavior. This is not a defect in this module — it is an honest consequence of a
documented gap in a module this stage must not modify (and does not), surfaced here rather
than hidden. `test_every_genuine_taint_descendant_is_structurally_derivation_touched`
records this directly. No fix was attempted (mission section 8's explicit non-scope).

## 5. `tainted_by` vs. `counterfactually_influential` (Initiative A) — kept separate

`TaintReport`'s own docstring states explicitly, in a clearly marked section: this is a
LINEAGE-REACHABILITY fact (reachable from a confirmed attack via `derived_from`), never a
counterfactual-influence or causal-attribution fact. `TaintReport` has no
`counterfactually_influential`-shaped field, and no test or code path in this module
conflates the two — tested directly (`test_taint_report_docstring_disclaims_counterfactual_
influence`, `test_taint_report_has_no_counterfactually_influential_field`).

## 6. Invariants and adversarial cases

All of mission section 6's invariants and section 7's adversarial cases are tested in
`test_taint_propagation.py` (19 tests): read-only (no `.put()`/`.append()` call anywhere in
the module, checked both by source-text scan and by observing ledger state unchanged
before/after a call); an attack id excludes itself unless genuinely reachable from a
*different* attack id in the same call (tested with a confirmed-attack chain X→Y); only
`parent_ids`/`derived_from` propagates (an `equivalent_to` relationship_detected edge does
NOT taint); deterministic and order-independent across `attack_memory_ids` permutations;
the derivation-touched workaround never crashes; `any_cycle_detected` surfaces correctly
for a genuine cycle and stays `False` for an acyclic chain; overlapping descendant sets
from two attacks are counted once in the union but listed under both in
`tainted_by_attack`; an attack with no descendants returns an empty result, not an error;
an unknown attack id raises `UnknownAttackMemoryError` immediately (checked before any
traversal, never a partial result); and a chain of confirmed attacks (one attack
downstream of another) is represented without double-counting in the union tuple.

## 7. Explicit non-scope / deferred (mission section 8)

- No modification to `provenance.py`, `canonical.py`, `ledger.py`, or `memory_versioning.py`
  — confirmed via `git diff --stat`, all empty.
- No fix to the H.3/H.4-D versioning gap — worked around identically, as required; the
  further finding in section 4 is documented, not repaired.
- No Phase 4 attack-implementation or confirmed-attack-determination logic — this module
  only builds the query Phase 4 will call once it has its own list of confirmed-attack ids.
- **No integration into `campaign_formal_runner.py` or any live reporting pipeline.**
  `tainted_memories()` is a standalone, callable query function; no such wiring was done as
  part of this stage.
- Initiative A — unrelated; kept structurally and documentarily separate (section 5).

## 8. Files touched

- `phase3/evaluation/foundations/taint_propagation.py` — new module:
  `UnknownAttackMemoryError`, `TaintReport`, `tainted_memories()`,
  `LIFECYCLE_STATUS_UNKNOWN_VERSIONING_GAP`, `LIFECYCLE_STATUS_NO_LIFECYCLE_HISTORY`.
- `phase3/evaluation/tests/test_taint_propagation.py` — new, 19 tests covering mission
  sections 6 and 7.

**Frozen/existing-untouched files — verified unmodified (empty diff):** `canonical.py`,
`ledger.py` (H.1); `memory_versioning.py` (H.3); `metrics/provenance.py` (Phase 3.2-D);
`qualification_harness.py` (H.4-D, referenced only for its documented prior art, no import
of its private names). `canonical_event.py`/`event_ledger.py` are imported only for their
existing, unmodified types (`CanonicalEvent`, `CanonicalEventLedger`) in the test file — no
line of either was touched.

## 9. Tests

**Before H.4-G (this session's own baseline, carried over from the H.4-E report):**
`python -m pytest phase3/evaluation/tests/ -q` → **1518 passed, 1 failed, 17 skipped**
(294.22s). The one failure is the same pre-existing, unrelated dataset-fingerprint drift
reported in every prior H.4 report this session.

**After H.4-G:** **1537 passed, 1 failed (the same pre-existing failure), 17 skipped**
(404.18s) — exactly `1518 + 19` new tests, zero regressions, identical failure and skip
counts.

**New H.4-G tests only:**
`python -m pytest phase3/evaluation/tests/test_taint_propagation.py -q` →
**19 passed** (0.35s).

## 10. Definition of done — checklist

- [x] `tainted_memories()` correctly reuses `provenance.descendants()` against a live
      canonical-ledger snapshot.
- [x] Correctly unions multi-attack descendant sets while preserving per-attack
      attribution (`tainted_by_attack`).
- [x] Correctly reports lifecycle status while safely routing around the known H.3/H.4-D
      versioning gap (and documents the further finding that this routing applies to every
      genuine taint result under the gap's current, unfixed behavior).
- [x] All invariants (section 6) and adversarial cases (section 7) pass.
- [x] Regression suite shows zero regressions (1518→1537 passed, same 1 pre-existing
      unrelated failure, same 17 skipped).
- [x] This report states the module's placement/rationale and confirms no modification to
      `provenance.py`, `canonical.py`, `ledger.py`, or `memory_versioning.py`.
- [x] No modification to any file listed as frozen/existing-untouched in mission section 3.

This is the last of the six initiatives (B, C, D, E, F, G) from
`MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md` other than Initiative A, which remains
the sole outstanding item per that document's own §10.
