# Phase 3.3-H4-PROVENANCE-GRAPH — Implementation Report

Status: **COMPLETE**. Closes §7 of the Phase 3 completion audit (`[NOT DONE]` →
`[DONE]`) — a real, persisted-by-projection graph artifact assembling memory nodes, task
nodes, and grounded provenance/lifecycle edges, where previously only individually
queryable ledgers existed.

## 1. Design decision: a projection, not a new store

`ProvenanceGraph` is built fresh, every call, from `CanonicalMemoryLedger`/
`CanonicalEventLedger`/`SupersessionLedger` — no new persisted file is introduced. This
deliberately follows H.3's own precedent for `CanonicalMemoryVersion` ("a version is a
pure, deterministic projection over the event log... no separate versions.jsonl store"),
for the same reason: a second, independently-persisted graph store would need its own
consistency-with-the-ledgers guarantee; a projection gets that for free, since it cannot
drift from data it is recomputed from every time.

This single decision satisfies several audit checklist items simultaneously, by
construction rather than by separate mechanism:
- **Deterministic** — pure function of ledger contents (tested: two builds from
  identical state produce an identical `to_dict()`).
- **Vendor-independent** — zero foundation/adapter imports anywhere in the module
  (tested structurally, mirroring `taint_propagation.py`'s own proof style).
- **Survives process restart** — trivially, since the ledgers it reads already do.
- **Respects experiment boundaries** — the builder's own signature takes exactly one
  `(memory_ledger, event_ledger[, supersession_ledger])` triple, the natural per-pool/
  per-experiment scope every real caller in this codebase already uses. Nothing can
  cross a boundary because nothing merges two ledger instances into one graph.

## 2. What was built

`phase3/evaluation/foundations/provenance_graph.py`: `GraphNode` (memory or task),
`GraphEdge` (9 types: `derived_from`, `retrieved`, `selected`, `rejected`, `used`,
`counterfactually_influential`, `superseded_by`, `equivalent_to`, `conflicts_with`),
`ProvenanceGraph` (with `ancestors_of()`/`descendants_of()` cycle-safe traversal,
`edges_for_task()`, `to_dict()` export), and `build_provenance_graph()`.

**Grounding discipline, the module's own central invariant**: every edge carries
`established_by_event_id` (or, for `derived_from`, the child's own `creation_event`
string) pointing at the real record that produced it. Nothing is inferred — most
importantly, a `used` edge is only ever added if a real `used` `CanonicalEvent` actually
exists in the ledger; this module never synthesizes one from a `selected` edge (confirmed
by a dedicated test — `test_never_invents_a_used_edge_from_selected`). Repo-wide grep
confirms no real runtime code has ever appended a raw `used` event, so `used` edges are
legitimately absent from every graph built against real data today — stated honestly in
the module docstring, not glossed over.

**Lifecycle state resolution**: when a `SupersessionLedger` is supplied, node
`lifecycle_state` comes from `get_current_version()` — safe to call directly and
unconditionally now, since H.3-R2 (this session) fixed the bug that previously made this
unreliable for derivation-touched memories. When omitted, nodes carry only their
at-creation `lifecycle_state`, explicitly labeled `lifecycle_status=AT_CREATION_ONLY` so a
caller can never mistake it for current state.

**`SUPERSEDED_BY` edges**: `SupersessionLedger` has no all-records enumeration method (by
design — point lookups only). Rather than adding one, this module reuses the same
`get_current_version()` call already needed for `lifecycle_state`, so the two facts (a
memory's current state, and who superseded it) can never disagree with each other by
construction.

## 3. Testing

11 tests, `test_provenance_graph.py`: node/edge construction, grounding correctness,
transitive/cycle-safe `ancestors_of()`/`descendants_of()`, both lifecycle-resolution modes,
`relationship_detected` → `equivalent_to` edge construction, the never-invent-`used`
invariant, dangling-edge rejection, determinism, vendor-independence, and experiment-
boundary isolation (two same-id memories in two separate ledger triples never merge).

**Critically, one test builds the graph against this session's own real, real-Mem0-
produced ledger data** (`phase3/experiments/canonical_store/h4a-real-locomo-smoke-1/
locomo-g_65a9868ec81852be/`, from the real, sampled LoCoMo counterfactual run) — not only
hand-constructed synthetic fixtures. Confirms real memory/task nodes, real `retrieved`/
`selected` edges, and that every edge's `established_by_event_id` resolves to an actual
event via `event_ledger.get_event()`. This test is skip-guarded for checkouts without that
session artifact present, rather than assumed to always exist.

## 4. Regression

Full suite: **1612 passed**, 14 skipped, same single pre-existing unrelated memoryarena
fingerprint-drift failure.

## 5. What this does not do

- No change to `CanonicalMemoryLedger`, `CanonicalEventLedger`, `SupersessionLedger`,
  `taint_propagation.py`, or `metrics/provenance.py` — this module calls into all of them
  read-only.
- Not wired into `campaign_formal_runner.py` or any live campaign path — this is a
  standalone, callable capability, consistent with how every H.4-* mechanism this session
  built was first delivered standalone before any live-wiring decision. Wiring it into a
  reporting/export step is a natural, smaller follow-up, not performed here.
- Does not attempt to resolve the `EDGE_USED` gap (no real `used` events exist to graph) —
  that is a separate, pre-existing observability gap this module correctly reflects rather
  than papers over.

## 6. Compatibility and freeze status

Additive only — one new module, one new test file. Not a frozen decision.
