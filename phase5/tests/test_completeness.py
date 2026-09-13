"""Phase 5.4 (fix) -- tests proving incomplete instrumentation sequences are detectable
and never silently indistinguishable from complete ones.

Each "partial failure" scenario here is a REAL reproducible failure mode of the current
code (not a hypothetical): `EventRunMembershipLedger.append()` checks the referenced
`run_id` exists BEFORE writing anything (see `run_identity.py`), so calling a
`record_*` wiring function with a `run_id` that was never registered raises
`UnknownRunError` strictly AFTER the preceding ledger write (event or Phase5Event) has
already durably committed -- leaving a real, on-disk orphaned event with no membership.
This module's completeness checks must catch exactly that gap.
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
from phase3.evaluation.foundations.memory_versioning import SupersessionLedger

from phase5.identity.run_identity import (
    EventRunMembershipLedger,
    ExperimentRunLedger,
    ExperimentRunRecord,
    UnknownRunError,
)
from phase5.schema.event import ADMISSION_STATUS_ADMITTED, ATTACK_INJECTION, generate_phase5_event_id
from phase5.schema.event_ledger import Phase5EventLedger
from phase5.wiring.completeness import (
    check_attack_injection_completeness,
    check_memory_creation_completeness,
    check_memory_supersession_completeness,
)
from phase5.wiring.memory_lifecycle import (
    record_attack_injection,
    record_memory_creation,
    record_memory_derivation,
    record_memory_lifecycle_transition,
)

TS = "2026-09-12T00:00:00+00:00"


def _foundation_record(memory_id: str, text: str) -> CanonicalMemoryRecord:
    return CanonicalMemoryRecord(
        memory_id=memory_id, memory_type=MEMORY_TYPE_FOUNDATION, content={"text": text},
        source={"source_type": SOURCE_TYPE_PHASE2_UMR}, parent_ids=(),
        creation_event=f"creation-of-{memory_id}", creation_timestamp=TS, lifecycle_state=LIFECYCLE_CREATED,
    )


@pytest.fixture
def ledgers(tmp_path):
    memory_ledger = CanonicalMemoryLedger(tmp_path / "memory")
    event_ledger = CanonicalEventLedger(tmp_path / "events", memory_ledger)
    run_ledger = ExperimentRunLedger(tmp_path / "runs")
    membership_ledger = EventRunMembershipLedger(tmp_path / "membership", run_ledger)
    phase5_ledger = Phase5EventLedger(tmp_path / "phase5_events")
    supersession_ledger = SupersessionLedger(tmp_path / "supersessions")

    registered_run = ExperimentRunRecord(
        experiment_id="exp-1", run_id="RUN-registered", dataset="locomo",
        scope={}, started_at=TS, actor="test", reason="registered run",
    )
    run_ledger.register(registered_run)

    return dict(
        memory_ledger=memory_ledger, event_ledger=event_ledger, run_ledger=run_ledger,
        membership_ledger=membership_ledger, phase5_ledger=phase5_ledger,
        supersession_ledger=supersession_ledger,
    )


def test_complete_memory_creation_reports_complete(ledgers):
    record = _foundation_record("mem-complete", "fact")
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id="RUN-registered",
        record=record, actor="test", reason="seed", timestamp=TS,
    )
    report = check_memory_creation_completeness(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], memory_id="mem-complete", run_id="RUN-registered",
    )
    assert report.is_complete
    assert report.missing_stages() == ()


def test_orphaned_created_event_is_detected_as_incomplete(ledgers):
    """Reproduces a real partial-failure sequence: the created CanonicalEvent commits,
    then membership registration fails because run_id was never registered."""
    record = _foundation_record("mem-orphaned", "fact")
    with pytest.raises(UnknownRunError):
        record_memory_creation(
            memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
            membership_ledger=ledgers["membership_ledger"], run_id="RUN-never-registered",
            record=record, actor="test", reason="seed", timestamp=TS,
        )

    # The memory and its created event ARE durably present -- this is the dangerous case:
    # a naive check ("does the memory exist?") would call this trace complete.
    assert ledgers["memory_ledger"].exists("mem-orphaned")
    creation_events = ledgers["event_ledger"].events_for_memory("mem-orphaned")
    assert len(creation_events) == 1

    report = check_memory_creation_completeness(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], memory_id="mem-orphaned", run_id="RUN-never-registered",
    )
    assert not report.is_complete
    assert "creation_event_has_no_run_membership" in report.missing_stages()


def test_memory_never_created_is_detected_as_incomplete(ledgers):
    report = check_memory_creation_completeness(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], memory_id="mem-nonexistent", run_id="RUN-registered",
    )
    assert not report.is_complete
    assert "memory_not_in_canonical_memory_ledger" in report.missing_stages()
    assert "no_created_or_derived_event_in_canonical_event_ledger" in report.missing_stages()


def test_membership_under_wrong_run_id_is_detected(ledgers):
    other_run = ExperimentRunRecord(
        experiment_id="exp-1", run_id="RUN-other", dataset="locomo",
        scope={}, started_at=TS, actor="test", reason="a second, different run",
    )
    ledgers["run_ledger"].register(other_run)

    record = _foundation_record("mem-wrong-run", "fact")
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id="RUN-registered",
        record=record, actor="test", reason="seed", timestamp=TS,
    )
    # Ask completeness against the WRONG run -- must not be reported complete just
    # because membership exists at all.
    report = check_memory_creation_completeness(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], memory_id="mem-wrong-run", run_id="RUN-other",
    )
    assert not report.is_complete
    assert report.membership_recorded  # a membership DOES exist...
    assert not report.membership_run_id_matches  # ...but not for the run being asked about
    assert "membership_recorded_under_a_different_run_id" in report.missing_stages()


def test_complete_attack_injection_reports_complete(ledgers):
    record_attack_injection(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id="RUN-registered", attack_id="farma", injection_id="INJ-complete",
        artifact_id="artifact-1", admission_status=ADMISSION_STATUS_ADMITTED,
        actor="test", reason="admitted", timestamp=TS, memory_id="mem-1",
    )
    report = check_attack_injection_completeness(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        injection_id="INJ-complete", run_id="RUN-registered",
    )
    assert report.is_complete
    assert report.missing_stages() == ()


def test_orphaned_attack_injection_event_is_detected_as_incomplete(ledgers):
    """Same real partial-failure shape as the memory-creation case, for the
    memory-independent injection path (issue: OR-11 must be detectable on its own)."""
    with pytest.raises(UnknownRunError):
        record_attack_injection(
            phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
            run_id="RUN-never-registered", attack_id="farma", injection_id="INJ-orphaned",
            artifact_id="artifact-2", admission_status=ADMISSION_STATUS_ADMITTED,
            actor="test", reason="admitted", timestamp=TS, memory_id="mem-2",
        )

    # Recompute the deterministic event_id to confirm it really was written despite the
    # raised exception -- proving this is a genuine orphan, not a no-op.
    expected_event_id = generate_phase5_event_id(
        event_type=ATTACK_INJECTION, timestamp=TS, actor="test", reason="admitted",
        attack_id="farma", injection_id="INJ-orphaned", artifact_id="artifact-2",
        admission_status=ADMISSION_STATUS_ADMITTED, memory_id="mem-2",
    )
    assert ledgers["phase5_ledger"].exists(expected_event_id)
    assert ledgers["membership_ledger"].run_for_event(expected_event_id) is None

    report = check_attack_injection_completeness(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        injection_id="INJ-orphaned", run_id="RUN-never-registered",
    )
    assert not report.is_complete
    assert "injection_event_has_no_run_membership" in report.missing_stages()


def test_injection_never_recorded_is_detected_as_incomplete(ledgers):
    report = check_attack_injection_completeness(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        injection_id="INJ-nonexistent", run_id="RUN-registered",
    )
    assert not report.is_complete
    assert "no_attack_injection_event_in_phase5_event_ledger" in report.missing_stages()


def test_frozen_ledger_semantics_unchanged_by_completeness_checks(ledgers):
    """Non-interference: completeness checks are read-only and must not themselves
    mutate any ledger state."""
    record = _foundation_record("mem-readonly-check", "fact")
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id="RUN-registered",
        record=record, actor="test", reason="seed", timestamp=TS,
    )
    before = ledgers["event_ledger"].events_for_memory("mem-readonly-check")
    check_memory_creation_completeness(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], memory_id="mem-readonly-check", run_id="RUN-registered",
    )
    after = ledgers["event_ledger"].events_for_memory("mem-readonly-check")
    assert before == after


# ---------------------------------------------------------------------------
# Derivation completeness (contract OR-5) -- reuses check_memory_creation_completeness()
# directly, since a `derived` event is one of the two _CREATION_EVENT_TYPES it already
# checks for. These tests prove that reuse is actually correct, not merely assumed.
# ---------------------------------------------------------------------------

def test_complete_memory_derivation_reports_complete(ledgers):
    parent = _foundation_record("mem-deriv-parent", "parent fact")
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id="RUN-registered",
        record=parent, actor="test", reason="seed parent", timestamp=TS,
    )
    derived = CanonicalMemoryRecord(
        memory_id="mem-deriv-child", memory_type=MEMORY_TYPE_DERIVED, content={"text": "derived fact"},
        source={"source_type": SOURCE_TYPE_DERIVATION_EVENT}, parent_ids=("mem-deriv-parent",),
        creation_event="derivation-of-mem-deriv-child", creation_timestamp=TS, lifecycle_state=LIFECYCLE_CREATED,
    )
    record_memory_derivation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id="RUN-registered",
        derived_record=derived, source_memory_ids=("mem-deriv-parent",),
        actor="test", reason="child derived from parent", timestamp=TS,
    )
    report = check_memory_creation_completeness(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], memory_id="mem-deriv-child", run_id="RUN-registered",
    )
    assert report.is_complete
    assert report.missing_stages() == ()


def test_orphaned_derived_event_is_detected_as_incomplete(ledgers):
    """Same real partial-failure shape as the foundation-creation case, but for a
    `derived` event -- proves derivation orphaning is caught too, not just creation."""
    parent = _foundation_record("mem-deriv-parent-2", "parent fact")
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id="RUN-registered",
        record=parent, actor="test", reason="seed parent", timestamp=TS,
    )
    derived = CanonicalMemoryRecord(
        memory_id="mem-deriv-orphan", memory_type=MEMORY_TYPE_DERIVED, content={"text": "orphaned derived fact"},
        source={"source_type": SOURCE_TYPE_DERIVATION_EVENT}, parent_ids=("mem-deriv-parent-2",),
        creation_event="derivation-of-mem-deriv-orphan", creation_timestamp=TS, lifecycle_state=LIFECYCLE_CREATED,
    )
    with pytest.raises(UnknownRunError):
        record_memory_derivation(
            memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
            membership_ledger=ledgers["membership_ledger"], run_id="RUN-never-registered",
            derived_record=derived, source_memory_ids=("mem-deriv-parent-2",),
            actor="test", reason="child derived from parent", timestamp=TS,
        )

    assert ledgers["memory_ledger"].exists("mem-deriv-orphan")
    report = check_memory_creation_completeness(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], memory_id="mem-deriv-orphan", run_id="RUN-never-registered",
    )
    assert not report.is_complete
    assert "creation_event_has_no_run_membership" in report.missing_stages()


# ---------------------------------------------------------------------------
# Supersession completeness (contract OR-2).
# ---------------------------------------------------------------------------

def _supersede(ledgers, old_id, new_id, run_id, event_id_suffix=""):
    superseded_event = CanonicalEvent(
        event_id=f"evt-superseded-{event_id_suffix}", event_type=EVENT_SUPERSEDED, memory_ids=(old_id,),
        timestamp=TS, actor="test", reason="corrected", previous_state=LIFECYCLE_ACTIVE, new_state=LIFECYCLE_RETIRED,
    )
    retired_event = CanonicalEvent(
        event_id=f"evt-retired-{event_id_suffix}", event_type=EVENT_RETIRED, memory_ids=(old_id,),
        timestamp=TS, actor="test", reason="corrected", previous_state=LIFECYCLE_ACTIVE, new_state=LIFECYCLE_RETIRED,
    )
    return record_memory_lifecycle_transition(
        event_ledger=ledgers["event_ledger"], memory_ledger=ledgers["memory_ledger"],
        supersession_ledger=ledgers["supersession_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=run_id, superseded_memory_id=old_id, superseding_memory_id=new_id,
        superseded_event=superseded_event, retired_event=retired_event,
    )


def test_complete_supersession_reports_complete(ledgers):
    old, new = _foundation_record("mem-old-1", "outdated"), _foundation_record("mem-new-1", "corrected")
    for rec in (old, new):
        record_memory_creation(
            memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
            membership_ledger=ledgers["membership_ledger"], run_id="RUN-registered",
            record=rec, actor="test", reason="seed", timestamp=TS,
        )
    _supersede(ledgers, "mem-old-1", "mem-new-1", "RUN-registered", event_id_suffix="1")

    report = check_memory_supersession_completeness(
        event_ledger=ledgers["event_ledger"], supersession_ledger=ledgers["supersession_ledger"],
        membership_ledger=ledgers["membership_ledger"], superseded_memory_id="mem-old-1",
        superseding_memory_id="mem-new-1", run_id="RUN-registered",
    )
    assert report.is_complete
    assert report.missing_stages() == ()


def test_orphaned_supersession_events_detected_as_incomplete(ledgers):
    """Reproduces the real partial-failure shape for supersession: both events commit to
    CanonicalEventLedger (supersede_memory() itself succeeds), but membership
    registration for BOTH fails because run_id was never registered."""
    old, new = _foundation_record("mem-old-2", "outdated"), _foundation_record("mem-new-2", "corrected")
    for rec in (old, new):
        record_memory_creation(
            memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
            membership_ledger=ledgers["membership_ledger"], run_id="RUN-registered",
            record=rec, actor="test", reason="seed", timestamp=TS,
        )
    with pytest.raises(UnknownRunError):
        _supersede(ledgers, "mem-old-2", "mem-new-2", "RUN-never-registered", event_id_suffix="2")

    # The supersession itself (supersede_memory()'s own three writes) fully succeeded --
    # only the Phase 5 membership registration on top of it failed.
    assert ledgers["supersession_ledger"].superseder_of("mem-old-2") == "mem-new-2"

    report = check_memory_supersession_completeness(
        event_ledger=ledgers["event_ledger"], supersession_ledger=ledgers["supersession_ledger"],
        membership_ledger=ledgers["membership_ledger"], superseded_memory_id="mem-old-2",
        superseding_memory_id="mem-new-2", run_id="RUN-never-registered",
    )
    assert not report.is_complete
    assert "superseded_event_has_no_run_membership" in report.missing_stages()
    assert "retired_event_has_no_run_membership" in report.missing_stages()
    # The supersession record link itself IS present -- proving the checker distinguishes
    # "the fact exists" from "the fact is attributed to a run via membership."
    assert report.supersession_record_linked


def test_supersession_never_recorded_is_detected_as_incomplete(ledgers):
    report = check_memory_supersession_completeness(
        event_ledger=ledgers["event_ledger"], supersession_ledger=ledgers["supersession_ledger"],
        membership_ledger=ledgers["membership_ledger"], superseded_memory_id="mem-nonexistent-old",
        superseding_memory_id="mem-nonexistent-new", run_id="RUN-registered",
    )
    assert not report.is_complete
    assert "no_superseded_event_in_canonical_event_ledger" in report.missing_stages()
    assert "no_supersession_record_linking_superseded_to_superseding" in report.missing_stages()
    assert "no_retired_event_in_canonical_event_ledger" in report.missing_stages()
