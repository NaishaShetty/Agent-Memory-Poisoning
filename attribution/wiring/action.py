"""Attribution -- ACTION-targeted attribution (closes the previously-disclosed gap).

Every real `agent_action` `Phase5Event` already carries a `decision_id` back to the
`agent_decision` that produced it (`phase5/schema/event.py`'s own required field for
`AGENT_ACTION`). No new evidence exists at the ACTION level that isn't already available
by resolving to its DECISION first -- so `attribute_action()` does not invent a new
attribution mechanism; it resolves `action_id -> decision_id` via the real
`Phase5EventLedger` and delegates the actual attribution question (currently EXPOSURE --
"was this memory exposed to the decision that produced this action") to
`attribute_exposure()` verbatim, then re-wraps the result with `target_type=ACTION`.

This is deliberately a thin resolution layer, not a duplicate of `attribute_exposure()`'s
logic: if that function's behavior ever changes, `attribute_action()` inherits the change
automatically rather than drifting out of sync with a second copy.
"""

from __future__ import annotations

from phase5.schema.event import AGENT_ACTION
from phase5.schema.event_ledger import Phase5EventLedger

from attribution.schema import ATTRIBUTION_EXPOSURE, TARGET_ACTION, AttributionResult, generate_attribution_id
from attribution.wiring.exposure import attribute_exposure


def attribute_action(
    action_id: str, memory_id: str, *, run_id: str, phase5_event_ledger: Phase5EventLedger,
) -> AttributionResult:
    """One `AttributionResult` for whether `memory_id` was exposed to the real
    `agent_decision` that produced `action_id`, within `run_id`. Raises `ValueError` if
    `action_id` names no real `agent_action` event -- an attribution question about an
    action that never happened is a caller error, not a negative finding to report
    silently (mirrors `attribute_exposure()`'s own discipline for an unknown decision_id).
    """
    action_event = next(
        (e for e in phase5_event_ledger.all_events() if e.event_type == AGENT_ACTION and e.action_id == action_id),
        None,
    )
    if action_event is None:
        raise ValueError(f"action_id {action_id!r} does not name any real agent_action event in this ledger.")

    exposure_result = attribute_exposure(
        memory_id, action_event.decision_id, run_id=run_id, phase5_event_ledger=phase5_event_ledger,
    )

    details = dict(exposure_result.details or {})
    details.update({
        "action_id": action_id,
        "action": action_event.action,
        "result": action_event.result,
        "decision_id": action_event.decision_id,
    })

    return AttributionResult(
        attribution_id=generate_attribution_id(
            attribution_type=ATTRIBUTION_EXPOSURE, run_id=run_id, target_type=TARGET_ACTION,
            target_id=action_id, memory_id=memory_id,
        ),
        run_id=run_id, task_id=exposure_result.task_id, target_type=TARGET_ACTION, target_id=action_id,
        attribution_type=ATTRIBUTION_EXPOSURE, status=exposure_result.status, source_type=exposure_result.source_type,
        source_id=exposure_result.source_id, evidence_event_ids=exposure_result.evidence_event_ids,
        evidence_kind=exposure_result.evidence_kind,
        rationale=(
            f"Resolved via real agent_action event {action_event.event_id} "
            f"(action_id={action_id!r}) -> decision_id={action_event.decision_id!r}. {exposure_result.rationale}"
        ),
        details=details,
    )


__all__ = ["attribute_action"]
