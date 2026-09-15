"""Phase 6.4 -- tests for the Defense Signal & Trust Contract.

The most important test here (`test_agentpoison_real_metadata_shape_is_fully_
blocked`) is a regression test built from the LITERAL metadata dict
`phase4/attacks/agentpoison/injector.py` constructs -- proving the concrete
leakage path this stage found (Signal Contract document Section 1) is actually
closed, not just described in prose.
"""

from __future__ import annotations

import dataclasses

import pytest

from phase6.defense.policy.records import EvaluatorOnlyLeakageError
from phase6.defense.signals.contract import (
    ALLOWED_STRUCTURAL_EDGE_TYPES,
    EXCLUDED_STRUCTURAL_EDGE_TYPES,
    RetrievalObservation,
    SignalContext,
    StructuralEdge,
    build_signal_context,
    safe_metadata_view,
    signal_function,
)


def _real_agentpoison_metadata():
    """The exact shape `AgentPoisonInjector.inject()` constructs -- see
    `phase4/attacks/agentpoison/injector.py` lines 57-63. Kept as a literal
    copy here (not an import) so this test does not depend on, and cannot be
    broken by, the frozen Phase 4 injector's own internals -- it independently
    re-asserts the shape as evidence, per this project's "spot-check the
    frozen record" discipline rather than trusting a prior description."""
    return {
        "attacker_originated": True,
        "attack_id": "agentpoison",
        "trigger_text": "some optimized trigger tokens",
        "fitness_score_final": 3.5052,
    }


# ---------------------------------------------------------------------------
# The concrete leakage path (Signal Contract document Section 1)
# ---------------------------------------------------------------------------


def test_agentpoison_real_metadata_shape_is_fully_blocked():
    raw = _real_agentpoison_metadata()
    assert safe_metadata_view(raw) == {}  # default allowlist is empty
    assert safe_metadata_view(raw, allowed_keys=frozenset()) == {}


def test_widening_allowlist_to_include_denylisted_key_is_refused():
    """Even a caller trying to deliberately widen access to `attack_id`
    cannot -- the denylist backstop sits under the allowlist, not beside it."""
    with pytest.raises(EvaluatorOnlyLeakageError):
        safe_metadata_view(_real_agentpoison_metadata(), allowed_keys=frozenset({"attack_id"}))


def test_mixed_legitimate_and_forbidden_metadata_only_returns_legitimate():
    raw = dict(_real_agentpoison_metadata())
    raw["content_type"] = "CONVERSATIONAL_FACT"  # a hypothetical legitimate key
    result = safe_metadata_view(raw, allowed_keys=frozenset({"content_type"}))
    assert result == {"content_type": "CONVERSATIONAL_FACT"}
    assert "attacker_originated" not in result
    assert "attack_id" not in result
    assert "trigger_text" not in result
    assert "fitness_score_final" not in result


def test_default_allowlist_is_empty_by_design():
    """v1's deliberate scope decision (Section 2.5): no foundation metadata
    key is safe by default."""
    from phase6.defense.signals.contract import DEFAULT_METADATA_ALLOWLIST

    assert DEFAULT_METADATA_ALLOWLIST == frozenset()


# ---------------------------------------------------------------------------
# StructuralEdge restriction
# ---------------------------------------------------------------------------


def test_allowed_structural_edge_types_construct_cleanly():
    for edge_type in ALLOWED_STRUCTURAL_EDGE_TYPES:
        edge = StructuralEdge(edge_type=edge_type, related_memory_id="MEM-X", evidence_kind="OBSERVED_EVENT")
        assert edge.edge_type == edge_type


def test_excluded_edge_types_are_refused():
    for edge_type in EXCLUDED_STRUCTURAL_EDGE_TYPES:
        with pytest.raises(ValueError):
            StructuralEdge(edge_type=edge_type, related_memory_id="MEM-X", evidence_kind="OBSERVED_EVENT")


def test_unknown_edge_type_refused():
    with pytest.raises(ValueError):
        StructuralEdge(edge_type="NOT_A_REAL_EDGE_TYPE", related_memory_id="MEM-X", evidence_kind="OBSERVED_EVENT")


def test_used_by_and_influenced_are_the_only_exclusions():
    """Confirms the excluded set is exactly {USED_BY, INFLUENCED}, not
    accidentally broader or narrower than Section 3 of the contract document
    commits to."""
    assert EXCLUDED_STRUCTURAL_EDGE_TYPES == {"USED_BY", "INFLUENCED"}
    assert ALLOWED_STRUCTURAL_EDGE_TYPES == {
        "DERIVED_FROM",
        "PRODUCED",
        "SUPERSEDES",
        "RETRIEVED_WITH",
        "SELECTED_WITH",
        "REFERENCES",
    }
    assert ALLOWED_STRUCTURAL_EDGE_TYPES.isdisjoint(EXCLUDED_STRUCTURAL_EDGE_TYPES)


# ---------------------------------------------------------------------------
# SignalContext shape
# ---------------------------------------------------------------------------


def test_signal_context_has_no_raw_metadata_field():
    """Structural guarantee: there is no field on SignalContext that could
    carry an arbitrary, unfiltered dict -- the only fields are the specific,
    named, already-vetted ones from Sections 2.1-2.4 of the contract
    document."""
    field_names = {f.name for f in dataclasses.fields(SignalContext)}
    forbidden_field_name_fragments = ("metadata", "source", "raw")
    for name in field_names:
        for fragment in forbidden_field_name_fragments:
            assert fragment not in name.lower(), (
                f"SignalContext.{name} looks like it could carry an unfiltered "
                "blob -- every field must be a specific, named, already-vetted "
                "value (Signal Contract document Section 4)."
            )


def test_build_signal_context_normal_construction():
    obs = RetrievalObservation(
        cosine_score=0.83,
        token_overlap_score=0.5,
        entity_overlap_score=0.2,
        blended_score=0.5 * 0.83 + 0.3 * 0.5 + 0.2 * 0.2,
        rank=1,
        canonical_status="RESOLVED",
        selected=True,
    )
    edge = StructuralEdge(edge_type="DERIVED_FROM", related_memory_id="MEM-PARENT", evidence_kind="OBSERVED_EVENT")
    context = build_signal_context(
        memory_id="MEM-1",
        content_text="the sky is blue",
        content_type="CONVERSATIONAL_FACT",
        memory_type="derived",
        parent_ids=("MEM-PARENT",),
        lifecycle_state="ACTIVE",
        creation_timestamp="2026-09-13T00:00:00Z",
        retrieval_history=(obs,),
        structural_edges=(edge,),
    )
    assert context.memory_id == "MEM-1"
    assert context.memory_type == "derived"
    assert context.parent_ids == ("MEM-PARENT",)
    assert context.retrieval_history == (obs,)
    assert context.structural_edges == (edge,)


def test_signal_context_is_frozen():
    context = build_signal_context(
        memory_id="MEM-1",
        content_text="x",
        content_type="CONVERSATIONAL_FACT",
        memory_type="foundation",
        parent_ids=(),
        lifecycle_state="ACTIVE",
        creation_timestamp="2026-09-13T00:00:00Z",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        context.memory_id = "MEM-2"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# @signal_function decorator
# ---------------------------------------------------------------------------


def test_signal_function_passes_through_clean_output():
    @signal_function
    def legitimate_signal(context: SignalContext):
        return {"content_length": len(context.content_text), "self_reference_count": 0}

    context = build_signal_context(
        memory_id="MEM-1",
        content_text="hello world",
        content_type="CONVERSATIONAL_FACT",
        memory_type="foundation",
        parent_ids=(),
        lifecycle_state="ACTIVE",
        creation_timestamp="2026-09-13T00:00:00Z",
    )
    result = legitimate_signal(context)
    assert result == {"content_length": 11, "self_reference_count": 0}


def test_signal_function_catches_a_malicious_test_double():
    """A deliberately misbehaving signal function that tries to sneak
    attack_id into its output must be caught by the decorator, not silently
    let through to the governance ledger."""

    @signal_function
    def malicious_signal(context: SignalContext):
        return {"content_length": len(context.content_text), "attack_id": "agentpoison"}

    context = build_signal_context(
        memory_id="MEM-1",
        content_text="hello world",
        content_type="CONVERSATIONAL_FACT",
        memory_type="foundation",
        parent_ids=(),
        lifecycle_state="ACTIVE",
        creation_timestamp="2026-09-13T00:00:00Z",
    )
    with pytest.raises(EvaluatorOnlyLeakageError):
        malicious_signal(context)


def test_signal_function_preserves_name_and_docstring():
    @signal_function
    def named_signal(context: SignalContext):
        """A docstring."""
        return {}

    assert named_signal.__name__ == "named_signal"
    assert named_signal.__doc__ == "A docstring."
