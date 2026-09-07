"""Phase 3.3-H4-PROVENANCE-GRAPH extension tests -- memory-version nodes, experiment-
boundary nodes, multi-boundary composition, the named Phase-4-facing query catalog, and
the `provenance_graph_schema.json` export schema. Per
PHASE3_PROVENANCE_GRAPH_DESIGN_REVIEW.md, implemented after review, not before.
"""

from __future__ import annotations

import json

import jsonschema
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
    EVENT_RETIRED,
    EVENT_SELECTED,
    EVENT_SUPERSEDED,
)
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase3.evaluation.foundations.memory_versioning import SupersessionLedger, supersede_memory
from phase3.evaluation.foundations.provenance_graph import (
    EDGE_DERIVED_FROM,
    EDGE_HAS_VERSION,
    EDGE_SELECTED,
    EDGE_WITHIN_BOUNDARY,
    NODE_TYPE_EXPERIMENT_BOUNDARY,
    NODE_TYPE_MEMORY_VERSION,
    SCHEMA_PATH,
    ProvenanceGraphError,
    attack_origin_lineage,
    backward_provenance,
    build_multi_boundary_provenance_graph,
    build_provenance_graph,
    derivation_propagation,
    forward_provenance,
    task_exposure_and_use,
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


# ---------------------------------------------------------------------------
# Memory-version nodes
# ---------------------------------------------------------------------------


def test_include_versions_attaches_version_nodes(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_foundation(memory_ledger, event_ledger, "m1")
    memory_ledger.put(CanonicalMemoryRecord(
        memory_id="m2", memory_type=MEMORY_TYPE_FOUNDATION, content={"text": "m2"},
        source={"source_type": "phase2_umr", "reference_id": "m2"}, parent_ids=(),
        creation_event="create-m2", creation_timestamp="2026-01-01T00:00:01Z", lifecycle_state=LIFECYCLE_CREATED,
    ))
    event_ledger.append(CanonicalEvent(
        event_id="create-m2", event_type=EVENT_CREATED, memory_ids=("m2",),
        timestamp="2026-01-01T00:00:01Z", actor="creation_policy", reason="ingested", new_state=LIFECYCLE_CREATED,
    ))
    result = supersede_memory(
        event_ledger, memory_ledger, supersession_ledger,
        superseded_memory_id="m1", superseding_memory_id="m2",
        superseded_event=CanonicalEvent(
            event_id="ev-sup", event_type=EVENT_SUPERSEDED, memory_ids=("m1",),
            timestamp="2026-01-01T00:00:02Z", actor="creation_policy", reason="m2 supersedes m1",
            previous_state=LIFECYCLE_CREATED, new_state=LIFECYCLE_RETIRED,
        ),
        retired_event=CanonicalEvent(
            event_id="ev-ret", event_type=EVENT_RETIRED, memory_ids=("m1",),
            timestamp="2026-01-01T00:00:03Z", actor="creation_policy", reason="m1 retired",
            previous_state=LIFECYCLE_CREATED, new_state=LIFECYCLE_RETIRED,
        ),
    )

    graph = build_provenance_graph(memory_ledger, event_ledger, supersession_ledger, include_versions=True)
    version_nodes = graph.nodes_of_type(NODE_TYPE_MEMORY_VERSION)
    m1_versions = [n for n in version_nodes if n.attributes["memory_id"] == "m1"]
    # H.3's own established behavior (test_11_version_history_reconstructs_correctly):
    # created -> v1, superseded -> v2 (the A->B linkage), retired -> v3 (terminal state) --
    # three versions, not two; the `superseded` event produces its own version distinct
    # from `retired`, per PHASE3_3_H3_MEMORY_VERSIONING.md section 11.
    assert len(m1_versions) == 3
    assert {n.attributes["lifecycle_state"] for n in m1_versions} == {LIFECYCLE_CREATED, LIFECYCLE_RETIRED}

    has_version_edges = [e for e in graph.edges if e.edge_type == EDGE_HAS_VERSION and e.source_id == "m1"]
    assert len(has_version_edges) == 3
    for e in has_version_edges:
        assert e.established_by_event_id in ("create-m1", "ev-sup", "ev-ret")


def test_include_versions_false_by_default_no_behavior_change(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_foundation(memory_ledger, event_ledger, "m1")
    graph = build_provenance_graph(memory_ledger, event_ledger, supersession_ledger)
    assert graph.nodes_of_type(NODE_TYPE_MEMORY_VERSION) == ()


# ---------------------------------------------------------------------------
# Experiment boundary nodes / multi-boundary composition
# ---------------------------------------------------------------------------


def test_single_boundary_label_prefixes_ids_and_adds_boundary_node(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_foundation(memory_ledger, event_ledger, "m1")
    graph = build_provenance_graph(memory_ledger, event_ledger, supersession_ledger, boundary_label="clean")
    assert "clean::m1" in graph.memory_ids()
    boundary_nodes = graph.nodes_of_type(NODE_TYPE_EXPERIMENT_BOUNDARY)
    assert len(boundary_nodes) == 1
    assert boundary_nodes[0].node_id == "boundary::clean"
    within_edges = [e for e in graph.edges if e.edge_type == EDGE_WITHIN_BOUNDARY]
    assert len(within_edges) == 1
    assert within_edges[0].source_id == "clean::m1"
    # canonical_id preserved despite the prefixed node_id -- identity requirement.
    assert graph.node("clean::m1").attributes["canonical_id"] == "m1"


def test_no_boundary_label_unprefixed_backward_compatible(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_foundation(memory_ledger, event_ledger, "m1")
    graph = build_provenance_graph(memory_ledger, event_ledger, supersession_ledger)
    assert graph.memory_ids() == ("m1",)
    assert graph.nodes_of_type(NODE_TYPE_EXPERIMENT_BOUNDARY) == ()


def test_multi_boundary_composes_two_experiments_with_same_memory_id(tmp_path):
    clean_dir = tmp_path / "clean"
    manipulated_dir = tmp_path / "manipulated"
    clean = _system(clean_dir)
    manipulated = _system(manipulated_dir)
    _seed_foundation(clean[0], clean[1], "m1")
    _seed_foundation(manipulated[0], manipulated[1], "m1")  # same canonical id, different experiment

    graph = build_multi_boundary_provenance_graph([
        ("clean", *clean),
        ("manipulated", *manipulated),
    ])

    assert "clean::m1" in graph.memory_ids()
    assert "manipulated::m1" in graph.memory_ids()
    assert len(graph.nodes_of_type(NODE_TYPE_EXPERIMENT_BOUNDARY)) == 2


def test_multi_boundary_never_synthesizes_cross_boundary_edges(tmp_path):
    """The one invariant that matters most for this feature: no edge may ever connect a
    node from one boundary to a node from another."""
    clean_dir = tmp_path / "clean"
    manipulated_dir = tmp_path / "manipulated"
    clean = _system(clean_dir)
    manipulated = _system(manipulated_dir)
    _seed_foundation(clean[0], clean[1], "m1")
    memory_ledger_c, event_ledger_c, _ = clean
    memory_ledger_c.put(CanonicalMemoryRecord(
        memory_id="m2", memory_type=MEMORY_TYPE_DERIVED, content={"text": "m2"},
        source={"source_type": "derivation_event", "reference_id": "derive-m2"}, parent_ids=("m1",),
        creation_event="derive-m2", creation_timestamp="2026-01-01T00:00:01Z", lifecycle_state=LIFECYCLE_CREATED,
    ))
    event_ledger_c.append(CanonicalEvent(
        event_id="derive-m2", event_type=EVENT_DERIVED, memory_ids=("m1", "m2"),
        timestamp="2026-01-01T00:00:01Z", actor="derivation_policy", reason="derived",
        source_memory_ids=("m1",), target_memory_id="m2",
    ))
    _seed_foundation(manipulated[0], manipulated[1], "m1")

    graph = build_multi_boundary_provenance_graph([("clean", *clean), ("manipulated", *manipulated)])

    def boundary_of(node_id: str) -> str:
        return node_id.split("::", 1)[0]

    for e in graph.edges:
        if e.edge_type == EDGE_WITHIN_BOUNDARY:
            continue  # these intentionally connect a boundary's own nodes to the boundary node itself
        assert boundary_of(e.source_id) == boundary_of(e.target_id), (
            f"cross-boundary edge found: {e.source_id} -> {e.target_id} ({e.edge_type})"
        )


def test_multi_boundary_rejects_duplicate_labels(tmp_path):
    a = _system(tmp_path / "a")
    b = _system(tmp_path / "b")
    with pytest.raises(ProvenanceGraphError):
        build_multi_boundary_provenance_graph([("same", *a), ("same", *b)])


# ---------------------------------------------------------------------------
# Named query catalog
# ---------------------------------------------------------------------------


def test_forward_and_backward_provenance_match_existing_primitives(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_foundation(memory_ledger, event_ledger, "a")
    memory_ledger.put(CanonicalMemoryRecord(
        memory_id="b", memory_type=MEMORY_TYPE_DERIVED, content={"text": "b"},
        source={"source_type": "derivation_event", "reference_id": "derive-b"}, parent_ids=("a",),
        creation_event="derive-b", creation_timestamp="2026-01-02T00:00:00Z", lifecycle_state=LIFECYCLE_CREATED,
    ))
    event_ledger.append(CanonicalEvent(
        event_id="derive-b", event_type=EVENT_DERIVED, memory_ids=("a", "b"),
        timestamp="2026-01-02T00:00:00Z", actor="derivation_policy", reason="derived",
        source_memory_ids=("a",), target_memory_id="b",
    ))
    graph = build_provenance_graph(memory_ledger, event_ledger, supersession_ledger)

    assert forward_provenance(graph, "a") == graph.descendants_of("a") == {"b"}
    assert backward_provenance(graph, "b") == graph.ancestors_of("b") == {"a"}
    assert derivation_propagation(graph, "a") == forward_provenance(graph, "a")


def test_task_exposure_and_use_groups_by_edge_type(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_foundation(memory_ledger, event_ledger, "m1")
    event_ledger.append(CanonicalEvent(
        event_id="sel-1", event_type=EVENT_SELECTED, memory_ids=("m1",), task_id="t1",
        timestamp="2026-01-01T00:00:01Z", actor="evidence_selection", reason="selected",
        config_fingerprint="CFG-test",
    ))
    graph = build_provenance_graph(memory_ledger, event_ledger, supersession_ledger)
    result = task_exposure_and_use(graph, "t1")
    assert result == {EDGE_SELECTED: ("m1",)}
    assert "retrieved" not in result  # never a fabricated empty entry


def test_attack_origin_lineage_reuses_taint_propagation_directly(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_foundation(memory_ledger, event_ledger, "attack")
    memory_ledger.put(CanonicalMemoryRecord(
        memory_id="leaf", memory_type=MEMORY_TYPE_DERIVED, content={"text": "leaf"},
        source={"source_type": "derivation_event", "reference_id": "derive-leaf"}, parent_ids=("attack",),
        creation_event="derive-leaf", creation_timestamp="2026-01-02T00:00:00Z", lifecycle_state=LIFECYCLE_CREATED,
    ))
    event_ledger.append(CanonicalEvent(
        event_id="derive-leaf", event_type=EVENT_DERIVED, memory_ids=("attack", "leaf"),
        timestamp="2026-01-02T00:00:00Z", actor="derivation_policy", reason="derived",
        source_memory_ids=("attack",), target_memory_id="leaf",
    ))
    graph = build_provenance_graph(memory_ledger, event_ledger, supersession_ledger)

    report = attack_origin_lineage(
        graph, memory_ledger, ["attack"], event_ledger=event_ledger, supersession_ledger=supersession_ledger,
    )
    assert report.tainted_memory_ids == ("leaf",)
    # And the graph's own primitive agrees -- same underlying fact, two access paths.
    assert set(report.tainted_memory_ids) == forward_provenance(graph, "attack")


# ---------------------------------------------------------------------------
# Export schema
# ---------------------------------------------------------------------------


def test_to_dict_output_validates_against_schema(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_foundation(memory_ledger, event_ledger, "m1")
    event_ledger.append(CanonicalEvent(
        event_id="sel-1", event_type=EVENT_SELECTED, memory_ids=("m1",), task_id="t1",
        timestamp="2026-01-01T00:00:01Z", actor="evidence_selection", reason="selected",
        config_fingerprint="CFG-test",
    ))
    graph = build_provenance_graph(memory_ledger, event_ledger, supersession_ledger, boundary_label="clean", include_versions=True)

    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = json.load(f)
    jsonschema.validate(instance=graph.to_dict(), schema=schema)  # raises on any violation
