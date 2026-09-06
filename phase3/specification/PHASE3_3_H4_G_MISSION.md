# Phase 3.3-H.4-G — `tainted_by` Attack-Propagation Query — Mission Brief

Status: **NOT STARTED**. Mission brief for an implementation pass, in the same role as
[PHASE3_3_H4_BC_MISSION.md](PHASE3_3_H4_BC_MISSION.md),
[PHASE3_3_H4_F_MISSION.md](PHASE3_3_H4_F_MISSION.md),
[PHASE3_3_H4_D_MISSION.md](PHASE3_3_H4_D_MISSION.md), and
[PHASE3_3_H4_E_MISSION.md](PHASE3_3_H4_E_MISSION.md) played for the completed H.4-BC/F/D/E
stages. Covers **Initiative G only**, per
[MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md §7](MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md).
On completion, produce `PHASE3_3_H4_G_IMPLEMENTATION_REPORT.md` under
`phase3/experiments/`.

## 1. Problem

Phase 4 will need to ask, given a confirmed-successful attack memory (or set of them),
"which currently-active memories are reachable from it via `derived_from`" — a
lineage-reachability query, distinct from (and never to be confused with) Initiative A's
`counterfactually_influential` finding. Per the revised plan, `tainted_by` is explicitly
**not** a new stored edge or schema field — it is a read-only traversal query over data
that already exists (`parent_ids`/`derived_from`), and **only `derived_from` propagates
taint** — `equivalent_to`/`conflicts_with` do not, since they are symmetric
relevance/contradiction facts, not provenance facts.

## 2. Corrected understanding from repo inspection — this is smaller than it looks

Before writing this brief, `phase3/evaluation/metrics/provenance.py` was inspected. It
already provides `descendants(memories: Mapping[str, Mapping[str, object]], memory_id: str,
include_self: bool = False) -> MetricResult`, which:

- Transitively follows `parent_ids` edges **downward** (i.e., exactly `derived_from`'s own
  direction, per `relationship_schema.md §2`'s `A → C` convention) from a given
  `memory_id`.
- Is already cycle-safe (`cycle_detected` reported in `detail`, traversal does not loop).
- Already returns the full descendant set as a sorted list in `detail["descendants"]`.
- Is already tested (`test_provenance_lineage.py`) against the `fixtures/lineage/*.json`
  fixtures, including branching, multi-parent, and cycle cases.

**This function already does exactly the traversal Initiative G needs, with exactly the
right edge-type scoping (only `parent_ids`, never `equivalent_to`/`conflicts_with`) by
construction — because it was never built to look at those relationship types in the first
place.** This mission's actual scope is therefore narrow: (a) build a live snapshot of
`{memory_id: {"parent_ids": [...]}}` from the canonical ledger (not a static fixture) for
`descendants()` to run against, (b) run it once per confirmed-attack `memory_id` and union
the results, (c) cross-reference current lifecycle state (H.3) to answer "currently
active," and (d) wrap the result in one clean, documented function — never reimplementing
graph traversal that already exists and is already tested.

## 3. Relationship to frozen/existing files (must remain untouched)

- `canonical.py`, `ledger.py` (H.1) — **call only** (`CanonicalMemoryLedger.list_records()`
  → `Tuple[CanonicalMemoryRecord, ...]`, each with `.memory_id`/`.parent_ids` fields
  confirmed present at lines 109/113 of `canonical.py`).
- `canonical_event.py`, `event_ledger.py` (H.2, extended by H.4-BC/F) — not needed for this
  query at all; `parent_ids` already lives directly on `CanonicalMemoryRecord` (H.1), so
  this mission does not need to replay `derived` events to reconstruct lineage — reading
  the ledger's own records directly is simpler and sufficient. Do not add an event-replay
  path here if the direct record read already answers the question.
- `memory_versioning.py` (H.3) — **call only** (`get_current_version()` to determine
  whether a tainted descendant's current `lifecycle_state` is still `ACTIVE`, `RETIRED`,
  etc.). **Known caveat, carried over from H.4-D — read before implementing:**
  `PHASE3_3_H4_D_IMPLEMENTATION_REPORT.md` documents that `memory_versioning
  .reconstruct_version_history()`/`get_current_version()` has a latent bug: a memory that
  is merely a PARENT of some `derived` memory incorrectly picks up that `derived` event
  into its own version history (via `events_for_memory()`'s "matches on any appearance in
  `memory_ids`" property) and `CanonicalMemoryVersion.__post_init__` then rejects it. Any
  tainted descendant this mission's query finds that is *also* a parent of some other
  derived memory (i.e., "derivation-touched" in H.4-D's own terminology) will hit this
  exact bug if `get_current_version()` is called on it. **Do not silently crash or silently
  skip this.** Reuse H.4-D's own documented pattern: identify derivation-touched ids first
  (`qualification_harness._derivation_touched_ids()`'s logic, or an equivalent local
  helper — call the existing one if it is public/reusable, replicate the narrow logic
  locally with a comment pointing at the H.4-D precedent if it is not, but do not silently
  duplicate a divergent implementation) and report their lifecycle status as
  `LIFECYCLE_STATUS_UNKNOWN_VERSIONING_GAP` rather than calling `get_current_version()` on
  them and letting it raise.
- `metrics/provenance.py` (Phase 3.2-D) — **call only** (`descendants()`, reused verbatim,
  per §2). Do not modify this function, add parameters to it, or fork a copy — if it turns
  out to need a live-ledger-shaped input adapter, write that adapter in the new module
  (§4), not inside `provenance.py`.
- `qualification_harness.py` (H.4-D) — reference only, for its `_derivation_touched_ids()`
  precedent (previous bullet). Do not import private (`_`-prefixed) names across modules if
  avoidable — if the logic isn't already exposed as a public function, replicate the
  narrow, specific check locally with an explicit comment citing H.4-D as prior art, rather
  than reaching into another module's internals.

## 4. Deliverable — the `tainted_by` query

New module (e.g. `phase3/evaluation/metrics/taint_propagation.py` or
`phase3/evaluation/foundations/taint_propagation.py` — implementer's choice of package,
document which and why):

```
tainted_memories(
    memory_ledger: CanonicalMemoryLedger,
    attack_memory_ids: Sequence[str],
) -> TaintReport
```

1. Validate every id in `attack_memory_ids` exists in `memory_ledger` (raise
   `UnknownCanonicalMemoryError`-equivalent, reusing H.1's own existing error type if
   accessible, rather than inventing a new one for the same fact, if `memory_ledger`
   exposes a way to check existence consistently with how other stages already do this).
2. Build the live snapshot: `{record.memory_id: {"parent_ids": list(record.parent_ids)}
   for record in memory_ledger.list_records()}` — a pure, read-only transformation, no
   mutation of anything.
3. For each id in `attack_memory_ids`, call `provenance.descendants(snapshot, id,
   include_self=False)` (excluding the attack memory itself — taint describes what is
   *reachable from* the attack, not the attack memory's own status) and collect
   `result.detail["descendants"]` and `result.detail["cycle_detected"]`.
4. Union all descendant sets into `tainted_memory_ids` (sorted tuple, deterministic
   output). Retain a per-attack-id breakdown (`Mapping[str, Tuple[str, ...]]`) as well, so
   a caller can distinguish "tainted by attack A" from "tainted by attack B" when multiple
   attack ids are passed — do not flatten this information away, since Phase 4's own
   attribution work (per
   [PHASE4_INTERFACE_REQUIREMENTS.md](PHASE4_INTERFACE_REQUIREMENTS.md)) will likely need
   to know which specific attack a given tainted memory traces back to, not just that it
   traces back to *some* attack in the set.
5. For each id in `tainted_memory_ids`, determine current lifecycle status:
   - If the id is derivation-touched (§3's caveat) — report
     `LIFECYCLE_STATUS_UNKNOWN_VERSIONING_GAP`, never call `get_current_version()` on it.
   - Otherwise, call `memory_versioning.get_current_version()` and report its
     `lifecycle_state`.
6. `TaintReport` (frozen dataclass): `attack_memory_ids`, `tainted_memory_ids` (union,
   sorted), `tainted_by_attack` (per-attack-id breakdown), `lifecycle_status` (mapping
   tainted id → status, including the versioning-gap marker where applicable),
   `any_cycle_detected` (OR across all traversals).

**No new persisted state.** This function reads the canonical ledger and computes an
answer; it does not write anything, does not append an event, and produces no new file —
consistent with the plan's own framing ("requires no schema mutation and no new persisted
state in Phase 3").

## 5. Explicit clarification this mission must preserve (already stated in the revised plan, restated here so the implementation carries it forward)

`tainted_by` is a lineage-reachability fact, not a counterfactual-influence or
causal-attribution fact. A memory appearing in `tainted_memory_ids` means it is
*reachable* from a confirmed attack via `derived_from` — it does **not** mean the memory
was ever selected, exposed, or counterfactually influential in any specific task's answer
(Initiative A). `TaintReport`'s docstring must state this explicitly, and any future
report or metric built on top of `tainted_memories()` must report it alongside, never as a
substitute for, `counterfactually_influential` findings.

## 6. Invariants to implement and test

1. `tainted_memories()` never mutates `memory_ledger` or any other ledger — read-only,
   provable by construction (no `put()`/`append()` call anywhere in this module).
2. `tainted_memory_ids` never includes any `attack_memory_ids` member itself (excluded by
   `include_self=False`, per §4 step 3) unless that id is also a genuine descendant of a
   *different* attack id in the same call (a legitimate case — document it, don't suppress
   it).
3. `tainted_memories()` only follows `parent_ids`/`derived_from` edges — never
   `equivalent_to`/`conflicts_with` (true by construction, since `descendants()` never
   reads those fields at all; add a test that a memory `equivalent_to` an attack memory,
   with no `derived_from` relationship to it, is NOT included in `tainted_memory_ids`, to
   prove this isn't accidentally true only because no such fixture was tried).
4. Deterministic: identical ledger state + identical `attack_memory_ids` (any order)
   produces identical `TaintReport` (sorted tuples, no dependency on dict iteration order).
5. A derivation-touched tainted id is never passed to `get_current_version()` — reported as
   `LIFECYCLE_STATUS_UNKNOWN_VERSIONING_GAP` instead (§3's caveat, tested directly against
   a constructed case that would otherwise trigger H.3's known bug).
6. `any_cycle_detected` is `True` whenever any underlying `descendants()` call reports a
   cycle — never silently dropped.

## 7. Adversarial cases to test

- Two attack memory ids whose descendant sets overlap (a memory derived from both) —
  `tainted_memory_ids` contains it once; `tainted_by_attack` correctly lists it under both
  attack ids.
- An attack memory id with no descendants at all — `tainted_memory_ids` is empty, not an
  error.
- An attack memory id not present in `memory_ledger` — raises clearly, does not silently
  return an empty/partial result.
- A cyclic `derived_from` graph containing the attack memory — `descendants()`'s own
  existing cycle-safety is relied upon; confirm `any_cycle_detected` surfaces correctly
  through this module's wrapping rather than being swallowed.
- A tainted descendant that is itself an attack-confirmed id passed in the same
  `attack_memory_ids` list (i.e., a chain of confirmed attacks) — must appear in both its
  own per-attack-id entry (as a taint source) and any other attack's descendant set that
  reaches it, without double-counting incorrectly in the union.

## 8. Explicit non-scope for this stage

- No change to `provenance.py`, `canonical.py`, `ledger.py`, or `memory_versioning.py`.
- No fix to the H.3/H.4-D-documented `reconstruct_version_history()` versioning gap — this
  mission works around it identically to H.4-D (§3), it does not repair it. If this
  mission's own testing surfaces a *third* instance of the same class of bug, document it
  the same honest way H.4-D did rather than attempting an undocumented fix to a frozen
  file.
- No Phase 4 attack implementation or actual "confirmed attack" determination — this
  mission only builds the query that Phase 4 will call once it has determined which
  memory ids are confirmed attacks by whatever mechanism Phase 4 itself defines.
- No integration into `campaign_formal_runner.py` or any live reporting pipeline — this is
  a standalone, callable query function; wiring it into a report generator is a follow-up
  step, not part of this mission (state explicitly in the report whether any such wiring
  was done).
- Initiative A — unrelated; do not conflate `tainted_by` with
  `counterfactually_influential` anywhere in the implementation or its tests (§5).

## 9. Deliverables checklist

- [ ] New module with `tainted_memories()`, `TaintReport`, and the lifecycle-status
      resolution logic (§4), including the derivation-touched-id workaround (§3).
- [ ] New test file covering §6/§7.
- [ ] Full existing regression suite re-run with zero regressions.
- [ ] `PHASE3_3_H4_G_IMPLEMENTATION_REPORT.md`, stating explicitly which module/package
      this was placed in and why, and confirming no modification to `provenance.py`,
      `canonical.py`, `ledger.py`, or `memory_versioning.py`.
- [ ] No modification to any file listed as frozen/existing-untouched in §3.

## 10. Definition of done

Complete when: `tainted_memories()` correctly reuses `provenance.descendants()` against a
live canonical-ledger snapshot, correctly unions multi-attack descendant sets while
preserving per-attack attribution, correctly reports lifecycle status while safely routing
around the known H.3/H.4-D versioning gap rather than triggering it, all invariants (§6)
and adversarial cases (§7) pass, and the regression suite shows zero regressions. This is
the last of the six initiatives (B, C, D, E, F, G) from
[MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md](MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md)
other than **Initiative A**, which remains the sole outstanding item — its own mission
brief should be written next, per that document's §10.
