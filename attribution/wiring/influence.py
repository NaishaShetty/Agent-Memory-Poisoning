"""Attribution -- INFLUENCE.

Question: is there a real counterfactual finding that this memory influenced a task
outcome? Reuses `phase5.wiring.lineage.derive_influenced_edges()` verbatim -- the ONLY
source of an `INFLUENCED` edge in this framework, itself sourced from nothing but a real
`counterfactually_influential` `CanonicalEvent`.

THE CENTRAL DISCIPLINE THIS MODULE EXISTS TO ENFORCE
--------------------------------------------------------------------------------
`attribute_influence()` NEVER derives `INFLUENCE_ESTABLISHED` from retrieval, selection,
exposure, or temporal order -- only from a real counterfactual finding. There is no code
path here that inspects `agent_decision`/`agent_action` timing or `exposed_memory_ids` at
all. A memory can be `EXPOSURE_ESTABLISHED` (attribution/wiring/exposure.py) and
simultaneously `INFLUENCE_NOT_ESTABLISHED` here -- this is the CORRECT, expected outcome
for "exposure without influence" and this module does not attempt to reconcile the two
into one combined verdict.
"""

from __future__ import annotations

from typing import Optional

from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger

from phase5.wiring.lineage import EVIDENCE_COUNTERFACTUAL, derive_influenced_edges

from attribution.schema import (
    ATTRIBUTION_INFLUENCE,
    SOURCE_NONE,
    STATUS_INFLUENCE_ESTABLISHED,
    STATUS_INFLUENCE_NOT_ESTABLISHED,
    TARGET_MEMORY,
    AttributionResult,
    generate_attribution_id,
)


def attribute_influence(
    memory_id: str, *, run_id: str, event_ledger: CanonicalEventLedger, task_id: Optional[str] = None,
) -> AttributionResult:
    """One `AttributionResult` for whether `memory_id` has a real counterfactual-influence
    finding, within `run_id`. If `task_id` is given, the finding must also match that
    task; a memory can be influential for one task and not another, and this function
    never conflates the two."""
    edges = [e for e in derive_influenced_edges(event_ledger) if e.source_id == memory_id]
    if task_id is not None:
        edges = [e for e in edges if e.target_id == task_id]

    if not edges:
        return AttributionResult(
            attribution_id=generate_attribution_id(
                attribution_type=ATTRIBUTION_INFLUENCE, run_id=run_id, target_id=memory_id, task_id=task_id,
            ),
            run_id=run_id, task_id=task_id, target_type=TARGET_MEMORY, target_id=memory_id,
            attribution_type=ATTRIBUTION_INFLUENCE, status=STATUS_INFLUENCE_NOT_ESTABLISHED, source_type=SOURCE_NONE,
            rationale=(
                f"No real counterfactually_influential CanonicalEvent names memory_id={memory_id!r} "
                f"{'for task_id=' + repr(task_id) if task_id is not None else 'for any task'} in this run. "
                "This is NOT evidence of absence of retrieval/selection/exposure -- only of influence."
            ),
        )

    # A memory can, in principle, have distinct counterfactual findings across multiple
    # tasks; when task_id is not pinned, report every citing event together as one
    # established finding (they all independently ground the SAME claim -- "this memory
    # has been shown counterfactually influential somewhere in this run" -- never averaged
    # or reduced to one arbitrary task).
    all_event_ids = tuple(sorted({e.established_by_event_ids[0] for e in edges}))
    task_ids_involved = tuple(sorted({e.target_id for e in edges if e.target_id is not None}))
    return AttributionResult(
        attribution_id=generate_attribution_id(
            attribution_type=ATTRIBUTION_INFLUENCE, run_id=run_id, target_id=memory_id, task_id=task_id, event_ids=all_event_ids,
        ),
        run_id=run_id, task_id=task_id, target_type=TARGET_MEMORY, target_id=memory_id,
        attribution_type=ATTRIBUTION_INFLUENCE, status=STATUS_INFLUENCE_ESTABLISHED, source_type=SOURCE_NONE,
        evidence_event_ids=all_event_ids, evidence_kind=EVIDENCE_COUNTERFACTUAL,
        rationale=(
            f"Real counterfactually_influential CanonicalEvent(s) {all_event_ids!r} establish memory_id={memory_id!r} "
            f"as influential for task(s) {task_ids_involved!r}, via masking-intervention evidence."
        ),
        details={"task_ids_involved": task_ids_involved},
    )


__all__ = ["attribute_influence"]
