"""Phase 3.3-H.2-R2 (Final H.2 Hardening Pass) contract tests.

Covers event identity semantics, namespace enforcement, boundary-ledger concurrency
ownership, and the integration API surface, per the mission's 30 test items and 15
invariants. Does not re-test H.2/H.2-R's own contract (see test_canonical_event_ledger_h2.py
and test_h2_remediation.py, both run unmodified except for canonical_event.py's new
single-memory-id constraint, which every existing fixture already satisfied).
"""

from __future__ import annotations

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
    EVENT_RETIRED,
    EVENT_RETRIEVED,
    EVENT_SELECTED,
    EVENT_SUPERSEDED,
    EVENT_USED,
)
from phase3.evaluation.foundations.event_identity import (
    build_canonical_event,
    generate_event_id,
    looks_like_generated_event_id,
)
from phase3.evaluation.foundations.event_ledger import (
    APPEND_CREATED,
    APPEND_IDEMPOTENT,
    CanonicalEventLedger,
    SingleOccurrenceViolationError,
)
from phase3.evaluation.foundations.experiment_boundary import (
    BOUNDARY_RESET,
    ExperimentBoundaryLedger,
    ExperimentBoundaryRecord,
    build_reset_boundary,
    generate_boundary_id,
    looks_like_generated_boundary_id,
    merge_experiment_boundary_ledgers,
)
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger


def _memory_record(memory_id: str, memory_type=MEMORY_TYPE_FOUNDATION, parent_ids=()) -> CanonicalMemoryRecord:
    source = (
        {"source_type": SOURCE_TYPE_DERIVATION_EVENT, "reference_id": "deriv-1"}
        if memory_type == MEMORY_TYPE_DERIVED
        else {"source_type": SOURCE_TYPE_PHASE2_UMR, "reference_id": "umr-1"}
    )
    return CanonicalMemoryRecord(
        memory_id=memory_id, memory_type=memory_type, content={"text": f"content for {memory_id}"},
        source=source, parent_ids=tuple(parent_ids), creation_event="evt-seed",
        creation_timestamp="2026-01-01T00:00:00Z", lifecycle_state=LIFECYCLE_CREATED,
    )


def _ledgers(tmp_path):
    memory_ledger = CanonicalMemoryLedger(tmp_path / "memory-ledger")
    memory_ledger.put(_memory_record("m1"))
    memory_ledger.put(_memory_record("m2"))
    event_ledger = CanonicalEventLedger(tmp_path / "event-ledger", memory_ledger)
    return memory_ledger, event_ledger


def _created_kwargs(memory_id="m1", **overrides):
    kwargs = dict(
        event_type=EVENT_CREATED, memory_ids=(memory_id,), timestamp="2026-01-01T00:00:00Z",
        actor="creation_policy", reason="ingested", new_state=LIFECYCLE_CREATED,
    )
    kwargs.update(overrides)
    return kwargs


# ===========================================================================
# A. EVENT IDENTITY -- items 1-7
# ===========================================================================


def test_1_identity_semantics_documented_and_content_derived():
    """Chosen semantics: identical canonical event content == same historical fact."""
    kwargs = _created_kwargs()
    a = generate_event_id(**kwargs)
    b = generate_event_id(**kwargs)
    assert a == b


def test_2_repeated_identical_event_coalesces(tmp_path):
    _, event_ledger = _ledgers(tmp_path)
    kwargs = _created_kwargs()
    event_id = generate_event_id(**kwargs)
    event = CanonicalEvent(event_id=event_id, **kwargs)
    assert event_ledger.append(event) == APPEND_CREATED
    assert event_ledger.append(CanonicalEvent(event_id=event_id, **kwargs)) == APPEND_IDEMPOTENT
    assert len(event_ledger.events_for_memory("m1")) == 1


def test_3_duplicate_identical_append_is_idempotent(tmp_path):
    _, event_ledger = _ledgers(tmp_path)
    event = build_canonical_event(**_created_kwargs())
    event_ledger.append(event)
    same = build_canonical_event(**_created_kwargs())
    assert event.event_id == same.event_id
    assert event_ledger.append(same) == APPEND_IDEMPOTENT


def test_4_duplicate_conflicting_event_id_is_rejected(tmp_path):
    from phase3.evaluation.foundations.event_ledger import CanonicalEventCollisionError

    _, event_ledger = _ledgers(tmp_path)
    event_id = generate_event_id(**_created_kwargs())
    event_ledger.append(CanonicalEvent(event_id=event_id, **_created_kwargs()))
    with pytest.raises(CanonicalEventCollisionError):
        event_ledger.append(CanonicalEvent(event_id=event_id, **_created_kwargs(reason="a forged different reason")))


def test_5_distinct_observations_permitted_where_ontology_allows(tmp_path):
    """M1 retrieved for task T1, then again for task T2 -- genuinely distinct facts
    (different task_id), so they get DIFFERENT ids and BOTH persist."""
    _, event_ledger = _ledgers(tmp_path)
    retrieved_t1 = build_canonical_event(
        event_type=EVENT_RETRIEVED, memory_ids=("m1",), timestamp="2026-01-01T00:00:00Z",
        actor="candidate_discovery", reason="matched query embedding.", task_id="T1",
    )
    retrieved_t2 = build_canonical_event(
        event_type=EVENT_RETRIEVED, memory_ids=("m1",), timestamp="2026-01-01T00:05:00Z",
        actor="candidate_discovery", reason="matched query embedding.", task_id="T2",
    )
    assert retrieved_t1.event_id != retrieved_t2.event_id
    event_ledger.append(retrieved_t1)
    event_ledger.append(retrieved_t2)
    assert len(event_ledger.events_for_memory("m1")) == 2


def test_6_event_identity_is_deterministic_across_calls():
    kwargs = dict(
        event_type=EVENT_SELECTED, memory_ids=("m1", "m2"), timestamp="2026-01-01T00:00:00Z",
        actor="evidence_selection", reason="selected for context.", task_id="T1",
    )
    ids = {generate_event_id(**kwargs) for _ in range(5)}
    assert len(ids) == 1


def test_7_identity_survives_reload(tmp_path):
    _, event_ledger = _ledgers(tmp_path)
    event = build_canonical_event(**_created_kwargs())
    event_ledger.append(event)
    reloaded = CanonicalEventLedger(event_ledger._dir, CanonicalMemoryLedger(tmp_path / "memory-ledger"))
    assert reloaded.get_event(event.event_id) == event


# ---------------------------------------------------------------------------
# Single-occurrence invariant (the OTHER identity gap H.2-R2 found -- section A)
# ---------------------------------------------------------------------------


def test_single_occurrence_created_rejects_second_different_event(tmp_path):
    _, event_ledger = _ledgers(tmp_path)
    event_ledger.append(build_canonical_event(**_created_kwargs()))
    conflicting = build_canonical_event(**_created_kwargs(reason="a SECOND, different origin story"))
    with pytest.raises(SingleOccurrenceViolationError):
        event_ledger.append(conflicting)


def test_single_occurrence_created_and_derived_share_one_slot(tmp_path):
    memory_ledger, event_ledger = _ledgers(tmp_path)
    memory_ledger.put(_memory_record("m3", memory_type=MEMORY_TYPE_DERIVED, parent_ids=("m1", "m2")))
    event_ledger.append(build_canonical_event(**_created_kwargs(memory_id="m1")))
    derived_conflict = build_canonical_event(
        event_type=EVENT_DERIVED, memory_ids=("m1", "m2"), source_memory_ids=("m2",), target_memory_id="m1",
        timestamp="2026-01-01T00:10:00Z", actor="creation_policy", reason="a conflicting derivation of m1",
    )
    with pytest.raises(SingleOccurrenceViolationError):
        event_ledger.append(derived_conflict)


def test_single_occurrence_superseded_and_retired_each_own_slot(tmp_path):
    _, event_ledger = _ledgers(tmp_path)
    event_ledger.append(build_canonical_event(**_created_kwargs()))
    first_retire = build_canonical_event(
        event_type=EVENT_RETIRED, memory_ids=("m1",), timestamp="2026-01-02T00:00:00Z",
        actor="creation_policy", reason="retired for reason A.", previous_state=LIFECYCLE_ACTIVE, new_state=LIFECYCLE_RETIRED,
    )
    event_ledger.append(first_retire)
    second_retire = build_canonical_event(
        event_type=EVENT_RETIRED, memory_ids=("m1",), timestamp="2026-01-03T00:00:00Z",
        actor="creation_policy", reason="retired for a DIFFERENT reason B.", previous_state=LIFECYCLE_ACTIVE, new_state=LIFECYCLE_RETIRED,
    )
    with pytest.raises(SingleOccurrenceViolationError):
        event_ledger.append(second_retire)


def test_single_occurrence_does_not_block_idempotent_replay(tmp_path):
    _, event_ledger = _ledgers(tmp_path)
    event = build_canonical_event(**_created_kwargs())
    event_ledger.append(event)
    assert event_ledger.append(event) == APPEND_IDEMPOTENT


def test_created_and_superseded_now_require_exactly_one_memory_id():
    with pytest.raises(CanonicalEventValidationError, match="exactly one memory_id"):
        CanonicalEvent(
            event_id="e1", event_type=EVENT_CREATED, memory_ids=("m1", "m2"),
            timestamp="2026-01-01T00:00:00Z", actor="creation_policy", reason="test", new_state=LIFECYCLE_CREATED,
        )


# ===========================================================================
# B. NAMESPACE ENFORCEMENT -- items 8-15
# ===========================================================================


def test_8_valid_generated_event_id():
    event_id = generate_event_id(**_created_kwargs())
    assert looks_like_generated_event_id(event_id)


def test_9_non_prefixed_event_id_still_valid_no_format_enforced(tmp_path):
    """Deliberate decision (section B1): the EVT- prefix is advisory, not enforced -- a
    caller-supplied event_id with no prefix at all remains fully valid, preserving every
    historical H.2 fixture."""
    _, event_ledger = _ledgers(tmp_path)
    event = CanonicalEvent(event_id="e1", **_created_kwargs())  # no "EVT-" prefix
    assert event_ledger.append(event) == APPEND_CREATED
    assert not looks_like_generated_event_id("e1")


def test_10_valid_generated_boundary_id():
    boundary_id = generate_boundary_id(BOUNDARY_RESET, {"dataset": "longmemeval"}, "2026-01-01T00:00:00Z", "system", "reset")
    assert looks_like_generated_boundary_id(boundary_id)


def test_11_non_prefixed_boundary_id_still_valid(tmp_path):
    ledger = ExperimentBoundaryLedger(tmp_path / "boundaries")
    record = ExperimentBoundaryRecord(
        boundary_id="b1", boundary_type=BOUNDARY_RESET, scope={}, timestamp="2026-01-01T00:00:00Z",
        actor="system", reason="reset",
    )
    from phase3.evaluation.foundations.experiment_boundary import APPEND_CREATED as BND_CREATED

    assert ledger.append(record) == BND_CREATED
    assert not looks_like_generated_boundary_id("b1")


def test_12_event_and_boundary_ledgers_never_cross_contaminate_even_on_id_collision(tmp_path):
    """The SAME literal string used as both an event_id and a boundary_id in two
    different ledgers must never let one satisfy a lookup meant for the other -- proves
    namespace separation is structural (different ledgers/files), not format-based."""
    _, event_ledger = _ledgers(tmp_path)
    boundary_ledger = ExperimentBoundaryLedger(tmp_path / "boundaries")
    shared_literal = "SHARED-ID-001"

    event_ledger.append(CanonicalEvent(event_id=shared_literal, **_created_kwargs()))
    boundary_ledger.append(
        ExperimentBoundaryRecord(
            boundary_id=shared_literal, boundary_type=BOUNDARY_RESET, scope={"dataset": "x"},
            timestamp="2026-01-01T00:00:00Z", actor="system", reason="reset",
        )
    )
    assert event_ledger.get_event(shared_literal) is not None
    assert boundary_ledger.get_boundary(shared_literal) is not None
    # Neither ledger has the other's query method at all -- structurally impossible to
    # confuse a boundary for an event or vice versa.
    assert not hasattr(event_ledger, "get_boundary")
    assert not hasattr(boundary_ledger, "get_event")
    # And the two records fetched under the identical literal id are genuinely different
    # object types, never conflated.
    assert type(event_ledger.get_event(shared_literal)) is CanonicalEvent
    assert type(boundary_ledger.get_boundary(shared_literal)) is ExperimentBoundaryRecord


def test_13_memory_ids_remain_independent_namespace(tmp_path):
    memory_ledger, event_ledger = _ledgers(tmp_path)
    event_id = generate_event_id(**_created_kwargs())
    assert not memory_ledger.exists(event_id)
    event_ledger.append(CanonicalEvent(event_id=event_id, **_created_kwargs()))
    assert event_ledger.events_for_memory(event_id) == ()  # event id is not a memory id


def test_14_vendor_ids_remain_independent_namespace(tmp_path):
    _, event_ledger = _ledgers(tmp_path)
    event = build_canonical_event(
        event_type=EVENT_RETRIEVED, memory_ids=("m1",), timestamp="2026-01-01T00:00:00Z",
        actor="candidate_discovery", reason="matched.", task_id="T1",
        foundation_name="mem0", foundation_memory_id="vendor-uuid-abc",
    )
    event_ledger.append(event)
    assert event.event_id != "vendor-uuid-abc"
    assert event_ledger.events_for_foundation("mem0")[0].event_id != "vendor-uuid-abc"


def test_15_task_ids_remain_independent_namespace(tmp_path):
    _, event_ledger = _ledgers(tmp_path)
    event = build_canonical_event(
        event_type=EVENT_USED, memory_ids=("m1",), timestamp="2026-01-01T00:00:00Z",
        actor="agent", reason="cited.", task_id="task-42",
    )
    event_ledger.append(event)
    assert event.event_id != "task-42"
    assert event_ledger.events_for_task("task-42")[0].event_id != "task-42"


def test_memory_and_task_and_vendor_ids_are_not_given_artificial_prefixes():
    """B3: no prefix is imposed on dataset-native memory/task ids or vendor ids -- only
    benchmark-MINTED identifiers (event/boundary) carry an advisory prefix."""
    record = _memory_record("loco-mem-001")
    assert record.memory_id == "loco-mem-001"  # unprefixed, as the dataset supplied it


# ===========================================================================
# C. CONCURRENCY -- items 16-20
# ===========================================================================


def test_16_boundary_single_writer_contract_is_explicit(tmp_path):
    """Ownership contract: one storage_dir == one owning writer. Two ledger instances
    pointed at DIFFERENT dirs never see each other's writes until explicitly merged."""
    ledger_a = ExperimentBoundaryLedger(tmp_path / "worker-0")
    ledger_b = ExperimentBoundaryLedger(tmp_path / "worker-1")
    ledger_a.append(build_reset_boundary({"pool": "p0"}, "2026-01-01T00:00:00Z", "worker-0", "reset before p0"))
    assert ledger_b.all_boundaries() == ()


def test_17_merge_combines_independent_worker_ledgers(tmp_path):
    """The repository-established multi-writer pattern (per-worker isolated storage +
    merge, mirroring campaign_formal_runner.py's own checkpoint-merge design)."""
    worker0 = ExperimentBoundaryLedger(tmp_path / "worker-0")
    worker1 = ExperimentBoundaryLedger(tmp_path / "worker-1")
    b0 = build_reset_boundary({"pool": "p0"}, "2026-01-01T00:00:00Z", "worker-0", "reset before p0")
    b1 = build_reset_boundary({"pool": "p1"}, "2026-01-01T00:05:00Z", "worker-1", "reset before p1")
    worker0.append(b0)
    worker1.append(b1)

    merged = merge_experiment_boundary_ledgers(tmp_path / "merged", [tmp_path / "worker-0", tmp_path / "worker-1"])
    assert len(merged.all_boundaries()) == 2
    assert merged.get_boundary(b0.boundary_id) is not None
    assert merged.get_boundary(b1.boundary_id) is not None


def test_18_no_lost_boundary_records_across_merge(tmp_path):
    workers = []
    expected_ids = []
    for i in range(3):
        w = ExperimentBoundaryLedger(tmp_path / f"worker-{i}")
        b = build_reset_boundary({"pool": f"p{i}"}, f"2026-01-0{i+1}T00:00:00Z", f"worker-{i}", f"reset {i}")
        w.append(b)
        workers.append(tmp_path / f"worker-{i}")
        expected_ids.append(b.boundary_id)
    merged = merge_experiment_boundary_ledgers(tmp_path / "merged-all", workers)
    assert {b.boundary_id for b in merged.all_boundaries()} == set(expected_ids)


def test_19_merge_detects_a_genuine_conflict_rather_than_silently_overwriting(tmp_path):
    from phase3.evaluation.foundations.experiment_boundary import ExperimentBoundaryCollisionError

    worker0 = ExperimentBoundaryLedger(tmp_path / "worker-0")
    worker1 = ExperimentBoundaryLedger(tmp_path / "worker-1")
    # Force an artificial id collision with different payloads between two workers.
    worker0.append(
        ExperimentBoundaryRecord(
            boundary_id="COLLIDE", boundary_type=BOUNDARY_RESET, scope={"pool": "p0"},
            timestamp="2026-01-01T00:00:00Z", actor="worker-0", reason="reset p0",
        )
    )
    worker1.append(
        ExperimentBoundaryRecord(
            boundary_id="COLLIDE", boundary_type=BOUNDARY_RESET, scope={"pool": "p1"},
            timestamp="2026-01-01T00:00:00Z", actor="worker-1", reason="reset p1",
        )
    )
    with pytest.raises(ExperimentBoundaryCollisionError):
        merge_experiment_boundary_ledgers(tmp_path / "merged-conflict", [tmp_path / "worker-0", tmp_path / "worker-1"])


def test_20_reload_consistency_after_merge(tmp_path):
    worker0 = ExperimentBoundaryLedger(tmp_path / "worker-0")
    b0 = build_reset_boundary({"pool": "p0"}, "2026-01-01T00:00:00Z", "worker-0", "reset p0")
    worker0.append(b0)
    merge_experiment_boundary_ledgers(tmp_path / "merged", [tmp_path / "worker-0"])

    reloaded = ExperimentBoundaryLedger(tmp_path / "merged")
    assert reloaded.get_boundary(b0.boundary_id) == b0


# ===========================================================================
# D. INTEGRATION API -- items 21-25
# ===========================================================================


def test_21_event_factory_produces_valid_canonical_event():
    event = build_canonical_event(**_created_kwargs())
    assert isinstance(event, CanonicalEvent)
    assert event.event_type == EVENT_CREATED


def test_22_factory_cannot_bypass_ledger_collision_validation(tmp_path):
    from phase3.evaluation.foundations.event_ledger import CanonicalEventCollisionError

    _, event_ledger = _ledgers(tmp_path)
    event = build_canonical_event(**_created_kwargs())
    event_ledger.append(event)
    # Forge a conflicting event under the SAME factory-generated id by hand (bypassing the
    # factory's own consistency, as a malicious/buggy caller might) -- the ledger still
    # rejects it; the factory has no special back door into append().
    forged = CanonicalEvent(event_id=event.event_id, **_created_kwargs(reason="forged"))
    with pytest.raises(CanonicalEventCollisionError):
        event_ledger.append(forged)


def test_23_boundary_factory_produces_valid_boundary_record():
    boundary = build_reset_boundary({"dataset": "longmemeval"}, "2026-01-01T00:00:00Z", "system", "reset")
    assert isinstance(boundary, ExperimentBoundaryRecord)
    assert boundary.boundary_type == BOUNDARY_RESET


def test_24_no_automatic_runtime_wiring():
    """None of the new H.2-R2 modules is imported anywhere on the live G.1 execution
    path -- purely additive infrastructure, not integrated."""
    import inspect

    from phase3.evaluation.agent_runtime import campaign_formal_runner

    source = inspect.getsource(campaign_formal_runner)
    assert "event_identity" not in source
    assert "experiment_boundary" not in source
    assert "event_ledger" not in source
    assert "canonical_event" not in source


def test_25_no_event_ledger_import_edge_into_agent_visible_context():
    import inspect

    from phase3.evaluation.agent import conditions as agent_conditions
    from phase3.evaluation.agent_runtime import runner as agent_runner

    for module in (agent_conditions, agent_runner):
        source = inspect.getsource(module)
        assert "event_identity" not in source
        assert "experiment_boundary" not in source


def test_agent_visible_boundary_check_unweakened():
    with pytest.raises(AgentVisibilityViolation):
        validate_agent_visible({"gold_evidence_ids": ["m1"]})


# ===========================================================================
# INVARIANTS
# ===========================================================================


def test_invariant_boundary_records_cannot_become_memory_lifecycle_events():
    boundary = build_reset_boundary({"dataset": "x"}, "2026-01-01T00:00:00Z", "system", "reset")
    assert not isinstance(boundary, CanonicalEvent)
    assert not hasattr(boundary, "memory_ids")


def test_invariant_events_and_boundaries_remain_append_only():
    _, _ = ExperimentBoundaryLedger, CanonicalEventLedger  # imported above
    boundary_ledger_cls = ExperimentBoundaryLedger
    event_ledger_cls = CanonicalEventLedger
    for cls in (boundary_ledger_cls, event_ledger_cls):
        assert not hasattr(cls, "update_event")
        assert not hasattr(cls, "delete_event")
        assert not hasattr(cls, "update_boundary")
        assert not hasattr(cls, "delete_boundary")


def test_invariant_event_id_generation_remains_benchmark_owned():
    import inspect

    sig = inspect.signature(generate_event_id)
    param_names = set(sig.parameters)
    # foundation_name/foundation_memory_id are plain str DATA fields (part of the event's
    # own content being fingerprinted) -- the factory takes no live adapter OBJECT at all.
    assert "adapter" not in param_names
    assert "foundation" not in param_names
    for annotation in (p.annotation for p in sig.parameters.values()):
        assert "MemoryFoundationAdapter" not in str(annotation)


def test_invariant_ledger_remains_final_collision_authority(tmp_path):
    """Even a factory-minted id is only ever validated for real by the ledger's own
    append() -- constructing the event object never itself writes anything."""
    _, event_ledger = _ledgers(tmp_path)
    event = build_canonical_event(**_created_kwargs())
    assert event_ledger.get_event(event.event_id) is None  # not yet appended
    event_ledger.append(event)
    assert event_ledger.get_event(event.event_id) is not None
