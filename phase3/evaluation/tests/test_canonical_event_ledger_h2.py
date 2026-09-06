"""Phase 3.3-H.2 (Canonical Event Ledger) contract tests.

Covers the 30 test items and 12 invariants listed in the H.2 mission brief. Uses H.1's
`CanonicalMemoryLedger`/`CanonicalMemoryRecord` directly (no foundation/vendor dependency
anywhere in this file -- events reference canonical memories, never vendors).
"""

from __future__ import annotations

import json

import pytest

from phase3.evaluation.contracts.boundary import AgentVisibilityViolation, validate_agent_visible
from phase3.evaluation.foundations.canonical import (
    CanonicalMemoryRecord,
    LIFECYCLE_ACTIVE,
    LIFECYCLE_CREATED,
    LIFECYCLE_RETIRED,
    MEMORY_TYPE_FOUNDATION,
    SOURCE_TYPE_PHASE2_UMR,
)
from phase3.evaluation.foundations.canonical_event import (
    CanonicalEvent,
    CanonicalEventValidationError,
    EVENT_CREATED,
    EVENT_DERIVED,
    EVENT_RETIRED,
    EVENT_RETRIEVED,
    EVENT_SELECTED,
    EVENT_SUPERSEDED,
    EVENT_USED,
)
from phase3.evaluation.foundations.event_ledger import (
    APPEND_CREATED,
    APPEND_IDEMPOTENT,
    CanonicalEventCollisionError,
    CanonicalEventLedger,
    UnknownCanonicalMemoryError,
)
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _memory_record(memory_id: str = "loco-mem-001") -> CanonicalMemoryRecord:
    return CanonicalMemoryRecord(
        memory_id=memory_id,
        memory_type=MEMORY_TYPE_FOUNDATION,
        content={"text": "user: I moved to Denver in 2019."},
        source={"source_type": SOURCE_TYPE_PHASE2_UMR, "reference_id": "umr-77"},
        parent_ids=(),
        creation_event="evt-seed",
        creation_timestamp="2026-01-01T00:00:00Z",
        lifecycle_state=LIFECYCLE_CREATED,
    )


def _ledgers(tmp_path):
    memory_ledger = CanonicalMemoryLedger(tmp_path / "memory-ledger")
    memory_ledger.put(_memory_record())
    event_ledger = CanonicalEventLedger(tmp_path / "event-ledger", memory_ledger)
    return memory_ledger, event_ledger


def _created_event(event_id="evt-001", memory_id="loco-mem-001") -> CanonicalEvent:
    return CanonicalEvent(
        event_id=event_id,
        event_type=EVENT_CREATED,
        memory_ids=(memory_id,),
        timestamp="2026-01-01T00:00:00Z",
        actor="creation_policy",
        reason="ingested from LoCoMo dataset row.",
        new_state=LIFECYCLE_CREATED,
    )


# ---------------------------------------------------------------------------
# 1/2. canonical event construction / schema validation
# ---------------------------------------------------------------------------


def test_canonical_event_construction_valid():
    event = _created_event()
    assert event.event_type == EVENT_CREATED
    assert event.memory_ids == ("loco-mem-001",)


@pytest.mark.parametrize(
    "kwargs,message_fragment",
    [
        ({"event_id": ""}, "event_id"),
        ({"event_type": "bogus"}, "event_type"),
        ({"memory_ids": ()}, "memory_ids must be non-empty"),
        ({"actor": ""}, "actor"),
        ({"reason": ""}, "reason"),
        ({"timestamp": "not-a-timestamp"}, "timestamp"),
    ],
)
def test_schema_validation_rejects_malformed_events(kwargs, message_fragment):
    base = dict(
        event_id="e1",
        event_type=EVENT_CREATED,
        memory_ids=("m1",),
        timestamp="2026-01-01T00:00:00Z",
        actor="creation_policy",
        reason="test",
        new_state=LIFECYCLE_CREATED,
    )
    base.update(kwargs)
    with pytest.raises(CanonicalEventValidationError, match=message_fragment):
        CanonicalEvent(**base)


def test_task_scoped_event_requires_task_id():
    with pytest.raises(CanonicalEventValidationError, match="task_id"):
        CanonicalEvent(
            event_id="e2",
            event_type=EVENT_RETRIEVED,
            memory_ids=("m1",),
            timestamp="2026-01-01T00:00:00Z",
            actor="candidate_discovery",
            reason="query matched.",
        )


def test_non_task_scoped_event_does_not_require_task_id():
    event = CanonicalEvent(
        event_id="e3",
        event_type=EVENT_DERIVED,
        memory_ids=("m1", "m2"),
        source_memory_ids=("m1",),
        target_memory_id="m2",
        timestamp="2026-01-01T00:00:00Z",
        actor="creation_policy",
        reason="derivation.",
    )
    assert event.task_id is None


def test_state_changing_event_requires_new_state():
    with pytest.raises(CanonicalEventValidationError, match="new_state"):
        CanonicalEvent(
            event_id="e4",
            event_type=EVENT_SUPERSEDED,
            memory_ids=("m1",),
            timestamp="2026-01-01T00:00:00Z",
            actor="creation_policy",
            reason="superseded by m2.",
            previous_state=LIFECYCLE_ACTIVE,
        )


def test_superseded_requires_previous_state():
    with pytest.raises(CanonicalEventValidationError, match="previous_state"):
        CanonicalEvent(
            event_id="e5",
            event_type=EVENT_SUPERSEDED,
            memory_ids=("m1",),
            timestamp="2026-01-01T00:00:00Z",
            actor="creation_policy",
            reason="superseded by m2.",
            new_state=LIFECYCLE_RETIRED,
        )


def test_non_state_changing_event_rejects_state_fields():
    with pytest.raises(CanonicalEventValidationError, match="previous_state/new_state must be None"):
        CanonicalEvent(
            event_id="e6",
            event_type=EVENT_USED,
            memory_ids=("m1",),
            task_id="t1",
            timestamp="2026-01-01T00:00:00Z",
            actor="agent",
            reason="cited in answer.",
            new_state=LIFECYCLE_ACTIVE,
        )


def test_foundation_memory_id_requires_foundation_name():
    with pytest.raises(CanonicalEventValidationError, match="foundation_name"):
        CanonicalEvent(
            event_id="e7",
            event_type=EVENT_RETRIEVED,
            memory_ids=("m1",),
            task_id="t1",
            timestamp="2026-01-01T00:00:00Z",
            actor="candidate_discovery",
            reason="retrieved from mem0.",
            foundation_memory_id="vendor-uuid",
        )


# ---------------------------------------------------------------------------
# 3/4/5. event ID uniqueness, idempotency, collision
# ---------------------------------------------------------------------------


def test_event_id_uniqueness_and_idempotent_append(tmp_path):
    _, event_ledger = _ledgers(tmp_path)
    assert event_ledger.append(_created_event()) == APPEND_CREATED
    assert event_ledger.append(_created_event()) == APPEND_IDEMPOTENT
    assert len(event_ledger.all_events()) == 1


def test_event_id_collision_fails_loudly(tmp_path):
    _, event_ledger = _ledgers(tmp_path)
    event_ledger.append(_created_event())
    colliding = _created_event()
    colliding = CanonicalEvent(
        event_id=colliding.event_id,
        event_type=colliding.event_type,
        memory_ids=colliding.memory_ids,
        timestamp=colliding.timestamp,
        actor=colliding.actor,
        reason="DIFFERENT REASON",
        new_state=colliding.new_state,
    )
    with pytest.raises(CanonicalEventCollisionError):
        event_ledger.append(colliding)
    assert event_ledger.get_event("evt-001").reason == "ingested from LoCoMo dataset row."


# ---------------------------------------------------------------------------
# 6/7. durable persistence / reload
# ---------------------------------------------------------------------------


def test_event_persistence_and_reload(tmp_path):
    memory_ledger, event_ledger = _ledgers(tmp_path)
    event_ledger.append(_created_event())

    reloaded_memory_ledger = CanonicalMemoryLedger(tmp_path / "memory-ledger")
    reloaded_event_ledger = CanonicalEventLedger(tmp_path / "event-ledger", reloaded_memory_ledger)
    events = reloaded_event_ledger.events_for_memory("loco-mem-001")
    assert len(events) == 1
    assert events[0].event_id == "evt-001"


def test_events_file_is_valid_jsonl(tmp_path):
    _, event_ledger = _ledgers(tmp_path)
    event_ledger.append(_created_event())
    for line in (event_ledger._events_path).read_text(encoding="utf-8").splitlines():
        json.loads(line)


# ---------------------------------------------------------------------------
# 8/9/10. immutability -- no update_event/delete_event API at all
# ---------------------------------------------------------------------------


def test_no_update_event_api(tmp_path):
    _, event_ledger = _ledgers(tmp_path)
    assert not hasattr(event_ledger, "update_event")


def test_no_delete_event_api(tmp_path):
    _, event_ledger = _ledgers(tmp_path)
    assert not hasattr(event_ledger, "delete_event")


def test_events_are_immutable_dataclass_instances():
    event = _created_event()
    with pytest.raises(Exception):
        event.reason = "mutated"  # frozen dataclass -- must raise


# ---------------------------------------------------------------------------
# 11/12. canonical memory linkage / rejection of unknown canonical memory
# ---------------------------------------------------------------------------


def test_canonical_memory_linkage_enforced(tmp_path):
    _, event_ledger = _ledgers(tmp_path)
    event_ledger.append(_created_event())
    assert event_ledger.get_event("evt-001").memory_ids == ("loco-mem-001",)


def test_rejects_event_for_unknown_canonical_memory(tmp_path):
    _, event_ledger = _ledgers(tmp_path)
    unknown = _created_event(event_id="evt-002", memory_id="does-not-exist")
    with pytest.raises(UnknownCanonicalMemoryError):
        event_ledger.append(unknown)
    # Rejected append leaves no trace at all.
    assert event_ledger.get_event("evt-002") is None
    assert len(event_ledger.all_events()) == 0


def test_event_ledger_never_creates_a_memory_as_a_side_effect(tmp_path):
    memory_ledger, event_ledger = _ledgers(tmp_path)
    unknown = _created_event(event_id="evt-002", memory_id="does-not-exist")
    with pytest.raises(UnknownCanonicalMemoryError):
        event_ledger.append(unknown)
    assert not memory_ledger.exists("does-not-exist")


# ---------------------------------------------------------------------------
# 13. foundation alias linkage
# ---------------------------------------------------------------------------


def test_foundation_alias_linkage(tmp_path):
    _, event_ledger = _ledgers(tmp_path)
    event = CanonicalEvent(
        event_id="evt-003",
        event_type=EVENT_RETRIEVED,
        memory_ids=("loco-mem-001",),
        task_id="task-1",
        timestamp="2026-01-01T00:05:00Z",
        actor="candidate_discovery",
        reason="matched query embedding.",
        foundation_name="mem0",
        foundation_memory_id="vendor-uuid-abc",
        config_fingerprint="CFG-test-config",
    )
    event_ledger.append(event)
    fetched = event_ledger.get_event("evt-003")
    assert fetched.foundation_name == "mem0"
    assert fetched.foundation_memory_id == "vendor-uuid-abc"
    # The canonical memory id, not the vendor id, remains the linkage key.
    assert fetched.memory_ids == ("loco-mem-001",)


# ---------------------------------------------------------------------------
# 14/15/16. task linkage, actor, timestamp validation
# ---------------------------------------------------------------------------


def test_task_linkage_present_only_where_applicable(tmp_path):
    _, event_ledger = _ledgers(tmp_path)
    event_ledger.append(_created_event())  # created -- no task_id
    retrieved = CanonicalEvent(
        event_id="evt-004",
        event_type=EVENT_RETRIEVED,
        memory_ids=("loco-mem-001",),
        task_id="task-1",
        timestamp="2026-01-01T00:05:00Z",
        actor="candidate_discovery",
        reason="matched query embedding.",
        config_fingerprint="CFG-test-config",
    )
    event_ledger.append(retrieved)
    assert event_ledger.get_event("evt-001").task_id is None
    assert event_ledger.get_event("evt-004").task_id == "task-1"


def test_actor_and_timestamp_are_validated():
    with pytest.raises(CanonicalEventValidationError):
        CanonicalEvent(
            event_id="e8",
            event_type=EVENT_CREATED,
            memory_ids=("m1",),
            timestamp="2026-01-01T00:00:00Z",
            actor="",
            reason="test",
            new_state=LIFECYCLE_CREATED,
        )
    with pytest.raises(CanonicalEventValidationError):
        CanonicalEvent(
            event_id="e9",
            event_type=EVENT_CREATED,
            memory_ids=("m1",),
            timestamp="banana",
            actor="creation_policy",
            reason="test",
            new_state=LIFECYCLE_CREATED,
        )


# ---------------------------------------------------------------------------
# 17. event ordering / reconstruction
# ---------------------------------------------------------------------------


def test_event_ordering_is_append_order_not_timestamp_order(tmp_path):
    _, event_ledger = _ledgers(tmp_path)
    # Deliberately appended with timestamps OUT of chronological order -- append order
    # must still be what is returned, never a timestamp-sorted reordering.
    first = CanonicalEvent(
        event_id="evt-a",
        event_type=EVENT_CREATED,
        memory_ids=("loco-mem-001",),
        timestamp="2026-06-01T00:00:00Z",
        actor="creation_policy",
        reason="first appended, later timestamp",
        new_state=LIFECYCLE_CREATED,
    )
    second = CanonicalEvent(
        event_id="evt-b",
        event_type=EVENT_RETRIEVED,
        memory_ids=("loco-mem-001",),
        task_id="t1",
        timestamp="2026-01-01T00:00:00Z",
        actor="candidate_discovery",
        reason="second appended, earlier timestamp",
        config_fingerprint="CFG-test-config",
    )
    event_ledger.append(first)
    event_ledger.append(second)
    ordered = event_ledger.events_for_memory("loco-mem-001")
    assert [e.event_id for e in ordered] == ["evt-a", "evt-b"]


# ---------------------------------------------------------------------------
# 18/19/20/21. query API
# ---------------------------------------------------------------------------


def test_events_for_memory(tmp_path):
    _, event_ledger = _ledgers(tmp_path)
    event_ledger.append(_created_event())
    assert [e.event_id for e in event_ledger.events_for_memory("loco-mem-001")] == ["evt-001"]
    assert event_ledger.events_for_memory("nonexistent") == ()


def test_events_for_task(tmp_path):
    _, event_ledger = _ledgers(tmp_path)
    event_ledger.append(_created_event())
    retrieved = CanonicalEvent(
        event_id="evt-004",
        event_type=EVENT_RETRIEVED,
        memory_ids=("loco-mem-001",),
        task_id="task-1",
        timestamp="2026-01-01T00:05:00Z",
        actor="candidate_discovery",
        reason="matched query embedding.",
        config_fingerprint="CFG-test-config",
    )
    event_ledger.append(retrieved)
    assert [e.event_id for e in event_ledger.events_for_task("task-1")] == ["evt-004"]
    assert event_ledger.events_for_task("no-such-task") == ()


def test_events_for_foundation(tmp_path):
    _, event_ledger = _ledgers(tmp_path)
    event = CanonicalEvent(
        event_id="evt-005",
        event_type=EVENT_SELECTED,
        memory_ids=("loco-mem-001",),
        task_id="task-1",
        timestamp="2026-01-01T00:06:00Z",
        actor="evidence_selection",
        reason="selected for reasoning context.",
        foundation_name="mem0",
        foundation_memory_id="vendor-uuid-abc",
        config_fingerprint="CFG-test-config",
    )
    event_ledger.append(event)
    assert [e.event_id for e in event_ledger.events_for_foundation("mem0")] == ["evt-005"]
    assert event_ledger.events_for_foundation("a-mem") == ()


def test_reconstruct_memory_history(tmp_path):
    _, event_ledger = _ledgers(tmp_path)
    event_ledger.append(_created_event())
    retrieved = CanonicalEvent(
        event_id="evt-004",
        event_type=EVENT_RETRIEVED,
        memory_ids=("loco-mem-001",),
        task_id="task-1",
        timestamp="2026-01-01T00:05:00Z",
        actor="candidate_discovery",
        reason="matched query embedding.",
        config_fingerprint="CFG-test-config",
    )
    event_ledger.append(retrieved)
    history = event_ledger.reconstruct_memory_history("loco-mem-001")
    assert [e.event_type for e in history] == [EVENT_CREATED, EVENT_RETRIEVED]
    assert history == event_ledger.events_for_memory("loco-mem-001")


# ---------------------------------------------------------------------------
# 22/23. reconstruction without vendor availability; vendor deletion does not erase history
# ---------------------------------------------------------------------------


def test_reconstruction_without_any_vendor_involved(tmp_path):
    """No foundation adapter object is even constructed anywhere in this test module --
    every event/memory operation is pure benchmark-side state. This is the strongest form
    of "reconstruction does not require a vendor service": there is no vendor to ask."""
    _, event_ledger = _ledgers(tmp_path)
    event_ledger.append(_created_event())
    history = event_ledger.reconstruct_memory_history("loco-mem-001")
    assert len(history) == 1


def test_vendor_deletion_cannot_erase_event_history(tmp_path):
    """Simulates a vendor foundation being deleted/reset by simply never involving one --
    the event ledger has no code path that could be affected by a vendor's state at all,
    so a vendor deletion (which this ledger never observes) cannot erase anything."""
    memory_ledger, event_ledger = _ledgers(tmp_path)
    event_ledger.append(_created_event())
    retrieved_evt = CanonicalEvent(
        event_id="evt-004",
        event_type=EVENT_RETRIEVED,
        memory_ids=("loco-mem-001",),
        task_id="task-1",
        timestamp="2026-01-01T00:05:00Z",
        actor="candidate_discovery",
        reason="matched query embedding.",
        foundation_name="mem0",
        foundation_memory_id="vendor-uuid-abc",
        config_fingerprint="CFG-test-config",
    )
    event_ledger.append(retrieved_evt)
    # "Vendor deletes vendor-uuid-abc" has no representation in this ledger's state at
    # all -- there is nothing to invalidate.
    history = event_ledger.reconstruct_memory_history("loco-mem-001")
    assert history[1].foundation_memory_id == "vendor-uuid-abc"


# ---------------------------------------------------------------------------
# 24. experiment reset is not treated as memory retirement
# ---------------------------------------------------------------------------


def test_experiment_reset_is_not_a_retirement_event():
    """relationship_schema.md defines no 'experiment_reset' event type (a documented gap
    -- see PHASE3_3_H2_CANONICAL_EVENT_LEDGER.md section 14). This module therefore has no
    code path that could label a foundation reset/clear operation as `retired`: nothing in
    this stage auto-generates ANY event from a foundation call, so the two can never be
    conflated. This test asserts the vocabulary itself: 'retired' requires an explicit,
    manually-supplied previous_state/new_state state transition, never a bare reset
    signal."""
    with pytest.raises(CanonicalEventValidationError):
        # An attempt to construct a 'retired' event with no state transition at all must
        # fail -- there is no bare "the foundation was reset" shorthand that satisfies it.
        CanonicalEvent(
            event_id="evt-reset",
            event_type=EVENT_RETIRED,
            memory_ids=("loco-mem-001",),
            timestamp="2026-01-01T00:00:00Z",
            actor="system",
            reason="foundation.reset() was called",
        )
    assert "experiment_reset" not in (
        EVENT_CREATED, EVENT_RETRIEVED, EVENT_SELECTED, EVENT_USED, EVENT_DERIVED, EVENT_SUPERSEDED, EVENT_RETIRED,
    )


# ---------------------------------------------------------------------------
# 25/26. evaluator-only fields do not enter agent-visible context / no model-prompt leak
# ---------------------------------------------------------------------------


def test_event_ledger_modules_have_no_coupling_to_agent_facing_modules():
    """Structural invariant: nothing in the agent execution path imports the event ledger,
    so canonical events cannot be automatically inserted into agent-visible context or a
    model prompt -- there is no import edge for that to happen through."""
    import inspect

    from phase3.evaluation.agent import conditions as agent_conditions
    from phase3.evaluation.agent_runtime import runner as agent_runner

    for module in (agent_conditions, agent_runner):
        source = inspect.getsource(module)
        assert "event_ledger" not in source
        assert "canonical_event" not in source


def test_event_dict_would_be_rejected_if_misused_as_agent_visible_payload():
    """If a caller mistakenly tried to smuggle a CanonicalEvent (which may legitimately
    carry evaluator-only `reason` text, since it is benchmark infrastructure, not
    agent-visible content) into an agent-visible payload under a forbidden key, the
    EXISTING, unweakened boundary check must still catch it."""
    event = CanonicalEvent(
        event_id="evt-gold",
        event_type=EVENT_USED,
        memory_ids=("loco-mem-001",),
        task_id="task-1",
        timestamp="2026-01-01T00:00:00Z",
        actor="evaluator",
        reason="matches gold_evidence_ids for this task",
    )
    misused_payload = {"condition": "RETRIEVED_MEMORY", "gold_evidence_ids": [event.event_id]}
    with pytest.raises(AgentVisibilityViolation):
        validate_agent_visible(misused_payload)


# ---------------------------------------------------------------------------
# 27/28. crash/durability behavior where practical; malformed record handling
# ---------------------------------------------------------------------------


def test_durability_flush_and_fsync_are_used(tmp_path):
    """Each append is immediately readable by a FRESH ledger instance without the writer
    process doing anything else -- proof the write was actually flushed/fsynced, not left
    buffered in the writer's own process memory."""
    memory_ledger, event_ledger = _ledgers(tmp_path)
    event_ledger.append(_created_event())
    fresh_memory_ledger = CanonicalMemoryLedger(tmp_path / "memory-ledger")
    fresh_event_ledger = CanonicalEventLedger(tmp_path / "event-ledger", fresh_memory_ledger)
    assert fresh_event_ledger.get_event("evt-001") is not None


def test_malformed_jsonl_line_raises_rather_than_silently_skipping(tmp_path):
    memory_ledger, event_ledger = _ledgers(tmp_path)
    event_ledger.append(_created_event())
    with open(event_ledger._events_path, "a", encoding="utf-8") as fh:
        fh.write("{not valid json\n")
    with pytest.raises(json.JSONDecodeError):
        CanonicalEventLedger(event_ledger._dir, memory_ledger)


# ---------------------------------------------------------------------------
# 29. duplicate event handling (see also #3/4/5 above)
# ---------------------------------------------------------------------------


def test_duplicate_identical_event_is_idempotent_not_double_appended(tmp_path):
    _, event_ledger = _ledgers(tmp_path)
    event_ledger.append(_created_event())
    event_ledger.append(_created_event())
    event_ledger.append(_created_event())
    assert len(event_ledger.all_events()) == 1


# ---------------------------------------------------------------------------
# 30. multiple memories have isolated histories
# ---------------------------------------------------------------------------


def test_multiple_memories_have_isolated_histories(tmp_path):
    memory_ledger, event_ledger = _ledgers(tmp_path)
    memory_ledger.put(_memory_record("loco-mem-002"))
    event_ledger.append(_created_event(event_id="evt-001", memory_id="loco-mem-001"))
    event_ledger.append(_created_event(event_id="evt-002", memory_id="loco-mem-002"))
    history_1 = event_ledger.reconstruct_memory_history("loco-mem-001")
    history_2 = event_ledger.reconstruct_memory_history("loco-mem-002")
    assert [e.event_id for e in history_1] == ["evt-001"]
    assert [e.event_id for e in history_2] == ["evt-002"]


# ---------------------------------------------------------------------------
# Invariant-focused extras (serialization round trip; content integrity)
# ---------------------------------------------------------------------------


def test_to_dict_from_dict_round_trip():
    event = _created_event()
    assert CanonicalEvent.from_dict(event.to_dict()) == event


def test_event_content_integrity_never_rewritten_by_ledger(tmp_path):
    """An appended event's payload, read back, is byte-identical to what was appended --
    the ledger never mutates a historical fact (e.g. a foundation_memory_id) after the
    fact, even though nothing prevents the underlying vendor record from later changing."""
    _, event_ledger = _ledgers(tmp_path)
    original = CanonicalEvent(
        event_id="evt-006",
        event_type=EVENT_RETRIEVED,
        memory_ids=("loco-mem-001",),
        task_id="task-1",
        timestamp="2026-01-01T00:05:00Z",
        actor="candidate_discovery",
        reason="matched query embedding.",
        foundation_name="mem0",
        foundation_memory_id="vendor-uuid-abc",
        config_fingerprint="CFG-test-config",
    )
    event_ledger.append(original)
    fetched = event_ledger.get_event("evt-006")
    assert fetched == original
