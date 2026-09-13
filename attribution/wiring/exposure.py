"""Attribution -- EXPOSURE.

Question: was this memory exposed to a given decision -- as distinct from retrieved,
selected, or (see `influence.py`) actually used/influential? Reuses
`phase5.wiring.lineage.derive_exposed_to_decision_edges()` verbatim for the exposure fact
itself, plus the real `agent_decision` Phase5Event (for its `task_id`) and
`query_co_retrieved_memory_ids()`/`query_co_selected_memory_ids()` (Stage 5.7, unmodified)
for the retrieved/selected facts.

WHY RETRIEVED/SELECTED/EXPOSED ARE THREE INDEPENDENT BOOLEANS, NEVER ONE COMBINED CLAIM
--------------------------------------------------------------------------------
Per contract OR-10 / `used_memories_observability`, exposure is NEVER upgraded to a usage
claim, and per this framework's own discipline, retrieval and selection are earlier,
weaker facts than exposure. `details` on the returned `AttributionResult` carries all
three (`retrieved`, `selected`, `exposed`) as independent booleans so a reader can see
every gradation, not just the final `status`.

STATUS
--------------------------------------------------------------------------------
`status=EXPOSURE_ESTABLISHED` iff a real `USED_BY`/`EXPOSURE_ONLY` edge from `memory_id`
to `decision_id` exists (i.e. `memory_id` is in that decision's real `exposed_memory_ids`).
Otherwise `EXPOSURE_NOT_ESTABLISHED` -- even if `retrieved`/`selected` are True, because
retrieval/selection are not exposure (a memory can be selected into context and still not
correspond to what `exposed_memory_ids` records, if the two are computed from different
observability paths in a given wiring -- this function never assumes they must agree).
"""

from __future__ import annotations

from phase5.schema.event import AGENT_DECISION
from phase5.schema.event_ledger import Phase5EventLedger
from phase5.wiring.lineage import (
    EVIDENCE_EXPOSURE_ONLY,
    derive_exposed_to_decision_edges,
    query_co_retrieved_memory_ids,
    query_co_selected_memory_ids,
)

from attribution.schema import (
    ATTRIBUTION_EXPOSURE,
    SOURCE_NONE,
    STATUS_EXPOSURE_ESTABLISHED,
    STATUS_EXPOSURE_NOT_ESTABLISHED,
    TARGET_MEMORY,
    AttributionResult,
    generate_attribution_id,
)


def attribute_exposure(
    memory_id: str, decision_id: str, *, run_id: str, phase5_event_ledger: Phase5EventLedger,
) -> AttributionResult:
    """One `AttributionResult` for whether `memory_id` was exposed to `decision_id`,
    within `run_id`. Raises `KeyError`-shaped `StopIteration`... no: raises a clear
    `ValueError` if `decision_id` names no real `agent_decision` event -- an attribution
    question about a decision that never happened is a caller error, not a negative
    finding to report silently."""
    decision_event = next(
        (e for e in phase5_event_ledger.all_events() if e.event_type == AGENT_DECISION and e.decision_id == decision_id),
        None,
    )
    if decision_event is None:
        raise ValueError(f"decision_id {decision_id!r} does not name any real agent_decision event in this ledger.")

    task_id = decision_event.task_id
    retrieved = memory_id in query_co_retrieved_memory_ids(phase5_event_ledger, task_id)
    selected = memory_id in query_co_selected_memory_ids(phase5_event_ledger, task_id)

    exposure_edges = [
        e for e in derive_exposed_to_decision_edges(phase5_event_ledger)
        if e.source_id == memory_id and e.target_id == decision_id
    ]
    exposed = bool(exposure_edges)

    details = {"retrieved": retrieved, "selected": selected, "exposed": exposed, "task_id": task_id}

    if exposed:
        edge = exposure_edges[0]
        return AttributionResult(
            attribution_id=generate_attribution_id(
                attribution_type=ATTRIBUTION_EXPOSURE, run_id=run_id, target_id=memory_id, decision_id=decision_id,
            ),
            run_id=run_id, task_id=task_id, target_type=TARGET_MEMORY, target_id=memory_id,
            attribution_type=ATTRIBUTION_EXPOSURE, status=STATUS_EXPOSURE_ESTABLISHED, source_type=SOURCE_NONE,
            evidence_event_ids=edge.established_by_event_ids, evidence_kind=EVIDENCE_EXPOSURE_ONLY,
            rationale=(
                f"Real agent_decision event {decision_event.event_id} names memory_id={memory_id!r} "
                f"in its exposed_memory_ids for decision_id={decision_id!r}. This is exposure ONLY -- "
                "not a claim the agent actually used or relied on this memory."
            ),
            details=details,
        )

    return AttributionResult(
        attribution_id=generate_attribution_id(
            attribution_type=ATTRIBUTION_EXPOSURE, run_id=run_id, target_id=memory_id, decision_id=decision_id, exposed=False,
        ),
        run_id=run_id, task_id=task_id, target_type=TARGET_MEMORY, target_id=memory_id,
        attribution_type=ATTRIBUTION_EXPOSURE, status=STATUS_EXPOSURE_NOT_ESTABLISHED, source_type=SOURCE_NONE,
        rationale=(
            f"memory_id={memory_id!r} does not appear in agent_decision {decision_event.event_id}'s "
            f"exposed_memory_ids (retrieved={retrieved!r}, selected={selected!r} for task_id={task_id!r} -- "
            "neither is treated as exposure)."
        ),
        details=details,
    )


__all__ = ["attribute_exposure"]
