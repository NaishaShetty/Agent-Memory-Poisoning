"""Attribution -- REFERENCES.

Question: does this memory's own real, persisted content literally cite one or more
other real memories (via the exact `[memory_id]` bracket citation format)? Reuses
`phase5.wiring.lineage.derive_references_edges()` verbatim -- itself added to Stage 5.7
on 2026-09-13 (that stage's frozen status was reopened, by explicit user instruction, to
close this exact gap; see `phase5/wiring/lineage.py`'s "REFERENCES -- REOPENED" module
docstring for the full rationale).

WHY THIS IS STRUCTURAL, NEVER A USAGE OR INFLUENCE CLAIM
--------------------------------------------------------------------------------
A REFERENCES finding says only "this memory's content contains that literal substring."
It says nothing about whether an agent ever saw, selected, used, or was influenced by
either memory -- those remain `attribute_exposure()`/`attribute_influence()`'s own,
entirely independent questions. `attribute_references()` never reads
`agent_decision`/`agent_action` at all.

MULTIPLICITY IS NOT AMBIGUITY
--------------------------------------------------------------------------------
A memory can literally cite more than one other real memory in its content -- this is a
confirmed, unambiguous fact about EACH citation independently (every one is verified by
exact substring match), never the kind of genuine uncertainty
`STATUS_MULTIPLE_POSSIBLE_SOURCES` represents elsewhere in this layer. All cited memory
ids are reported together in `candidate_source_ids`, regardless of count.
"""

from __future__ import annotations

from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger

from phase5.wiring.lineage import EVIDENCE_OBSERVED_EVENT, derive_references_edges

from attribution.schema import (
    ATTRIBUTION_REFERENCES,
    SOURCE_MEMORY,
    SOURCE_NONE,
    STATUS_REFERENCES_ESTABLISHED,
    STATUS_REFERENCES_NOT_ESTABLISHED,
    TARGET_MEMORY,
    AttributionResult,
    generate_attribution_id,
)


def attribute_references(
    memory_id: str, *, run_id: str, memory_ledger: CanonicalMemoryLedger, event_ledger: CanonicalEventLedger,
) -> AttributionResult:
    """One `AttributionResult` for every real memory `memory_id`'s own content literally
    cites, within `run_id`."""
    edges = [e for e in derive_references_edges(memory_ledger, event_ledger) if e.source_id == memory_id]

    if not edges:
        return AttributionResult(
            attribution_id=generate_attribution_id(attribution_type=ATTRIBUTION_REFERENCES, run_id=run_id, target_id=memory_id),
            run_id=run_id, target_type=TARGET_MEMORY, target_id=memory_id,
            attribution_type=ATTRIBUTION_REFERENCES, status=STATUS_REFERENCES_NOT_ESTABLISHED, source_type=SOURCE_NONE,
            rationale=f"No literal '[memory_id]' bracket citation to any other real memory was found in memory_id={memory_id!r}'s content.",
        )

    cited_ids = tuple(sorted({e.target_id for e in edges}))
    all_event_ids = tuple(sorted({eid for e in edges for eid in e.established_by_event_ids}))
    return AttributionResult(
        attribution_id=generate_attribution_id(
            attribution_type=ATTRIBUTION_REFERENCES, run_id=run_id, target_id=memory_id, cited_ids=cited_ids,
        ),
        run_id=run_id, target_type=TARGET_MEMORY, target_id=memory_id,
        attribution_type=ATTRIBUTION_REFERENCES, status=STATUS_REFERENCES_ESTABLISHED,
        source_type=SOURCE_MEMORY, candidate_source_ids=cited_ids,
        evidence_event_ids=all_event_ids, evidence_kind=EVIDENCE_OBSERVED_EVENT,
        rationale=(
            f"memory_id={memory_id!r}'s real content contains a literal '[memory_id]' bracket citation "
            f"to {len(cited_ids)} other real memor{'y' if len(cited_ids) == 1 else 'ies'}: {cited_ids!r}. "
            "This is a structural content fact only -- not a usage or influence claim."
        ),
    )


__all__ = ["attribute_references"]
