# Multi-Boundary Provenance Graph — Real-Data Demonstration Report

Status: **COMPLETE**. Closes the one open architectural question from
`PHASE3_PROVENANCE_GRAPH_DESIGN_REVIEW.md §8`, decided by the user: *"one unified
provenance graph with explicit experiment/run boundary nodes and strictly no
cross-boundary provenance edges; clean/manipulated comparisons happen as a separate
analysis layer."* This report is the real-data proof that the already-implemented,
already-unit-tested mechanism (`build_multi_boundary_provenance_graph()`) actually holds
that invariant against genuine real data, not only a hand-constructed fixture.

## 1. Method

Composed two genuinely separate real experiment runs from this session's own real
evidence into one unified graph — not a synthetic "clean vs. manipulated" pair (Phase 4
doesn't exist yet to produce one), but two real, independently-produced ledger triples,
which is exactly the structural case the mechanism needs to prove correct:

- Boundary `mem0_real_run`: one real pool from the n=20 Mem0/LoCoMo counterfactual run
  (`locomo-g_031ba2ff9ce2625c`, real `RealMem0Adapter` ingestion + real Qwen3-8B
  retrieval/selection events).
- Boundary `amem_real_run`: one real pool from the n=20 A-MEM/LoCoMo counterfactual run
  (`locomo-a_conv-26_session_1`, real `RealAMemAdapter` ingestion + real Qwen3-8B
  retrieval/selection events, post-`inspect_memory()`-fix).

## 2. Result

```
total nodes: 42
total edges: 80
boundary nodes: ['boundary::mem0_real_run', 'boundary::amem_real_run']
mem0 memory nodes: 18
amem memory nodes: 18
mem0 task nodes: 2
amem task nodes: 2
cross-boundary edges found (should be 0): 0
```

**Zero cross-boundary edges**, composing 36 real memory nodes and 4 real task nodes from
two independently-produced real experiment runs. The one invariant that matters most for
this feature — no edge synthesized between two boundaries — holds against actual data,
not only the synthetic fixture `test_multi_boundary_never_synthesizes_cross_boundary_edges`
already proved it against.

## 3. What this confirms about the decision

The decided design works exactly as specified: a caller gets one graph object, can
iterate/compare both boundaries' subgraphs side by side (e.g. `graph.nodes_of_type(...)`,
filtering by the `boundary_label::` node-id prefix), and Phase 3 never claims any
correspondence between a memory in one boundary and a memory in another — that
correspondence, when it eventually matters (e.g. "does manipulated-run memory X'
correspond to clean-run memory X"), is explicitly left to a future Phase 4 analysis layer,
never invented here.

## 4. Freeze status

Not a frozen decision — a dated real-data verification of an already-decided,
already-implemented design.
