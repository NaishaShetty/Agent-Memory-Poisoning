"""Phase 3.2-D tests for `phase3/evaluation/metrics/provenance.py`.

Scope note: this suite tests provenance validation, ancestry/descendant traversal, cycle
detection, orphan detection, lineage depth, root-origin analysis, and the lineage-based
evidence independence diagnostic. It does not modify, re-run, or depend on
`test_evaluation_contracts.py` or `test_core_memory_metrics.py`, which must remain green,
unmodified, alongside this file.

Uses the 12 JSON fixtures under `phase3/evaluation/fixtures/lineage/` for the worked,
cross-module scenarios, plus small literal Python dicts for isolated unit cases.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from phase3.evaluation.metrics import provenance as provenance_mod
from phase3.evaluation.metrics.provenance import (
    validate_parent_edges,
    orphan_parent_count,
    detect_cycles,
    ancestors,
    descendants,
    root_origins,
    shared_origin_report,
    lineage_depth,
    validate_provenance,
    independence_report,
    PROVENANCE_COMPLETE,
    PROVENANCE_INCOMPLETE,
    PROVENANCE_INVALID,
    CLASS_LINEAGE_INDEPENDENT,
    CLASS_SHARED_LINEAGE_ORIGIN,
    CLASS_DIRECT_ANCESTOR_DESCENDANT,
    CLASS_EQUIVALENT_INFORMATION,
    FINDING_ORPHAN_PARENT_REFERENCE,
)
from phase3.evaluation.metrics.types import STATUS_OK, STATUS_UNDEFINED_EMPTY_SEQUENCE

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "lineage"


def _load(name: str) -> dict:
    with open(FIXTURES_DIR / name, "r", encoding="utf-8") as f:
        return json.load(f)


def _mem(memory_id, memory_type="foundation", parent_ids=None, **extra):
    record = {
        "memory_id": memory_id,
        "memory_type": memory_type,
        "content": {"text": f"content for {memory_id}"},
        "source": {
            "source_type": "phase2_umr" if memory_type == "foundation" else "derivation_event",
            "reference_id": f"ref-{memory_id}",
        },
        "parent_ids": parent_ids or [],
        "creation_event": f"evt-{memory_id}",
        "creation_timestamp": "2026-08-01T00:00:00Z",
        "lifecycle_state": "ACTIVE",
    }
    record.update(extra)
    return record


# ---------------------------------------------------------------------------
# Scenario 1: independent memories
# ---------------------------------------------------------------------------


def test_fixture_01_independent_no_ancestors():
    data = _load("01_independent.json")["memories"]
    assert ancestors(data, "mem-lin-A").detail["ancestors"] == []
    assert ancestors(data, "mem-lin-B").detail["ancestors"] == []


def test_fixture_01_independent_classified_lineage_independent():
    data = _load("01_independent.json")["memories"]
    result = independence_report(data, ["mem-lin-A", "mem-lin-B"])
    assert result.detail["pairwise"]["mem-lin-A|mem-lin-B"] == CLASS_LINEAGE_INDEPENDENT


# ---------------------------------------------------------------------------
# Scenario 2: direct derivation A -> B
# ---------------------------------------------------------------------------


def test_fixture_02_direct_derivation_ancestry():
    data = _load("02_direct_derivation.json")["memories"]
    assert ancestors(data, "mem-lin-B").detail["ancestors"] == ["mem-lin-A"]
    assert descendants(data, "mem-lin-A").detail["descendants"] == ["mem-lin-B"]


def test_fixture_02_direct_ancestor_descendant_classification():
    data = _load("02_direct_derivation.json")["memories"]
    result = independence_report(data, ["mem-lin-A", "mem-lin-B"])
    assert (
        result.detail["pairwise"]["mem-lin-A|mem-lin-B"]
        == CLASS_DIRECT_ANCESTOR_DESCENDANT
    )


def test_fixture_02_depths():
    data = _load("02_direct_derivation.json")["memories"]
    assert lineage_depth(data, "mem-lin-A").value == 0.0
    assert lineage_depth(data, "mem-lin-B").value == 1.0


# ---------------------------------------------------------------------------
# Scenario 3: chain A -> B -> C
# ---------------------------------------------------------------------------


def test_fixture_03_chain_ancestry_and_descendants():
    data = _load("03_chain.json")["memories"]
    assert set(ancestors(data, "mem-lin-C").detail["ancestors"]) == {"mem-lin-A", "mem-lin-B"}
    assert set(descendants(data, "mem-lin-A").detail["descendants"]) == {"mem-lin-B", "mem-lin-C"}


def test_fixture_03_chain_depths():
    data = _load("03_chain.json")["memories"]
    assert lineage_depth(data, "mem-lin-A").value == 0.0
    assert lineage_depth(data, "mem-lin-B").value == 1.0
    assert lineage_depth(data, "mem-lin-C").value == 2.0


def test_fixture_03_a_and_c_are_ancestor_descendant_not_independent():
    data = _load("03_chain.json")["memories"]
    result = independence_report(data, ["mem-lin-A", "mem-lin-C"])
    assert (
        result.detail["pairwise"]["mem-lin-A|mem-lin-C"]
        == CLASS_DIRECT_ANCESTOR_DESCENDANT
    )


# ---------------------------------------------------------------------------
# Scenario 4: branching A -> B, A -> C
# ---------------------------------------------------------------------------


def test_fixture_04_branching_descendants_of_root():
    data = _load("04_branching.json")["memories"]
    assert set(descendants(data, "mem-lin-A").detail["descendants"]) == {
        "mem-lin-B",
        "mem-lin-C",
    }


def test_fixture_04_siblings_share_lineage_origin():
    data = _load("04_branching.json")["memories"]
    result = independence_report(data, ["mem-lin-B", "mem-lin-C"])
    assert (
        result.detail["pairwise"]["mem-lin-B|mem-lin-C"] == CLASS_SHARED_LINEAGE_ORIGIN
    )


# ---------------------------------------------------------------------------
# Scenario 5: multi-parent A -> C, B -> C
# ---------------------------------------------------------------------------


def test_fixture_05_multi_parent_retains_both_parents():
    data = _load("05_multi_parent.json")["memories"]
    assert sorted(data["mem-lin-C"]["parent_ids"]) == ["mem-lin-A", "mem-lin-B"]


def test_fixture_05_multi_parent_root_origins_two_distinct_roots():
    data = _load("05_multi_parent.json")["memories"]
    result = root_origins(data, "mem-lin-C")
    assert sorted(result.detail["roots"]) == ["mem-lin-A", "mem-lin-B"]
    assert result.value == 2.0


def test_fixture_05_multi_parent_no_synthetic_family_id():
    """No function anywhere collapses A,B into a single family/origin id -- ancestors(C)
    must list both A and B explicitly, never a merged identifier."""
    data = _load("05_multi_parent.json")["memories"]
    anc = ancestors(data, "mem-lin-C").detail["ancestors"]
    assert set(anc) == {"mem-lin-A", "mem-lin-B"}


# ---------------------------------------------------------------------------
# Scenario 6/7/8: equivalence-related (cross-checked here for lineage non-implication)
# ---------------------------------------------------------------------------


def test_fixture_06_equivalence_pair_has_no_lineage_edges():
    data = _load("06_equivalence_pair.json")["memories"]
    assert ancestors(data, "mem-lin-A").detail["ancestors"] == []
    assert ancestors(data, "mem-lin-B").detail["ancestors"] == []


def test_fixture_06_equivalent_pair_classified_equivalent_information():
    data = _load("06_equivalence_pair.json")["memories"]
    result = independence_report(data, ["mem-lin-A", "mem-lin-B"])
    assert (
        result.detail["pairwise"]["mem-lin-A|mem-lin-B"] == CLASS_EQUIVALENT_INFORMATION
    )


def test_fixture_08_equivalence_does_not_imply_lineage():
    """A≡B is declared; A also has a real child C. B must NOT be reported as an ancestor
    of C, proving equivalence never implies a lineage edge."""
    data = _load("08_equivalence_and_lineage.json")["memories"]
    anc_of_c = ancestors(data, "mem-lin-C").detail["ancestors"]
    assert anc_of_c == ["mem-lin-A"]
    assert "mem-lin-B" not in anc_of_c


def test_fixture_08_lineage_does_not_imply_equivalence():
    """A->C is a lineage edge; A and C must not be reported equivalent."""
    data = _load("08_equivalence_and_lineage.json")["memories"]
    result = independence_report(data, ["mem-lin-A", "mem-lin-C"])
    assert (
        result.detail["pairwise"]["mem-lin-A|mem-lin-C"]
        == CLASS_DIRECT_ANCESTOR_DESCENDANT
    )
    assert (
        result.detail["pairwise"]["mem-lin-A|mem-lin-C"] != CLASS_EQUIVALENT_INFORMATION
    )


# ---------------------------------------------------------------------------
# Scenario 9: orphan reference
# ---------------------------------------------------------------------------


def test_fixture_09_orphan_parent_reference_detected():
    data = _load("09_orphan_reference.json")["memories"]
    result = validate_parent_edges(data)
    assert result.detail["orphan_parent_reference_count"] == 1
    assert "mem-lin-X->mem-lin-A" in result.detail["orphan_edges"]


def test_fixture_09_orphan_parent_count():
    data = _load("09_orphan_reference.json")["memories"]
    result = orphan_parent_count(data)
    assert result.value == 1.0
    assert result.detail["orphaned_children"] == ["mem-lin-A"]


def test_fixture_09_orphan_reference_not_repaired():
    """The orphan parent id must never be invented or silently dropped from the report --
    it appears verbatim in the orphan edge string."""
    data = _load("09_orphan_reference.json")["memories"]
    result = validate_parent_edges(data)
    assert any("mem-lin-X" in edge for edge in result.detail["orphan_edges"])


def test_fixture_09_provenance_classified_invalid():
    data = _load("09_orphan_reference.json")["memories"]
    result = validate_provenance(data, "mem-lin-A")
    assert result.detail["classification"] == PROVENANCE_INVALID
    assert FINDING_ORPHAN_PARENT_REFERENCE in result.detail["findings"]


# ---------------------------------------------------------------------------
# Scenario 10: cycle A -> B -> C -> A
# ---------------------------------------------------------------------------


def test_fixture_10_cycle_detected():
    data = _load("10_cycle.json")["memories"]
    result = detect_cycles(data)
    assert result.value >= 1.0
    assert len(result.detail["cycles"]) >= 1


def test_fixture_10_cycle_traversal_terminates_for_ancestors():
    """Ancestor traversal on a cyclic node must terminate (not hang) and report
    cycle_detected=True rather than looping forever."""
    data = _load("10_cycle.json")["memories"]
    result = ancestors(data, "mem-lin-A")
    assert result.status == STATUS_OK
    assert result.detail["cycle_detected"] is True


def test_fixture_10_cycle_traversal_terminates_for_descendants():
    data = _load("10_cycle.json")["memories"]
    result = descendants(data, "mem-lin-A")
    assert result.status == STATUS_OK
    assert result.detail["cycle_detected"] is True


def test_fixture_10_lineage_depth_undefined_on_cycle():
    data = _load("10_cycle.json")["memories"]
    result = lineage_depth(data, "mem-lin-A")
    assert result.value is None
    assert result.status == STATUS_UNDEFINED_EMPTY_SEQUENCE


def test_fixture_10_cycle_not_repaired():
    """detect_cycles must report the cycle members verbatim, never dropping an edge to
    'fix' the graph."""
    data = _load("10_cycle.json")["memories"]
    result = detect_cycles(data)
    all_cycle_members = {m for cycle in result.detail["cycles"] for m in cycle}
    assert {"mem-lin-A", "mem-lin-B", "mem-lin-C"}.issubset(all_cycle_members)


# ---------------------------------------------------------------------------
# Scenario 11: equivalent selected evidence
# ---------------------------------------------------------------------------


def test_fixture_11_equivalent_selected_not_lineage_independent():
    data = _load("11_equivalent_selected_evidence.json")
    result = independence_report(data["memories"], data["selected_memory_ids"])
    classification = result.detail["pairwise"]["mem-lin-A|mem-lin-B"]
    assert classification == CLASS_EQUIVALENT_INFORMATION
    assert classification != CLASS_LINEAGE_INDEPENDENT


# ---------------------------------------------------------------------------
# Scenario 12: shared origin selected
# ---------------------------------------------------------------------------


def test_fixture_12_shared_origin_detected_for_selected_pair():
    data = _load("12_shared_origin_selected.json")
    result = shared_origin_report(data["memories"], data["selected_memory_ids"])
    assert result.value == 1.0
    assert "mem-lin-A" in result.detail["shared_roots"]
    assert sorted(result.detail["shared_roots"]["mem-lin-A"]) == ["mem-lin-B", "mem-lin-C"]


def test_fixture_12_independence_report_classifies_shared_origin():
    data = _load("12_shared_origin_selected.json")
    result = independence_report(data["memories"], data["selected_memory_ids"])
    classification = result.detail["pairwise"]["mem-lin-B|mem-lin-C"]
    assert classification == CLASS_SHARED_LINEAGE_ORIGIN
    assert classification != CLASS_LINEAGE_INDEPENDENT


# ---------------------------------------------------------------------------
# Provenance completeness: COMPLETE / INCOMPLETE / INVALID
# ---------------------------------------------------------------------------


def test_provenance_complete_foundation_memory():
    memories = {"A": _mem("A", memory_type="foundation")}
    result = validate_provenance(memories, "A")
    assert result.detail["classification"] == PROVENANCE_COMPLETE


def test_provenance_complete_derived_memory_with_parent():
    memories = {
        "A": _mem("A", memory_type="foundation"),
        "B": _mem("B", memory_type="derived", parent_ids=["A"]),
    }
    result = validate_provenance(memories, "B")
    assert result.detail["classification"] == PROVENANCE_COMPLETE


def test_provenance_invalid_foundation_with_parents():
    memories = {
        "A": _mem("A", memory_type="foundation"),
        "B": _mem("B", memory_type="foundation", parent_ids=["A"]),
    }
    result = validate_provenance(memories, "B")
    assert result.detail["classification"] == PROVENANCE_INVALID
    assert "FOUNDATION_WITH_PARENTS" in result.detail["findings"]


def test_provenance_invalid_derived_without_parents():
    memories = {"B": _mem("B", memory_type="derived", parent_ids=[])}
    result = validate_provenance(memories, "B")
    assert result.detail["classification"] == PROVENANCE_INVALID
    assert "DERIVED_WITHOUT_PARENTS" in result.detail["findings"]


def test_provenance_invalid_bad_memory_type():
    memories = {"A": _mem("A", memory_type="not_a_real_type")}
    result = validate_provenance(memories, "A")
    assert result.detail["classification"] == PROVENANCE_INVALID


def test_provenance_incomplete_missing_source_reference_id():
    memories = {
        "A": _mem("A", memory_type="foundation"),
        "B": _mem(
            "B",
            memory_type="derived",
            parent_ids=["A"],
            source={"source_type": "derivation_event"},
        ),
    }
    result = validate_provenance(memories, "B")
    assert result.detail["classification"] == PROVENANCE_INCOMPLETE
    assert "MISSING_SOURCE_REFERENCE_ID" in result.detail["incomplete_findings"]


def test_provenance_never_silently_coerces_missing_to_complete():
    memories = {"A": {"memory_id": "A"}}  # missing memory_type, source, parent_ids
    result = validate_provenance(memories, "A")
    assert result.detail["classification"] != PROVENANCE_COMPLETE
    assert result.detail["classification"] == PROVENANCE_INVALID


def test_provenance_unknown_memory_undefined():
    result = validate_provenance({}, "ghost")
    assert result.value is None
    assert result.status == STATUS_UNDEFINED_EMPTY_SEQUENCE


# ---------------------------------------------------------------------------
# Parent/lineage edge validation: no family collapsing
# ---------------------------------------------------------------------------


def test_multi_parent_edges_never_collapsed():
    memories = {
        "A": _mem("A"),
        "B": _mem("B"),
        "C": _mem("C", memory_type="derived", parent_ids=["A", "B"]),
    }
    result = validate_parent_edges(memories)
    assert result.detail["total_edges"] == 2
    edge_strs = set()
    for child_id, record in memories.items():
        for p in record["parent_ids"]:
            edge_strs.add(f"{p}->{child_id}")
    assert edge_strs == {"A->C", "B->C"}


# ---------------------------------------------------------------------------
# Ancestor/descendant: never own ancestor/descendant on acyclic input
# ---------------------------------------------------------------------------


def test_node_never_its_own_ancestor_on_acyclic_input():
    data = _load("03_chain.json")["memories"]
    for mid in data:
        anc = ancestors(data, mid).detail["ancestors"]
        assert mid not in anc


def test_node_never_its_own_descendant_on_acyclic_input():
    data = _load("03_chain.json")["memories"]
    for mid in data:
        desc = descendants(data, mid).detail["descendants"]
        assert mid not in desc


def test_ancestors_include_self_param():
    data = _load("03_chain.json")["memories"]
    result = ancestors(data, "mem-lin-C", include_self=True)
    assert "mem-lin-C" in result.detail["ancestors"]


# ---------------------------------------------------------------------------
# Empty / single-node / disconnected graph edge cases
# ---------------------------------------------------------------------------


def test_empty_graph_ancestors_undefined():
    result = ancestors({}, "ghost")
    assert result.value is None
    assert result.status == STATUS_UNDEFINED_EMPTY_SEQUENCE


def test_single_node_graph_no_ancestors_no_descendants():
    memories = {"A": _mem("A")}
    assert ancestors(memories, "A").detail["ancestors"] == []
    assert descendants(memories, "A").detail["descendants"] == []
    assert lineage_depth(memories, "A").value == 0.0


def test_disconnected_graph_root_origins_independent():
    memories = {
        "A": _mem("A"),
        "B": _mem("B"),
        "C": _mem("C", memory_type="derived", parent_ids=["A"]),
    }
    result = independence_report(memories, ["B", "C"])
    assert result.detail["pairwise"]["B|C"] == CLASS_LINEAGE_INDEPENDENT


# ---------------------------------------------------------------------------
# Malformed references
# ---------------------------------------------------------------------------


def test_malformed_parent_reference_reported_not_raised():
    memories = {"A": _mem("A", memory_type="derived", parent_ids=["does-not-exist"])}
    result = validate_parent_edges(memories)
    assert result.detail["orphan_parent_reference_count"] == 1


def test_independence_report_unknown_memory_classified_unknown():
    memories = {"A": _mem("A")}
    result = independence_report(memories, ["A", "ghost"])
    assert result.detail["pairwise"]["A|ghost"] == "UNKNOWN"


# ---------------------------------------------------------------------------
# Independence diagnostic: worked examples from the task brief
# ---------------------------------------------------------------------------


def test_independence_a_equiv_b_selected_not_independent():
    memories = {
        "A": _mem("A", equivalent_to=["B"]),
        "B": _mem("B", equivalent_to=["A"]),
    }
    result = independence_report(memories, ["A", "B"])
    assert result.detail["pairwise"]["A|B"] != CLASS_LINEAGE_INDEPENDENT


def test_independence_a_to_b_selected_not_independent():
    memories = {
        "A": _mem("A"),
        "B": _mem("B", memory_type="derived", parent_ids=["A"]),
    }
    result = independence_report(memories, ["A", "B"])
    assert result.detail["pairwise"]["A|B"] != CLASS_LINEAGE_INDEPENDENT


def test_independence_multi_parent_c_selected_shows_two_parent_origins():
    memories = {
        "A": _mem("A"),
        "B": _mem("B"),
        "C": _mem("C", memory_type="derived", parent_ids=["A", "B"]),
    }
    result = independence_report(memories, ["C"])
    per_item = result.detail["per_item"]["C"]
    assert sorted(per_item["root_origins"]) == ["A", "B"]
    assert per_item["multi_origin_derived"] is True


def test_independence_unrelated_selected_is_lineage_independent_not_proven_independent():
    memories = {"A": _mem("A"), "B": _mem("B")}
    result = independence_report(memories, ["A", "B"])
    assert result.detail["pairwise"]["A|B"] == CLASS_LINEAGE_INDEPENDENT
    # The prominent caveat: this classification must never be documented/returned as
    # absolute proof of independence -- check the module docstring states this.
    source = inspect.getsource(provenance_mod)
    assert "NEVER proof of epistemic" in " ".join(source.split())


def test_independence_report_empty_selection_undefined():
    result = independence_report({"A": _mem("A")}, [])
    assert result.value is None
    assert result.status == STATUS_UNDEFINED_EMPTY_SEQUENCE


# ---------------------------------------------------------------------------
# Invariant tests
# ---------------------------------------------------------------------------


def test_invariant_cycles_detected_across_all_fixtures_only_in_cycle_fixture():
    for name in [
        "01_independent.json",
        "02_direct_derivation.json",
        "03_chain.json",
        "04_branching.json",
        "05_multi_parent.json",
    ]:
        data = _load(name)["memories"]
        result = detect_cycles(data)
        assert result.value == 0.0, f"{name} should be acyclic"

    cyclic = _load("10_cycle.json")["memories"]
    assert detect_cycles(cyclic).value >= 1.0


def test_invariant_nonexistent_parents_always_detected():
    data = _load("09_orphan_reference.json")["memories"]
    assert orphan_parent_count(data).value == 1.0


def test_invariant_lineage_edges_never_imply_equivalence():
    data = _load("02_direct_derivation.json")["memories"]
    result = independence_report(data, ["mem-lin-A", "mem-lin-B"])
    assert result.detail["pairwise"]["mem-lin-A|mem-lin-B"] != CLASS_EQUIVALENT_INFORMATION


def test_invariant_different_ids_never_imply_independence_without_check():
    """Two distinct memory ids with a hidden shared root must NOT be reported
    LINEAGE_INDEPENDENT just because their ids differ."""
    data = _load("12_shared_origin_selected.json")
    result = independence_report(data["memories"], data["selected_memory_ids"])
    assert result.detail["pairwise"]["mem-lin-B|mem-lin-C"] != CLASS_LINEAGE_INDEPENDENT


# ---------------------------------------------------------------------------
# Architectural tests
# ---------------------------------------------------------------------------

_FORBIDDEN_IMPORTS = (
    "sentence_transformers",
    "openai",
    "torch",
    "sklearn",
    "requests",
    "urllib",
    "phase3_reference",
)


def test_provenance_module_never_imports_forbidden_libraries():
    source = inspect.getsource(provenance_mod)
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            for forbidden in _FORBIDDEN_IMPORTS:
                assert forbidden not in stripped, (
                    f"provenance.py has a forbidden import: {stripped!r}"
                )


def test_provenance_module_never_accepts_agent_visible_context_param():
    for _, func in inspect.getmembers(provenance_mod, inspect.isfunction):
        sig = inspect.signature(func)
        for name in sig.parameters:
            assert "agent_visible" not in name.lower()
            assert "agentvisible" not in name.lower().replace("_", "")


def test_provenance_module_makes_no_network_calls():
    source = inspect.getsource(provenance_mod)
    for forbidden_token in ("socket.", "http.client", "random.", "numpy.random"):
        assert forbidden_token not in source
