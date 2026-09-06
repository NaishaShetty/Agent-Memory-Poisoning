# Phase 3.3-H.3-R2 — Versioning Fix for `derived` Events' Implied Lifecycle State — Implementation Report

Status: **COMPLETE**. Second of two remediation stages against H.3's
`memory_versioning.py` (first: H.3-R,
`PHASE3_3_H3_R_IMPLEMENTATION_REPORT.md`). Follows
[PHASE3_3_H3_R2_MISSION.md](../specification/PHASE3_3_H3_R2_MISSION.md).

## 1. Root cause (confirmed exactly as the mission brief predicted)

`canonical_event.py`'s `_STATE_CHANGING_EVENT_TYPES = (EVENT_CREATED, EVENT_SUPERSEDED,
EVENT_RETIRED)` deliberately excludes `EVENT_DERIVED` — `CanonicalEvent.__post_init__`
forbids `new_state` from being anything but `None` for any event type outside that list.
`memory_versioning.py::reconstruct_version_history()` built every lifecycle event's
resulting `CanonicalMemoryVersion` with `lifecycle_state=event.new_state` unconditionally,
so a `derived` event — even the exact target-side one H.3-R's own fix correctly identifies
as belonging to a memory's own history — always produced `lifecycle_state=None`, which
`CanonicalMemoryVersion.__post_init__` correctly rejects (`None not in LIFECYCLE_STATES`).

Confirmed directly: `test_h3_r_target_memorys_own_derived_creation_is_a_documented_
separate_gap` (added by H.3-R specifically to document this as a known, deferred gap)
asserted `pytest.raises(Exception)` for exactly this case. Running the full H.3 suite
*before* this fix reproduced that `raises` as passing; after this fix, the same
construction succeeds, so that test was rewritten (§3) to assert success instead of
documenting a gap that no longer exists.

## 2. The fix

One conditional added to `reconstruct_version_history()`'s per-event loop
(`memory_versioning.py`), plus one new import (`LIFECYCLE_CREATED` from `canonical.py`,
alongside the already-imported `LIFECYCLE_RETIRED`/`LIFECYCLE_STATES`):

```python
if event.event_type == EVENT_DERIVED:
    version_lifecycle_state = LIFECYCLE_CREATED
else:
    version_lifecycle_state = event.new_state
```

`LIFECYCLE_CREATED` was chosen because every `created` event in this codebase's existing
usage (test fixtures, no exception found) sets `new_state=LIFECYCLE_CREATED`, never
`LIFECYCLE_ACTIVE` directly — a derived memory's own creation is semantically identical to
a foundation memory's initial state for version-1 purposes; the "how it came to exist"
distinction is already fully captured elsewhere (`memory_type`, `parent_ids`, `source`),
never by `lifecycle_state`. This mirrors the existing code's own precedent of inferring a
version field from something other than a raw event field (the adjacent `EVENT_SUPERSEDED`
branch already looks `current_superseded_by` up from `SupersessionLedger` rather than
reading it off the event).

No other line of `memory_versioning.py` was changed. No other file was touched.

## 3. Tests

`test_h3_versioning.py`:

- Rewrote `test_h3_r_target_memorys_own_derived_creation_is_a_documented_separate_gap`
  (previously asserted a raise) into
  `test_h3_r2_target_memorys_own_derived_creation_reconstructs_as_created` — asserts
  version 1 succeeds, `lifecycle_state == LIFECYCLE_CREATED`, `version_number == 1`,
  `superseded_by is None`, and `get_current_version()` agrees.
- Added `test_h3_r2_derived_memory_supersession_composes_correctly` — a derived memory
  (C, from A) is later superseded by a foundation memory (D); asserts the full
  `[CREATED, RETIRED, RETIRED]` history and correct `superseded_by` linkage, proving the
  H.3-R2 base state composes correctly with the pre-existing, unmodified
  supersession/retirement machinery, not just in isolation.
- Added `test_h3_r2_three_memory_derivation_chain_reconstructs_for_all_three` — A created,
  B derived from A, C derived from B (B is both a target and a source). Asserts all three
  memories' histories reconstruct correctly, each exactly one version,
  `lifecycle_state == LIFECYCLE_CREATED`, proving H.3-R (which events count) and H.3-R2
  (what state a `derived` event implies) compose correctly together, not just individually.

`test_h3_versioning.py`: **59 passed** (56 pre-existing + 3 new), 0 failed.

## 4. Downstream re-verification

`test_qualification_h4_d.py` + `test_taint_propagation.py`: **93 passed** (74 + 19), 0
failed, 0 changed — reachability/qualification outcomes are unaffected by this fix, exactly
as expected (this fix changes lifecycle-status *resolution*, not reachability).

**Concrete before/after example**, constructed directly (attack memory `ATTACK`, one
derived descendant `LEAF`, never itself a further parent):

```
tainted_memory_ids: ('LEAF',)
lifecycle_status (via taint_propagation's own, unmodified skip logic): {'LEAF': 'UNKNOWN_VERSIONING_GAP'}
DIRECT get_current_version(LEAF) after H.3-R2 fix -> CREATED
```

This proves the underlying gap `taint_propagation.py`'s `_is_derivation_touched()` was
built to protect against is now fully closed: a direct call to `get_current_version()` on
a genuine taint descendant succeeds and returns the correct state. `taint_propagation.py`
itself was **not modified** (out of scope, per the mission) — it still conservatively
reports `UNKNOWN_VERSIONING_GAP` via its own unchanged skip predicate, which is now
provably more conservative than necessary rather than incorrect.

## 5. Full repository regression

Before this stage: 1572 passed, 17 skipped, 1 pre-existing unrelated failure
(`test_candidate_memoryarena.py::test_raw_fingerprint_file_count_matches_actual_raw_
directory`, investigated separately this session — caused by commit `67c042b`
materializing a gitlink after the fingerprint manifest was frozen; not touched by this
stage).

After this stage: **1574 passed**, 17 skipped, same 1 pre-existing unrelated failure
(net +2: one existing test was rewritten in place — same name-slot, new assertions, not an
addition — and two genuinely new tests were added; full command:
`python -m pytest phase3/evaluation/tests/ -q`, 280.04s).

Separately, under `C:\h4venv` (this session's own real-library environment work, unrelated
to this fix): re-cloned `A-mem-sys` at its pinned commit to a stable path (the adapter's
previous hardcoded path pointed at a since-deleted, ephemeral prior-session scratchpad
directory) and confirmed 74/74 previously-real-library-dependent tests now pass with 0
skips under that interpreter, resolving 14 of the original 17 skips. The remaining 3
(`test_llm_provider.py`, requiring a running local `llama-server`) remain unaddressed —
separate, larger infrastructure, not part of this stage.

## 6. Recommendation on the H.4-D/G skip-logic cleanup (still not performed, per explicit scope)

§4's concrete example confirms the recommendation from H.3-R's own report: with both
H.3-R and H.3-R2 in place, `_derivation_touched_ids()` (H.4-D) and
`_is_derivation_touched()` (H.4-G) are very likely no longer necessary *at all* for any
case — their first clause ("is this memory itself `derived`-shaped") now always resolves
correctly via `get_current_version()`, and their second clause was already found to be
dead code by H.3-R. This is now a low-risk, well-understood cleanup: removing the skip and
calling `get_current_version()`/`reconstruct_version_history()` directly should work for
every case current tests exercise. Recommended as a near-term follow-up, still
deliberately not performed here, to keep this stage's own regression evidence unambiguous
(a "this fix enables X" claim is stronger when X is verified by direct construction, as in
§4, than by simultaneously refactoring the caller that was relying on the workaround).

## 7. Compatibility

`canonical.py`, `ledger.py`, `canonical_write.py`, `canonical_event.py`, `event_ledger.py`
— untouched (confirmed: only `memory_versioning.py` and `test_h3_versioning.py` appear in
this stage's changes). Every H.1/H.2/H.3/H.3-R API remains valid; only the internal
`lifecycle_state` inference for one branch of one function's loop changed.

## 8. Freeze status

This mission is complete. Together with H.3-R, the versioning gap that has existed,
undiscovered, since H.3 was first implemented is now closed. This was the last open
correctness item flagged after H.4-G — next step per the user's own sequencing is
re-evaluating the readiness rubric in
[MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md §11](../specification/MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md).
