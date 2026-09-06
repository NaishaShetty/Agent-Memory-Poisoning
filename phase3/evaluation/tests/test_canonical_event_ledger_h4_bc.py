"""Phase 3.3-H.4-BC (Rejected & Relationship-Detection Events) contract tests.

Covers every invariant in section 8 and every adversarial case in section 9 of
PHASE3_3_H4_BC_MISSION.md. Uses H.1's `CanonicalMemoryLedger`/`CanonicalMemoryRecord` and
H.2's `CanonicalEventLedger` directly, exactly as `test_canonical_event_ledger_h2.py` does --
no foundation/vendor dependency, and no memory-creation policy is built or exercised here
(section 6.1's explicit STOP condition): every `relationship_detected` event below is
constructed directly with test-authored `mechanism`/`score`/`threshold` values.
"""

from __future__ import annotations

import pytest

from phase3.evaluation.foundations.canonical import (
    CanonicalMemoryRecord,
    LIFECYCLE_CREATED,
    MEMORY_TYPE_FOUNDATION,
    SOURCE_TYPE_PHASE2_UMR,
)
from phase3.evaluation.foundations.canonical_event import (
    CanonicalEvent,
    CanonicalEventValidationError,
    EVENT_CREATED,
    EVENT_REJECTED,
    EVENT_RELATIONSHIP_DETECTED,
    EVENT_RETRIEVED,
    EVENT_SELECTED,
    EVENT_TYPES,
    REJECTED_REASON_BELOW_RERANK_THRESHOLD,
    REJECTED_REASON_CAPACITY_CUT,
    REJECTED_REASONS,
    RELATIONSHIP_CONFLICTS_WITH,
    RELATIONSHIP_EQUIVALENT_TO,
    RELATIONSHIP_SUPERSEDED_BY,
    RELATIONSHIP_TYPES,
)
from phase3.evaluation.foundations.event_ledger import (
    APPEND_CREATED,
    APPEND_IDEMPOTENT,
    CanonicalEventLedger,
    RetrievalResolutionViolation,
    SingleOccurrenceViolationError,
    UnknownCanonicalMemoryError,
)
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _memory_record(memory_id: str) -> CanonicalMemoryRecord:
    return CanonicalMemoryRecord(
        memory_id=memory_id,
        memory_type=MEMORY_TYPE_FOUNDATION,
        content={"text": f"user fact for {memory_id}."},
        source={"source_type": SOURCE_TYPE_PHASE2_UMR, "reference_id": "umr-77"},
        parent_ids=(),
        creation_event="evt-seed",
        creation_timestamp="2026-01-01T00:00:00Z",
        lifecycle_state=LIFECYCLE_CREATED,
    )


def _ledgers(tmp_path, memory_ids=("loco-mem-001",)):
    memory_ledger = CanonicalMemoryLedger(tmp_path / "memory-ledger")
    for mid in memory_ids:
        memory_ledger.put(_memory_record(mid))
    event_ledger = CanonicalEventLedger(tmp_path / "event-ledger", memory_ledger)
    return memory_ledger, event_ledger


def _rejected_event(
    event_id="evt-rej-001",
    memory_id="loco-mem-001",
    task_id="task-1",
    reason=REJECTED_REASON_BELOW_RERANK_THRESHOLD,
) -> CanonicalEvent:
    return CanonicalEvent(
        event_id=event_id,
        event_type=EVENT_REJECTED,
        memory_ids=(memory_id,),
        task_id=task_id,
        timestamp="2026-01-01T00:05:00Z",
        actor="evidence_selection",
        reason=reason,
    )


def _relationship_event(
    event_id="evt-rel-001",
    memory_ids=("loco-mem-001", "loco-mem-002"),
    relationship_type=RELATIONSHIP_EQUIVALENT_TO,
    mechanism="embedding_similarity_threshold",
    score=0.94,
    threshold=0.9,
) -> CanonicalEvent:
    return CanonicalEvent(
        event_id=event_id,
        event_type=EVENT_RELATIONSHIP_DETECTED,
        memory_ids=memory_ids,
        timestamp="2026-01-01T00:10:00Z",
        actor="creation_policy",
        reason="detected during candidate discovery.",
        relationship_type=relationship_type,
        mechanism=mechanism,
        score=score,
        threshold=threshold,
    )


def _retrieved_event(event_id, memory_id, task_id="task-1") -> CanonicalEvent:
    return CanonicalEvent(
        event_id=event_id,
        event_type=EVENT_RETRIEVED,
        memory_ids=(memory_id,),
        task_id=task_id,
        timestamp="2026-01-01T00:04:00Z",
        actor="candidate_discovery",
        reason="matched query embedding.",
        config_fingerprint="CFG-test-config",
    )


def _selected_event(event_id, memory_id, task_id="task-1") -> CanonicalEvent:
    return CanonicalEvent(
        event_id=event_id,
        event_type=EVENT_SELECTED,
        memory_ids=(memory_id,),
        task_id=task_id,
        timestamp="2026-01-01T00:06:00Z",
        actor="evidence_selection",
        reason="selected for reasoning context.",
        config_fingerprint="CFG-test-config",
    )


# ---------------------------------------------------------------------------
# Section 8, item 1: both event types are valid, appendable CanonicalEvent.event_type values
# ---------------------------------------------------------------------------


def test_rejected_and_relationship_detected_are_valid_event_types():
    assert EVENT_REJECTED in EVENT_TYPES
    assert EVENT_RELATIONSHIP_DETECTED in EVENT_TYPES


def test_rejected_event_appends_through_unmodified_ledger(tmp_path):
    _, event_ledger = _ledgers(tmp_path)
    assert event_ledger.append(_rejected_event()) == APPEND_CREATED
    assert event_ledger.get_event("evt-rej-001").event_type == EVENT_REJECTED


def test_relationship_detected_event_appends_through_unmodified_ledger(tmp_path):
    _, event_ledger = _ledgers(tmp_path, memory_ids=("loco-mem-001", "loco-mem-002"))
    assert event_ledger.append(_relationship_event()) == APPEND_CREATED
    assert event_ledger.get_event("evt-rel-001").event_type == EVENT_RELATIONSHIP_DETECTED


# ---------------------------------------------------------------------------
# Section 8, item 2 / section 9, item 1: rejected.reason closed enum
# ---------------------------------------------------------------------------


def test_rejected_reason_must_be_in_closed_enum():
    for reason in REJECTED_REASONS:
        event = _rejected_event(event_id=f"evt-{reason}", reason=reason)
        assert event.reason == reason


def test_rejected_reason_outside_enum_is_rejected_at_construction():
    with pytest.raises(CanonicalEventValidationError, match="reason"):
        _rejected_event(reason="i felt like it")


def test_rejected_reason_placeholder_is_not_silently_coerced():
    with pytest.raises(CanonicalEventValidationError):
        CanonicalEvent(
            event_id="evt-rej-bad",
            event_type=EVENT_REJECTED,
            memory_ids=("loco-mem-001",),
            task_id="task-1",
            timestamp="2026-01-01T00:05:00Z",
            actor="evidence_selection",
            reason="unknown",
        )


def test_rejected_requires_task_id():
    with pytest.raises(CanonicalEventValidationError, match="task_id"):
        CanonicalEvent(
            event_id="evt-rej-no-task",
            event_type=EVENT_REJECTED,
            memory_ids=("loco-mem-001",),
            timestamp="2026-01-01T00:05:00Z",
            actor="evidence_selection",
            reason=REJECTED_REASON_CAPACITY_CUT,
        )


def test_rejected_requires_exactly_one_memory_id():
    with pytest.raises(CanonicalEventValidationError, match="memory_ids"):
        CanonicalEvent(
            event_id="evt-rej-multi",
            event_type=EVENT_REJECTED,
            memory_ids=("loco-mem-001", "loco-mem-002"),
            task_id="task-1",
            timestamp="2026-01-01T00:05:00Z",
            actor="evidence_selection",
            reason=REJECTED_REASON_CAPACITY_CUT,
        )


# ---------------------------------------------------------------------------
# Section 8, item 3: relationship_type closed set
# ---------------------------------------------------------------------------


def test_relationship_type_must_be_one_of_closed_set():
    for rtype in RELATIONSHIP_TYPES:
        memory_ids = ("loco-mem-001", "loco-mem-002")
        event = _relationship_event(event_id=f"evt-{rtype}", relationship_type=rtype, memory_ids=memory_ids)
        assert event.relationship_type == rtype


def test_relationship_type_outside_closed_set_is_rejected():
    with pytest.raises(CanonicalEventValidationError, match="relationship_type"):
        _relationship_event(relationship_type="probably_related")


# ---------------------------------------------------------------------------
# Section 8, item 4: append-only -- no update/delete path for either new event type
# ---------------------------------------------------------------------------


def test_no_update_or_delete_event_api_still_absent(tmp_path):
    _, event_ledger = _ledgers(tmp_path, memory_ids=("loco-mem-001", "loco-mem-002"))
    assert not hasattr(event_ledger, "update_event")
    assert not hasattr(event_ledger, "delete_event")


def test_rejected_and_relationship_detected_events_are_frozen():
    rejected = _rejected_event()
    with pytest.raises(Exception):
        rejected.reason = "mutated"
    relationship = _relationship_event()
    with pytest.raises(Exception):
        relationship.mechanism = "mutated"


# ---------------------------------------------------------------------------
# Section 8, item 5: retrieved/selected/rejected cross-event invariant
# ---------------------------------------------------------------------------


def test_retrieval_resolution_passes_when_every_candidate_is_selected_or_rejected(tmp_path):
    _, event_ledger = _ledgers(tmp_path, memory_ids=("loco-mem-001", "loco-mem-002"))
    event_ledger.append(_retrieved_event("evt-r1", "loco-mem-001"))
    event_ledger.append(_retrieved_event("evt-r2", "loco-mem-002"))
    event_ledger.append(_selected_event("evt-s1", "loco-mem-001"))
    event_ledger.append(_rejected_event(event_id="evt-j1", memory_id="loco-mem-002"))
    event_ledger.check_retrieval_resolution("task-1")  # must not raise


def test_retrieval_resolution_fails_when_candidate_left_with_neither(tmp_path):
    _, event_ledger = _ledgers(tmp_path, memory_ids=("loco-mem-001", "loco-mem-002"))
    event_ledger.append(_retrieved_event("evt-r1", "loco-mem-001"))
    event_ledger.append(_retrieved_event("evt-r2", "loco-mem-002"))
    event_ledger.append(_selected_event("evt-s1", "loco-mem-001"))
    # loco-mem-002 was retrieved but never selected nor rejected.
    with pytest.raises(RetrievalResolutionViolation):
        event_ledger.check_retrieval_resolution("task-1")


def test_retrieval_resolution_fails_when_candidate_has_both(tmp_path):
    _, event_ledger = _ledgers(tmp_path, memory_ids=("loco-mem-001",))
    event_ledger.append(_retrieved_event("evt-r1", "loco-mem-001"))
    event_ledger.append(_selected_event("evt-s1", "loco-mem-001"))
    event_ledger.append(_rejected_event(event_id="evt-j1", memory_id="loco-mem-001"))
    with pytest.raises(RetrievalResolutionViolation):
        event_ledger.check_retrieval_resolution("task-1")


def test_retrieval_resolution_is_scoped_per_task(tmp_path):
    _, event_ledger = _ledgers(tmp_path, memory_ids=("loco-mem-001",))
    event_ledger.append(_retrieved_event("evt-r1", "loco-mem-001", task_id="task-a"))
    event_ledger.append(_selected_event("evt-s1", "loco-mem-001", task_id="task-a"))
    event_ledger.check_retrieval_resolution("task-a")
    # task-b has no events at all -- vacuously resolved.
    event_ledger.check_retrieval_resolution("task-b")


# ---------------------------------------------------------------------------
# Section 8, item 6: events_for_relationship query
# ---------------------------------------------------------------------------


def test_events_for_relationship_query(tmp_path):
    _, event_ledger = _ledgers(tmp_path, memory_ids=("loco-mem-001", "loco-mem-002", "loco-mem-003"))
    event_ledger.append(_relationship_event())
    other = _relationship_event(
        event_id="evt-rel-002",
        memory_ids=("loco-mem-001", "loco-mem-003"),
    )
    event_ledger.append(other)
    found = event_ledger.events_for_relationship("loco-mem-001", "loco-mem-002")
    assert [e.event_id for e in found] == ["evt-rel-001"]
    # Order-independent on the caller's side.
    found_reversed = event_ledger.events_for_relationship("loco-mem-002", "loco-mem-001")
    assert found_reversed == found
    assert event_ledger.events_for_relationship("loco-mem-002", "loco-mem-003") == ()


# ---------------------------------------------------------------------------
# Section 8, item 7: no vendor/foundation id in either new event type's required fields
# ---------------------------------------------------------------------------


def test_no_foundation_fields_required_for_new_event_types():
    rejected = _rejected_event()
    assert rejected.foundation_name is None
    assert rejected.foundation_memory_id is None
    relationship = _relationship_event()
    assert relationship.foundation_name is None
    assert relationship.foundation_memory_id is None


# ---------------------------------------------------------------------------
# Section 9, item 2: relationship_detected recorded without an eventual supersede_memory()
# call is a valid, permanently-recorded state
# ---------------------------------------------------------------------------


def test_relationship_detected_without_a_following_supersede_call_is_valid(tmp_path):
    _, event_ledger = _ledgers(tmp_path, memory_ids=("loco-mem-001", "loco-mem-002"))
    event = _relationship_event(
        event_id="evt-rel-detect-only",
        relationship_type=RELATIONSHIP_SUPERSEDED_BY,
        memory_ids=("loco-mem-001", "loco-mem-002"),
    )
    assert event_ledger.append(event) == APPEND_CREATED
    # No SupersessionRecord, no 'superseded'/'retired' event exists anywhere -- and none is
    # required for this event to be a legitimate, permanent fact.
    assert event_ledger.get_event("evt-rel-detect-only") is not None


# ---------------------------------------------------------------------------
# Section 9, item 3: unknown memory_id reuses UnknownCanonicalMemoryError
# ---------------------------------------------------------------------------


def test_relationship_detected_rejects_unknown_memory_id(tmp_path):
    _, event_ledger = _ledgers(tmp_path, memory_ids=("loco-mem-001",))
    event = _relationship_event(memory_ids=("loco-mem-001", "zzz-does-not-exist"))
    with pytest.raises(UnknownCanonicalMemoryError):
        event_ledger.append(event)
    assert event_ledger.get_event("evt-rel-001") is None


def test_rejected_rejects_unknown_memory_id(tmp_path):
    _, event_ledger = _ledgers(tmp_path, memory_ids=("loco-mem-001",))
    event = _rejected_event(memory_id="does-not-exist")
    with pytest.raises(UnknownCanonicalMemoryError):
        event_ledger.append(event)


# ---------------------------------------------------------------------------
# Section 9, item 4: two rejected events, same (memory_id, task_id), different reason ->
# collision (default recommendation, per mission section 9)
# ---------------------------------------------------------------------------


def test_two_different_rejected_events_same_memory_and_task_is_a_collision(tmp_path):
    _, event_ledger = _ledgers(tmp_path)
    event_ledger.append(_rejected_event(event_id="evt-j1", reason=REJECTED_REASON_BELOW_RERANK_THRESHOLD))
    colliding = _rejected_event(event_id="evt-j2", reason=REJECTED_REASON_CAPACITY_CUT)
    with pytest.raises(SingleOccurrenceViolationError):
        event_ledger.append(colliding)
    # The original, first-recorded rejection is left untouched.
    assert event_ledger.get_event("evt-j1").reason == REJECTED_REASON_BELOW_RERANK_THRESHOLD
    assert event_ledger.get_event("evt-j2") is None


def test_identical_rejected_event_reappended_is_idempotent_not_a_collision(tmp_path):
    _, event_ledger = _ledgers(tmp_path)
    assert event_ledger.append(_rejected_event()) == APPEND_CREATED
    assert event_ledger.append(_rejected_event()) == APPEND_IDEMPOTENT
    assert len(event_ledger.all_events()) == 1


def test_rejected_events_for_different_tasks_are_both_allowed(tmp_path):
    _, event_ledger = _ledgers(tmp_path)
    event_ledger.append(_rejected_event(event_id="evt-j1", task_id="task-a"))
    event_ledger.append(_rejected_event(event_id="evt-j2", task_id="task-b"))
    assert len(event_ledger.all_events()) == 2


# ---------------------------------------------------------------------------
# Section 9, item 5: relationship_detected with the same memory_id twice is malformed
# ---------------------------------------------------------------------------


def test_relationship_detected_rejects_self_pair():
    with pytest.raises(CanonicalEventValidationError, match="memory_ids"):
        _relationship_event(memory_ids=("loco-mem-001", "loco-mem-001"))


# ---------------------------------------------------------------------------
# Section 3.2 ordering rule: symmetric relationship types record memory_ids lexicographically
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("relationship_type", [RELATIONSHIP_EQUIVALENT_TO, RELATIONSHIP_CONFLICTS_WITH])
def test_symmetric_relationship_types_require_lexicographic_order(relationship_type):
    with pytest.raises(CanonicalEventValidationError, match="lexicographic"):
        _relationship_event(
            memory_ids=("loco-mem-002", "loco-mem-001"),  # out of lexicographic order
            relationship_type=relationship_type,
        )
    # In order -- accepted.
    ok = _relationship_event(
        memory_ids=("loco-mem-001", "loco-mem-002"),
        relationship_type=relationship_type,
    )
    assert ok.memory_ids == ("loco-mem-001", "loco-mem-002")


def test_superseded_by_order_is_semantic_not_lexicographic():
    # superseded first, superseding second -- "z-mem" superseded by "a-mem" is valid even
    # though it is not lexicographic order, because superseded_by's order carries meaning.
    event = _relationship_event(
        memory_ids=("z-mem", "a-mem"),
        relationship_type=RELATIONSHIP_SUPERSEDED_BY,
    )
    assert event.memory_ids == ("z-mem", "a-mem")


# ---------------------------------------------------------------------------
# mechanism/score/threshold field shape
# ---------------------------------------------------------------------------


def test_mechanism_is_required_for_relationship_detected():
    with pytest.raises(CanonicalEventValidationError, match="mechanism"):
        CanonicalEvent(
            event_id="evt-rel-no-mech",
            event_type=EVENT_RELATIONSHIP_DETECTED,
            memory_ids=("loco-mem-001", "loco-mem-002"),
            timestamp="2026-01-01T00:10:00Z",
            actor="creation_policy",
            reason="detected.",
            relationship_type=RELATIONSHIP_EQUIVALENT_TO,
        )


def test_score_and_threshold_are_optional():
    event = CanonicalEvent(
        event_id="evt-rel-no-score",
        event_type=EVENT_RELATIONSHIP_DETECTED,
        memory_ids=("loco-mem-001", "loco-mem-002"),
        timestamp="2026-01-01T00:10:00Z",
        actor="creation_policy",
        reason="manually annotated by a reviewer.",
        relationship_type=RELATIONSHIP_EQUIVALENT_TO,
        mechanism="manual_annotation",
    )
    assert event.score is None
    assert event.threshold is None


def test_relationship_fields_forbidden_on_other_event_types():
    with pytest.raises(CanonicalEventValidationError, match="relationship_type/mechanism/score/threshold"):
        CanonicalEvent(
            event_id="evt-bad-rel-field",
            event_type=EVENT_CREATED,
            memory_ids=("loco-mem-001",),
            timestamp="2026-01-01T00:00:00Z",
            actor="creation_policy",
            reason="ingested.",
            new_state=LIFECYCLE_CREATED,
            mechanism="embedding_similarity_threshold",
        )


# ---------------------------------------------------------------------------
# Serialization round trip
# ---------------------------------------------------------------------------


def test_rejected_event_to_dict_from_dict_round_trip():
    event = _rejected_event()
    assert CanonicalEvent.from_dict(event.to_dict()) == event


def test_relationship_detected_event_to_dict_from_dict_round_trip():
    event = _relationship_event()
    assert CanonicalEvent.from_dict(event.to_dict()) == event


def test_relationship_detected_persists_and_reloads(tmp_path):
    memory_ledger, event_ledger = _ledgers(tmp_path, memory_ids=("loco-mem-001", "loco-mem-002"))
    event_ledger.append(_relationship_event())
    reloaded_memory_ledger = CanonicalMemoryLedger(tmp_path / "memory-ledger")
    reloaded_event_ledger = CanonicalEventLedger(tmp_path / "event-ledger", reloaded_memory_ledger)
    fetched = reloaded_event_ledger.get_event("evt-rel-001")
    assert fetched.relationship_type == RELATIONSHIP_EQUIVALENT_TO
    assert fetched.mechanism == "embedding_similarity_threshold"
    assert fetched.score == 0.94
    assert fetched.threshold == 0.9
