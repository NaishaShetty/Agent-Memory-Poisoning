"""Phase 3.2-D tests for `phase3/evaluation/metrics/equivalence.py`.

Scope note: this suite tests EQUIVALENCE representation/validation/component-computation
only. It does not modify, re-run, or depend on `test_evaluation_contracts.py` (the 62
Phase 3.2-B tests) or `test_core_memory_metrics.py` (the 88 Phase 3.2-C tests), which must
remain green, unmodified, alongside this file.

Fixtures used here are a mix of (a) small literal Python dicts embedded directly in this
module for unit-level cases, and (b) the 12 JSON fixtures under
`phase3/evaluation/fixtures/lineage/` for the worked, cross-module scenarios shared with
`test_provenance_lineage.py`.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from phase3.evaluation.metrics import equivalence as equivalence_mod
from phase3.evaluation.metrics.equivalence import (
    extract_equivalence_edges,
    validate_equivalence_edges,
    equivalence_classes,
    equivalence_group_size,
    FINDING_OK,
    FINDING_UNKNOWN_MEMORY_REFERENCE,
    FINDING_SELF_EQUIVALENCE_DECLARED,
    FINDING_ASYMMETRIC_DECLARATION,
)
from phase3.evaluation.metrics.types import STATUS_OK, STATUS_UNDEFINED_EMPTY_SEQUENCE

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "lineage"


def _load(name: str) -> dict:
    with open(FIXTURES_DIR / name, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Small literal fixtures for unit-level cases
# ---------------------------------------------------------------------------

MEM_A_B_SYMMETRIC = {
    "A": {"memory_id": "A", "equivalent_to": ["B"]},
    "B": {"memory_id": "B", "equivalent_to": ["A"]},
}

MEM_A_B_ONE_SIDED = {
    "A": {"memory_id": "A", "equivalent_to": ["B"]},
    "B": {"memory_id": "B", "equivalent_to": []},
}

MEM_SELF_EQUIV = {
    "A": {"memory_id": "A", "equivalent_to": ["A"]},
}

MEM_UNKNOWN_REF = {
    "A": {"memory_id": "A", "equivalent_to": ["Z"]},
}

MEM_CHAIN_EQUIV = {
    "A": {"memory_id": "A", "equivalent_to": ["B"]},
    "B": {"memory_id": "B", "equivalent_to": ["A", "C"]},
    "C": {"memory_id": "C", "equivalent_to": ["B"]},
}

MEM_NO_RELATION = {
    "A": {"memory_id": "A"},
    "B": {"memory_id": "B"},
}


# ---------------------------------------------------------------------------
# Identity preservation
# ---------------------------------------------------------------------------


def test_equivalence_never_creates_a_merged_identity():
    """Component computation returns GROUPS of existing ids -- never a synthesized id."""
    result = equivalence_classes(memories=MEM_A_B_SYMMETRIC)
    for component in result.detail["components"]:
        for member in component:
            assert member in ("A", "B")


def test_equivalence_classes_preserves_all_original_ids():
    result = equivalence_classes(memories=MEM_A_B_SYMMETRIC)
    all_members = {m for c in result.detail["components"] for m in c}
    assert all_members == {"A", "B"}


# ---------------------------------------------------------------------------
# Symmetry
# ---------------------------------------------------------------------------


def test_symmetric_declaration_is_valid():
    result = validate_equivalence_edges(MEM_A_B_SYMMETRIC)
    findings = result.detail["findings"]
    assert findings["A->B"] == [FINDING_OK]
    assert findings["B->A"] == [FINDING_OK]


def test_one_sided_declaration_flagged_asymmetric():
    result = validate_equivalence_edges(MEM_A_B_ONE_SIDED)
    findings = result.detail["findings"]
    assert FINDING_ASYMMETRIC_DECLARATION in findings["A->B"]


def test_one_sided_declaration_not_silently_symmetrized_in_default_component_mode():
    """DECISION E1: require_symmetric=True (the default) means a one-sided edge does NOT
    connect A and B into one component."""
    result = equivalence_classes(memories=MEM_A_B_ONE_SIDED)
    components = result.detail["components"]
    assert ["A"] in components
    assert ["B"] in components
    assert ["A", "B"] not in components


def test_require_symmetric_false_does_connect_one_sided_declarations():
    """The looser, explicitly-opt-in mode does treat a one-sided edge as connecting the pair."""
    result = equivalence_classes(memories=MEM_A_B_ONE_SIDED, require_symmetric=False)
    assert ["A", "B"] in result.detail["components"]


# ---------------------------------------------------------------------------
# Equivalence components / classes
# ---------------------------------------------------------------------------


def test_equivalence_component_a_b_c_via_transitive_closure():
    """A≡B, B≡C (symmetric both ways) -> one component {A,B,C} even though A and C never
    declare each other directly."""
    result = equivalence_classes(memories=MEM_CHAIN_EQUIV)
    assert result.detail["components"] == [["A", "B", "C"]]
    assert result.value == 1.0


def test_no_relation_yields_singleton_components():
    result = equivalence_classes(memories=MEM_NO_RELATION)
    assert sorted(result.detail["components"]) == [["A"], ["B"]]
    assert result.value == 2.0


def test_equivalence_classes_deterministic_across_repeated_calls():
    r1 = equivalence_classes(memories=MEM_CHAIN_EQUIV)
    r2 = equivalence_classes(memories=MEM_CHAIN_EQUIV)
    assert r1.detail["components"] == r2.detail["components"]


def test_equivalence_group_size_singleton():
    result = equivalence_group_size("A", memories=MEM_NO_RELATION)
    assert result.value == 1.0


def test_equivalence_group_size_component_of_three():
    result = equivalence_group_size("A", memories=MEM_CHAIN_EQUIV)
    assert result.value == 3.0


def test_equivalence_group_size_unknown_memory_undefined():
    result = equivalence_group_size("nonexistent", memories=MEM_NO_RELATION)
    assert result.value is None
    assert result.status == STATUS_UNDEFINED_EMPTY_SEQUENCE


def test_distinct_equivalence_component_count_via_value():
    result = equivalence_classes(memories={**MEM_CHAIN_EQUIV, **MEM_NO_RELATION})
    # {A,B,C} equivalence chain (3 members) + A,B singletons from MEM_NO_RELATION
    # -- but MEM_NO_RELATION's "A"/"B" keys collide with MEM_CHAIN_EQUIV's; merging dicts
    # means MEM_NO_RELATION's A/B overwrite MEM_CHAIN_EQUIV's, so use disjoint ids instead.
    disjoint = {
        "A": {"memory_id": "A", "equivalent_to": ["B"]},
        "B": {"memory_id": "B", "equivalent_to": ["A", "C"]},
        "C": {"memory_id": "C", "equivalent_to": ["B"]},
        "D": {"memory_id": "D"},
        "E": {"memory_id": "E"},
    }
    result = equivalence_classes(memories=disjoint)
    assert result.value == 3.0  # {A,B,C}, {D}, {E}


# ---------------------------------------------------------------------------
# Validation: unknown reference / self-equivalence
# ---------------------------------------------------------------------------


def test_unknown_memory_reference_flagged():
    result = validate_equivalence_edges(MEM_UNKNOWN_REF)
    assert FINDING_UNKNOWN_MEMORY_REFERENCE in result.detail["findings"]["A->Z"]


def test_unknown_reference_excluded_from_components():
    result = equivalence_classes(memories=MEM_UNKNOWN_REF)
    # Z is not in `memories`, so it must not appear in any component.
    all_members = {m for c in result.detail["components"] for m in c}
    assert "Z" not in all_members
    assert all_members == {"A"}


def test_self_equivalence_flagged_invalid():
    result = validate_equivalence_edges(MEM_SELF_EQUIV)
    assert FINDING_SELF_EQUIVALENCE_DECLARED in result.detail["findings"]["A->A"]


def test_self_equivalence_contributes_no_connectivity():
    """A self-edge must not create a bigger component than {A} alone."""
    result = equivalence_classes(memories=MEM_SELF_EQUIV)
    assert result.detail["components"] == [["A"]]


def test_no_relation_edges_are_valid_empty_state():
    """Not declaring any equivalent_to at all is a well-defined, valid state -- zero edges,
    STATUS_OK, not an error."""
    result = validate_equivalence_edges(MEM_NO_RELATION)
    assert result.status == STATUS_OK
    assert result.detail["total_edges"] == 0


# ---------------------------------------------------------------------------
# Equivalence never implies lineage / provenance / relevance (structural check)
# ---------------------------------------------------------------------------


def test_equivalence_module_never_reads_parent_ids():
    """Static check: equivalence.py has no notion of parent_ids at all -- it is purely
    about the equivalent_to relation, never lineage."""
    source = inspect.getsource(equivalence_mod)
    assert "parent_ids" not in source


def test_equivalent_memories_need_not_share_any_parent():
    """Worked example: A and B are equivalent but have completely disjoint (absent)
    parent_ids -- equivalence does not require or imply any lineage relationship."""
    memories = {
        "A": {"memory_id": "A", "memory_type": "foundation", "parent_ids": [], "equivalent_to": ["B"]},
        "B": {"memory_id": "B", "memory_type": "foundation", "parent_ids": [], "equivalent_to": ["A"]},
    }
    result = equivalence_classes(memories=memories)
    assert result.detail["components"] == [["A", "B"]]
    # No assertion about parent_ids is made anywhere by this module -- it simply never
    # inspects that field, which this test also confirms behaviorally: both memories'
    # empty parent_ids lists are irrelevant to the computed component.


# ---------------------------------------------------------------------------
# Edge cases: empty / single-node / disconnected graphs
# ---------------------------------------------------------------------------


def test_empty_memories_yields_zero_components():
    result = equivalence_classes(memories={})
    assert result.value == 0.0
    assert result.detail["components"] == []
    assert result.status == STATUS_OK


def test_single_node_graph_is_its_own_component():
    result = equivalence_classes(memories={"A": {"memory_id": "A"}})
    assert result.detail["components"] == [["A"]]


def test_disconnected_graph_multiple_components():
    memories = {
        "A": {"memory_id": "A", "equivalent_to": ["B"]},
        "B": {"memory_id": "B", "equivalent_to": ["A"]},
        "C": {"memory_id": "C", "equivalent_to": ["D"]},
        "D": {"memory_id": "D", "equivalent_to": ["C"]},
        "E": {"memory_id": "E"},
    }
    result = equivalence_classes(memories=memories)
    assert sorted(result.detail["components"]) == [["A", "B"], ["C", "D"], ["E"]]
    assert result.value == 3.0


def test_malformed_reference_asymmetric_and_unknown_combined():
    """A declares B (unknown) and also a self-edge -- both findings reported on distinct
    edges, neither silently dropped."""
    memories = {
        "A": {"memory_id": "A", "equivalent_to": ["A", "ghost"]},
    }
    result = validate_equivalence_edges(memories)
    findings = result.detail["findings"]
    assert FINDING_SELF_EQUIVALENCE_DECLARED in findings["A->A"]
    assert FINDING_UNKNOWN_MEMORY_REFERENCE in findings["A->ghost"]


# ---------------------------------------------------------------------------
# JSON-fixture-driven scenarios (shared naming convention with test_provenance_lineage.py)
# ---------------------------------------------------------------------------


def test_fixture_06_equivalence_pair():
    data = _load("06_equivalence_pair.json")
    result = equivalence_classes(memories=data["memories"])
    assert ["mem-lin-A", "mem-lin-B"] in result.detail["components"]


def test_fixture_07_equivalence_component():
    data = _load("07_equivalence_component.json")
    result = equivalence_classes(memories=data["memories"])
    assert result.detail["components"] == [["mem-lin-A", "mem-lin-B", "mem-lin-C"]]


def test_fixture_08_equivalence_and_lineage_distinct_relations():
    """A≡B and A->C are declared on the SAME memory set. The equivalence component for A
    must be {A, B} only -- C must never appear in it, proving lineage edges are not
    conflated with equivalence edges."""
    data = _load("08_equivalence_and_lineage.json")
    result = equivalence_classes(memories=data["memories"])
    component_with_a = next(c for c in result.detail["components"] if "mem-lin-A" in c)
    assert set(component_with_a) == {"mem-lin-A", "mem-lin-B"}
    assert "mem-lin-C" not in component_with_a


def test_fixture_09_orphan_reference_not_an_equivalence_concern():
    """The orphan fixture has no equivalent_to edges at all -- equivalence_classes should
    report each memory as its own singleton, untouched by the (lineage-only) orphan issue."""
    data = _load("09_orphan_reference.json")
    result = equivalence_classes(memories=data["memories"])
    assert result.detail["components"] == [["mem-lin-A"]]


def test_fixture_11_equivalent_selected_evidence_component():
    data = _load("11_equivalent_selected_evidence.json")
    result = equivalence_classes(memories=data["memories"])
    assert result.detail["components"] == [["mem-lin-A", "mem-lin-B"]]


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


def test_equivalence_module_never_imports_forbidden_libraries():
    source = inspect.getsource(equivalence_mod)
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            for forbidden in _FORBIDDEN_IMPORTS:
                assert forbidden not in stripped, (
                    f"equivalence.py has a forbidden import: {stripped!r}"
                )


def test_equivalence_module_never_accepts_agent_visible_context_param():
    for _, func in inspect.getmembers(equivalence_mod, inspect.isfunction):
        sig = inspect.signature(func)
        for name in sig.parameters:
            assert "agent_visible" not in name.lower()
            assert "agentvisible" not in name.lower().replace("_", "")


def test_equivalence_module_has_no_network_or_random_calls():
    source = inspect.getsource(equivalence_mod)
    for forbidden_token in ("socket.", "http.client", "random.", "numpy.random"):
        assert forbidden_token not in source
