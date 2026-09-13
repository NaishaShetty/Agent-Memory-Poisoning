# Phase 5.8A — Memory Behavior Dataset Derivation

Status: PASS. Reconciled (2026-09-13, final Phase 5.8–5.9 reconciliation pass) — see
"Reconciliation" section near the end of this document. No code change was required
here.
Depends on: Stage 5.8 (`assemble_trace()`/`build_propagation_graph()`, reused verbatim
as the sole inputs to this stage's derivation).

Inserted between 5.8 and 5.9 by explicit instruction — placement is mandatory because
this stage consumes 5.8's assembled trace/graph as input, and 5.9's determinism/
non-interference validation must also cover this stage's derivation procedure.

## Scope

A **derived analytical artifact only** — never a second source of truth. Structured
records for: memory lifecycle, retrieval/selection, agent interactions,
memory-to-memory relationships, propagation/lineage, attack/injection events, and
counterfactual evidence where applicable. Every record traceable back to real canonical/
Phase 5 event identifiers. Deterministic, documented derivation. No frozen Phase 3/4
semantics touched.

## Design

New module: [wiring/memory_behavior_dataset.py](wiring/memory_behavior_dataset.py).

**One uniform record envelope, not six bespoke dataclasses.** Every category already has
a real, strict, validated schema (`CanonicalEvent`, `Phase5Event`,
`MemoryInteractionEdge`) — re-typing each into a seventh bespoke dataclass would be
exactly the "second, parallel schema" problem this project has avoided at every prior
stage. `MemoryBehaviorRecord` is instead one flat envelope:

```
record_type       -- one of 6 closed categories
run_id            -- which experiment run this record belongs to
source_event_ids  -- the REAL, citable event id(s) this record was flattened from
                     (required non-empty -- no record without a citable event)
fields            -- the category's own real data, copied verbatim from the
                     underlying event/edge's own to_dict(), never recomputed
```

**Six record categories**, one per requested area: `memory_lifecycle` (created/derived/
superseded/retired `CanonicalEvent`s), `retrieval_selection` (retrieved/selected/
rejected/used `CanonicalEvent`s plus `retrieval_candidate_scored` `Phase5Event`s),
`agent_interaction` (`context_assembled`/`agent_decision`/`agent_action`
`Phase5Event`s), `memory_relationship` (every `MemoryInteractionEdge` from the run's
propagation graph), `attack_injection` (`attack_injection` `Phase5Event`s), and
`counterfactual_evidence` (`counterfactually_influential` `CanonicalEvent`s — correctly
absent from any pipeline that never ran a counterfactual mask, never fabricated to fill
the category).

**Deterministic derivation procedure**: `derive_memory_behavior_dataset(run_id, ...)`
calls `assemble_trace()`/`build_propagation_graph()` (Stage 5.8, unmodified) exactly
once each, then maps their output to records in one fixed, documented order. Two calls
against the same ledger state — even after a full ledger reload from disk — produce
byte-identical output (tested both ways).

**Persistence**: `write_memory_behavior_dataset_jsonl()`/`read_memory_behavior_dataset_jsonl()`
— newline-delimited JSON, one record per line, in derivation order, round-trip tested.

## The generated dataset (deliverable)

[phase5/datasets/memory_behavior_dataset_sample.jsonl](datasets/memory_behavior_dataset_sample.jsonl) —
10 real records, generated from an actual full pipeline run (a real live FARMA injection
through Stage 5.4, real retrieval/selection/context assembly through Stage 5.5, a real
decision/action through Stage 5.6, and the resulting lineage edges through Stage 5.7),
not hand-written. Every record's `source_event_ids` resolves to a real, persisted event
in either `CanonicalEventLedger` or `Phase5EventLedger` (verified by test).

## What was NOT done

- No new event type or ledger was introduced — this stage is pure derivation over
  Stage 5.2–5.8's already-persisted state.
- No frozen Phase 3/4 file was read for anything beyond what Stage 5.8 already reads.
- No record was fabricated to fill out a category that has no real data in a given run
  (confirmed for `counterfactual_evidence` in the generated sample).

## Evidence

- [phase5/wiring/memory_behavior_dataset.py](wiring/memory_behavior_dataset.py)
- [phase5/tests/test_memory_behavior_dataset.py](../tests/test_memory_behavior_dataset.py)
  — 9 tests: all 5 populated categories present for the real pipeline (counterfactual
  correctly absent), every cited `source_event_id` resolves to a real ledger entry,
  determinism across repeated calls and across a fresh ledger reload, schema validation
  (empty citation list and unknown record_type both rejected), JSONL round-trip, a
  non-interference check confirming derivation never mutates either ledger, and the
  actual sample-dataset generation test itself.
- Full Phase 5 suite: `python -m pytest phase5/tests/ -q` → 154 passed, 2 skipped (by
  design).
- Frozen Phase 3/4 regression: recorded below once complete.

## Things worth flagging before moving on

- **The dataset is per-run, not filterable by task at the schema level** — same
  limitation `ExperimentTrace` itself has; a consumer wanting one task's records filters
  `fields.task_id` themselves.
- **`fields` is a loosely-typed `Mapping[str, Any]`** rather than a per-category typed
  schema — a deliberate simplicity trade-off (see "one uniform envelope" above), but it
  means a downstream consumer must know each category's real field set (documented in
  `CanonicalEvent`/`Phase5Event`/`MemoryInteractionEdge` themselves) rather than reading
  it off this dataset's own schema directly.
- **The committed sample dataset reflects one specific test run's fixture data**
  (FARMA's `SEED_CAMPING`) — it is a worked example proving the mechanism, not a
  representative or complete corpus across all 7 attacks.

---

## Reconciliation (2026-09-13) — `REFERENCES` flows through the existing `memory_relationship` category

**Question**: once Stage 5.7 gained `derive_references_edges()` and Stage 5.8's
`build_propagation_graph()` was reconciled to compose it (see
`PHASE5_5_8_TRACE_ASSEMBLY_PROPAGATION_GRAPH.md`'s own "Reconciliation" section), should
this stage's dataset gain a new, seventh category for it?

**Inspection finding**: no. `_relationship_record()` (`memory_behavior_dataset.py`)
already builds a `memory_relationship` record generically from ANY `MemoryInteractionEdge`
the propagation graph contains — `edge.relationship_type`, `edge.source_id`,
`edge.target_id`, `edge.evidence_kind` are copied verbatim regardless of what
`relationship_type` string the edge carries. `derive_memory_behavior_dataset()` itself
just iterates `graph.edges` (line: `for edge in graph.edges: records.append(_relationship_record(run_id, edge))`)
with no type-based filtering. This is exactly this stage's own "one uniform envelope, not
six [now seven] bespoke dataclasses" design principle (see "Design" section above),
applied automatically to a relationship type that did not exist when this stage was
first built.

**Decision: no new category was created.** `REFERENCES` records appear under the
existing `memory_relationship` category with `fields.relationship_type == "REFERENCES"`,
exactly like `DERIVED_FROM`/`PRODUCED`/`SUPERSEDES`/etc. already do — zero code change to
`memory_behavior_dataset.py` was needed; the existing generic composition already
handles it correctly, by construction, once Stage 5.8 supplies the edge.

**Test added**: `test_references_edge_flows_through_existing_memory_relationship_category`
(`phase5/tests/test_memory_behavior_dataset.py`) — seeds a real citing/cited memory pair,
derives the dataset, and confirms exactly one `memory_relationship` record with
`relationship_type="REFERENCES"`, correct `source_id`/`target_id`, `evidence_kind`
still `"OBSERVED_EVENT"`, and a real, non-fabricated `source_event_ids` citation.

**Verification**: `python -m pytest phase5/tests -q` → 1 new test, 0 regressions (exact
final count in `PHASE5_CHECKLIST.md`).

**STAGE 5.8A STATUS (after reconciliation): PASS. Refrozen. No dataset schema change.**

---

**STAGE 5.8A STATUS: PASS.**
