"""Attribution -- orchestrator.

Combines every applicable attribution type for one target into a flat tuple of
`AttributionResult`s -- never one merged/collapsed answer (per the explicit instruction
against conflating the five questions). A caller wanting only one attribution type should
call that module's function directly; `attribute_memory()` exists for the common case of
"give me everything currently knowable about this memory."

`EXPOSURE` requires a `decision_id` (it is a memory-to-decision fact, not a memory-alone
fact) -- included only when the caller supplies one. `PROPAGATION` requires the caller's
own `attack_memory_ids` (this layer does not itself decide what counts as an attack
origin across a whole run; that is `attribute_origin()`'s job, one call at a time, or a
caller's own pre-computed set from Stage 5.7's `derive_produced_edges()`).
"""

from __future__ import annotations

from typing import Optional, Sequence, Tuple

from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase3.evaluation.foundations.memory_versioning import SupersessionLedger

from phase5.schema.event_ledger import Phase5EventLedger

from attribution.schema import AttributionResult
from attribution.wiring.action import attribute_action
from attribution.wiring.exposure import attribute_exposure
from attribution.wiring.influence import attribute_influence
from attribution.wiring.lineage import attribute_lineage
from attribution.wiring.origin import attribute_origin
from attribution.wiring.propagation import attribute_propagation
from attribution.wiring.references import attribute_references


def attribute_memory(
    memory_id: str,
    *,
    run_id: str,
    event_ledger: CanonicalEventLedger,
    phase5_event_ledger: Phase5EventLedger,
    memory_ledger: Optional[CanonicalMemoryLedger] = None,
    attack_memory_ids: Optional[Sequence[str]] = None,
    supersession_ledger: Optional[SupersessionLedger] = None,
    decision_id: Optional[str] = None,
    action_id: Optional[str] = None,
    task_id: Optional[str] = None,
    full_lineage_chain: bool = False,
) -> Tuple[AttributionResult, ...]:
    """ORIGIN and LINEAGE always run (they need only `event_ledger`/`phase5_event_ledger`).
    PROPAGATION runs only if both `memory_ledger` and `attack_memory_ids` are given.
    EXPOSURE runs only if `decision_id` is given. ACTION-resolved EXPOSURE runs only if
    `action_id` is given (resolves its own `decision_id` -- do not also pass `decision_id`
    for the same fact unless a second, direct EXPOSURE result is also wanted). INFLUENCE
    always runs (optionally scoped to `task_id`). `full_lineage_chain=True` makes the
    LINEAGE result the full ancestor chain instead of one-hop immediate parentage."""
    results = [
        attribute_origin(memory_id, run_id=run_id, phase5_event_ledger=phase5_event_ledger),
        attribute_lineage(memory_id, run_id=run_id, event_ledger=event_ledger, full_chain=full_lineage_chain),
        attribute_influence(memory_id, run_id=run_id, event_ledger=event_ledger, task_id=task_id),
    ]
    if memory_ledger is not None and attack_memory_ids:
        results.append(attribute_propagation(
            memory_id, run_id=run_id, memory_ledger=memory_ledger, event_ledger=event_ledger,
            attack_memory_ids=attack_memory_ids, supersession_ledger=supersession_ledger,
        ))
    if memory_ledger is not None:
        results.append(attribute_references(
            memory_id, run_id=run_id, memory_ledger=memory_ledger, event_ledger=event_ledger,
        ))
    if decision_id is not None:
        results.append(attribute_exposure(
            memory_id, decision_id, run_id=run_id, phase5_event_ledger=phase5_event_ledger,
        ))
    if action_id is not None:
        results.append(attribute_action(
            action_id, memory_id, run_id=run_id, phase5_event_ledger=phase5_event_ledger,
        ))
    return tuple(results)


__all__ = ["attribute_memory"]
