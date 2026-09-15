"""Phase 5.2 -- tests for `Phase5Event` (the six new event families) and, separately, a
non-modification check confirming Phase 5 did not alter frozen Phase 3 `CanonicalEvent`
behavior. Mirrors the validation style of
`phase3/evaluation/tests/test_canonical_event_ledger_h2.py`.
"""

from __future__ import annotations

import pytest

from phase5.schema.event import (
    CANONICAL_STATUS_IN_LEDGER,
    CANONICAL_STATUS_NOT_IN_LEDGER,
    ADMISSION_STATUS_ADMITTED,
    ADMISSION_STATUS_REJECTED,
    AGENT_ACTION,
    AGENT_DECISION,
    ATTACK_GROUND_TRUTH_TRANSITION,
    ATTACK_INJECTION,
    CONTEXT_ASSEMBLED,
    GROUND_TRUTH_STATES,
    POISON_SELECTED_TOP_K,
    Phase5Event,
    Phase5EventValidationError,
    RETRIEVAL_CANDIDATE_SCORED,
    compute_rendered_context_fingerprint,
    generate_phase5_event_id,
)

TS = "2026-09-12T00:00:00+00:00"


def _rcs_kwargs(**overrides):
    kwargs = dict(
        event_type=RETRIEVAL_CANDIDATE_SCORED,
        timestamp=TS,
        actor="retrieval_wiring",
        reason="candidate scored during hybrid selection",
        task_id="task-1",
        config_fingerprint="CFG-abc123",
        memory_id="mem-1",
        candidate_rank=3,
        cosine_score=0.71,
        token_overlap_score=0.2,
        entity_overlap_score=0.1,
        blended_score=0.55,
        selected=False,
        canonical_status=CANONICAL_STATUS_IN_LEDGER,
    )
    kwargs.update(overrides)
    kwargs["event_id"] = generate_phase5_event_id(**{k: v for k, v in kwargs.items() if k != "event_id"})
    return kwargs


def test_retrieval_candidate_scored_constructs_and_serializes_round_trip():
    event = Phase5Event(**_rcs_kwargs())
    assert event.event_type == RETRIEVAL_CANDIDATE_SCORED
    d = event.to_dict()
    assert d["memory_id"] == "mem-1"
    reconstructed = Phase5Event.from_dict(d)
    assert reconstructed == event


def test_retrieval_candidate_scored_rejects_missing_score():
    kwargs = _rcs_kwargs()
    kwargs["cosine_score"] = None
    with pytest.raises(Phase5EventValidationError, match="cosine_score"):
        Phase5Event(**kwargs)


def test_retrieval_candidate_scored_requires_canonical_status():
    kwargs = _rcs_kwargs(canonical_status=None)
    with pytest.raises(Phase5EventValidationError, match="canonical_status"):
        Phase5Event(**kwargs)


def test_retrieval_candidate_scored_rejects_unknown_canonical_status_value():
    kwargs = _rcs_kwargs(canonical_status="SOMETHING_ELSE")
    with pytest.raises(Phase5EventValidationError, match="canonical_status"):
        Phase5Event(**kwargs)


def test_retrieval_candidate_scored_accepts_not_in_ledger_independent_of_selected():
    # canonical_status is a THIRD, independent axis -- a candidate can be selected=True
    # (top-K by score) while still NOT_IN_CANONICAL_LEDGER (identity never resolved), and
    # vice versa. Neither combination is forbidden by the schema.
    selected_but_unresolved = _rcs_kwargs(selected=True, canonical_status=CANONICAL_STATUS_NOT_IN_LEDGER)
    event = Phase5Event(**selected_but_unresolved)
    assert event.selected is True
    assert event.canonical_status == CANONICAL_STATUS_NOT_IN_LEDGER

    rejected_and_resolved = _rcs_kwargs(selected=False, canonical_status=CANONICAL_STATUS_IN_LEDGER)
    event2 = Phase5Event(**rejected_and_resolved)
    assert event2.selected is False
    assert event2.canonical_status == CANONICAL_STATUS_IN_LEDGER


def test_retrieval_candidate_scored_rejects_foreign_field():
    kwargs = _rcs_kwargs()
    kwargs["action"] = "should not be set here"
    with pytest.raises(Phase5EventValidationError, match="must be None"):
        Phase5Event(**kwargs)


def test_retrieval_candidate_scored_requires_task_id():
    kwargs = _rcs_kwargs(task_id=None)
    with pytest.raises(Phase5EventValidationError, match="task_id"):
        Phase5Event(**kwargs)


def test_retrieval_candidate_scored_requires_config_fingerprint():
    kwargs = _rcs_kwargs(config_fingerprint=None)
    with pytest.raises(Phase5EventValidationError, match="config_fingerprint"):
        Phase5Event(**kwargs)


def _rendered_messages():
    return (
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "[mem-3] fact three\n[mem-1] fact one\n\nQuestion: what happened?"},
    )


def test_context_assembled_preserves_order_and_requires_nonempty():
    messages = _rendered_messages()
    kwargs = dict(
        event_type=CONTEXT_ASSEMBLED,
        timestamp=TS,
        actor="campaign_runner",
        reason="prompt rendered for generation",
        task_id="task-1",
        context_memory_ids=("mem-3", "mem-1", "mem-2"),
        rendered_messages=messages,
        rendered_context_fingerprint=compute_rendered_context_fingerprint(messages),
    )
    kwargs["event_id"] = generate_phase5_event_id(**kwargs)
    event = Phase5Event(**kwargs)
    assert event.context_memory_ids == ("mem-3", "mem-1", "mem-2")  # order not resorted
    assert event.rendered_messages == messages

    empty_kwargs = dict(kwargs, context_memory_ids=())
    empty_kwargs["event_id"] = generate_phase5_event_id(**empty_kwargs)
    with pytest.raises(Phase5EventValidationError, match="non-empty tuple"):
        Phase5Event(**empty_kwargs)

    no_rendered_kwargs = dict(kwargs, rendered_messages=None, rendered_context_fingerprint=None)
    no_rendered_kwargs["event_id"] = generate_phase5_event_id(**no_rendered_kwargs)
    with pytest.raises(Phase5EventValidationError, match="rendered_messages is required"):
        Phase5Event(**no_rendered_kwargs)

    wrong_fingerprint_kwargs = dict(kwargs, rendered_context_fingerprint="P5CTX-not-the-real-hash")
    wrong_fingerprint_kwargs["event_id"] = generate_phase5_event_id(**wrong_fingerprint_kwargs)
    with pytest.raises(Phase5EventValidationError, match="does not match a fresh fingerprint"):
        Phase5Event(**wrong_fingerprint_kwargs)


def test_agent_decision_requires_explicit_observability_marker():
    base = dict(
        event_type=AGENT_DECISION,
        timestamp=TS,
        actor="agent_runtime",
        reason="generation completed",
        task_id="task-1",
        config_fingerprint="CFG-abc123",
        decision_id="dec-1",
        exposed_memory_ids=("mem-1", "mem-2"),
        output="the answer",
        finish_reason="stop",
        model_identity="qwen2.5-7b-instruct",
    )
    missing = dict(base, used_memories_observability=None)
    missing["event_id"] = generate_phase5_event_id(**missing)
    with pytest.raises(Phase5EventValidationError, match="used_memories_observability"):
        Phase5Event(**missing)

    ok = dict(base, used_memories_observability="NOT_OBSERVABLE")
    ok["event_id"] = generate_phase5_event_id(**ok)
    event = Phase5Event(**ok)
    assert event.used_memories_observability == "NOT_OBSERVABLE"


def test_agent_action_links_back_to_decision():
    kwargs = dict(
        event_type=AGENT_ACTION,
        timestamp=TS,
        actor="agent_runtime",
        reason="action executed",
        task_id="task-1",
        decision_id="dec-1",
        action_id="act-1",
        action="submit_answer",
        result="accepted",
    )
    kwargs["event_id"] = generate_phase5_event_id(**kwargs)
    event = Phase5Event(**kwargs)
    assert event.decision_id == "dec-1"

    missing_decision = dict(kwargs, decision_id=None)
    missing_decision["event_id"] = generate_phase5_event_id(**missing_decision)
    with pytest.raises(Phase5EventValidationError, match="decision_id"):
        Phase5Event(**missing_decision)


def test_attack_injection_admitted_requires_memory_id():
    admitted = dict(
        event_type=ATTACK_INJECTION,
        timestamp=TS,
        actor="farma_injector",
        reason="artifact injected via add_memory",
        attack_id="farma",
        injection_id="INJ-1",
        artifact_id="farma-artifact-7",
        admission_status=ADMISSION_STATUS_ADMITTED,
        memory_id="mem-9",
    )
    admitted["event_id"] = generate_phase5_event_id(**admitted)
    event = Phase5Event(**admitted)
    assert event.memory_id == "mem-9"

    # P1 fix note: build `rejected`/`rejected_with_memory` from `admitted` MINUS its own
    # `event_id` key -- reusing `admitted` (which already carries a computed `event_id`)
    # directly would pollute generate_phase5_event_id()'s own defining-fields payload
    # with a stale event_id, which no real phase5/wiring/*.py call site ever does (none
    # of them include event_id in the kwargs dict passed to generate_phase5_event_id()).
    admitted_fields = {k: v for k, v in admitted.items() if k != "event_id"}

    rejected = dict(admitted_fields, admission_status=ADMISSION_STATUS_REJECTED, memory_id=None)
    rejected["event_id"] = generate_phase5_event_id(**rejected)
    Phase5Event(**rejected)  # must not raise

    rejected_with_memory = dict(admitted_fields, admission_status=ADMISSION_STATUS_REJECTED)
    rejected_with_memory["event_id"] = generate_phase5_event_id(**rejected_with_memory)
    with pytest.raises(Phase5EventValidationError, match="memory_id must be None"):
        Phase5Event(**rejected_with_memory)


# ---------------------------------------------------------------------------
# P1 fix (2026-09-14) -- event_id must actually equal a fresh recomputation
# from an event's own defining fields, not merely be a non-empty string. The
# audit finding this closes: __post_init__ only checked event_id was a
# non-empty string, so a hand-picked id (or a bug in a future wiring module)
# would go undetected -- the module's own "two calls describing the
# identical fact coalesce onto the same id" claim was a convention, not an
# enforced invariant.
# ---------------------------------------------------------------------------


def test_hand_picked_event_id_is_rejected():
    kwargs = dict(_rcs_kwargs())
    kwargs["event_id"] = "P5EVT-hand-picked-not-a-real-hash"
    with pytest.raises(Phase5EventValidationError, match="does not match a fresh recomputation"):
        Phase5Event(**kwargs)


def test_correctly_minted_event_id_is_accepted():
    event = Phase5Event(**_rcs_kwargs())
    assert event.event_id.startswith("P5EVT-")


def test_two_calls_with_identical_defining_fields_coalesce_onto_the_same_id():
    """The module's own stated guarantee, actually verified now (previously
    only asserted in prose)."""
    assert _rcs_kwargs()["event_id"] == _rcs_kwargs()["event_id"]  # two independent builds


def test_event_id_changes_when_a_defining_field_changes():
    id_a = _rcs_kwargs()["event_id"]
    id_b = _rcs_kwargs(cosine_score=0.99)["event_id"]
    assert id_a != id_b


def test_event_id_reconstruction_handles_an_optional_group_field_left_unset():
    """context_assembled's decision_id is optional within its active group
    (unlike attack_injection's memory_id, which is a deliberate, documented
    exception -- see event.py's __post_init__ comment) -- a real event built
    without it must still validate cleanly."""
    kwargs = dict(
        event_type=CONTEXT_ASSEMBLED, timestamp=TS, actor="retrieval_wiring",
        reason="context assembled", task_id="task-1",
        context_memory_ids=("mem-1",),
        rendered_messages=({"role": "system", "content": "x"},),
        rendered_context_fingerprint=compute_rendered_context_fingerprint(
            ({"role": "system", "content": "x"},)
        ),
    )
    event_id = generate_phase5_event_id(**kwargs)
    event = Phase5Event(event_id=event_id, **kwargs)
    assert event.decision_id is None


def test_event_id_reconstruction_handles_attack_injection_rejected_with_memory_id_none():
    kwargs = dict(
        event_type=ATTACK_INJECTION, timestamp=TS, actor="farma_injector",
        reason="artifact rejected", attack_id="farma", injection_id="INJ-2",
        artifact_id="farma-artifact-8", admission_status=ADMISSION_STATUS_REJECTED,
        memory_id=None,
    )
    event_id = generate_phase5_event_id(**kwargs)
    event = Phase5Event(event_id=event_id, **kwargs)
    assert event.memory_id is None


def test_ground_truth_transition_requires_derivation_source():
    assert len(GROUND_TRUTH_STATES) == 9  # the full master-prompt vocabulary, not a subset
    base = dict(
        event_type=ATTACK_GROUND_TRUTH_TRANSITION,
        timestamp=TS,
        actor="ground_truth_deriver",
        reason="candidate scored event shows memory in top-K",
        attack_id="farma",
        memory_id="mem-9",
        state=POISON_SELECTED_TOP_K,
    )
    missing = dict(base, derived_from_event_id=None)
    missing["event_id"] = generate_phase5_event_id(**missing)
    with pytest.raises(Phase5EventValidationError, match="derived_from_event_id"):
        Phase5Event(**missing)

    ok = dict(base, derived_from_event_id="P5EVT-somehash")
    ok["event_id"] = generate_phase5_event_id(**ok)
    event = Phase5Event(**ok)
    assert event.state == POISON_SELECTED_TOP_K


def test_generate_phase5_event_id_is_deterministic_and_namespaced():
    kwargs = _rcs_kwargs()
    kwargs.pop("event_id")
    id1 = generate_phase5_event_id(**kwargs)
    id2 = generate_phase5_event_id(**kwargs)
    assert id1 == id2
    assert id1.startswith("P5EVT-")


def test_frozen_phase3_canonical_event_is_untouched_by_this_module():
    """Non-interference check for this stage: importing/using Phase5Event must not change
    CanonicalEvent's own behavior. Constructs a real CanonicalEvent exactly as
    canonical_wiring.py does and confirms its existing validation still holds unchanged."""
    from phase3.evaluation.foundations.canonical_event import (
        CanonicalEvent,
        CanonicalEventValidationError,
        EVENT_RETRIEVED,
    )

    event = CanonicalEvent(
        event_id="evt-1",
        event_type=EVENT_RETRIEVED,
        memory_ids=("mem-1",),
        timestamp=TS,
        actor="retrieval",
        reason="candidate pool query",
        task_id="task-1",
        config_fingerprint="CFG-abc123",
    )
    assert event.event_type == EVENT_RETRIEVED

    with pytest.raises(CanonicalEventValidationError):
        CanonicalEvent(
            event_id="evt-2",
            event_type=EVENT_RETRIEVED,
            memory_ids=("mem-1",),
            timestamp=TS,
            actor="retrieval",
            reason="candidate pool query",
            task_id="task-1",
            config_fingerprint="CFG-abc123",
            score=0.9,  # still forbidden -- confirms Phase 3 validation is unmodified
        )
