# Phase 5.8 — Trace Assembly & Propagation Graph

Status: PASS. Reconciled once (2026-09-13, final Phase 5.8–5.9 reconciliation pass) to
compose Stage 5.7's `REFERENCES` edges — see "Reconciliation" section near the end of
this document. Refrozen after that reconciliation.
Depends on: all prior stages (this stage composes their output; it introduces no new
event type or raw fact).

## What exists

Every prior stage (5.2–5.7) either added a persisted event family or a derivation
function over already-persisted events, but nothing assembled them into the single
structured trace the master prompt's own architecture diagram describes, or composed
Stage 5.7's lineage functions into one graph.

## Why this stage is possible at all: Stage 5.3's membership ledger

`EventRunMembershipLedger.events_for_run(run_id)` is the one mechanism that makes
"assemble everything that happened in run X" a well-defined query instead of a guess:
every event this framework's Phase 5 wiring appends — whichever of the two schemas
(`CanonicalEvent` or `Phase5Event`) minted it — is registered there.

## The minimal, scientifically sufficient change

New module: [wiring/trace_assembly.py](wiring/trace_assembly.py).

1. **`assemble_trace(run_id, ...)` → `ExperimentTrace`** — asks the membership ledger for
   the run's event ids, resolves each to its real event object via
   `EventRunMembership.event_schema`, and buckets the results into the master prompt's
   own sections: Injection, Memory Lifecycle (created/derived/superseded/retired/
   retrieved/selected/rejected/used, plus retrieval-candidate scores), Agent Events
   (context assembly/decision/action), Memory Evolution (relationship_detected), and
   Outcome (ground-truth transitions, counterfactual findings). An event id registered to
   the run but unresolvable in either ledger is reported in `unresolved_event_ids`, never
   silently dropped.
2. **`build_propagation_graph(run_id, ...)` → `PropagationGraph`** — calls every
   applicable Stage 5.7 `derive_*` function exactly as Stage 5.7 defines it (never
   reimplementing any of them), then filters every resulting edge to ones whose
   `established_by_event_ids` are **all** registered to `run_id` via the membership
   ledger. This scoping step is the one genuinely new piece of logic in this stage —
   Stage 5.7's functions each scan their whole ledger, correct for their own purpose but
   wrong for "this experiment's graph" if a ledger ever holds more than one run.
   `PROPAGATED_TO`'s attack-memory-id input is derived from the run's own `PRODUCED`
   edges, never a caller-supplied, potentially stale/cross-run list. `RETRIEVED_WITH`/
   `SELECTED_WITH` are derived per distinct `task_id` found in the run's own
   `retrieval_candidate_scored` events.

Both functions are read-only and recompute their output fresh every call — the same
"projection, never a second store" discipline `ProvenanceGraph` itself established,
extended to the cross-schema, whole-trace case. This directly satisfies the master
prompt's own requirement: "the graph must be derived from persisted evidence, not
manually constructed after observing an outcome."

## A real finding surfaced while testing this stage

Two of the "different runs" test scenarios initially reused the same FARMA fixture
(`SEED_CAMPING`) twice against a shared `CanonicalMemoryLedger`. This failed —
correctly — because `SEED_CAMPING`'s `artifact_id` (hence its canonical `memory_id`) is
fixed, and `CanonicalMemoryLedger.put()`'s own collision policy refuses two different
records under the same `memory_id`. This is the ledger working exactly as designed, not
a bug: it confirms that two genuinely independent runs sharing one memory ledger and
reusing the identical fixture is not a realistic scenario this framework's own identity
discipline permits — the tests were corrected to use genuinely distinct injections per
run, matching how two real, independent experiment runs would actually differ.

## What was NOT done

- `ProvenanceGraph`, `taint_propagation.py`, and every Stage 5.7 `derive_*` function were
  called, never modified or reimplemented.
- No new event type, ledger, or persisted fact was introduced — this stage is pure
  composition and query.
- No cross-run edge or event is ever silently merged into one trace/graph.

## Evidence

- [phase5/wiring/trace_assembly.py](wiring/trace_assembly.py)
- [phase5/tests/test_trace_assembly.py](../tests/test_trace_assembly.py) — 9 tests: full
  real-pipeline reconstruction (Stage 5.4 live attack injection through Stage 5.6
  decision/action, assembled and checked section-by-section), determinism across repeated
  calls, reconstruction from a fresh ledger reload, strict run-scoping for both
  `assemble_trace()` and `build_propagation_graph()` (including the collision finding
  above, worked around correctly), `PRODUCED`/`USED_BY` composition, no fabricated
  `INFLUENCED`, pairwise `RETRIEVED_WITH` composition, and a non-interference check
  confirming `ProvenanceGraph`'s own output is unaffected by anything this stage does.
- Full Phase 5 suite: `python -m pytest phase5/tests/ -q` → 145 passed, 2 skipped (the
  Stage 5.7 future-vendor tests, skipping by design).
- Frozen Phase 3/4 regression: recorded below once complete.

## Coverage check

The master prompt's own trace-assembly diagram (Experiment/Injection/Memory Lifecycle/
Agent Events/Memory Evolution/Outcome) is fully represented as `ExperimentTrace` fields.
The propagation graph is genuinely derived from persisted evidence per run, not
hand-constructed.

## Things worth flagging before moving on

- **Attribution is intentionally not implemented in Phase 5** (confirmed by explicit
  design decision, 2026-09-12) — not a gap. Phase 5's job is to instrument and preserve
  the evidence (lineage edges, injection records, memory identity) a later attribution
  mechanism would need; `ExperimentTrace`/`PropagationGraph` deliberately make no
  attribution claim themselves. The master prompt's own outcome section names
  "Attribution" alongside ground truth and counterfactual — this stage does not populate
  it, by design, rather than fabricating one. **Update (2026-09-13)**: Attribution has
  since been implemented as a completely separate, top-level `attribution/` layer,
  outside Phase 5, consuming this stage's `PropagationGraph`/lineage evidence read-only.
  This does not change the statement above — Phase 5 itself still makes no attribution
  claim.
- **`ExperimentTrace`/`PropagationGraph` are per-run, not per-task.** A run with many
  tasks gets one trace containing all of them together; a caller wanting one task's
  slice must filter `ExperimentTrace`'s tuples by `task_id` themselves — no
  `assemble_task_trace()` convenience was added in this pass.
- **`build_propagation_graph()`'s cost scales with ledger size**, since every underlying
  `derive_*` call scans its whole ledger before this stage's scoping filter is applied —
  fine at test/campaign scale, would need indexing (e.g. membership-ledger-side
  per-run event lists, which already exist and could be used to pre-filter before calling
  `derive_*`) before a very large multi-run shared ledger.

---

## Reconciliation (2026-09-13) — `REFERENCES` composed into `build_propagation_graph()`

**Context**: Stage 5.7 was reopened on 2026-09-13 (by explicit user instruction) to add
`derive_references_edges()` — see `PHASE5_5_7_PROVENANCE_LINEAGE_INSTRUMENTATION.md`'s
"Reopening" section. That reopening was deliberately scoped to Stage 5.7 only and did
NOT touch this stage, leaving an open question: does `PropagationGraph` need to include
the new edge type?

**The central decision, evidence-based, not by convenience**: inspecting this stage's
OWN documentation and implementation (not assumption) settles it. This document's own
"minimal, scientifically sufficient change" section (above) already states
`build_propagation_graph()`'s contract as **"calls every applicable Stage 5.7 `derive_*`
function"** — not "only propagation/lineage-relevant relationships." The actual
implementation already composes `USED_BY` (an exposure fact, not lineage/propagation)
and `RETRIEVED_WITH`/`SELECTED_WITH` (co-occurrence facts, not lineage/propagation)
unconditionally. This is direct, pre-existing evidence that `PropagationGraph` was
already built to represent the COMPLETE Stage 5.7 `MemoryInteractionEdge` vocabulary
(Option B), not a narrower propagation-only projection (Option A) — `REFERENCES` was
simply never composed before because no producer function existed for it yet, not
because the graph's contract excluded it.

**Decision: REFERENCES belongs in the Stage 5.8 graph**, per the stage's own long-standing
contract. `build_propagation_graph()` now also calls `derive_references_edges()` verbatim
(no reimplementation), exactly like its other unconditional Stage 5.7 calls
(`derive_derived_from_edges()`, `derive_exposed_to_decision_edges()`,
`derive_influenced_edges()`) — no new parameters, no second reference-detection
mechanism, existing edge types and their ordering/scoping logic untouched.

**Exact change**: one line added to `build_propagation_graph()`
(`phase5/wiring/trace_assembly.py`):
`all_edges.extend(derive_references_edges(memory_ledger, event_ledger))`. The existing
`_edge_belongs_to_run()` run-scoping filter (unmodified) applies to `REFERENCES` edges
identically to every other edge type — no special-casing needed, since the filter only
inspects `established_by_event_ids`, which `derive_references_edges()` already populates
with a real, membership-registered event id.

**Tests added** (`phase5/tests/test_trace_assembly.py`, 8 new): a real structural
reference appears in the assembled graph and is grounded in the real creation/derivation
event; no edge without an exact `[memory_id]` bracket citation; no edge from mere word
overlap (the exact behavioral-inference idea the Post-Phase-5 hardening pass rejected,
confirmed still not to fire); no self-reference edge; `REFERENCES` never produces
`INFLUENCED` and never carries `COUNTERFACTUAL_EVIDENCE`; deterministic across repeated
calls; identical after a fresh ledger reload; and strict run isolation (a citation
recorded under a different run never leaks into this run's graph, even when both
memories share one physical `CanonicalMemoryLedger`).

**What was NOT touched**: `derive_references_edges()` itself (Stage 5.7, unmodified),
every other edge type's derivation and ordering, `assemble_trace()`, `ExperimentTrace`,
`validate_run()` (Stage 5.9 — does not read `PropagationGraph` at all, so this change
does not affect it), and Stage 5.8A's `derive_memory_behavior_dataset()` code (it already
iterates `graph.edges` generically via `_relationship_record()`, so `REFERENCES` records
now flow through the existing `memory_relationship` category automatically — see
`PHASE5_5_8A_MEMORY_BEHAVIOR_DATASET.md`'s own reconciliation note).

**Verification**: `python -m pytest phase5/tests -q` → **203 passed, 2 skipped** (194
prior + 8 new, 0 regressions). Full frozen Phase 3/4 regression re-run fresh — see
`PHASE5_CHECKLIST.md`.

**STAGE 5.8 STATUS (after reconciliation): PASS. Refrozen.**

---

**STAGE 5.8 STATUS: PASS.**
