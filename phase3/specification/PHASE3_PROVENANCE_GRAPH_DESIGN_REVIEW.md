# Provenance/Lifecycle Graph — Design Review (Extension Pass)

Status: **DECIDED AND IMPLEMENTED.** Originally written as a pre-implementation design
review; every proposal below has since been built, tested, and — for the one open
architectural question (§8) — explicitly decided by the user and verified against real
data. See
[PHASE3_3_H4_PROVENANCE_GRAPH_EXTENSION_IMPLEMENTATION_REPORT.md](../experiments/PHASE3_3_H4_PROVENANCE_GRAPH_EXTENSION_IMPLEMENTATION_REPORT.md)
for the implementation report and
[PHASE3_3_H4_MULTI_BOUNDARY_REAL_DEMONSTRATION_REPORT.md](../experiments/PHASE3_3_H4_MULTI_BOUNDARY_REAL_DEMONSTRATION_REPORT.md)
for the real-data proof of §8's decision. This document is kept as the historical design
record, not rewritten to hide that it was originally a proposal.

This reviews the *existing* `provenance_graph.py` (built this session) against the 10-point
spec, against the frozen contracts it must not contradict
([TRACEABILITY_CONTRACT.md](../contracts/TRACEABILITY_CONTRACT.md),
[PHASE4_INTERFACE_REQUIREMENTS.md](PHASE4_INTERFACE_REQUIREMENTS.md),
[relationship_schema.md](../schemas/relationship_schema.md)), and proposes concrete
extensions. **Nothing below should be implemented until you've reviewed and either
approved, amended, or rejected each proposal.**

## 1. Node types

**Existing**: `memory`, `task`.

**Proposed additions**:

- **`memory_version`** — one node per `CanonicalMemoryVersion` (H.3), linked to its
  memory node via a new `HAS_VERSION` edge, in the exact append order H.3 already
  guarantees (never re-sorted). This exposes the full lifecycle-state sequence
  (`CREATED → ... → RETIRED`) as graph structure, not just a current-state attribute on
  the memory node (today's design). **Open question for you**: should retrieval/
  selection/etc. edges attach to the *memory* node (today's design — simpler, matches
  `CanonicalEvent.memory_ids` which reference memory_id, not a version) or to the specific
  *version* that was current at the time of that event (richer, but requires reconstructing
  "which version was current at timestamp T," a capability that doesn't exist today and
  would need new code in `memory_versioning.py` — a frozen-adjacent file, per H.3-R/H.3-R2's
  own precedent for how carefully that file gets touched). **Recommendation: memory-level
  edges, version nodes are a separate, attached sub-structure for lifecycle inspection
  only** — avoids touching `memory_versioning.py` and avoids inventing "current version at
  time T" semantics the frozen schema doesn't define.
- **`experiment_boundary`** — one node per `ExperimentBoundaryRecord` (H.2-R). This is the
  more consequential addition — see §8.
- **`event`** — considered, **not recommended**. `relationship_schema.md §3` already
  treats events as the log, not as first-class entities with their own relationships to
  other events; every edge already carries `established_by_event_id` for full traceability
  back to the specific event. Adding event nodes would duplicate the event ledger's own
  role without adding a capability the audit's checklist actually asked for ("event/
  lifecycle nodes... where required" — required, not mandatory; this design treats the
  requirement as already satisfied by edge-level grounding).

## 2. Edge types

**Existing**: `derived_from`, `retrieved`, `selected`, `rejected`, `used`,
`counterfactually_influential`, `superseded_by`, `equivalent_to`, `conflicts_with`.

**Proposed addition**: `HAS_VERSION` (memory → its own version nodes, ordered), if §1's
version-node proposal is approved. No other new edge type is needed — `retired` remains a
terminal *state* on the last version node, not a separate edge (mirrors H.3's own decision
that retirement is "a `lifecycle_state=RETIRED` version snapshot," never a second
structure — `PHASE3_3_H3_MEMORY_VERSIONING.md §10`). No "agent" node/edge — this is a
single-agent benchmark; adding one would be inventing structure the frozen contracts don't
require.

## 3. Authoritative source — no change needed

Already correct in the existing implementation: ledgers remain authoritative,
`ProvenanceGraph` is a pure projection, explicitly justified against H.3's own precedent.
This principle extends unchanged to every proposal below — nothing here introduces a
second mutable store.

## 4. Persistence / serialization format

**Existing**: an ad hoc `to_dict()`, never formally specified.

**Proposal**: a documented JSON Schema, `phase3/schemas/provenance_graph_schema.json`
(mirroring `memory_schema.json`/`relationship_schema.md`'s own narrative+schema pairing
convention), defining the exact shape of `nodes[]`/`edges[]` and each node/edge type's
required attributes. **This remains export-only** — a snapshot for handing to a
visualization tool or Phase 4's own analysis code, never re-read back as authoritative
input (no `load_provenance_graph_from_json()` function should exist; the only path back to
a `ProvenanceGraph` object is `build_provenance_graph()` from the live ledgers). Stated
explicitly here so this boundary doesn't erode over time.

## 5. Reconstruction — no change needed

Already correct; extends unchanged to multi-boundary graphs (§8) since reconstruction
still means "call `build_provenance_graph()` again," not "reload a persisted snapshot."

## 6. Phase-4-facing queries — the real gap

**Existing**: generic `ancestors_of()`/`descendants_of()`/`edges_for_task()`/
`edges_from()`/`edges_to()`. Functionally capable of answering most of the required
questions, but never named, documented, or tested as the specific queries Phase 4 needs.

**Proposed named query functions** (thin wrappers over existing primitives, plus one real
integration gap to close):

| Query | Proposed function | Implementation |
|---|---|---|
| Forward provenance | `forward_provenance(graph, memory_id)` | Wraps `descendants_of()` — already correct, just needs the Phase-4-facing name |
| Backward provenance | `backward_provenance(graph, memory_id)` | Wraps `ancestors_of()` |
| Derived-memory propagation | `derivation_propagation(graph, memory_id)` | Same as forward provenance, scoped to `derived_from` edges only (already the only edge type these traverse) — mostly a naming/documentation change |
| **Attack-origin lineage** | `attack_origin_lineage(graph, memory_ledger, event_ledger, supersession_ledger, attack_memory_ids)` | **Real gap.** Must call `taint_propagation.tainted_memories()` (H.4-G, reused, never reimplemented) and return its `TaintReport` annotated with the graph's own node/edge context (e.g. which specific `derived_from` edges compose each propagation path) — today these are two completely disconnected modules |
| Task exposure/use | `task_exposure_and_use(graph, task_id)` | Wraps `edges_for_task()`, grouped by edge type into `{retrieved, selected, rejected, used, counterfactually_influential}` |
| Taint propagation | (same as attack-origin lineage — one function, not two; the audit's checklist names both but they're the same capability under two names) | |

**This is the single most important gap to close** — Phase 4's own interface
requirements document (`PHASE4_INTERFACE_REQUIREMENTS.md §3`) explicitly lists
"attack-origin attribution" and "propagation analysis" as required capabilities the clean
agent must expose. Right now that capability exists (`taint_propagation.py`) but isn't
reachable through the graph object Phase 4 would naturally reach for first.

## 7. Identity — no change needed

Already correct; canonical `memory_id`/`task_id` only, tested, extends unchanged.

## 8. Experiment isolation — needs a real architectural decision from you

**Existing**: isolation achieved by never combining two ledger triples into one graph —
`build_provenance_graph()`'s signature accepts exactly one `(memory_ledger, event_ledger,
supersession_ledger)` triple. This is *correct* for preventing contamination, but it means
**the graph cannot represent a clean run and a manipulated run side by side**, which is
precisely the comparison `PHASE4_INTERFACE_REQUIREMENTS.md §2` names as the whole point of
the clean/manipulated path split ("Any difference in decision must therefore be
attributable to the memory-layer difference").

**DECIDED**: one unified provenance graph with explicit experiment/run boundary nodes and
strictly no cross-boundary provenance edges; clean/manipulated comparisons happen as a
separate analysis layer, never as edges this graph itself invents. Implemented as
`build_multi_boundary_provenance_graph()`, accepting multiple `(boundary_label,
memory_ledger, event_ledger, supersession_ledger)` tuples, each contributing its own
subgraph plus one `experiment_boundary` node that every node from that ledger triple
carries a `within_boundary` edge to. **The no-synthesized-cross-boundary-edge invariant is
tested directly** (`test_multi_boundary_never_synthesizes_cross_boundary_edges`) and
**verified against real data**, not only a constructed fixture — see
[PHASE3_3_H4_MULTI_BOUNDARY_REAL_DEMONSTRATION_REPORT.md](../experiments/PHASE3_3_H4_MULTI_BOUNDARY_REAL_DEMONSTRATION_REPORT.md),
which composes two of this session's own real experiment runs (Mem0 and A-MEM, each a
real, independent 18-pool/20-task run) into one graph and confirms zero cross-boundary
edges appear among the real data.

## 9. Determinism — no change needed

Preserved by construction under every proposal above (still a pure function of ledger
contents, now just accepting more than one triple).

## 10. Validation / grounding — extends unchanged

`HAS_VERSION` edges grounded by the version's own `established_by_event_id` (already
exists on `CanonicalMemoryVersion`, per H.3). `experiment_boundary` nodes grounded by the
`ExperimentBoundaryRecord`'s own `boundary_id` (H.2-R). No new class of ungrounded edge is
introduced by any proposal here.

## Summary of what needs your decision before implementation

1. **§1/§8, multi-boundary graphs**: approve, amend, or reject the proposed design for
   representing a clean run and a manipulated run in one graph object without inventing
   cross-boundary edges.
2. **§1, version nodes**: approve the memory-level-edges-with-attached-version-substructure
   design (recommended, avoids touching `memory_versioning.py`), or ask for version-level
   edge attachment instead (bigger, touches frozen-adjacent territory).
3. **§4, persistence**: approve the JSON-Schema-as-export-only approach, or specify a
   different format/location.
4. **§6, attack-origin lineage**: this one has only one reasonable design (reuse
   `taint_propagation.py`, never reimplement) — flagging it as the highest-priority fix
   regardless of how §1/§8 are decided, since it's independently valuable and touches
   nothing controversial.

Once you've reviewed these, the next step is implementation — following the same
mission-brief-then-execute pattern every other H.4-* stage this session used, this time
with the design agreed *before* code, not after.
