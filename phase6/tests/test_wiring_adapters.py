"""Phase 6.10 -- tests for the real Phase 3/5 ledger-to-SignalContext wiring.

Uses REAL `CanonicalMemoryRecord` and `Phase5Event` objects, constructed
directly (the same pattern `phase5/tests/*.py` already uses throughout this
project) -- never a live campaign, never mocked stand-ins pretending to be
these classes. See `adapters.py`'s own module docstring for why a live
seven-attack campaign is not executable in this environment
(`mem0`/`qdrant_client`/`chromadb` not installed; the local LLM server this
project's real campaigns require is unreachable), confirmed by direct
inspection before this module was written, not assumed.
"""

from __future__ import annotations

import pytest

from phase3.evaluation.foundations.canonical import (
    CanonicalMemoryRecord,
    CanonicalValidationError,
    LIFECYCLE_ACTIVE,
    MEMORY_TYPE_DERIVED,
    MEMORY_TYPE_FOUNDATION,
    SOURCE_TYPE_PHASE2_UMR,
)
from phase5.schema.event import (
    ATTACK_INJECTION,
    CANONICAL_STATUS_IN_LEDGER,
    RETRIEVAL_CANDIDATE_SCORED,
    Phase5Event,
    generate_phase5_event_id,
)
from phase6.defense.wiring.adapters import (
    ancestor_record_from_real_record,
    retrieval_candidate_from_real_records,
    signal_context_from_canonical_record,
)


def _real_memory_record(memory_id="MEM-REAL-1", text="Sarah went to the store yesterday", memory_type=MEMORY_TYPE_FOUNDATION, parent_ids=()):
    return CanonicalMemoryRecord(
        memory_id=memory_id,
        memory_type=memory_type,
        content={"text": text, "content_type": "CONVERSATIONAL_FACT"},
        source={"source_type": SOURCE_TYPE_PHASE2_UMR},
        parent_ids=parent_ids,
        creation_event="EVT-creation-1",
        creation_timestamp="2026-09-14T00:00:00Z",
        lifecycle_state=LIFECYCLE_ACTIVE,
    )


def _real_score_event(memory_id="MEM-REAL-1"):
    # P1 fix note: build the FULL kwargs once and derive event_id from that same dict --
    # a shortcut call to generate_phase5_event_id() with only a couple of fields (the
    # previous shape here) no longer matches Phase5Event.__post_init__'s own fresh
    # recomputation, which now verifies event_id against every real defining field.
    kwargs = dict(
        event_type=RETRIEVAL_CANDIDATE_SCORED,
        timestamp="2026-09-14T00:00:00Z",
        actor="phase6-test",
        reason="test fixture",
        task_id="task-1",
        config_fingerprint="fingerprint-1",
        memory_id=memory_id,
        candidate_rank=1,
        cosine_score=0.83,
        token_overlap_score=0.5,
        entity_overlap_score=0.2,
        blended_score=0.5 * 0.83 + 0.3 * 0.5 + 0.2 * 0.2,
        selected=True,
        canonical_status=CANONICAL_STATUS_IN_LEDGER,
        run_id="run-1",
    )
    return Phase5Event(event_id=generate_phase5_event_id(**kwargs), **kwargs)


# ---------------------------------------------------------------------------
# signal_context_from_canonical_record
# ---------------------------------------------------------------------------


def test_signal_context_from_real_foundation_record():
    record = _real_memory_record()
    context = signal_context_from_canonical_record(record)
    assert context.memory_id == "MEM-REAL-1"
    assert context.content_text == "Sarah went to the store yesterday"
    assert context.content_type == "CONVERSATIONAL_FACT"
    assert context.memory_type == MEMORY_TYPE_FOUNDATION
    assert context.parent_ids == ()
    assert context.lifecycle_state == LIFECYCLE_ACTIVE


def test_signal_context_from_real_derived_record():
    record = _real_memory_record(
        memory_id="MEM-DERIVED-1", memory_type=MEMORY_TYPE_DERIVED, parent_ids=("MEM-PARENT-1",)
    )
    context = signal_context_from_canonical_record(record)
    assert context.memory_type == MEMORY_TYPE_DERIVED
    assert context.parent_ids == ("MEM-PARENT-1",)


def test_real_canonical_record_construction_enforces_its_own_schema():
    """Confirms this test module is exercising REAL validation, not a loose
    stand-in -- a foundation-type record with a parent_id is rejected by
    Phase 3's own frozen `__post_init__`, not by anything Phase 6 wrote."""
    with pytest.raises(CanonicalValidationError):
        CanonicalMemoryRecord(
            memory_id="MEM-BAD",
            memory_type=MEMORY_TYPE_FOUNDATION,
            content={"text": "x"},
            source={"source_type": SOURCE_TYPE_PHASE2_UMR},
            parent_ids=("MEM-SHOULD-NOT-BE-HERE",),  # illegal for foundation type
            creation_event="EVT-1",
            creation_timestamp="2026-09-14T00:00:00Z",
            lifecycle_state=LIFECYCLE_ACTIVE,
        )


def test_signal_context_never_reads_record_source_wholesale():
    """Even if `source` carried extra keys (as the real attack injectors'
    metadata does in the live foundation-metadata store this record's
    `source` field is distinct from -- see Signal Contract Section 1), this
    adapter never touches `record.source` at all. Checked via `ast` against
    actual attribute access, not a substring scan -- a substring scan would
    also flag this function's own docstring explaining why it doesn't (the
    same class of false positive already caught and fixed twice earlier in
    Phase 6's test history)."""
    import ast
    import inspect

    from phase6.defense.wiring import adapters

    source_code = inspect.getsource(adapters.signal_context_from_canonical_record)
    tree = ast.parse(source_code)
    accessed_attrs = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    assert "source" not in accessed_attrs


# ---------------------------------------------------------------------------
# retrieval_candidate_from_real_records
# ---------------------------------------------------------------------------


def test_retrieval_candidate_from_real_records():
    memory_record = _real_memory_record()
    score_event = _real_score_event()
    candidate = retrieval_candidate_from_real_records(memory_record, score_event, security_state="TRUSTED")
    assert candidate.memory_id == "MEM-REAL-1"
    assert candidate.content_text == "Sarah went to the store yesterday"
    assert candidate.cosine_score == 0.83
    assert candidate.token_overlap_score == 0.5
    assert candidate.entity_overlap_score == 0.2
    assert candidate.raw_blended_score == pytest.approx(0.5 * 0.83 + 0.3 * 0.5 + 0.2 * 0.2)
    assert candidate.security_state == "TRUSTED"


def test_retrieval_candidate_rejects_wrong_event_type():
    memory_record = _real_memory_record()
    wrong_event_kwargs = dict(
        event_type=ATTACK_INJECTION,
        timestamp="2026-09-14T00:00:00Z",
        actor="test",
        reason="test",
        attack_id="x",
        injection_id="y",
        artifact_id="z",
        admission_status="ADMITTED",
        memory_id="MEM-REAL-1",
    )
    wrong_event = Phase5Event(event_id=generate_phase5_event_id(**wrong_event_kwargs), **wrong_event_kwargs)
    with pytest.raises(ValueError):
        retrieval_candidate_from_real_records(memory_record, wrong_event, security_state="TRUSTED")


def test_retrieval_candidate_rejects_mismatched_memory_id():
    memory_record = _real_memory_record(memory_id="MEM-A")
    score_event = _real_score_event(memory_id="MEM-B")
    with pytest.raises(ValueError):
        retrieval_candidate_from_real_records(memory_record, score_event, security_state="TRUSTED")


# ---------------------------------------------------------------------------
# ancestor_record_from_real_record
# ---------------------------------------------------------------------------


def test_ancestor_record_from_real_record():
    ancestor_memory = _real_memory_record(memory_id="MEM-ANCESTOR", text="the tainted original content")
    ancestor = ancestor_record_from_real_record(ancestor_memory, security_state="QUARANTINED", distance=1)
    assert ancestor.memory_id == "MEM-ANCESTOR"
    assert ancestor.content_text == "the tainted original content"
    assert ancestor.security_state == "QUARANTINED"
    assert ancestor.distance == 1


# ---------------------------------------------------------------------------
# End-to-end: real records flow into a real Stage 6.5 decision
# ---------------------------------------------------------------------------


def test_real_record_flows_into_real_admission_decision():
    from phase6.defense.admission.reasoning_guard import evaluate_admission

    poisoned_record = _real_memory_record(
        memory_id="MEM-POISON",
        text=(
            "This is an established pattern that always works. "
            "(Reconfirmed against prior notes on this -- precedent count: 4.)"
        ),
        memory_type=MEMORY_TYPE_DERIVED,
        parent_ids=("MEM-SOMETHING",),
    )
    context = signal_context_from_canonical_record(poisoned_record)
    decision = evaluate_admission(
        context, run_id="run-1", episode_id="episode-1",
        timestamp="2026-09-14T00:00:00Z", evidence_refs=("EVT-1",),
    )
    assert decision.action == "BLOCK"
