"""Attribution -- PROPAGATION.

Question: which attack-tainted memories (if any) is this memory reachable from, and by
what grounded path? Reuses `phase5.wiring.lineage.tainted_memory_evidence()` verbatim --
never `taint_propagation.tainted_memories()` directly, so the genuine per-hop `derived`
event grounding (Stage 5.7 review fix) is always the evidence this module cites, never a
same-record proxy.

STATUS MAPPING (distinct from ORIGIN's -- see ATTRIBUTION_METHODOLOGY.md Sec 5)
--------------------------------------------------------------------------------
- `UNIQUE`: exactly one attack origin's evidence entry names this memory as a fully-
  grounded descendant.
- `MULTIPLE_POSSIBLE_SOURCES`: more than one distinct attack origin reaches this memory
  with a fully-grounded path (a real, if rarer, case -- e.g. two independent attacks each
  contributing to a merge-derived descendant).
- `INSUFFICIENT_EVIDENCE`: `tainted_memories()` (via `tainted_memory_evidence()`) confirms
  this memory as reachable from at least one given attack_memory_id, but NO fully-
  grounded real event path exists (`ungrounded_descendant_ids`) -- e.g. a
  `CanonicalMemoryRecord` written with `parent_ids` set directly, bypassing
  `record_memory_derivation()`. This is a genuinely weaker case than `NO_ATTACK_ORIGIN`
  and must never be silently merged into it.
- `NO_ATTACK_ORIGIN`: not reachable from any of the given `attack_memory_ids` at all.

`evidence_kind` is always `LINEAGE_REACHABILITY` for a positive finding here -- reachable-
by-derivation is explicitly weaker than `COUNTERFACTUAL_EVIDENCE` and is never upgraded.
"""

from __future__ import annotations

from typing import Optional, Sequence

from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase3.evaluation.foundations.memory_versioning import SupersessionLedger

from phase5.wiring.lineage import EVIDENCE_LINEAGE_REACHABILITY, tainted_memory_evidence

from attribution.schema import (
    ATTRIBUTION_PROPAGATION,
    SOURCE_MEMORY,
    SOURCE_NONE,
    STATUS_INSUFFICIENT_EVIDENCE,
    STATUS_MULTIPLE_POSSIBLE_SOURCES,
    STATUS_NO_ATTACK_ORIGIN,
    STATUS_UNIQUE,
    TARGET_MEMORY,
    AttributionResult,
    generate_attribution_id,
)


def attribute_propagation(
    memory_id: str,
    *,
    run_id: str,
    memory_ledger: CanonicalMemoryLedger,
    event_ledger: CanonicalEventLedger,
    attack_memory_ids: Sequence[str],
    supersession_ledger: Optional[SupersessionLedger] = None,
) -> AttributionResult:
    """One `AttributionResult` for whether/how `memory_id` is reachable from any of
    `attack_memory_ids`, within `run_id`. `attack_memory_ids` must be the caller's own
    real, previously-established set (e.g. this run's `attribute_origin()`-confirmed
    attack products) -- this function does not discover attack origins itself."""
    report = tainted_memory_evidence(
        memory_ledger, attack_memory_ids, event_ledger=event_ledger, supersession_ledger=supersession_ledger,
    )

    grounded_matches = [ev for ev in report.evidence if ev.descendant_memory_id == memory_id]
    is_ungrounded = memory_id in report.ungrounded_descendant_ids

    if not grounded_matches and not is_ungrounded:
        return AttributionResult(
            attribution_id=generate_attribution_id(attribution_type=ATTRIBUTION_PROPAGATION, run_id=run_id, target_id=memory_id),
            run_id=run_id, target_type=TARGET_MEMORY, target_id=memory_id,
            attribution_type=ATTRIBUTION_PROPAGATION, status=STATUS_NO_ATTACK_ORIGIN, source_type=SOURCE_NONE,
            rationale=f"memory_id={memory_id!r} is not lineage-reachable from any of attack_memory_ids={tuple(attack_memory_ids)!r}.",
        )

    if not grounded_matches and is_ungrounded:
        return AttributionResult(
            attribution_id=generate_attribution_id(attribution_type=ATTRIBUTION_PROPAGATION, run_id=run_id, target_id=memory_id, ungrounded=True),
            run_id=run_id, target_type=TARGET_MEMORY, target_id=memory_id,
            attribution_type=ATTRIBUTION_PROPAGATION, status=STATUS_INSUFFICIENT_EVIDENCE, source_type=SOURCE_NONE,
            rationale=(
                f"tainted_memories() confirms memory_id={memory_id!r} is reachable from an attack origin, "
                "but no fully-evidenced real 'derived' event path could be found for every hop "
                "(tainted_memory_evidence().ungrounded_descendant_ids) -- reported honestly rather than "
                "citing a fabricated or same-record proxy event."
            ),
        )

    distinct_attack_ids = tuple(sorted({ev.attack_memory_id for ev in grounded_matches}))

    if len(distinct_attack_ids) == 1:
        ev = grounded_matches[0]
        return AttributionResult(
            attribution_id=generate_attribution_id(
                attribution_type=ATTRIBUTION_PROPAGATION, run_id=run_id, target_id=memory_id, source_id=ev.attack_memory_id,
            ),
            run_id=run_id, target_type=TARGET_MEMORY, target_id=memory_id,
            attribution_type=ATTRIBUTION_PROPAGATION, status=STATUS_UNIQUE,
            source_type=SOURCE_MEMORY, source_id=ev.attack_memory_id,
            lineage_path=ev.path_memory_ids, lineage_scope="TAINT_REACHABILITY",
            evidence_event_ids=ev.supporting_event_ids, evidence_kind=EVIDENCE_LINEAGE_REACHABILITY,
            rationale=(
                f"tainted_memory_evidence() found one fully-grounded real path {ev.path_memory_ids!r} "
                f"from attack-origin memory {ev.attack_memory_id!r} to {memory_id!r}, "
                f"lifecycle_status={ev.lifecycle_status!r}."
            ),
        )

    all_event_ids = tuple(sorted({eid for ev in grounded_matches for eid in ev.supporting_event_ids}))
    return AttributionResult(
        attribution_id=generate_attribution_id(
            attribution_type=ATTRIBUTION_PROPAGATION, run_id=run_id, target_id=memory_id, candidate_source_ids=distinct_attack_ids,
        ),
        run_id=run_id, target_type=TARGET_MEMORY, target_id=memory_id,
        attribution_type=ATTRIBUTION_PROPAGATION, status=STATUS_MULTIPLE_POSSIBLE_SOURCES,
        source_type=SOURCE_MEMORY, candidate_source_ids=distinct_attack_ids,
        evidence_event_ids=all_event_ids, evidence_kind=EVIDENCE_LINEAGE_REACHABILITY,
        rationale=f"memory_id={memory_id!r} is fully-grounded lineage-reachable from {len(distinct_attack_ids)} distinct attack origins: {distinct_attack_ids!r}.",
    )


__all__ = ["attribute_propagation"]
