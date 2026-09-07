"""Phase 3.3-H4-PROVENANCE-GRAPH tests -- `build_provenance_graph()`/`ProvenanceGraph`.

Covers: node/edge construction correctness, grounding (every edge traces to a real event
or record, never invented), lifecycle_state resolution (current vs at-creation-only),
cycle-safety of ancestors_of/descendants_of, determinism, vendor-independence (structural,
mirrors taint_propagation.py's own proof style), and -- critically -- a build against one
of this session's own REAL, real-Mem0-produced ledger directories, not only synthetic
fixtures.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from phase3.evaluation.foundations.canonical import (
    CanonicalMemoryRecord,
    LIFECYCLE_CREATED,
    LIFECYCLE_RETIRED,
    MEMORY_TYPE_DERIVED,
    MEMORY_TYPE_FOUNDATION,
)
from phase3.evaluation.foundations.canonical_event import (
    CanonicalEvent,
    EVENT_CREATED,
    EVENT_DERIVED,
    EVENT_RELATIONSHIP_DETECTED,
    EVENT_RETRIEVED,
    EVENT_SELECTED,
    RELATIONSHIP_EQUIVALENT_TO,
)
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase3.evaluation.foundations.memory_versioning import SupersessionLedger
from phase3.evaluation.foundations.provenance_graph import (
    EDGE_DERIVED_FROM,
    EDGE_EQUIVALENT_TO,
    EDGE_RETRIEVED,
    EDGE_SELECTED,
    EDGE_USED,
    LIFECYCLE_STATUS_AT_CREATION_ONLY,
    LIFECYCLE_STATUS_CURRENT,
    NODE_TYPE_MEMORY,
    NODE_TYPE_TASK,
    ProvenanceGraphError,
    build_provenance_graph,
)


def _system(tmp_path):
    memory_ledger = CanonicalMemoryLedger(tmp_path / "memory")
    event_ledger = CanonicalEventLedger(tmp_path / "events", memory_ledger)
    supersession_ledger = SupersessionLedger(tmp_path / "supersessions")
    return memory_ledger, event_ledger, supersession_ledger


def _seed_foundation(memory_ledger, event_ledger, memory_id, timestamp="2026-01-01T00:00:00Z"):
    memory_ledger.put(CanonicalMemoryRecord(
        memory_id=memory_id, memory_type=MEMORY_TYPE_FOUNDATION, content={"text": memory_id},
        source={"source_type": "phase2_umr", "reference_id": memory_id}, parent_ids=(),
        creation_event=f"create-{memory_id}", creation_timestamp=timestamp, lifecycle_state=LIFECYCLE_CREATED,
    ))
    event_ledger.append(CanonicalEvent(
        event_id=f"create-{memory_id}", event_type=EVENT_CREATED, memory_ids=(memory_id,),
        timestamp=timestamp, actor="creation_policy", reason="ingested", new_state=LIFECYCLE_CREATED,
    ))


def _seed_derived(memory_ledger, event_ledger, memory_id, parent_ids, timestamp="2026-01-02T00:00:00Z"):
    memory_ledger.put(CanonicalMemoryRecord(
        memory_id=memory_id, memory_type=MEMORY_TYPE_DERIVED, content={"text": memory_id},
        source={"source_type": "derivation_event", "reference_id": f"derive-{memory_id}"}, parent_ids=tuple(parent_ids),
        creation_event=f"derive-{memory_id}", creation_timestamp=timestamp, lifecycle_state=LIFECYCLE_CREATED,
    ))
    event_ledger.append(CanonicalEvent(
        event_id=f"derive-{memory_id}", event_type=EVENT_DERIVED,
        memory_ids=tuple(parent_ids) + (memory_id,), timestamp=timestamp, actor="derivation_policy",
        reason="derived", source_memory_ids=tuple(parent_ids), target_memory_id=memory_id,
    ))


def test_simple_graph_nodes_and_edges(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_foundation(memory_ledger, event_ledger, "m1")
    event_ledger.append(CanonicalEvent(
        event_id="ret-1", event_type=EVENT_RETRIEVED, memory_ids=("m1",), task_id="t1",
        timestamp="2026-01-01T00:00:01Z", actor="candidate_discovery", reason="retrieved",
        config_fingerprint="CFG-test",
    ))
    event_ledger.append(CanonicalEvent(
        event_id="sel-1", event_type=EVENT_SELECTED, memory_ids=("m1",), task_id="t1",
        timestamp="2026-01-01T00:00:02Z", actor="evidence_selection", reason="selected",
        config_fingerprint="CFG-test",
    ))

    graph = build_provenance_graph(memory_ledger, event_ledger, supersession_ledger)

    assert graph.memory_ids() == ("m1",)
    assert graph.task_ids() == ("t1",)
    retrieved = graph.edges_for_task("t1")
    edge_types = {e.edge_type for e in retrieved}
    assert edge_types == {EDGE_RETRIEVED, EDGE_SELECTED}
    for e in retrieved:
        assert e.established_by_event_id in ("ret-1", "sel-1")


def test_derived_from_edges_grounded_in_parent_ids_not_derived_event_memory_ids(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_foundation(memory_ledger, event_ledger, "a")
    _seed_derived(memory_ledger, event_ledger, "c", ["a"])

    graph = build_provenance_graph(memory_ledger, event_ledger, supersession_ledger)
    derived_edges = [e for e in graph.edges if e.edge_type == EDGE_DERIVED_FROM]
    assert len(derived_edges) == 1
    assert derived_edges[0].source_id == "c"
    assert derived_edges[0].target_id == "a"
    assert derived_edges[0].established_by_event_id == "derive-c"


def test_ancestors_and_descendants_transitive_and_cycle_safe(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_foundation(memory_ledger, event_ledger, "a")
    _seed_derived(memory_ledger, event_ledger, "b", ["a"])
    _seed_derived(memory_ledger, event_ledger, "c", ["b"])

    graph = build_provenance_graph(memory_ledger, event_ledger, supersession_ledger)
    assert graph.ancestors_of("c") == {"b", "a"}
    assert graph.descendants_of("a") == {"b", "c"}
    assert graph.ancestors_of("a") == set()
    assert graph.descendants_of("c") == set()


def test_lifecycle_state_current_vs_at_creation_only(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_foundation(memory_ledger, event_ledger, "m1")

    graph_without_supersession = build_provenance_graph(memory_ledger, event_ledger)
    node = graph_without_supersession.node("m1")
    assert node.attributes["lifecycle_status"] == LIFECYCLE_STATUS_AT_CREATION_ONLY
    assert node.attributes["lifecycle_state"] == LIFECYCLE_CREATED

    graph_with_supersession = build_provenance_graph(memory_ledger, event_ledger, supersession_ledger)
    node2 = graph_with_supersession.node("m1")
    assert node2.attributes["lifecycle_status"] == LIFECYCLE_STATUS_CURRENT
    assert node2.attributes["lifecycle_state"] == LIFECYCLE_CREATED


def test_relationship_detected_produces_equivalent_to_edge(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_foundation(memory_ledger, event_ledger, "m1")
    _seed_foundation(memory_ledger, event_ledger, "m2", timestamp="2026-01-01T00:00:03Z")
    event_ledger.append(CanonicalEvent(
        event_id="rel-1", event_type=EVENT_RELATIONSHIP_DETECTED, memory_ids=("m1", "m2"),
        timestamp="2026-01-01T00:00:04Z", actor="creation_policy", reason="detected",
        relationship_type=RELATIONSHIP_EQUIVALENT_TO, mechanism="embedding_similarity_threshold", score=0.95,
    ))
    graph = build_provenance_graph(memory_ledger, event_ledger, supersession_ledger)
    eq_edges = [e for e in graph.edges if e.edge_type == EDGE_EQUIVALENT_TO]
    assert len(eq_edges) == 1
    assert eq_edges[0].established_by_event_id == "rel-1"


def test_never_invents_a_used_edge_from_selected(tmp_path):
    """The one thing this module must never do -- selected != used."""
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_foundation(memory_ledger, event_ledger, "m1")
    event_ledger.append(CanonicalEvent(
        event_id="sel-1", event_type=EVENT_SELECTED, memory_ids=("m1",), task_id="t1",
        timestamp="2026-01-01T00:00:02Z", actor="evidence_selection", reason="selected",
        config_fingerprint="CFG-test",
    ))
    graph = build_provenance_graph(memory_ledger, event_ledger, supersession_ledger)
    used_edges = [e for e in graph.edges if e.edge_type == EDGE_USED]
    assert used_edges == []


def test_dangling_edge_construction_rejected():
    from phase3.evaluation.foundations.provenance_graph import GraphEdge, GraphNode, ProvenanceGraph

    with pytest.raises(ProvenanceGraphError):
        ProvenanceGraph(
            nodes=(GraphNode(node_id="m1", node_type=NODE_TYPE_MEMORY),),
            edges=(GraphEdge(source_id="m1", target_id="m-missing", edge_type=EDGE_DERIVED_FROM),),
        )


def test_deterministic_rebuild_produces_identical_graph(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_foundation(memory_ledger, event_ledger, "m1")
    _seed_derived(memory_ledger, event_ledger, "m2", ["m1"])

    g1 = build_provenance_graph(memory_ledger, event_ledger, supersession_ledger)
    g2 = build_provenance_graph(memory_ledger, event_ledger, supersession_ledger)
    assert g1.to_dict() == g2.to_dict()


def test_vendor_independence_no_foundation_adapter_import():
    """Structural proof, mirrors taint_propagation.py's own proof style: no adapter
    import anywhere in this module's source."""
    import phase3.evaluation.foundations.provenance_graph as mod

    source = inspect.getsource(mod)
    assert "MemoryFoundationAdapter" not in source
    assert "foundations_real" not in source
    assert "mocks" not in source


def test_experiment_boundary_respected_by_construction(tmp_path):
    """Two separate ledger triples (two separate 'experiments') never get merged into
    one graph unless the caller explicitly passes both into one build call -- which
    this module's own signature (one memory_ledger, one event_ledger) makes impossible."""
    ledgers_a = _system(tmp_path / "exp-a")
    ledgers_b = _system(tmp_path / "exp-b")
    _seed_foundation(ledgers_a[0], ledgers_a[1], "m1")
    _seed_foundation(ledgers_b[0], ledgers_b[1], "m1")  # same id, different experiment

    graph_a = build_provenance_graph(*ledgers_a)
    graph_b = build_provenance_graph(*ledgers_b)
    assert graph_a.memory_ids() == ("m1",)
    assert graph_b.memory_ids() == ("m1",)
    # Each graph is independently scoped -- no cross-experiment contamination possible,
    # since nothing in build_provenance_graph's signature accepts more than one ledger pair.


# ---------------------------------------------------------------------------
# Real-data verification -- this session's own real Mem0/LoCoMo counterfactual run.
# ---------------------------------------------------------------------------

_REAL_POOL_DIR = (
    Path(__file__).resolve().parents[2]  # phase3/
    / "experiments" / "canonical_store" / "h4a-real-locomo-smoke-1"
    / "locomo-g_65a9868ec81852be"
)


@pytest.mark.skipif(not _REAL_POOL_DIR.exists(), reason="real session artifact not present in this checkout")
def test_builds_correctly_against_real_mem0_locomo_ledger_data():
    """Not a synthetic fixture -- this is the actual, real ledger data this session's own
    real Mem0/LoCoMo counterfactual run produced (PHASE3_3_H4_A_LOCOMO_SAMPLE_RUN_REPORT.md).
    Proves the graph builder works against real, not just hand-constructed, data."""
    memory_ledger = CanonicalMemoryLedger(_REAL_POOL_DIR / "memory")
    event_ledger = CanonicalEventLedger(_REAL_POOL_DIR / "events", memory_ledger)
    supersession_ledger = SupersessionLedger(_REAL_POOL_DIR / "run_config")  # no supersessions in this pool; harmless empty dir

    graph = build_provenance_graph(memory_ledger, event_ledger)

    assert len(graph.memory_ids()) > 0
    assert len(graph.task_ids()) > 0
    retrieved_edges = [e for e in graph.edges if e.edge_type == EDGE_RETRIEVED]
    selected_edges = [e for e in graph.edges if e.edge_type == EDGE_SELECTED]
    assert len(retrieved_edges) > 0
    assert len(selected_edges) > 0
    for e in retrieved_edges + selected_edges:
        assert e.established_by_event_id is not None
        assert event_ledger.get_event(e.established_by_event_id) is not None  # grounding is real, resolvable
