# Phase 3.3-H4-PROVENANCE-GRAPH — Extension Pass Implementation Report

Status: **COMPLETE**. Implements `PHASE3_PROVENANCE_GRAPH_DESIGN_REVIEW.md` after
review, closing every gap that review identified between the original graph module and
the fuller 10-point design specification.

## 1. What was added, per design-review section

- **§1 (version nodes)**: `include_versions=True` attaches one `memory_version` node per
  `CanonicalMemoryVersion` (H.3), linked via `has_version` edges, in exact append order.
  Attaches at the memory level (recommended option), not touching `memory_versioning.py`.
- **§1/§8 (experiment boundary nodes, multi-boundary graphs)**: `boundary_label` parameter
  on `build_provenance_graph()` namespaces node ids (`f"{label}::{canonical_id}"`, raw id
  preserved in `attributes["canonical_id"]`) and adds an `experiment_boundary` node with
  `within_boundary` edges. New `build_multi_boundary_provenance_graph()` composes N
  single-boundary graphs into one object. **Verified directly, not just asserted**: a
  dedicated test constructs a clean+manipulated pair sharing the same canonical memory id
  and confirms zero edges cross the boundary (only `within_boundary` edges touch the
  boundary node itself).
- **§4 (persistence)**: `phase3/schemas/provenance_graph_schema.json`, a formal JSON
  Schema for `to_dict()`'s export shape, explicitly documented as export-only (no
  load-back path exists).
- **§6 (named query catalog)**: `forward_provenance()`, `backward_provenance()`,
  `derivation_propagation()` (thin wrappers over existing primitives), `task_exposure_and_use()`
  (groups edges by type for one task, no fabricated empty entries), and — the one genuine
  integration gap — `attack_origin_lineage()`, which calls `taint_propagation
  .tainted_memories()` directly rather than reimplementing reachability a second time.
  Tested that the graph's own `forward_provenance()` and `attack_origin_lineage()`'s
  `TaintReport.tainted_memory_ids` agree on the same underlying fact.
- **§2**: no new edge type beyond `has_version`/`within_boundary` — retirement remains a
  terminal version-node state, not a separate edge, matching H.3's own established
  decision.

## 2. A real mistake made and caught during this pass, not hidden

While implementing boundary-prefixing, I initially added an unrequested `"task::"` infix
to task node ids — which would have silently changed `graph.task_ids()`'s return shape
even for the ordinary, already-tested single-boundary case (`"t1"` → `"task::t1"`),
breaking every existing test and real-data usage for no reason the design review asked
for. Caught by re-running the original `test_provenance_graph.py` suite before writing any
new tests — all 11 originally-passing tests are re-verified passing, unchanged, confirming
this was corrected before it became a regression.

A second mistake, in the new test file itself: I initially asserted 2 versions for a
superseded-then-retired memory; H.3's own established behavior
(`test_11_version_history_reconstructs_correctly`) produces 3 (`created` → `superseded` →
`retired`, since the `superseded` event produces its own version distinct from `retired`).
Caught by the test failing against the real, correct behavior, not by re-deriving the
expected count from memory — fixed to match H.3's actual, already-tested semantics.

## 3. Testing

22 tests total across `test_provenance_graph.py` (11, unchanged) and
`test_provenance_graph_extensions.py` (11, new): version-node attachment and its
no-op-by-default backward compatibility, single-boundary prefixing, multi-boundary
composition, the cross-boundary-edge invariant (the single most important test in this
pass), duplicate-boundary-label rejection, all five named query functions, and
`to_dict()` output validated directly against the new JSON Schema via `jsonschema.validate()`.

## 4. Regression

Full suite: **1634 passed**, 14 skipped, same single pre-existing unrelated failure.

## 5. What remains open (unchanged from the design review)

- Whether Phase 4 will actually prefer the multi-boundary composition over requesting two
  separate single-boundary graphs — the mechanism now supports both; which one gets used
  in practice is Phase 4's own future call, not decided here.
- No live wiring into `campaign_formal_runner.py` — still a standalone, callable
  capability, consistent with every other H.4-* mechanism's own delivery pattern.

## 6. Compatibility and freeze status

`provenance_graph.py` extended in place (additive parameters, defaults preserve original
behavior exactly, verified by re-running the original test suite unchanged). One new
schema file, one new test file. Not a frozen decision.
