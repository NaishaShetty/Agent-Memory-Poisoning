"""Attribution -- ORIGIN.

Question: which attack (if any) produced this memory directly? Reuses
`phase5.wiring.lineage.derive_produced_edges()` verbatim -- this module does not
re-scan `Phase5EventLedger` itself for `attack_injection` events; it asks the one
function Stage 5.7 already built for exactly this fact.

STRUCTURAL FINDING (see ATTRIBUTION_METHODOLOGY.md Sec 4): `Phase5EventLedger.append()`'s
`DuplicateMemoryClaimError` invariant already prevents two different `attack_injection`
events from claiming the same `memory_id`. Consequence: for one `memory_id`,
`attribute_origin()` can only ever produce `UNIQUE` or `NO_ATTACK_ORIGIN` --
`MULTIPLE_POSSIBLE_SOURCES` is not reachable here and this module does not manufacture a
path to it.
"""

from __future__ import annotations

from phase5.schema.event_ledger import Phase5EventLedger
from phase5.wiring.lineage import EVIDENCE_OBSERVED_EVENT, derive_produced_edges

from attribution.schema import (
    ATTRIBUTION_ORIGIN,
    SOURCE_ATTACK,
    SOURCE_NONE,
    STATUS_NO_ATTACK_ORIGIN,
    STATUS_UNIQUE,
    TARGET_MEMORY,
    AttributionResult,
    generate_attribution_id,
)


def attribute_origin(memory_id: str, *, run_id: str, phase5_event_ledger: Phase5EventLedger) -> AttributionResult:
    """One `AttributionResult` for `memory_id`'s attack origin, within `run_id`."""
    produced_edges = derive_produced_edges(phase5_event_ledger)
    matches = [e for e in produced_edges if e.target_id == memory_id]

    if not matches:
        return AttributionResult(
            attribution_id=generate_attribution_id(
                attribution_type=ATTRIBUTION_ORIGIN, run_id=run_id, target_id=memory_id,
            ),
            run_id=run_id, target_type=TARGET_MEMORY, target_id=memory_id,
            attribution_type=ATTRIBUTION_ORIGIN, status=STATUS_NO_ATTACK_ORIGIN, source_type=SOURCE_NONE,
            rationale=f"No admitted attack_injection event in this run's Phase5EventLedger claims memory_id={memory_id!r} as its product.",
        )

    # Structurally at most one match under the DuplicateMemoryClaimError invariant --
    # asserted, not silently assumed, so a future ledger change that ever violated it
    # would surface here rather than silently picking one.
    assert len(matches) == 1, (
        f"Found {len(matches)} PRODUCED edges targeting memory_id={memory_id!r}; "
        "Phase5EventLedger's DuplicateMemoryClaimError invariant is expected to make this impossible."
    )
    edge = matches[0]
    injection_event = next(
        e for e in phase5_event_ledger.all_events()
        if e.event_id == edge.established_by_event_ids[0]
    )
    return AttributionResult(
        attribution_id=generate_attribution_id(
            attribution_type=ATTRIBUTION_ORIGIN, run_id=run_id, target_id=memory_id, source_id=edge.source_id,
        ),
        run_id=run_id, target_type=TARGET_MEMORY, target_id=memory_id,
        attribution_type=ATTRIBUTION_ORIGIN, status=STATUS_UNIQUE,
        source_type=SOURCE_ATTACK, source_id=edge.source_id,
        attack_id=injection_event.attack_id, injection_id=injection_event.injection_id,
        evidence_event_ids=edge.established_by_event_ids, evidence_kind=EVIDENCE_OBSERVED_EVENT,
        rationale=(
            f"Real ADMITTED attack_injection event {injection_event.event_id} "
            f"(attack_id={injection_event.attack_id!r}, injection_id={injection_event.injection_id!r}) "
            f"names memory_id={memory_id!r} as its product."
        ),
    )


__all__ = ["attribute_origin"]
