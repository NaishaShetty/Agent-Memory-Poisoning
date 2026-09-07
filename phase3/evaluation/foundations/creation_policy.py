"""Phase 3.3-DATASET -- the `superseded_by` half of the creation policy, per
`PHASE3_SELECTION_AND_CREATION_POLICY_DESIGN_REVIEW.md` section 3.2's approved split:
this half is NOT a novel research decision (supersession is always an explicit,
already-decided caller action, never a discovered similarity candidate) -- it is a
missing `relationship_detected` event emission at an already-frozen, already-tested
call site (`memory_versioning.py::supersede_memory()`).

`equivalent_to`/`conflicts_with` detection (the genuinely unfrozen half, requiring a
new similarity/contradiction mechanism) is deliberately NOT touched here -- see
`similarity.py`'s own docstring for where that boundary is drawn.

WHY `memory_versioning.py` IS NOT MODIFIED
--------------------------------------------------------------------------------
`memory_versioning.py` is frozen-adjacent (H.3), touched exactly twice this session
(H.3-R, H.3-R2), both times via a reviewed remediation process for real, discovered
bugs -- never for a new capability. This module stays a pure SIBLING: it emits the
`relationship_detected(superseded_by)` event ALONGSIDE a `supersede_memory()` call,
never inside it. `supersede_memory_with_detection()` below is a convenience
orchestrator that calls both, unmodified, in the caller's place -- it is not a
replacement for either function and adds no new logic to what either already does.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from phase3.evaluation.foundations.canonical_event import (
    RELATIONSHIP_SUPERSEDED_BY,
    CanonicalEvent,
    EVENT_RELATIONSHIP_DETECTED,
)
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase3.evaluation.foundations.memory_versioning import (
    SupersessionLedger,
    SupersessionResult,
    supersede_memory,
)

MECHANISM_EXPLICIT_SUPERSESSION_CALL = "explicit_supersession_call"
REASON_SUPERSEDED_BY_DETECTED = (
    "relationship_detected(superseded_by) recorded alongside an explicit "
    "supersede_memory() call -- detection here is definitional, not a similarity "
    "judgment: the caller has already decided B supersedes A."
)


def emit_superseded_by_detected(
    event_ledger: CanonicalEventLedger,
    *,
    event_id: str,
    superseded_memory_id: str,
    superseding_memory_id: str,
    timestamp: str,
    task_id: Optional[str] = None,
) -> CanonicalEvent:
    """Append one `relationship_detected(superseded_by)` event for an ALREADY-DECIDED
    supersession pair. `memory_ids` order is `(superseded, superseding)` -- semantic
    order, per `relationship_schema.md` section 3.2, never lexicographic (that ordering
    rule applies only to the two SYMMETRIC relationship types, which this function does
    not emit).
    """
    event = CanonicalEvent(
        event_id=event_id,
        event_type=EVENT_RELATIONSHIP_DETECTED,
        memory_ids=(superseded_memory_id, superseding_memory_id),
        task_id=task_id,
        timestamp=timestamp,
        actor="creation_policy",
        reason=REASON_SUPERSEDED_BY_DETECTED,
        relationship_type=RELATIONSHIP_SUPERSEDED_BY,
        mechanism=MECHANISM_EXPLICIT_SUPERSESSION_CALL,
    )
    event_ledger.append(event)
    return event


def supersede_memory_with_detection(
    event_ledger: CanonicalEventLedger,
    memory_ledger: CanonicalMemoryLedger,
    supersession_ledger: SupersessionLedger,
    superseded_memory_id: str,
    superseding_memory_id: str,
    *,
    superseded_event: CanonicalEvent,
    retired_event: CanonicalEvent,
    relationship_detected_event_id: str,
    task_id: Optional[str] = None,
) -> "SupersessionWithDetectionResult":
    """Orchestrates `supersede_memory()` (unmodified) followed by
    `emit_superseded_by_detected()` -- the detection event is appended AFTER
    `supersede_memory()` returns, so a detection-emission failure can never affect or
    be affected by the already-durable supersession result. If detection emission
    raises, the (already-successful or already-partial) `SupersessionResult` is still
    returned, with `detection_event=None` and `detection_error` set -- an honest
    partial state, mirroring `supersede_memory()`'s own "each step independently
    durable" discipline, never silently swallowed.
    """
    supersession_result = supersede_memory(
        event_ledger, memory_ledger, supersession_ledger,
        superseded_memory_id, superseding_memory_id,
        superseded_event=superseded_event, retired_event=retired_event,
    )

    detection_event: Optional[CanonicalEvent] = None
    detection_error: Optional[str] = None
    try:
        detection_event = emit_superseded_by_detected(
            event_ledger,
            event_id=relationship_detected_event_id,
            superseded_memory_id=superseded_memory_id,
            superseding_memory_id=superseding_memory_id,
            timestamp=retired_event.timestamp,
            task_id=task_id,
        )
    except Exception as exc:  # noqa: BLE001 -- reported, never silently swallowed
        detection_error = repr(exc)

    return SupersessionWithDetectionResult(
        supersession_result=supersession_result,
        detection_event=detection_event,
        detection_error=detection_error,
    )


@dataclass(frozen=True)
class SupersessionWithDetectionResult:
    supersession_result: SupersessionResult
    detection_event: Optional[CanonicalEvent]
    detection_error: Optional[str]


__all__ = [
    "MECHANISM_EXPLICIT_SUPERSESSION_CALL",
    "REASON_SUPERSEDED_BY_DETECTED",
    "emit_superseded_by_detected",
    "supersede_memory_with_detection",
    "SupersessionWithDetectionResult",
]
