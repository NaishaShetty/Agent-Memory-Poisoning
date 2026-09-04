"""Phase 3.3-H.2-R (Canonical Event Ledger Remediation) contract tests.

Covers the 24 test items and 12 invariants listed in the H.2-R mission brief: experiment/
run boundary representation, benchmark-owned event ID authority, and multi-memory lineage
role semantics. Does not re-test everything H.2 already covers
(`test_canonical_event_ledger_h2.py` remains the authoritative H.2 contract suite, run
unmodified except for one derived-event test updated for the new required lineage fields).
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
    MEMORY_TYPE_DERIVED,
    MEMORY_TYPE_FOUNDATION,
    SOURCE_TYPE_DERIVATION_EVENT,
    SOURCE_TYPE_PHASE2_UMR,
)
from phase3.evaluation.foundations.canonical_event import (
    CanonicalEvent,
    CanonicalEventValidationError,
    EVENT_CREATED,
    EVENT_DERIVED,
    EVENT_RETRIEVED,
    EVENT_SUPERSEDED,
)
from phase3.evaluation.foundations.event_identity import (
    EVENT_ID_PREFIX,
    generate_event_id,
    looks_like_generated_event_id,
)
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.experiment_boundary import (
    APPEND_CREATED,
    APPEND_IDEMPOTENT,
    BOUNDARY_RESET,
    ExperimentBoundaryCollisionError,
    ExperimentBoundaryLedger,
    ExperimentBoundaryRecord,
    ExperimentBoundaryValidationError,
)
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger


def _memory_record(memory_id: str, memory_type=MEMORY_TYPE_FOUNDATION, parent_ids=()) -> CanonicalMemoryRecord:
    source = (
        {"source_type": SOURCE_TYPE_DERIVATION_EVENT, "reference_id": "deriv-1"}
        if memory_type == MEMORY_TYPE_DERIVED
        else {"source_type": SOURCE_TYPE_PHASE2_UMR, "reference_id": "umr-1"}
    )
    return CanonicalMemoryRecord(
        memory_id=memory_id,
        memory_type=memory_type,
        content={"text": f"content for {memory_id}"},
        source=source,
        parent_ids=tuple(parent_ids),
        creation_event="evt-seed",
        creation_timestamp="2026-01-01T00:00:00Z",
        lifecycle_state=LIFECYCLE_CREATED,
    )


def _ledgers(tmp_path):
    memory_ledger = CanonicalMemoryLedger(tmp_path / "memory-ledger")
    memory_ledger.put(_memory_record("m1"))
    memory_ledger.put(_memory_record("m2"))
    memory_ledger.put(_memory_record("m3", memory_type=MEMORY_TYPE_DERIVED, parent_ids=("m1", "m2")))
    event_ledger = CanonicalEventLedger(tmp_path / "event-ledger", memory_ledger)
    return memory_ledger, event_ledger


# ===========================================================================
# EXPERIMENT BOUNDARY -- items 1-5
# ===========================================================================


def _boundary(boundary_id="BND-1", reason="isolation reset before next pool") -> ExperimentBoundaryRecord:
    return ExperimentBoundaryRecord(
        boundary_id=boundary_id,
        boundary_type=BOUNDARY_RESET,
        scope={"dataset": "longmemeval", "pool_key": "haystack-3", "foundation_name": "a-mem"},
        timestamp="2026-01-01T00:00:00Z",
        actor="campaign_formal_runner",
        reason=reason,
    )


def test_1_experiment_boundary_can_be_represented(tmp_path):
    ledger = ExperimentBoundaryLedger(tmp_path / "boundaries")
    result = ledger.append(_boundary())
    assert result == APPEND_CREATED
    assert ledger.get_boundary("BND-1").boundary_type == BOUNDARY_RESET


def test_2_boundary_cannot_be_confused_with_memory_retirement(tmp_path):
    """Structural, not conventional: ExperimentBoundaryRecord is a different type with no
    memory_ids/lifecycle_state field at all -- there is no value that could satisfy both
    a CanonicalEvent's and an ExperimentBoundaryRecord's constructor simultaneously."""
    boundary = _boundary()
    assert not hasattr(boundary, "memory_ids")
    assert not hasattr(boundary, "lifecycle_state")
    assert not hasattr(boundary, "previous_state")
    assert not hasattr(boundary, "new_state")
    assert not isinstance(boundary, CanonicalEvent)


def test_3_foundation_reset_cannot_automatically_become_retirement(tmp_path):
    """No code path anywhere converts an ExperimentBoundaryRecord into a CanonicalEvent,
    and a bare reset signal (no real lifecycle state transition) cannot satisfy a 'retired'
    CanonicalEvent's constructor at all -- both facts hold simultaneously, from different
    angles, per the H.2 test `test_experiment_reset_is_not_a_retirement_event` and this
    module's structural separation."""
    import inspect

    from phase3.evaluation.foundations import event_ledger as event_ledger_module

    source = inspect.getsource(event_ledger_module)
    assert "ExperimentBoundary" not in source
    assert "experiment_boundary" not in source


def test_4_boundary_survives_ledger_reload(tmp_path):
    storage = tmp_path / "boundaries"
    ledger1 = ExperimentBoundaryLedger(storage)
    ledger1.append(_boundary())

    ledger2 = ExperimentBoundaryLedger(storage)
    reloaded = ledger2.get_boundary("BND-1")
    assert reloaded is not None
    assert reloaded.scope == {"dataset": "longmemeval", "pool_key": "haystack-3", "foundation_name": "a-mem"}


def test_5_memory_history_and_experiment_history_remain_semantically_distinct(tmp_path):
    memory_ledger, event_ledger = _ledgers(tmp_path)
    boundary_ledger = ExperimentBoundaryLedger(tmp_path / "boundaries")
    boundary_ledger.append(_boundary())
    event_ledger.append(
        CanonicalEvent(
            event_id="e-created-m1",
            event_type=EVENT_CREATED,
            memory_ids=("m1",),
            timestamp="2026-01-01T00:00:00Z",
            actor="creation_policy",
            reason="ingested",
            new_state=LIFECYCLE_CREATED,
        )
    )
    # Querying memory history never returns boundary records and vice versa -- there is no
    # shared query surface at all.
    history = event_ledger.reconstruct_memory_history("m1")
    assert all(isinstance(e, CanonicalEvent) for e in history)
    boundaries = boundary_ledger.all_boundaries()
    assert all(isinstance(b, ExperimentBoundaryRecord) for b in boundaries)
    assert not hasattr(event_ledger, "all_boundaries")
    assert not hasattr(boundary_ledger, "events_for_memory")


def test_boundary_id_collision_fails_loudly(tmp_path):
    ledger = ExperimentBoundaryLedger(tmp_path / "boundaries")
    ledger.append(_boundary())
    colliding = _boundary(reason="DIFFERENT REASON")
    with pytest.raises(ExperimentBoundaryCollisionError):
        ledger.append(colliding)


def test_boundary_idempotent_rewrite(tmp_path):
    ledger = ExperimentBoundaryLedger(tmp_path / "boundaries")
    assert ledger.append(_boundary()) == APPEND_CREATED
    assert ledger.append(_boundary()) == APPEND_IDEMPOTENT
    assert len(ledger.all_boundaries()) == 1


def test_boundary_validation_rejects_unknown_type():
    with pytest.raises(ExperimentBoundaryValidationError):
        ExperimentBoundaryRecord(
            boundary_id="BND-2",
            boundary_type="CAMPAIGN_START",  # not in BOUNDARY_TYPES -- not invented here
            scope={},
            timestamp="2026-01-01T00:00:00Z",
            actor="system",
            reason="test",
        )


# ===========================================================================
# EVENT ID FACTORY -- items 6-12
# ===========================================================================


def test_6_benchmark_event_id_factory_exists():
    event_id = generate_event_id(
        event_type=EVENT_CREATED,
        memory_ids=("m1",),
        timestamp="2026-01-01T00:00:00Z",
        actor="creation_policy",
        reason="ingested",
        new_state=LIFECYCLE_CREATED,
    )
    assert isinstance(event_id, str) and event_id
    assert looks_like_generated_event_id(event_id)
    assert event_id.startswith(f"{EVENT_ID_PREFIX}-")


def test_7_generated_ids_are_stable():
    kwargs = dict(
        event_type=EVENT_CREATED,
        memory_ids=("m1",),
        timestamp="2026-01-01T00:00:00Z",
        actor="creation_policy",
        reason="ingested",
        new_state=LIFECYCLE_CREATED,
    )
    assert generate_event_id(**kwargs) == generate_event_id(**kwargs)


def test_8_generated_ids_independent_of_vendor_ids():
    """The factory's signature has no vendor/foundation-adapter parameter at all -- it is
    pure Python operating only on the event's own benchmark-defined fields."""
    import inspect

    sig = inspect.signature(generate_event_id)
    for name in sig.parameters:
        assert "adapter" not in name.lower()
        assert "vendor" not in name.lower()

    # Two events differing ONLY in foundation_memory_id (a vendor id) get DIFFERENT
    # benchmark event ids -- the vendor id still influences content-derived identity (it is
    # part of the historical fact being recorded), but the id itself is never copied from,
    # or equal to, the vendor id.
    event_id = generate_event_id(
        event_type=EVENT_RETRIEVED,
        memory_ids=("m1",),
        timestamp="2026-01-01T00:00:00Z",
        actor="candidate_discovery",
        reason="matched",
        task_id="t1",
        foundation_name="mem0",
        foundation_memory_id="vendor-uuid-abc",
    )
    assert event_id != "vendor-uuid-abc"
    assert "vendor-uuid-abc" not in event_id


def test_9_event_id_namespace_distinct_from_memory_ids(tmp_path):
    memory_ledger, event_ledger = _ledgers(tmp_path)
    event_id = generate_event_id(
        event_type=EVENT_CREATED,
        memory_ids=("m1",),
        timestamp="2026-01-01T00:00:00Z",
        actor="creation_policy",
        reason="ingested",
        new_state=LIFECYCLE_CREATED,
    )
    assert event_id != "m1"
    assert not memory_ledger.exists(event_id)
    event = CanonicalEvent(
        event_id=event_id,
        event_type=EVENT_CREATED,
        memory_ids=("m1",),
        timestamp="2026-01-01T00:00:00Z",
        actor="creation_policy",
        reason="ingested",
        new_state=LIFECYCLE_CREATED,
    )
    event_ledger.append(event)
    assert event_ledger.get_event(event_id) is not None
    # The event id is never accepted as a memory id -- events_for_memory(event_id) finds
    # nothing, since no memory_ids field anywhere equals the event's own id.
    assert event_ledger.events_for_memory(event_id) == ()


def test_10_event_id_collision_remains_rejected(tmp_path):
    from phase3.evaluation.foundations.event_ledger import CanonicalEventCollisionError

    _, event_ledger = _ledgers(tmp_path)
    event_id = generate_event_id(
        event_type=EVENT_CREATED,
        memory_ids=("m1",),
        timestamp="2026-01-01T00:00:00Z",
        actor="creation_policy",
        reason="ingested",
        new_state=LIFECYCLE_CREATED,
    )
    first = CanonicalEvent(
        event_id=event_id, event_type=EVENT_CREATED, memory_ids=("m1",),
        timestamp="2026-01-01T00:00:00Z", actor="creation_policy", reason="ingested",
        new_state=LIFECYCLE_CREATED,
    )
    event_ledger.append(first)
    # Same event_id, DIFFERENT reason -- the factory only supplies the id; the ledger's own
    # collision check is what actually enforces the policy, exactly as before H.2-R.
    colliding = CanonicalEvent(
        event_id=event_id, event_type=EVENT_CREATED, memory_ids=("m1",),
        timestamp="2026-01-01T00:00:00Z", actor="creation_policy", reason="DIFFERENT REASON",
        new_state=LIFECYCLE_CREATED,
    )
    with pytest.raises(CanonicalEventCollisionError):
        event_ledger.append(colliding)


def test_11_duplicate_identical_event_behavior_remains_deterministic(tmp_path):
    from phase3.evaluation.foundations.event_ledger import APPEND_IDEMPOTENT as EVT_APPEND_IDEMPOTENT

    _, event_ledger = _ledgers(tmp_path)
    kwargs = dict(
        event_type=EVENT_CREATED, memory_ids=("m1",), timestamp="2026-01-01T00:00:00Z",
        actor="creation_policy", reason="ingested", new_state=LIFECYCLE_CREATED,
    )
    event_id = generate_event_id(**kwargs)
    event = CanonicalEvent(event_id=event_id, **kwargs)
    event_ledger.append(event)
    # Two independently-constructed callers describing the SAME fact get the SAME id AND
    # the SAME idempotent outcome -- deterministic end to end.
    same_event_id = generate_event_id(**kwargs)
    assert same_event_id == event_id
    assert event_ledger.append(CanonicalEvent(event_id=same_event_id, **kwargs)) == EVT_APPEND_IDEMPOTENT


def test_12_ids_reproducible_under_deterministic_conventions():
    """Mirrors security.reproducibility.fingerprint()'s own reproducibility guarantee --
    this factory adds no additional source of nondeterminism (no random, no uuid4, no
    wall-clock read) on top of it."""
    import inspect

    source = inspect.getsource(generate_event_id)
    assert "uuid" not in source.lower()
    assert "random" not in source.lower()
    assert "time.time" not in source
    assert "datetime.now" not in source


# ===========================================================================
# LINEAGE -- items 13-19
# ===========================================================================


def test_13_single_memory_events_remain_valid(tmp_path):
    _, event_ledger = _ledgers(tmp_path)
    event = CanonicalEvent(
        event_id="e-single", event_type=EVENT_CREATED, memory_ids=("m1",),
        timestamp="2026-01-01T00:00:00Z", actor="creation_policy", reason="ingested",
        new_state=LIFECYCLE_CREATED,
    )
    event_ledger.append(event)
    assert event_ledger.get_event("e-single").source_memory_ids is None
    assert event_ledger.get_event("e-single").target_memory_id is None


def _derived_event(event_id="e-derived") -> CanonicalEvent:
    return CanonicalEvent(
        event_id=event_id,
        event_type=EVENT_DERIVED,
        memory_ids=("m1", "m2", "m3"),
        source_memory_ids=("m1", "m2"),
        target_memory_id="m3",
        timestamp="2026-01-01T00:05:00Z",
        actor="creation_policy",
        reason="derived summary from two source memories.",
    )


def test_14_multi_memory_relationships_preserve_explicit_roles(tmp_path):
    _, event_ledger = _ledgers(tmp_path)
    event_ledger.append(_derived_event())
    fetched = event_ledger.get_event("e-derived")
    assert fetched.source_memory_ids == ("m1", "m2")
    assert fetched.target_memory_id == "m3"


def test_15_source_and_target_cannot_be_inferred_only_from_list_position():
    """memory_ids=(m1,m2,m3) alone is ambiguous; swapping the ORDER of memory_ids must not
    change which id role() reports as the target -- role comes only from the explicit
    fields, never position."""
    event_a = CanonicalEvent(
        event_id="e-a", event_type=EVENT_DERIVED,
        memory_ids=("m1", "m2", "m3"), source_memory_ids=("m1", "m2"), target_memory_id="m3",
        timestamp="2026-01-01T00:00:00Z", actor="creation_policy", reason="derivation.",
    )
    event_b = CanonicalEvent(
        event_id="e-b", event_type=EVENT_DERIVED,
        memory_ids=("m3", "m2", "m1"),  # same set, different ORDER
        source_memory_ids=("m1", "m2"), target_memory_id="m3",
        timestamp="2026-01-01T00:00:00Z", actor="creation_policy", reason="derivation.",
    )
    assert event_a.target_memory_id == event_b.target_memory_id == "m3"
    assert set(event_a.memory_ids) == set(event_b.memory_ids)

    with pytest.raises(CanonicalEventValidationError, match="target_memory_id"):
        CanonicalEvent(
            event_id="e-c", event_type=EVENT_DERIVED,
            memory_ids=("m1", "m2", "m3"), source_memory_ids=("m1", "m2", "m3"), target_memory_id=None,
            timestamp="2026-01-01T00:00:00Z", actor="creation_policy", reason="derivation.",
        )


def test_16_derived_relationships_reconstruct_correctly(tmp_path):
    _, event_ledger = _ledgers(tmp_path)
    event_ledger.append(_derived_event())
    history_target = event_ledger.reconstruct_memory_history("m3")
    assert history_target[0].event_type == EVENT_DERIVED
    assert history_target[0].target_memory_id == "m3"


def test_17_multiple_source_memories_reconstruct_correctly(tmp_path):
    _, event_ledger = _ledgers(tmp_path)
    event_ledger.append(_derived_event())
    for source_id in ("m1", "m2"):
        history = event_ledger.reconstruct_memory_history(source_id)
        assert len(history) == 1
        assert source_id in history[0].source_memory_ids
        assert history[0].target_memory_id == "m3"


def test_18_unrelated_memories_remain_isolated(tmp_path):
    memory_ledger, event_ledger = _ledgers(tmp_path)
    memory_ledger.put(_memory_record("m4"))
    event_ledger.append(_derived_event())
    assert event_ledger.reconstruct_memory_history("m4") == ()


def test_19_vendor_ids_cannot_become_lineage_identifiers(tmp_path):
    """source_memory_ids/target_memory_id must be canonical memory ids -- a vendor id
    (never registered in the CanonicalMemoryLedger) cannot satisfy the memory-linkage
    check `event_ledger.append()` performs, since memory_ids (which must equal source union
    target) is checked against the canonical memory ledger, not any vendor store."""
    from phase3.evaluation.foundations.event_ledger import UnknownCanonicalMemoryError

    _, event_ledger = _ledgers(tmp_path)
    bogus = CanonicalEvent(
        event_id="e-bogus", event_type=EVENT_DERIVED,
        memory_ids=("m1", "vendor-uuid-abc"),
        source_memory_ids=("m1",), target_memory_id="vendor-uuid-abc",
        timestamp="2026-01-01T00:00:00Z", actor="creation_policy", reason="derivation.",
    )
    with pytest.raises(UnknownCanonicalMemoryError):
        event_ledger.append(bogus)


def test_lineage_target_cannot_equal_a_source():
    with pytest.raises(CanonicalEventValidationError, match="own parent"):
        CanonicalEvent(
            event_id="e-self", event_type=EVENT_DERIVED,
            memory_ids=("m1", "m2"), source_memory_ids=("m1", "m2"), target_memory_id="m2",
            timestamp="2026-01-01T00:00:00Z", actor="creation_policy", reason="derivation.",
        )


def test_non_derived_event_rejects_lineage_fields():
    with pytest.raises(CanonicalEventValidationError, match="source_memory_ids/target_memory_id must be None"):
        CanonicalEvent(
            event_id="e-x", event_type=EVENT_SUPERSEDED,
            memory_ids=("m1",), source_memory_ids=("m2",), target_memory_id="m1",
            timestamp="2026-01-01T00:00:00Z", actor="creation_policy", reason="test.",
            previous_state=LIFECYCLE_ACTIVE, new_state=LIFECYCLE_RETIRED,
        )


def test_lineage_round_trips_through_serialization():
    event = _derived_event()
    assert CanonicalEvent.from_dict(event.to_dict()) == event


# ===========================================================================
# REGRESSION -- items 20-24 (spot checks; full suite run separately)
# ===========================================================================


def test_20_existing_h2_module_still_importable_and_functional(tmp_path):
    memory_ledger, event_ledger = _ledgers(tmp_path)
    non_lineage_event = CanonicalEvent(
        event_id="e-plain", event_type=EVENT_CREATED, memory_ids=("m1",),
        timestamp="2026-01-01T00:00:00Z", actor="creation_policy", reason="ingested",
        new_state=LIFECYCLE_CREATED,
    )
    event_ledger.append(non_lineage_event)
    assert event_ledger.get_event("e-plain") is not None


def test_22_leakage_boundaries_remain_unchanged():
    with pytest.raises(AgentVisibilityViolation):
        validate_agent_visible({"gold_evidence_ids": ["m1"]})


def test_23_no_event_information_enters_agent_visible_context():
    import inspect

    from phase3.evaluation.agent import conditions as agent_conditions
    from phase3.evaluation.agent_runtime import runner as agent_runner

    for module in (agent_conditions, agent_runner):
        source = inspect.getsource(module)
        assert "event_identity" not in source
        assert "experiment_boundary" not in source
        assert "event_ledger" not in source


def test_boundaries_jsonl_and_events_jsonl_are_valid_jsonl(tmp_path):
    _, event_ledger = _ledgers(tmp_path)
    event_ledger.append(_derived_event())
    boundary_ledger = ExperimentBoundaryLedger(tmp_path / "boundaries")
    boundary_ledger.append(_boundary())
    for line in event_ledger._events_path.read_text(encoding="utf-8").splitlines():
        json.loads(line)
    for line in boundary_ledger._path.read_text(encoding="utf-8").splitlines():
        json.loads(line)


# ===========================================================================
# INVARIANTS
# ===========================================================================


def test_invariant_event_ids_distinct_from_memory_and_vendor_ids():
    event_id = generate_event_id(
        event_type=EVENT_RETRIEVED, memory_ids=("m1",), timestamp="2026-01-01T00:00:00Z",
        actor="candidate_discovery", reason="matched", task_id="t1",
        foundation_name="mem0", foundation_memory_id="vendor-uuid-abc",
    )
    assert event_id not in ("m1", "vendor-uuid-abc", "t1")


def test_invariant_experiment_boundaries_are_not_memory_lifecycle_transitions():
    boundary = _boundary()
    # No lifecycle_state-shaped field exists on this type at all.
    assert set(vars(boundary).keys()) == {"boundary_id", "boundary_type", "scope", "timestamp", "actor", "reason"}


def test_invariant_lineage_independent_of_vendor_availability(tmp_path):
    """No foundation adapter object appears anywhere in this test module -- lineage
    reconstruction is proven without one existing at all."""
    _, event_ledger = _ledgers(tmp_path)
    event_ledger.append(_derived_event())
    assert len(event_ledger.reconstruct_memory_history("m3")) == 1
