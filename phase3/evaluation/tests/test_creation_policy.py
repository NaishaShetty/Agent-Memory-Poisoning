"""Tests for `foundations.creation_policy` -- the `superseded_by` half of the creation
policy (design review section 3.2's approved split). Reuses the same fixture pattern
`test_h3_versioning.py` already establishes for `supersede_memory()` itself."""

from __future__ import annotations

import pytest

from phase3.evaluation.foundations.canonical import (
    CanonicalMemoryRecord,
    LIFECYCLE_CREATED,
    LIFECYCLE_RETIRED,
    MEMORY_TYPE_FOUNDATION,
    SOURCE_TYPE_PHASE2_UMR,
)
from phase3.evaluation.foundations.canonical_event import (
    EVENT_CREATED,
    EVENT_RELATIONSHIP_DETECTED,
    EVENT_RETIRED,
    EVENT_SUPERSEDED,
    RELATIONSHIP_SUPERSEDED_BY,
)
from phase3.evaluation.foundations.creation_policy import (
    MECHANISM_EXPLICIT_SUPERSESSION_CALL,
    emit_superseded_by_detected,
    supersede_memory_with_detection,
)
from phase3.evaluation.foundations.event_identity import build_canonical_event
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase3.evaluation.foundations.memory_versioning import SupersessionLedger


def _system(tmp_path, name="sys"):
    memory_ledger = CanonicalMemoryLedger(tmp_path / f"{name}-memory")
    event_ledger = CanonicalEventLedger(tmp_path / f"{name}-events", memory_ledger)
    supersession_ledger = SupersessionLedger(tmp_path / f"{name}-supersessions")
    return memory_ledger, event_ledger, supersession_ledger


def _memory_record(memory_id: str) -> CanonicalMemoryRecord:
    return CanonicalMemoryRecord(
        memory_id=memory_id, memory_type=MEMORY_TYPE_FOUNDATION, content={"text": f"content for {memory_id}"},
        source={"source_type": SOURCE_TYPE_PHASE2_UMR, "reference_id": "umr-1"},
        parent_ids=(), creation_event="evt-seed", creation_timestamp="2026-01-01T00:00:00Z",
        lifecycle_state=LIFECYCLE_CREATED,
    )


def _seed_memory(memory_ledger, event_ledger, memory_id, timestamp="2026-01-01T00:00:00Z"):
    memory_ledger.put(_memory_record(memory_id))
    event_ledger.append(build_canonical_event(
        event_type=EVENT_CREATED, memory_ids=(memory_id,), timestamp=timestamp,
        actor="creation_policy", reason="ingested", new_state=LIFECYCLE_CREATED,
    ))


def test_emit_superseded_by_detected_appends_a_valid_event(tmp_path):
    memory_ledger, event_ledger, _ = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "A")
    _seed_memory(memory_ledger, event_ledger, "B", "2026-01-02T00:00:00Z")

    event = emit_superseded_by_detected(
        event_ledger, event_id="rel-1", superseded_memory_id="A", superseding_memory_id="B",
        timestamp="2026-01-03T00:00:00Z",
    )

    assert event.event_type == EVENT_RELATIONSHIP_DETECTED
    assert event.memory_ids == ("A", "B")  # semantic order, not sorted
    assert event.relationship_type == RELATIONSHIP_SUPERSEDED_BY
    assert event.mechanism == MECHANISM_EXPLICIT_SUPERSESSION_CALL
    assert event_ledger.get_event("rel-1") is not None


def test_supersede_memory_with_detection_appends_both_the_supersession_and_the_detection_event(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    _seed_memory(memory_ledger, event_ledger, "m2", "2026-01-02T00:00:00Z")

    superseded_event = build_canonical_event(
        event_type=EVENT_SUPERSEDED, memory_ids=("m1",), timestamp="2026-01-03T00:00:00Z",
        actor="creation_policy", reason="m2 supersedes m1.",
        previous_state=LIFECYCLE_CREATED, new_state=LIFECYCLE_RETIRED,
    )
    retired_event = build_canonical_event(
        event_type=EVENT_RETIRED, memory_ids=("m1",), timestamp="2026-01-03T00:00:01Z",
        actor="creation_policy", reason="m1 retired via supersession.",
        previous_state=LIFECYCLE_CREATED, new_state=LIFECYCLE_RETIRED,
    )

    result = supersede_memory_with_detection(
        event_ledger, memory_ledger, supersession_ledger, "m1", "m2",
        superseded_event=superseded_event, retired_event=retired_event,
        relationship_detected_event_id="rel-1",
    )

    assert result.supersession_result.status is not None
    assert result.detection_event is not None
    assert result.detection_error is None
    assert result.detection_event.memory_ids == ("m1", "m2")
    assert event_ledger.get_event("rel-1") is not None
