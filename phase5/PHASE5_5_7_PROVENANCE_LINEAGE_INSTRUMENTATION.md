# Phase 5.7 — Provenance, Lineage & Memory Interaction Instrumentation

Status: PASS. Reopened once (2026-09-13, by explicit user instruction, after the
Post-Phase-5 freeze) to close the `REFERENCES` gap — see "Reopening" section near the
end of this document. Refrozen after that fix.
Depends on: `PHASE5_5_1_INSTRUMENTATION_CONTRACT.md` (OR-15), all prior stages (this
stage reads their output).

## What exists

- `provenance_graph.py::ProvenanceGraph` — real, tested, projects a graph purely from
  `CanonicalMemoryLedger`/`CanonicalEventLedger`/`SupersessionLedger`, grounding every
  edge in an `established_by_event_id`.
- `taint_propagation.py::tainted_memories()` — real, tested, lineage-reachability from
  confirmed-attack memory ids. Its own docstring is explicit: **lineage reachability, not
  counterfactual influence**.
- `canonical_event.py::EVENT_COUNTERFACTUALLY_INFLUENTIAL` — the one real,
  schema-validated influence claim in this framework, always tied to a specific masking
  intervention.

## The gap

None of the above ever sees a `Phase5Event` — `ProvenanceGraph` is frozen and reads only
`CanonicalEvent`-shaped ledgers. The master prompt's own worked example
(`Injection I1 → Memory M17 → Retrieved R4 → Selected S4 → Used by Decision D7 → Action
A3 → Generated Memory M31`) mixes `CanonicalEvent` facts with `Phase5Event` facts and
cannot be reconstructed from `ProvenanceGraph` alone.

## The minimal, scientifically sufficient change

New module: [wiring/lineage.py](wiring/lineage.py) — a closed relationship vocabulary
(`DERIVED_FROM`, `PRODUCED`, `SUPERSEDES`, `RETRIEVED_WITH`, `SELECTED_WITH`, `USED_BY`,
`INFLUENCED`, `PROPAGATED_TO`, `REFERENCES`) plus `MemoryInteractionEdge`, a frozen
dataclass requiring both a `relationship_type` **and** an `evidence_kind` — the
load-bearing field for the "temporal order is never influence" discipline:

| evidence_kind | Meaning | Used by |
|---|---|---|
| `OBSERVED_EVENT` | A directly recorded fact | `PRODUCED`, `DERIVED_FROM`, `SUPERSEDES` |
| `EXPOSURE_ONLY` | Memory was exposed to a decision — never upgraded to "used" | `USED_BY` |
| `COUNTERFACTUAL_EVIDENCE` | Backed by a real `counterfactually_influential` event | `INFLUENCED` (the *only* source) |
| `LINEAGE_REACHABILITY` | Backed by `tainted_memories()` — reachable, not proven influential | `PROPAGATED_TO` |

Seven derivation/query functions, each calling — never reimplementing — the real
underlying mechanism:

- `derive_produced_edges()` — from admitted `attack_injection` `Phase5Event`s.
- `derive_derived_from_edges()` — wraps `CanonicalEvent`'s own `derived` events verbatim.
- `derive_supersedes_edges()` — resolves `superseded` events to their `SupersessionRecord`
  via `SupersessionLedger.get_by_event_id()` (the only enumeration path available, since
  that frozen ledger has no `list_records()` method).
- `derive_exposed_to_decision_edges()` — from `agent_decision`'s `exposed_memory_ids`,
  always tagged `EXPOSURE_ONLY`.
- `derive_influenced_edges()` — the **only** function that can produce an `INFLUENCED`
  edge, and only from a real `counterfactually_influential` `CanonicalEvent`.
- `derive_propagated_to_edges()` — wraps `tainted_memories()` verbatim.
- `query_co_selected_memory_ids()` / `query_co_retrieved_memory_ids()` — group queries
  (not materialized pairwise edges — up to 190 pairs for a 20-candidate pool would mostly
  restate one "same pool" fact) for `SELECTED_WITH`/`RETRIEVED_WITH`.
- `derive_references_edges()` — added in the 2026-09-13 reopening (see "Reopening"
  section below); a real, structural content-citation signal, no longer disclosed as
  unimplemented.

## What was NOT done

- `ProvenanceGraph`, `taint_propagation.py`, and `SupersessionLedger` were not modified.
- No `INFLUENCED` edge is ever produced from temporal ordering, retrieval, selection, or
  exposure alone — verified directly by test (empty result before any counterfactual
  event exists, non-empty only after one is appended).
- `RETRIEVED_WITH` is not expanded into O(n²) pairwise edges by default.

## Evidence

- [phase5/wiring/lineage.py](wiring/lineage.py)
- [phase5/tests/test_lineage.py](../tests/test_lineage.py) — 12 tests: `PRODUCED` from a
  real live attack injection (and correctly empty for a rejected one), `DERIVED_FROM` and
  `SUPERSEDES` from real Stage 5.4 wiring, `USED_BY` from a real decision event (asserting
  `EXPOSURE_ONLY` on every edge), `INFLUENCED` proven empty before and non-empty only
  after a real `counterfactually_influential` event is appended, `PROPAGATED_TO` wrapping
  a real live-attack-origin derivation chain, the group queries against real Stage 5.5
  retrieval data, `MemoryInteractionEdge`'s own validation (unknown relationship type,
  unknown evidence kind, empty citation list all rejected), and a non-interference check
  confirming `tainted_memories()`'s own output size is preserved.
- Also added (empirically closing the "is real-vendor testing even possible" sub-question
  of the pre-5.8 gate): [phase5/tests/test_real_vendor_compatibility_gate.py](../tests/test_real_vendor_compatibility_gate.py)
  — confirms `RealMem0Adapter`/`RealAMemAdapter` both report `FOUNDATION_UNAVAILABLE` in
  this environment, replacing a docstring citation with a direct empirical result. See
  `PHASE5_CHECKLIST.md`'s updated pre-5.8 gate entry — **the gap remains open**, now with
  a confirmed reason and a concrete re-check for a future session with `h4venv` access.
- Full Phase 5 suite: `python -m pytest phase5/tests/ -q` → 123 passed.
- Frozen Phase 3/4 regression: recorded below once complete.

## Coverage check

OR-15 (derivable propagation graph) is satisfied for the cross-schema case. The master
prompt's Section 15 relationship vocabulary is now fully represented AND fully produced —
every one of the 9 relationship types (including `REFERENCES`, since the 2026-09-13
reopening) has a real `derive_*` function. The causality discipline (never confuse
temporal order with influence) is enforced structurally via the required `evidence_kind`
field, not left to convention.

## Things flagged after the initial pass (see "Review fixes" below for resolution)

- `derive_propagated_to_edges()`'s citation was a proxy (descendant's own `creation_event`), not a true grounding event.
- No pairwise `RETRIEVED_WITH`/`SELECTED_WITH` edges were produced, only group queries.
- The A-MEM/real-vendor pre-5.8 gate had no concrete, ready-to-run compatibility test.

---

## Review fixes

### Fix 1 — `PROPAGATED_TO` evidence grounding

**Problem**: `derive_propagated_to_edges()` cited the descendant memory's own
`creation_event` as a stand-in for "the event that established this taint" — real, but
not the event that actually established the propagation relationship.

**Fix**: added `tainted_memory_evidence()` — an additive companion to `tainted_memories()`
(called verbatim, unmodified, for the authoritative reachability computation and
`lifecycle_status`). It resolves each confirmed attack→descendant taint fact to a real
path of `derived` `CanonicalEvent`s by walking the same `parent_ids` data
`tainted_memories()`/`descendants()` themselves read (via a new, additive
`_find_parent_path()` BFS — never a second reachability algorithm, just a path
reconstruction over an already-confirmed pair), resolved to real event ids via
`derive_derived_from_edges()`'s own output. `derive_propagated_to_edges()` now cites this
genuine per-hop evidence; `event_ledger` changed from optional to required (grounding is
not possible without it — no fallback to the old proxy exists anymore). A descendant that
is reachable but has no fully-evidenced real event path (e.g. a `CanonicalMemoryRecord`
written with `parent_ids` set directly, bypassing `record_memory_derivation()`) produces
**no edge**, surfaced instead in `TaintLineageEvidenceReport.ungrounded_descendant_ids` —
never a fabricated event id.

Evidence (`test_lineage.py`, 8 new tests covering the review's required list 1–6 plus 2
more): tainted_memories() output proven byte-identical before/after the new helper exists;
every PROPAGATED_TO edge's citation verified to be a real `derived` event (not
creation_event); the evidence path/event chain verified to match the actual derivation
hops exactly; a temporally-later-but-unrelated memory proven to receive no edge; an
independent memory proven to receive no edge; `LIFECYCLE_STATUS_UNKNOWN_VERSIONING_GAP`
proven to still surface on `LineageEvidence.lifecycle_status`, unbypassed; and a
bypassed-derivation scenario proven to land in `ungrounded_descendant_ids` with zero
fabricated edges.

### Fixes 2 & 3 — pairwise `RETRIEVED_WITH`/`SELECTED_WITH` edges

**Fix**: added `derive_co_retrieved_edges()`/`derive_co_selected_edges()`, both built on
one shared, deterministic implementation (`_derive_co_membership_edges()`) — sorted by
`memory_id` (never ledger insertion order), deduplicated, scoped strictly to one
`task_id` per call (never expanded across a run), citing both real
`retrieval_candidate_scored` event ids per pair, always `evidence_kind=OBSERVED_EVENT`.
The existing group-query functions (`query_co_retrieved_memory_ids()`/
`query_co_selected_memory_ids()`) are unchanged and remain the right choice when only
membership, not edge objects, is needed.

Evidence (`test_lineage.py`, 6 new tests): full pairwise coverage (C(n,2)) for a
4-candidate pool, selected-only coverage for the smaller top-K set, strict non-crossing
between two different tasks — including the harder case of the *same* memory_id
retrieved in two different tasks, proving citations never mix across task boundaries —
determinism across repeated calls, real event-id citation, and an explicit check that no
pairwise edge ever claims `INFLUENCED` or `COUNTERFACTUAL_EVIDENCE`.

### Fix 4 — A-MEM/real-vendor gate: not faked, future test added

No fabrication, no assumption that vendor ids equal canonical ids, gate not marked
passed. Added two fully-written (not stub) compatibility tests
(`test_real_mem0_retrieval_identity_chain_when_available`,
`test_real_mem0_identity_continuity_across_update_when_available`) that self-skip with an
explicit "NOT VALIDATED — FOUNDATION_UNAVAILABLE" message in this environment, and are
immediately runnable, with no further design work, in a future session with access to the
real backend. See `PHASE5_CHECKLIST.md`'s updated pre-5.8 gate entry.

### Full verification after all four fixes

- `python -m pytest phase5/tests/ -q` → **136 passed, 2 skipped** (the 2 new
  future-compatibility tests, skipping correctly and honestly).
- Full integrated-chain test (`test_full_pipeline_chain.py`, extended): the real
  Stage 5.4→5.5→5.6 chain now also runs Stage 5.7 lineage derivation over the same real,
  reloaded ledgers — `PRODUCED` found for the real injected memory,
  `USED_BY`/`EXPOSURE_ONLY` found for its exposure to the real decision, zero
  `INFLUENCED` edges (no counterfactual event exists in this chain), and zero
  `PROPAGATED_TO` edges (nothing was derived from the poisoned memory in this chain) —
  passed on first run.
- Frozen Phase 3/4 regression: recorded below.

## Remaining limitations (honest, not resolved by this fix)

- The A-MEM/real-vendor identity-resolution question remains genuinely unverified in
  this environment — the gate is better-instrumented now, not closed.
- `tainted_memory_evidence()`'s path-finding returns one (shortest, deterministic) real
  path per descendant; if a memory has multiple real derivation paths to the same attack
  origin, only one is cited, not all of them.
- Pairwise edges are opt-in per `task_id` — a caller wanting them for an entire run must
  call the function once per task, by design (never an automatic O(n²) sweep).

---

## Reopening (2026-09-13) — `REFERENCES` gap closed

**Why reopened**: explicit user instruction, after the Post-Phase-5 hardening pass had
already assessed and deliberately left `REFERENCES` unimplemented
(`PHASE5_POST_FREEZE_HARDENING_REPORT.md` Sec 10). That assessment is NOT being reversed
without justification — it specifically rejected inferring that "the model actually
referenced [a memory] in its answer" from word overlap, semantic similarity, or citation
coincidence, an agent-BEHAVIOR claim requiring semantic judgment this framework has no
calibrated way to make. **That rejection stands, unchanged.**

**What was actually found and fixed**: a narrower, purely STRUCTURAL question was not
previously considered on its own terms — whether one real memory's own persisted CONTENT
literally contains another real memory's exact `[memory_id]` citation-bracket substring
(the identical literal format `agent_runtime/messages.py::render_messages()` uses,
reused here only as a textual pattern, never as a claim about model behavior). This is an
exact, deterministic substring match against real, known memory_ids — not a heuristic —
so it does not reintroduce the case Sec 10 rejected, and is exactly as strong an
evidentiary claim as `DERIVED_FROM` (a structural content/graph fact, `OBSERVED_EVENT`),
never an influence or usage claim.

**Fix**: added `derive_references_edges()` to [wiring/lineage.py](wiring/lineage.py).
Grounded in the citing memory's real creation-type (`created`/`derived`) `CanonicalEvent`
— resolved via `CanonicalEventLedger.events_for_memory()`, never the memory record's own
bare `creation_event` string field (already known, from this same stage's Fix 1, to
sometimes be only a descriptive marker rather than a real, citable event_id).
`CanonicalEventLedger`'s own single-occurrence invariant for creation-type events
guarantees this citation is always unambiguous when it exists; a citing memory whose
creation-type event cannot be found produces no edge, never a fabricated one.

**What was NOT touched**: no frozen Phase 3 file, no other Stage 5.7 function, no
existing test. `build_propagation_graph()` (Stage 5.8) is NOT updated to compose this new
edge type in this reopening — that is a separate stage, out of scope for this specific,
narrowly-authorized reopening of 5.7 only, and is flagged here explicitly as a follow-up
rather than silently left inconsistent: **a future, separately-authorized change to
Stage 5.8 would be needed before `PropagationGraph` includes `REFERENCES` edges.**

**Evidence**: 6 new tests in `test_lineage.py` — real content-citation detected and
correctly grounded to the real `derived` event (not the bare `creation_event` field); no
edge without a literal `[memory_id]` bracket citation; no edge from mere word-overlap/
mention-coincidence (the exact heuristic Sec 10 rejected, verified NOT to fire); no
self-reference edge; no `INFLUENCED`/`COUNTERFACTUAL_EVIDENCE` ever produced by this
function; deterministic across repeated calls. Full Phase 5 suite:
`python -m pytest phase5/tests -q` → **194 passed, 2 skipped** (188 prior + 6 new, 0
regressions). Full frozen Phase 3/4 regression re-run fresh after this change — see
`PHASE5_CHECKLIST.md`.

**STAGE 5.7 STATUS (after reopening): PASS. Refrozen.**

---

**STAGE 5.7 STATUS: PASS WITH REQUIRED FIX — fixes applied and verified above. See final
verdict in the response accompanying this document for the complete, itemized report.**
