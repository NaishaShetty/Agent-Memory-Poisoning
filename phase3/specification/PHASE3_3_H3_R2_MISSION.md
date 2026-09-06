# Phase 3.3-H.3-R2 — Versioning Fix for `derived` Events' Implied Lifecycle State — Mission Brief

Status: **NOT STARTED**. Mission brief for an implementation pass, second in the H.3-R
remediation series (see [PHASE3_3_H3_R_MISSION.md](PHASE3_3_H3_R_MISSION.md) /
`PHASE3_3_H3_R_IMPLEMENTATION_REPORT.md` for the first). On completion, produce
`PHASE3_3_H3_R2_IMPLEMENTATION_REPORT.md` under `phase3/experiments/`.

**This is the second of two defects in `reconstruct_version_history()`, discovered
together but genuinely separate.** H.3-R fixed *which* `derived` events count toward a
memory's own lifecycle history (only when that memory is the event's `target_memory_id`,
not merely a source). This mission fixes a second, independent problem that H.3-R's own
implementation report surfaced: **even a correctly-identified, target-side `derived`
event still fails**, because `derived` events structurally never carry a `new_state` value
at all, and `reconstruct_version_history()` unconditionally reads `event.new_state` for
every lifecycle event, `derived` included.

## 1. Root cause

`canonical_event.py`'s `_STATE_CHANGING_EVENT_TYPES = (EVENT_CREATED, EVENT_SUPERSEDED,
EVENT_RETIRED)` deliberately **excludes** `EVENT_DERIVED` — and `CanonicalEvent
.__post_init__` (canonical_event.py, the non-state-changing branch) *forbids*
`new_state`/`previous_state` from being anything other than `None` for any event type not
in that list. This is correct, frozen H.2 behavior: a `derived` event describes lineage
(`source_memory_ids`/`target_memory_id`), not a state transition, so it was deliberately
designed to never carry a lifecycle state.

`memory_versioning.py::reconstruct_version_history()` (line ~340-350), however, builds
every lifecycle event's resulting `CanonicalMemoryVersion` the same way, regardless of
event type:

```python
versions.append(
    CanonicalMemoryVersion(
        ...
        lifecycle_state=event.new_state,
        ...
    )
)
```

For a `derived` event, `event.new_state` is always `None` (enforced by H.2, per above).
`CanonicalMemoryVersion.__post_init__` requires `lifecycle_state in LIFECYCLE_STATES`, and
`None` is not a member — so construction raises `MemoryVersioningError`, **even for the
exact target-side `derived` event H.3-R's fix now correctly identifies as belonging to
this memory.**

**This means the version-1-via-derivation path (H.3's own design doc, §11: "`created`/
`derived` → version 1") has likely never actually worked, for any derived memory, since
H.3 was first implemented** — consistent with H.4-D's finding that "H.3's own test suite
never exercises this — it only ever seeds via `created`."

## 2. The fix

Every `created` event in this entire codebase's existing usage (test_h3_versioning.py,
every fixture, no exception found) sets `new_state=LIFECYCLE_CREATED` — never
`LIFECYCLE_ACTIVE` directly. A derived memory's own creation is semantically identical to
a foundation memory's own creation for version-1 purposes (both are "this memory now
exists, in its initial lifecycle state") — the only difference is what caused it to exist
(direct ingestion vs. derivation from parents), which is already fully captured elsewhere
(`memory_type`, `parent_ids`, `source`), not by `lifecycle_state`.

**Fix, localized to `reconstruct_version_history()`'s per-event construction, mirroring
how the existing code already special-cases `EVENT_SUPERSEDED` to look up
`current_superseded_by` from `SupersessionLedger` rather than reading it off the event
itself:**

```python
for index, event in enumerate(lifecycle_events, start=1):
    if event.event_type == EVENT_SUPERSEDED:
        linkage = supersession_ledger.get_by_event_id(event.event_id)
        current_superseded_by = linkage.superseding_memory_id if linkage is not None else None

    if event.event_type == EVENT_DERIVED:
        version_lifecycle_state = LIFECYCLE_CREATED
    else:
        version_lifecycle_state = event.new_state

    versions.append(
        CanonicalMemoryVersion(
            ...
            lifecycle_state=version_lifecycle_state,
            ...
        )
    )
```

`LIFECYCLE_CREATED` must be imported from `canonical.py` (already imported into
`memory_versioning.py` — confirm during implementation; if not already imported, add the
import, which is the only change needed outside the function body itself).

**Why this is correct and not an invented convention:** it makes a `derived` event's
implied version state exactly match what a `created` event's version state already is in
100% of existing usage, for the exact scenario H.3's own design doc names explicitly
("`created`/`derived` → version 1") — this is not a new design decision, it is completing
an existing one that was only ever half-implemented (the event-type branch existed in
intent, per the doc, but not in code).

**Why not instead allow `derived` events to carry `new_state`:** that would require
modifying `canonical_event.py`'s frozen `_STATE_CHANGING_EVENT_TYPES` and validation —
a change to H.2, not H.3, and a larger, less localized change than fixing the one
read site in `memory_versioning.py` that was wrong. Keep the fix in H.3's own file, per
the same "smallest coherent architectural change" discipline every H.4-* mission in this
series has followed.

## 3. Interaction with H.3-R — together, these two fixes should fully repair the path

H.3-R alone (fix #1: which events count) still leaves the target-side case broken (this
mission's bug). This mission alone (fix #2: what state a `derived` event implies), without
H.3-R, would still crash on source-touched parents receiving a spurious entry with a now-
"fixed" but still wrongly-attributed `LIFECYCLE_CREATED` state. **Both fixes are required
together** for `reconstruct_version_history()` to correctly handle every derived memory,
in every position (source-only, target-only, or both). Verify this explicitly (§5 item 3):
after this mission, a genuine derivation chain (A → B → C, i.e. B is both a target of A's
derivation and a source of C's) should reconstruct correctly for **all three** memories,
including B.

## 4. Relationship to frozen/existing files

- `canonical.py`, `ledger.py`, `canonical_write.py`, `canonical_event.py`, `event_ledger.py`
  — untouched. This fix is entirely internal to `memory_versioning.py`'s own function body
  (plus, if needed, one import line).
- `memory_versioning.py` — the one function, the one additional conditional. Do not touch
  any other function in this file.

## 5. Regression-safety requirements

1. **Full existing `test_h3_versioning.py` suite (52 original + 5 from H.3-R) must still
   pass unchanged.**
2. **New tests** proving: a derived memory's `reconstruct_version_history()` now succeeds
   (previously always raised `MemoryVersioningError` for the target-side entry, even after
   H.3-R alone); its version 1 has `lifecycle_state == LIFECYCLE_CREATED`; a subsequent
   `superseded`/`retired` event for that same derived memory still transitions correctly
   from that base state (proving this fix composes correctly with the pre-existing
   supersession/retirement logic, not just in isolation).
3. **The three-memory chain case (§3)** — A created, B derived from A, C derived from B —
   must reconstruct correctly for all three, with B correctly reflecting both its own
   creation-via-derivation (version 1, `LIFECYCLE_CREATED`) and never picking up C's
   derivation event (H.3-R's fix, still in effect).
4. **Re-run `test_qualification_h4_d.py` and `test_taint_propagation.py` in full** — per
   H.3-R's own report, H.4-G's `_is_derivation_touched()` second clause was found to be
   dead code for its actual call pattern; after this mission, genuinely check whether real
   taint descendants now resolve to an actual `lifecycle_state` instead of
   `LIFECYCLE_STATUS_UNKNOWN_VERSIONING_GAP` — this is the direct, user-visible payoff of
   completing this two-part fix, so confirm and report it concretely (with an example),
   not just "tests still pass."
5. **Full repository regression suite**, before/after counts.

## 6. Explicit non-scope for this stage

- Updating H.4-D's `_derivation_touched_ids()` or H.4-G's `_is_derivation_touched()` to
  stop being conservative now that the underlying bug is fully fixed — this remains a
  legitimate, recommended follow-up (now more clearly worth doing than when H.3-R deferred
  it, since after this mission the skip logic is likely no longer needed *at all* for any
  case, not just partially) — but still keep this mission scoped to the ledger-level fix.
  State explicitly in the report whether this follow-up now looks safe to do and worth
  prioritizing.
- Any other change to `memory_versioning.py` beyond the one conditional in
  `reconstruct_version_history()`.

## 7. Deliverables checklist

- [ ] The one added conditional in `reconstruct_version_history()` (§2), and the import of
      `LIFECYCLE_CREATED` if not already present.
- [ ] New tests in `test_h3_versioning.py` (§5 items 2-3).
- [ ] `test_qualification_h4_d.py` and `test_taint_propagation.py` re-run, with a concrete
      example of a previously-`UNKNOWN_VERSIONING_GAP` id now resolving to a real
      lifecycle state (§5 item 4).
- [ ] Full repository regression suite re-run, before/after counts.
- [ ] `PHASE3_3_H3_R2_IMPLEMENTATION_REPORT.md`: root cause, the fix, full regression
      evidence, the concrete before/after taint-resolution example, and an updated
      recommendation on the H.4-D/G skip-logic cleanup follow-up.
- [ ] No modification to any file other than `memory_versioning.py`.

## 8. Definition of done

Complete when: the one-conditional fix is in place; every existing H.3/H.3-R test passes
unchanged; new tests prove a derived memory's version history reconstructs correctly end
to end, including in a multi-hop chain; H.4-D and H.4-G both re-verified with a concrete
example showing real lifecycle-status resolution where `UNKNOWN_VERSIONING_GAP` previously
appeared; full regression suite shows zero unexpected regressions. Together with H.3-R,
this closes the versioning gap that has stood, undiscovered, since H.3 was first
implemented — the last open correctness item before re-evaluating the readiness rubric in
[MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md §11](MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md).
