# Phase 3.3-H.3-R — Versioning Fix for Multi-Memory `derived` Events — Mission Brief

Status: **NOT STARTED**. Mission brief for an implementation pass. On completion, produce
`PHASE3_3_H3_R_IMPLEMENTATION_REPORT.md` under `phase3/experiments/`.

**This mission is different in kind from every H.4-* mission that preceded it.** B, C, D,
E, F, G, and A were all purely additive — new modules, new event types, new optional
fields — specifically because H.1/H.2/H.3 were treated as frozen and untouchable. This
mission is the first that **corrects a genuine defect inside a frozen file**
(`memory_versioning.py`, H.3). That is only being done now because:

1. The defect was independently discovered and worked around, without modification, in
   **two separate stages** (H.4-D's `_derivation_touched_ids()`,
   `PHASE3_3_H4_D_IMPLEMENTATION_REPORT.md`; H.4-G's `_is_derivation_touched()`,
   `PHASE3_3_H4_G_IMPLEMENTATION_REPORT.md`) — it is a confirmed, reproducible bug, not a
   one-off misunderstanding.
2. H.4-G's own investigation found the defect is **load-bearing for the exact use case
   H.4-G exists to serve**: in any realistic multi-hop derivation chain, an intermediate
   tainted memory is *both* a target of one derivation and a source of the next, so it is
   "derivation-touched" by construction — meaning `lifecycle_status` is unreliable for
   precisely the memories a Phase 4 taint-propagation analysis most needs it for.
3. This codebase has an established, explicit precedent for correcting a frozen stage
   without silently patching it: **H.2-R and H.2-R2**, both of which modified originally-
   frozen H.2 behavior, under their own reviewed, named remediation stage, with full
   before/after regression proof. This mission follows that exact precedent, applied to
   H.3.

**Do not treat this brief as license to make other changes to `memory_versioning.py`,
`event_ledger.py`, or any other file beyond the single, narrow defect described below.**

## 1. Root cause — established by direct code reading, not inference

`event_ledger.py::CanonicalEventLedger.events_for_memory(memory_id)` (line 337-341):

```python
def events_for_memory(self, memory_id: str) -> Tuple[CanonicalEvent, ...]:
    matching = (eid for eid, ev in self._events_by_id.items() if memory_id in ev.memory_ids)
    return self._ordered(matching)
```

This is a correct, general-purpose "every event that mentions `memory_id` anywhere"
query — and it is exactly what `relationship_schema.md`/`TRACEABILITY_CONTRACT.md` want
for general observability (a full audit trail legitimately includes "this memory was
cited as a source of derivation X," even for the source, not just the target).

`memory_versioning.py::reconstruct_version_history()` (line 304-351) calls this same
general-purpose query and filters by `event_type in _LIFECYCLE_EVENT_TYPES` (line 326),
where `_LIFECYCLE_EVENT_TYPES = (EVENT_CREATED, EVENT_DERIVED, EVENT_SUPERSEDED,
EVENT_RETIRED)` (line 140). **`EVENT_DERIVED` is the one event type in this list that is
not single-memory-scoped**: per `canonical_event.py`'s own validated invariant, a
`derived` event's `memory_ids` always equals `set(source_memory_ids) | {target_memory_id}`
— i.e., it legitimately names every parent *and* the one child.

Consequence: for a memory `P` that is a **source/parent** of some `derived` event (never
itself that event's `target_memory_id`), `events_for_memory(P)` still returns that event
(since `P ∈ event.memory_ids`), `reconstruct_version_history(P)` still includes it in
`lifecycle_events` (since `EVENT_DERIVED ∈ _LIFECYCLE_EVENT_TYPES`), and then constructs
`CanonicalMemoryVersion(lifecycle_state=event.new_state, ...)`. Per `canonical_event.py`'s
own validation, `new_state` is **required to be `None`** for a `derived` event (only
`created`/`superseded`/`retired` are state-changing — `canonical_event.py`'s
`_STATE_CHANGING_EVENT_TYPES` deliberately excludes `derived`). `CanonicalMemoryVersion
.__post_init__` (memory_versioning.py line 293-295) then raises `MemoryVersioningError`,
since `None not in LIFECYCLE_STATES`.

**Every memory that is a parent of any derivation, and is not itself first created via its
own `created`/`derived` event before this happens, hits this.** In practice — since a
parent's own `created` event is a separate, earlier event, not this one — the crash occurs
specifically because the PARENT's OWN legitimate lifecycle history gets one extra,
spurious `derived` entry appended (belonging to the CHILD's creation, not the parent's own
transition), and that spurious entry is what `CanonicalMemoryVersion` correctly rejects
(it has no valid `lifecycle_state`, because it was never supposed to describe the parent's
own state to begin with).

## 2. The fix — narrow, localized, single condition

In `memory_versioning.py::reconstruct_version_history()`, line 325-327, change:

```python
lifecycle_events: List[CanonicalEvent] = [
    e for e in event_ledger.events_for_memory(memory_id) if e.event_type in _LIFECYCLE_EVENT_TYPES
]
```

to additionally require, for `derived` events specifically, that `memory_id` is the
event's own `target_memory_id` (i.e., this memory is the one actually created by this
derivation), not merely a source:

```python
lifecycle_events: List[CanonicalEvent] = [
    e for e in event_ledger.events_for_memory(memory_id)
    if e.event_type in _LIFECYCLE_EVENT_TYPES
    and (e.event_type != EVENT_DERIVED or e.target_memory_id == memory_id)
]
```

**Why this is the correct, minimal fix, not a workaround:**

- `created`, `superseded`, `retired` are already single-memory events
  (`canonical_event.py`'s `_SINGLE_MEMORY_EVENT_TYPES` includes all three) — this
  condition changes nothing for them.
- `derived` is the *only* multi-memory lifecycle event type — this is the only place the
  ambiguity between "mentioned" and "is this memory's own transition" can arise.
- This fix does not touch `event_ledger.py`/`canonical_event.py` at all —
  `events_for_memory()`'s own general-purpose, correct-for-its-actual-job semantics are
  untouched, so every other caller of `events_for_memory()`/`events_for_task()`/
  `events_for_foundation()` (traceability/observability use cases that legitimately want
  the broader "mentioned anywhere" view) is unaffected.
- It does not touch `CanonicalMemoryVersion`'s own validation (memory_versioning.py
  line 293-295) — that validation was correct; it was correctly rejecting a malformed
  input it should never have been given in the first place.

**Do not implement this fix any other way** (e.g. by relaxing
`CanonicalMemoryVersion.__post_init__` to tolerate `lifecycle_state=None`, or by changing
`events_for_memory()`'s own general semantics) — both alternatives would either weaken a
correct invariant or break a different, legitimate caller. The one-condition fix at the
`reconstruct_version_history()` call site is the only change with no other side effects.

## 3. What this means for `get_current_version()`/`get_version()`

Both are pure derivations of `reconstruct_version_history()`'s own output (lines 354-386)
— no separate fix needed; both are correct automatically once the source function no
longer produces a spurious entry.

## 4. Regression-safety requirements — this is the load-bearing part of this mission

Because this changes the observable behavior of a function every one of H.4-D/E/F/G/A
already depends on (directly or by working around its known failure mode), this mission
must prove, not merely assert, that nothing regresses:

1. **Full existing `test_h3_versioning.py` suite must still pass unchanged.** Per
   `PHASE3_3_H4_D_IMPLEMENTATION_REPORT.md`'s own finding, "H.3's own test suite never
   exercises this [bug] — it only ever seeds via `created`," so this fix should not need
   to change any existing H.3 test's expected outcome. If it does turn out to change any
   existing test's expectation, STOP and treat that as a signal the fix's scope needs
   re-examination before proceeding, rather than adjusting the test to match.
2. **New tests proving the fix**, added to `test_h3_versioning.py` (extending the frozen-
   but-now-correctly-remediated suite, following H.2-R/H.2-R2's own precedent of adding
   tests to a remediated stage's own test file rather than only testing from a downstream
   caller): a memory that is purely a source/parent of a `derived` event (never a target)
   must have `reconstruct_version_history()` succeed and reflect only its own genuine
   `created`/`superseded`/`retired` history, with no spurious entry from the derivation it
   contributed to.
3. **H.4-D's qualification harness must still produce identical results** on every
   existing fixture — re-run `test_qualification_h4_d.py` in full. Its own
   `_derivation_touched_ids()` workaround should remain harmless (it now skips checking
   ids that would have worked fine anyway) — confirm this by re-running, do not assume it.
4. **H.4-G's taint-propagation module must still produce identical `tainted_memory_ids`
   sets** (the fix does not change reachability, only lifecycle-status resolution) — but
   `lifecycle_status` values for genuinely-target-only tainted memories (leaf descendants,
   never themselves a further parent) should now resolve to a real `lifecycle_state`
   instead of being needlessly caught by H.4-G's own `_is_derivation_touched()` predicate,
   **if** that predicate is broad enough to include target-only ids too. Check this
   directly: H.4-G's predicate may already be scoped correctly (parent-only) or may be
   over-broad (any appearance, source or target) — read `_is_derivation_touched()`'s
   actual implementation before assuming either way, and report which it is.
5. **Full repository regression suite** re-run with before/after counts, matching every
   prior stage's own reporting convention.

## 5. Explicit non-scope for this stage

- **Do not** update H.4-D's `_derivation_touched_ids()` or H.4-G's
  `_is_derivation_touched()` to narrow their own now-partially-unnecessary skip logic
  (e.g. to stop skipping target-only ids that would now resolve correctly). This is a
  legitimate, valuable follow-up cleanup — flag it explicitly as a recommended next step in
  the implementation report — but keep this mission scoped to the H.3 ledger-level fix
  itself. Their current behavior (skip everyone derivation-touched) remains **correct,
  just more conservative than strictly necessary** after this fix lands; conservatism is
  not a bug.
- **Do not** attempt to fix any other latent gap that might exist elsewhere in
  `memory_versioning.py` or `event_ledger.py` beyond this one, specifically-identified
  defect. If implementation surfaces a *different* bug, document it the same honest way
  H.4-D/G did (name it, work around it if needed for this mission's own tests, do not
  silently fix it as a bonus) rather than expanding this mission's scope.
- **Do not** change `_LIFECYCLE_EVENT_TYPES`/`_CREATION_EVENT_TYPES` themselves, or any
  other constant.
- **Do not** touch `canonical.py`, `ledger.py`, `canonical_write.py` (H.1) — unrelated.

## 6. Deliverables checklist

- [ ] The one-condition fix in `memory_versioning.py::reconstruct_version_history()`
      (§2), and nowhere else.
- [ ] New tests in `test_h3_versioning.py` proving the fix (§4 item 2).
- [ ] Full `test_h3_versioning.py`, `test_qualification_h4_d.py`, and
      `test_taint_propagation.py` suites re-run and confirmed passing (§4 items 1, 3, 4).
- [ ] Full repository regression suite re-run, before/after counts reported.
- [ ] `PHASE3_3_H3_R_IMPLEMENTATION_REPORT.md`: root cause (§1), the exact fix (§2),
      full regression evidence (§4), and an explicit recommendation on whether/when to do
      the H.4-D/G skip-logic cleanup (§5) as a separate, future, optional stage.
- [ ] No modification to `canonical.py`, `ledger.py`, `canonical_write.py`,
      `canonical_event.py`, or `event_ledger.py` — only `memory_versioning.py`, and only
      the one identified condition.

## 7. Definition of done

Complete when: the one-line condition fix is in place; every existing H.3 test still
passes unchanged; new tests prove a pure-source memory's version history no longer
crashes and correctly reflects only its own transitions; H.4-D and H.4-G's own test suites
still pass with identical substantive results (reachability/qualification outcomes
unchanged, lifecycle-status resolution improved where the fix applies); the full
regression suite shows the expected new-test-count increase with zero unexpected
regressions; the report honestly states the H.4-D/G skip-logic follow-up recommendation
without performing it. This closes the last open item flagged after H.4-G, ahead of
re-evaluating the readiness rubric in
[MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md §11](MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md).
