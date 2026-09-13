"""Phase 5.4 -- tests for the memory lifecycle wiring layer, exercised against real
(file-backed, tmp_path-scoped) Phase 3 ledgers -- no mocks of the ledgers themselves,
since they are the frozen infrastructure this stage's PASS condition requires observing,
not replacing.
"""

from __future__ import annotations

import pytest

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
from phase3.evaluation.foundations.canonical_event import CanonicalEvent, EVENT_RETIRED, EVENT_SUPERSEDED
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase3.evaluation.foundations.memory_versioning import STATUS_FULLY_SUPERSEDED, SupersessionLedger

from phase5.identity.run_identity import EventRunMembershipLedger, ExperimentRunLedger, ExperimentRunRecord
from phase5.schema.event import ADMISSION_STATUS_ADMITTED, ADMISSION_STATUS_REJECTED
from phase5.schema.event_ledger import Phase5EventLedger
from phase5.wiring.memory_lifecycle import (
    record_attack_injection,
    record_memory_creation,
    record_memory_derivation,
    record_memory_lifecycle_transition,
)

TS = "2026-09-12T00:00:00+00:00"
TS2 = "2026-09-12T00:01:00+00:00"


def _foundation_record(memory_id: str, text: str) -> CanonicalMemoryRecord:
    return CanonicalMemoryRecord(
        memory_id=memory_id,
        memory_type=MEMORY_TYPE_FOUNDATION,
        content={"text": text},
        source={"source_type": SOURCE_TYPE_PHASE2_UMR},
        parent_ids=(),
        creation_event=f"creation-of-{memory_id}",
        creation_timestamp=TS,
        lifecycle_state=LIFECYCLE_CREATED,
    )


@pytest.fixture
def wired_ledgers(tmp_path):
    memory_ledger = CanonicalMemoryLedger(tmp_path / "memory")
    event_ledger = CanonicalEventLedger(tmp_path / "events", memory_ledger)
    run_ledger = ExperimentRunLedger(tmp_path / "runs")
    membership_ledger = EventRunMembershipLedger(tmp_path / "membership", run_ledger)
    phase5_ledger = Phase5EventLedger(tmp_path / "phase5_events")
    supersession_ledger = SupersessionLedger(tmp_path / "supersessions")

    run = ExperimentRunRecord(
        experiment_id="phase4-farma-campaign",
        run_id="RUN-test-1",
        dataset="locomo",
        scope={"attack_id": "farma"},
        started_at=TS,
        actor="test",
        reason="test run registration",
    )
    run_ledger.register(run)

    return dict(
        memory_ledger=memory_ledger,
        event_ledger=event_ledger,
        run_ledger=run_ledger,
        membership_ledger=membership_ledger,
        phase5_ledger=phase5_ledger,
        supersession_ledger=supersession_ledger,
        run_id=run.run_id,
    )


def test_record_memory_creation_clean_memory_no_attack_context(wired_ledgers):
    record = _foundation_record("mem-1", "clean fact")
    result = record_memory_creation(
        memory_ledger=wired_ledgers["memory_ledger"],
        event_ledger=wired_ledgers["event_ledger"],
        membership_ledger=wired_ledgers["membership_ledger"],
        run_id=wired_ledgers["run_id"],
        record=record,
        actor="test_wiring",
        reason="clean memory ingested",
        timestamp=TS,
    )
    assert result.attack_injection_event is None
    assert result.created_event.event_type == "created"
    assert wired_ledgers["memory_ledger"].exists("mem-1")
    assert wired_ledgers["membership_ledger"].run_for_event(result.created_event.event_id).run_id == wired_ledgers["run_id"]


def test_record_memory_creation_with_attack_context_admitted(wired_ledgers):
    record = _foundation_record("mem-poison-1", "poisoned fact")
    result = record_memory_creation(
        memory_ledger=wired_ledgers["memory_ledger"],
        event_ledger=wired_ledgers["event_ledger"],
        membership_ledger=wired_ledgers["membership_ledger"],
        run_id=wired_ledgers["run_id"],
        record=record,
        actor="farma_injector_wiring",
        reason="FARMA artifact admitted",
        timestamp=TS,
        attack_context={
            "attack_id": "farma",
            "injection_id": "INJ-1",
            "artifact_id": "farma-artifact-7",
            "admission_status": ADMISSION_STATUS_ADMITTED,
        },
        phase5_event_ledger=wired_ledgers["phase5_ledger"],
    )
    assert result.attack_injection_event is not None
    assert result.attack_injection_event.memory_id == "mem-poison-1"
    assert wired_ledgers["phase5_ledger"].exists(result.attack_injection_event.event_id)
    membership = wired_ledgers["membership_ledger"].run_for_event(result.attack_injection_event.event_id)
    assert membership.run_id == wired_ledgers["run_id"]
    assert wired_ledgers["phase5_ledger"].events_for_attack("farma") == (result.attack_injection_event,)


def test_record_memory_creation_attack_context_requires_ledger(wired_ledgers):
    record = _foundation_record("mem-poison-2", "poisoned fact")
    with pytest.raises(ValueError, match="phase5_event_ledger is required"):
        record_memory_creation(
            memory_ledger=wired_ledgers["memory_ledger"],
            event_ledger=wired_ledgers["event_ledger"],
            membership_ledger=wired_ledgers["membership_ledger"],
            run_id=wired_ledgers["run_id"],
            record=record,
            actor="farma_injector_wiring",
            reason="FARMA artifact admitted",
            timestamp=TS,
            attack_context={
                "attack_id": "farma", "injection_id": "INJ-2", "artifact_id": "artifact-8",
                "admission_status": ADMISSION_STATUS_ADMITTED,
            },
        )


def test_record_memory_creation_refuses_rejected_admission_status(wired_ledgers):
    # record_memory_creation() always creates a memory -- so it must never be called with
    # a rejected admission_status (there is nothing to create). This is the boundary
    # record_attack_injection() exists to cover instead (contract OR-11: "independently
    # of memory creation").
    record = _foundation_record("mem-would-be-rejected", "would-be-rejected content")
    with pytest.raises(ValueError, match="rejected/failed injection has no memory to create"):
        record_memory_creation(
            memory_ledger=wired_ledgers["memory_ledger"],
            event_ledger=wired_ledgers["event_ledger"],
            membership_ledger=wired_ledgers["membership_ledger"],
            run_id=wired_ledgers["run_id"],
            record=record,
            actor="farma_injector_wiring",
            reason="should never reach here",
            timestamp=TS,
            attack_context={
                "attack_id": "farma", "injection_id": "INJ-3", "artifact_id": "artifact-9",
                "admission_status": ADMISSION_STATUS_REJECTED,
            },
            phase5_event_ledger=wired_ledgers["phase5_ledger"],
        )


def test_record_attack_injection_admitted_independent_of_memory_creation(wired_ledgers):
    event = record_attack_injection(
        phase5_event_ledger=wired_ledgers["phase5_ledger"],
        membership_ledger=wired_ledgers["membership_ledger"],
        run_id=wired_ledgers["run_id"],
        attack_id="farma",
        injection_id="INJ-10",
        artifact_id="artifact-10",
        admission_status=ADMISSION_STATUS_ADMITTED,
        actor="farma_injector_wiring",
        reason="artifact admitted",
        timestamp=TS,
        memory_id="mem-not-yet-created-by-this-call",
    )
    assert event.admission_status == ADMISSION_STATUS_ADMITTED
    assert event.memory_id == "mem-not-yet-created-by-this-call"
    # No memory was ever written to memory_ledger by this call -- proves the function is
    # genuinely independent of memory creation, not a repackaging of it.
    assert not wired_ledgers["memory_ledger"].exists("mem-not-yet-created-by-this-call")


def test_record_attack_injection_rejected_is_recorded_with_no_memory_id(wired_ledgers):
    event = record_attack_injection(
        phase5_event_ledger=wired_ledgers["phase5_ledger"],
        membership_ledger=wired_ledgers["membership_ledger"],
        run_id=wired_ledgers["run_id"],
        attack_id="farma",
        injection_id="INJ-11",
        artifact_id="artifact-11",
        admission_status=ADMISSION_STATUS_REJECTED,
        actor="farma_injector_wiring",
        reason="artifact rejected by the foundation's own gate",
        timestamp=TS,
    )
    assert event.admission_status == ADMISSION_STATUS_REJECTED
    assert event.memory_id is None
    assert wired_ledgers["phase5_ledger"].exists(event.event_id)
    assert wired_ledgers["phase5_ledger"].events_for_attack("farma") == (event,)
    assert wired_ledgers["membership_ledger"].run_for_event(event.event_id) is not None


def test_record_attack_injection_rejects_inconsistent_memory_id(wired_ledgers):
    with pytest.raises(ValueError, match="memory_id is required"):
        record_attack_injection(
            phase5_event_ledger=wired_ledgers["phase5_ledger"],
            membership_ledger=wired_ledgers["membership_ledger"],
            run_id=wired_ledgers["run_id"],
            attack_id="farma", injection_id="INJ-12", artifact_id="artifact-12",
            admission_status=ADMISSION_STATUS_ADMITTED,
            actor="test", reason="test", timestamp=TS,
        )
    with pytest.raises(ValueError, match="memory_id must be None"):
        record_attack_injection(
            phase5_event_ledger=wired_ledgers["phase5_ledger"],
            membership_ledger=wired_ledgers["membership_ledger"],
            run_id=wired_ledgers["run_id"],
            attack_id="farma", injection_id="INJ-13", artifact_id="artifact-13",
            admission_status=ADMISSION_STATUS_REJECTED,
            actor="test", reason="test", timestamp=TS, memory_id="should-not-be-here",
        )


def test_record_memory_derivation(wired_ledgers):
    parent = _foundation_record("mem-parent", "parent fact")
    record_memory_creation(
        memory_ledger=wired_ledgers["memory_ledger"], event_ledger=wired_ledgers["event_ledger"],
        membership_ledger=wired_ledgers["membership_ledger"], run_id=wired_ledgers["run_id"],
        record=parent, actor="test", reason="seed parent", timestamp=TS,
    )
    derived = CanonicalMemoryRecord(
        memory_id="mem-child",
        memory_type=MEMORY_TYPE_DERIVED,
        content={"text": "derived fact"},
        source={"source_type": SOURCE_TYPE_DERIVATION_EVENT},
        parent_ids=("mem-parent",),
        creation_event="derivation-of-mem-child",
        creation_timestamp=TS2,
        lifecycle_state=LIFECYCLE_CREATED,
    )
    result = record_memory_derivation(
        memory_ledger=wired_ledgers["memory_ledger"], event_ledger=wired_ledgers["event_ledger"],
        membership_ledger=wired_ledgers["membership_ledger"], run_id=wired_ledgers["run_id"],
        derived_record=derived, source_memory_ids=("mem-parent",),
        actor="test", reason="child derived from parent", timestamp=TS2,
    )
    assert result.created_event.event_type == "derived"
    assert result.created_event.source_memory_ids == ("mem-parent",)
    assert result.created_event.target_memory_id == "mem-child"
    assert wired_ledgers["memory_ledger"].exists("mem-child")


def test_record_memory_lifecycle_transition_supersession(wired_ledgers):
    old = _foundation_record("mem-old", "outdated fact")
    new = _foundation_record("mem-new", "corrected fact")
    for rec in (old, new):
        record_memory_creation(
            memory_ledger=wired_ledgers["memory_ledger"], event_ledger=wired_ledgers["event_ledger"],
            membership_ledger=wired_ledgers["membership_ledger"], run_id=wired_ledgers["run_id"],
            record=rec, actor="test", reason="seed", timestamp=TS,
        )

    superseded_event = CanonicalEvent(
        event_id="evt-superseded-1", event_type=EVENT_SUPERSEDED, memory_ids=("mem-old",),
        timestamp=TS2, actor="test", reason="corrected by mem-new",
        previous_state=LIFECYCLE_ACTIVE, new_state=LIFECYCLE_RETIRED,
    )
    retired_event = CanonicalEvent(
        event_id="evt-retired-1", event_type=EVENT_RETIRED, memory_ids=("mem-old",),
        timestamp=TS2, actor="test", reason="corrected by mem-new",
        previous_state=LIFECYCLE_ACTIVE, new_state=LIFECYCLE_RETIRED,
    )
    result = record_memory_lifecycle_transition(
        event_ledger=wired_ledgers["event_ledger"], memory_ledger=wired_ledgers["memory_ledger"],
        supersession_ledger=wired_ledgers["supersession_ledger"], membership_ledger=wired_ledgers["membership_ledger"],
        run_id=wired_ledgers["run_id"], superseded_memory_id="mem-old", superseding_memory_id="mem-new",
        superseded_event=superseded_event, retired_event=retired_event,
    )
    assert result.status == STATUS_FULLY_SUPERSEDED
    assert wired_ledgers["membership_ledger"].run_for_event("evt-superseded-1") is not None
    assert wired_ledgers["membership_ledger"].run_for_event("evt-retired-1") is not None


def test_non_interference_frozen_write_canonical_memory_unchanged(wired_ledgers):
    """Confirms this wiring module calls, rather than reimplements, write_canonical_memory
    -- constructing the same collision case directly against the frozen function still
    behaves identically whether or not this module is used first."""
    from phase3.evaluation.foundations.canonical_write import write_canonical_memory
    from phase3.evaluation.foundations.ledger import CanonicalCollisionError

    record = _foundation_record("mem-collide", "original content")
    record_memory_creation(
        memory_ledger=wired_ledgers["memory_ledger"], event_ledger=wired_ledgers["event_ledger"],
        membership_ledger=wired_ledgers["membership_ledger"], run_id=wired_ledgers["run_id"],
        record=record, actor="test", reason="seed", timestamp=TS,
    )
    conflicting = _foundation_record("mem-collide", "different content")
    with pytest.raises(CanonicalCollisionError):
        write_canonical_memory(wired_ledgers["memory_ledger"], conflicting)
