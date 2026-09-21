"""Phase 11.x Option 2 -- new, non-semantic STRUCTURAL features.

Every feature below is computed from real fields already present on
`MemoryScenario`/`ScenarioPool` (`phase6/defense/orchestration/pipeline.py`)
and the SAME real, sanctioned edge vocabulary `phase11/gnn/graph_build.py`
already restricts itself to (`RETRIEVED_WITH`, `DERIVED_FROM` --
`phase5/wiring/lineage.py`'s own constants, unmodified, imported not
redefined). No new edge type, schema field, or event format is introduced.
Two features (`ancestor_count`, `derived_from_degree`) are close to
`lineage_taint_score`'s own inputs but measure something genuinely
different: `lineage_taint_score` is a CONTENT-similarity measure between a
memory and its tainted ancestors; these are pure STRUCTURAL counts,
computed without reading `content_text` at all, so a memory with many
untainted ancestors and one with few tainted ones are distinguished here in
a way `lineage_taint_score` alone cannot.

Every feature is documented below against the required 7-point checklist
(Section 4 of the governing instructions).
"""

from __future__ import annotations

from typing import Dict, Sequence, Tuple

import networkx as nx

from phase5.wiring.lineage import DERIVED_FROM, RETRIEVED_WITH
from phase6.defense.orchestration.pipeline import ScenarioPool
from phase11.gnn.graph_build import build_pools_graph

STRUCTURAL_FEATURE_KEYS: Tuple[str, ...] = (
    "retrieval_count_raw",
    "pool_size",
    "graph_degree",
    "retrieved_with_degree",
    "derived_from_degree",
    "ancestor_count",
    "descendant_count",
    "lineage_depth",
)

# --------------------------------------------------------------------------
# Per-feature documentation (Section 4's required checklist, one entry each)
# --------------------------------------------------------------------------
FEATURE_DOCUMENTATION: Dict[str, Dict[str, str]] = {
    "retrieval_count_raw": {
        "definition": "The real, raw `prior_retrieval_count` field already carried on "
        "`MemoryScenario` -- how many times this memory had already been retrieved "
        "before the event being evaluated.",
        "source": "`MemoryScenario.prior_retrieval_count` (phase6/defense/orchestration/pipeline.py). "
        "The SAME real field `dormancy_activation_signal(prior_retrieval_count)` already "
        "consumes to derive `dormancy_activation_score` -- but exposed here as its own raw "
        "value rather than passed through that one nonlinear formula, so information the "
        "existing sanctioned formula collapses (e.g. the difference between "
        "prior_retrieval_count=5 and =50, both of which saturate dormancy toward the same "
        "output) survives.",
        "computation": "identity: `float(scenario.prior_retrieval_count)`.",
        "interpretation": "Very low values indicate a freshly-admitted memory; very high "
        "values indicate sustained reuse -- relevant to volume/amplification mechanisms "
        "(brief Section 23) distinct from dormancy's specific decay-curve framing.",
        "available_before_prediction": "yes -- a static field already set on the scenario "
        "object before any signal is computed, identical to how the existing sanctioned "
        "features already consume it.",
        "leakage": "none -- this is the exact same real field the existing sanctioned "
        "`dormancy_activation_score` already legitimately reads; no label of any kind.",
        "attack_specificity": "attack-agnostic -- a general lifecycle property, not tied to "
        "any one attack's mechanism.",
    },
    "pool_size": {
        "definition": "The number of real memories in the same `ScenarioPool` as this "
        "memory.",
        "source": "`len(pool.memories)` (phase6/defense/orchestration/pipeline.py's "
        "`ScenarioPool.memories`).",
        "computation": "identity: `float(len(pool.memories))`.",
        "interpretation": "Context/normalization feature -- some structural counts below "
        "(e.g. `graph_degree`) are naturally larger in a larger pool; this lets a downstream "
        "estimator learn that relationship rather than confusing pool size with anomalousness.",
        "available_before_prediction": "yes -- pool composition is fixed input data for this "
        "project's static ablation-corpus protocol, the same availability class the existing "
        "sanctioned `consensus_divergence_score` already relies on (it reads every OTHER "
        "memory's content in the same pool to compute one memory's divergence).",
        "leakage": "none -- no label is used; pool membership is set by the corpus author, "
        "not by any detector output.",
        "attack_specificity": "attack-agnostic.",
    },
    "graph_degree": {
        "definition": "Total real edge count (both `RETRIEVED_WITH` and `DERIVED_FROM`) "
        "incident to this memory's node in its pool graph.",
        "source": "`phase11/gnn/graph_build.py::build_pools_graph()`, UNCHANGED -- this module "
        "only reads the graph that function already builds, it does not add any edge type.",
        "computation": "`graph.degree(node_id)` (networkx, real edge count).",
        "interpretation": "High degree can indicate either a popular, heavily-co-retrieved "
        "legitimate memory, or a propagation/amplification pattern (Phase 7's own concern) "
        "-- deliberately ambiguous on its own, which is why it is evaluated alongside the "
        "existing sanctioned signals, not in place of them.",
        "available_before_prediction": "yes -- computed from the same real `parent_ids`/"
        "`ancestors`/pool-co-retrieval structure the existing sanctioned pipeline already "
        "uses to build this graph.",
        "leakage": "none -- structural count only, no label read.",
        "attack_specificity": "attack-agnostic.",
    },
    "retrieved_with_degree": {
        "definition": "Real edge count restricted to the `RETRIEVED_WITH` relation only "
        "(co-retrieval within the same pool).",
        "source": "same graph as `graph_degree`, filtered by `edge_type == RETRIEVED_WITH` "
        "(the real constant from `phase5/wiring/lineage.py`, imported unmodified).",
        "computation": "count of incident edges with `data['edge_type'] == RETRIEVED_WITH`.",
        "interpretation": "Relationship-type-specific version of `graph_degree` (brief "
        "Section 4's explicit request for 'relationship-type counts') -- separates "
        "co-retrieval volume from lineage/derivation volume, which `graph_degree` alone "
        "conflates.",
        "available_before_prediction": "yes -- same basis as `graph_degree`.",
        "leakage": "none.",
        "attack_specificity": "attack-agnostic.",
    },
    "derived_from_degree": {
        "definition": "Real edge count restricted to the `DERIVED_FROM` relation only.",
        "source": "same graph, filtered by `edge_type == DERIVED_FROM`.",
        "computation": "count of incident edges with `data['edge_type'] == DERIVED_FROM`.",
        "interpretation": "Pure lineage-connectivity count -- how many real parent/ancestor "
        "OR child/descendant links touch this memory, independent of the CONTENT-similarity "
        "judgment `lineage_taint_score` makes about those same links.",
        "available_before_prediction": "yes.",
        "leakage": "none -- structural count only; does not read `content_text` and does not "
        "read `is_poison_ground_truth` on any ancestor.",
        "attack_specificity": "attack-agnostic.",
    },
    "ancestor_count": {
        "definition": "Real, directly-declared upstream provenance fan-in: the number of "
        "real parent/ancestor records this memory itself declares.",
        "source": "`len(scenario.parent_ids) + len(scenario.ancestors)` -- both real, "
        "already-existing `MemoryScenario` fields.",
        "computation": "identity sum of the two real tuple lengths.",
        "interpretation": "A memory claiming an unusually large number of direct ancestors "
        "may reflect an aggregation/synthesis mechanism (legitimate) or a derivation-chain "
        "contamination attempt (brief Section 16's 'derivation-chain contamination' "
        "mechanism) -- distinguishing these is exactly what this feature alone cannot do, "
        "which is the honest point of testing it empirically rather than assuming it works.",
        "available_before_prediction": "yes -- these are declared, static fields on the "
        "scenario, not values computed by any detector.",
        "leakage": "none.",
        "attack_specificity": "attack-agnostic -- a structural count, not an attack-specific "
        "marker.",
    },
    "descendant_count": {
        "definition": "Real, pool-local downstream fan-out: the number of OTHER real "
        "memories in the SAME pool that declare this memory as a parent/ancestor.",
        "source": "derived from the same real `parent_ids`/`ancestors` fields, read in the "
        "reverse direction, restricted to the current pool (this project's corpora have no "
        "cross-pool real lineage data, so no cross-pool descendant count is claimed).",
        "computation": "count of other scenarios `s` in the same pool where this memory's "
        "id appears in `s.parent_ids` or `{a.memory_id for a in s.ancestors}`.",
        "interpretation": "High fan-out could indicate a memory that many other real "
        "memories build on (either a trusted foundational fact, or -- if poisoned -- a "
        "single forged memory whose taint could propagate widely, the real concern Phase 7's "
        "propagation monitoring already exists for).",
        "available_before_prediction": "SAME availability class as the existing sanctioned "
        "`consensus_divergence_score`: both require reading OTHER memories already present "
        "in the same static pool, not information from a future event. This project's "
        "evaluation protocol is a static, whole-pool corpus assessment, not an online "
        "streaming detector -- stated explicitly here rather than left implicit, since this "
        "is the one candidate feature closest to a genuine 'looks forward' concern.",
        "leakage": "none -- no label of any kind is read; only real, declared `parent_ids`/"
        "`ancestors` fields already present in the corpus.",
        "attack_specificity": "attack-agnostic.",
    },
    "lineage_depth": {
        "definition": "The real length (in hops) of this memory's longest real "
        "`DERIVED_FROM` chain back to a node with no further real parents, within its pool.",
        "source": "same real graph edges as `derived_from_degree`, traversed.",
        "computation": "BFS/DFS from this node following `DERIVED_FROM` edges (parents "
        "only, i.e. the direction the pool graph's own edges are added in "
        "`build_pool_graph()`), depth = number of hops to the furthest real ancestor with no "
        "further parents in this pool.",
        "interpretation": "Deep chains indicate multi-hop derivation -- the specific "
        "mechanism brief Section 16 names ('derivation-chain contamination'). A memory 5 "
        "hops deep in a real chain is structurally different from one declared as a direct "
        "child of an original source, regardless of what `lineage_taint_score` says about "
        "content similarity along that chain.",
        "available_before_prediction": "yes -- same basis as `derived_from_degree`.",
        "leakage": "none.",
        "attack_specificity": "attack-agnostic.",
    },
}

assert set(FEATURE_DOCUMENTATION) == set(STRUCTURAL_FEATURE_KEYS)


def _descendant_counts(pool: ScenarioPool) -> Dict[str, int]:
    counts: Dict[str, int] = {m.scenario_id: 0 for m in pool.memories}
    for m in pool.memories:
        upstream_ids = set(m.parent_ids) | {a.memory_id for a in m.ancestors}
        for parent_id in upstream_ids:
            if parent_id in counts:
                counts[parent_id] += 1
    return counts


def _lineage_depth(scenario_id: str, pool: ScenarioPool) -> int:
    by_id = {m.scenario_id: m for m in pool.memories}

    def depth(sid: str, visited: frozenset) -> int:
        if sid in visited or sid not in by_id:
            return 0
        m = by_id[sid]
        upstream_ids = list(m.parent_ids) + [a.memory_id for a in m.ancestors]
        if not upstream_ids:
            return 0
        return 1 + max(depth(pid, visited | {sid}) for pid in upstream_ids)

    return depth(scenario_id, frozenset())


def pool_structural_features(pool: ScenarioPool) -> Dict[str, Tuple[float, ...]]:
    """Real per-memory structural feature values for every memory in `pool`,
    in the fixed `STRUCTURAL_FEATURE_KEYS` order. Reuses
    `build_pools_graph([pool])` (unmodified) for the graph-degree features,
    consistent with how `phase11/gnn/features.py::pool_node_features()`
    reuses shared, already-sanctioned machinery rather than recomputing
    structure ad hoc."""
    graph = build_pools_graph([pool])
    descendant_counts = _descendant_counts(pool)
    pool_size = float(len(pool.memories))

    features: Dict[str, Tuple[float, ...]] = {}
    for m in pool.memories:
        retrieved_with_degree = sum(
            1 for _, _, data in graph.edges(m.scenario_id, data=True) if data["edge_type"] == RETRIEVED_WITH
        )
        derived_from_degree = sum(
            1 for _, _, data in graph.edges(m.scenario_id, data=True) if data["edge_type"] == DERIVED_FROM
        )
        values = {
            "retrieval_count_raw": float(m.prior_retrieval_count),
            "pool_size": pool_size,
            "graph_degree": float(graph.degree(m.scenario_id)),
            "retrieved_with_degree": float(retrieved_with_degree),
            "derived_from_degree": float(derived_from_degree),
            "ancestor_count": float(len(m.parent_ids) + len(m.ancestors)),
            "descendant_count": float(descendant_counts.get(m.scenario_id, 0)),
            "lineage_depth": float(_lineage_depth(m.scenario_id, pool)),
        }
        features[m.scenario_id] = tuple(values[k] for k in STRUCTURAL_FEATURE_KEYS)
    return features


def pools_structural_features(pools: Sequence[ScenarioPool]) -> Dict[str, Tuple[float, ...]]:
    merged: Dict[str, Tuple[float, ...]] = {}
    for pool in pools:
        merged.update(pool_structural_features(pool))
    return merged
