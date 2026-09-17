"""Phase 8.4 -- the Dormancy-Window Signal.

`docs/phase8/PHASE8_PLAN.md` Stage 8.4: the real elapsed distance between an admitted
memory's `POISON_ADMITTED` ground-truth transition and its first `POISON_SELECTED_TOP_K`
transition (or "never yet selected" if none exists in the ledger's current state) -- a
real, computed duration from already-recorded ground-truth transitions
(`phase5/wiring/ground_truth.py::derive_ground_truth_transitions()`), not a new
instrumentation point.

CORRECTION FROM THE PLAN'S OWN WORDING: NOT "OR ATTACK_FAILURE"
--------------------------------------------------------------------------------
`docs/phase8/PHASE8_PLAN.md` §4 Signal 2 describes this window as running to "its first
`POISON_SELECTED_TOP_K` (or `ATTACK_FAILURE`, if it never activates)". Direct read of
`phase5/wiring/ground_truth.py`'s own module docstring shows `ATTACK_FAILURE` is
DELIBERATELY NOT mechanically derived there -- it "require[s] a task-specific, calibrated
success/behavior judgment" that module explicitly refuses to invent. This module honors
that same refusal: a memory with no `POISON_SELECTED_TOP_K` transition yet is reported as
`ever_selected=False` ("not yet selected, as of the ledger's current state"), never
labeled `ATTACK_FAILURE` -- that label would be an unbuilt, uncalibrated judgment call
this module has no more basis for making than `ground_truth.py` itself does.

WHY THIS DOES NOT READ `ATTACK_GROUND_TRUTH_TRANSITION.timestamp`
--------------------------------------------------------------------------------
`derive_ground_truth_transitions()` stamps every transition it emits in one call with the
SAME caller-supplied `timestamp` (the derivation run's own timestamp), not the real moment
each transition's underlying evidence actually occurred -- confirmed by direct read of
that function's `_emit()` helper. This module instead follows each transition's own
`derived_from_event_id` back to the REAL underlying `Phase5Event` (the `attack_injection`
event for admission, the `retrieval_candidate_scored` event for selection) and reads
`timestamp`/`task_id` off THAT event -- the same real-evidence discipline `ground_truth.py`
itself uses to justify every transition it emits.

REAL ORDERING, REUSING STAGE 8.2'S OWN CHOICE
--------------------------------------------------------------------------------
When more than one `POISON_SELECTED_TOP_K` transition exists for a memory, "first" is
determined by the real `Phase5EventLedger` append order (the same real chronological
ordering `phase8.detection.sleeper_dormancy_signals.real_prior_retrieval_count()` already
uses), not by transition emission order. `tasks_scored_before_first_selection` is computed
by calling that same function directly -- reused, not reimplemented.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Sequence

from phase5.schema.event import ATTACK_GROUND_TRUTH_TRANSITION, POISON_ADMITTED, POISON_SELECTED_TOP_K, Phase5Event
from phase5.schema.event_ledger import Phase5EventLedger

from phase8.detection.sleeper_dormancy_signals import real_prior_retrieval_count


def _parse_timestamp(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    return datetime.fromisoformat(normalized)


@dataclass(frozen=True)
class DormancyWindowResult:
    memory_id: str
    admitted_event_id: str
    admitted_timestamp: str
    ever_selected: bool
    first_selected_event_id: Optional[str]
    first_selected_task_id: Optional[str]
    first_selected_timestamp: Optional[str]
    tasks_scored_before_first_selection: Optional[int]
    elapsed_seconds: Optional[float]


def real_dormancy_window(
    memory_id: str,
    *,
    phase5_event_ledger: Phase5EventLedger,
    ground_truth_transitions: Sequence[Phase5Event],
) -> DormancyWindowResult:
    """Real, computed dormancy window for `memory_id`, from real `ATTACK_GROUND_TRUTH_
    TRANSITION` events a caller has already derived (via `derive_ground_truth_transitions()`,
    unmodified -- this function does not re-derive ground truth itself, only consumes it).

    Raises `ValueError` if no `POISON_ADMITTED` transition exists for `memory_id` -- there
    is no real admission event to measure a window from.
    """
    admitted = [
        t for t in ground_truth_transitions
        if t.event_type == ATTACK_GROUND_TRUTH_TRANSITION and t.memory_id == memory_id and t.state == POISON_ADMITTED
    ]
    if not admitted:
        raise ValueError(
            f"No POISON_ADMITTED ground-truth transition found for memory_id {memory_id!r} -- "
            "cannot measure a dormancy window for a memory that was never (mechanically "
            "observed to be) admitted."
        )
    admitted_event = phase5_event_ledger.get(admitted[0].derived_from_event_id)

    selected = [
        t for t in ground_truth_transitions
        if t.event_type == ATTACK_GROUND_TRUTH_TRANSITION and t.memory_id == memory_id and t.state == POISON_SELECTED_TOP_K
    ]
    if not selected:
        return DormancyWindowResult(
            memory_id=memory_id, admitted_event_id=admitted_event.event_id, admitted_timestamp=admitted_event.timestamp,
            ever_selected=False, first_selected_event_id=None, first_selected_task_id=None,
            first_selected_timestamp=None, tasks_scored_before_first_selection=None, elapsed_seconds=None,
        )

    all_events = phase5_event_ledger.all_events()
    event_position = {event.event_id: index for index, event in enumerate(all_events)}
    selected_events = [phase5_event_ledger.get(t.derived_from_event_id) for t in selected]
    first_selected_event = min(selected_events, key=lambda e: event_position[e.event_id])

    tasks_before = real_prior_retrieval_count(
        memory_id, phase5_event_ledger=phase5_event_ledger, as_of_task_id=first_selected_event.task_id,
    )
    elapsed_seconds = (
        _parse_timestamp(first_selected_event.timestamp) - _parse_timestamp(admitted_event.timestamp)
    ).total_seconds()

    return DormancyWindowResult(
        memory_id=memory_id, admitted_event_id=admitted_event.event_id, admitted_timestamp=admitted_event.timestamp,
        ever_selected=True, first_selected_event_id=first_selected_event.event_id,
        first_selected_task_id=first_selected_event.task_id, first_selected_timestamp=first_selected_event.timestamp,
        tasks_scored_before_first_selection=tasks_before, elapsed_seconds=elapsed_seconds,
    )


__all__ = ["DormancyWindowResult", "real_dormancy_window"]
