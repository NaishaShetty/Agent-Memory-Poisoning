"""Phase 6.13 -- Defense <-> Attribution Integration: "what did the defense
actually mitigate?"

READ-ONLY, POST-HOC, NEVER A RUNTIME DECISION INPUT
--------------------------------------------------------------------------------
This module calls Attribution's real, frozen `attribute_memory()` orchestrator
(`attribution/wiring/orchestrator.py`) exactly as it already exists -- Attribution
is NEVER modified to accommodate Phase 6 (Charter Section 6). Nothing here
writes to any ledger, and nothing here is ever called from a D1-D4 runtime
decision function; it exists purely to explain, after the fact, what a
defense decision already made actually corresponded to in the real evidence
trail.

THE FALLACY THIS MODULE EXISTS TO STRUCTURALLY PREVENT
--------------------------------------------------------------------------------
The Stage 6.13 brief gives the exact failure mode by name: "Defense blocked
retrieval, therefore it prevented influence" is NOT automatically valid.
`_build_narrative()` below never asserts an influence claim from an
admission/retrieval/propagation action alone -- it reports the REAL
`AttributionResult.status` for the INFLUENCE question type verbatim, and if
the defense's own action means no real event trail exists downstream of the
intervention (e.g. a memory `BLOCK`ed at admission was never even written, so
Attribution's `attribute_origin`/`attribute_lineage` correctly and gracefully
report `NO_ATTACK_ORIGIN`/`NO_LINEAGE_ANCESTOR` -- real, valid absence
findings, confirmed by direct inspection of those functions' own code, not
errors), the narrative says exactly that: no real evidence exists either way,
NOT "the defense proved it prevented anything downstream."

WHAT ATTRIBUTION ALREADY GUARANTEES, REUSED VERBATIM HERE
--------------------------------------------------------------------------------
retrieved != selected != exposed != used != influenced, and lineage
reachability != causal influence -- Attribution's own schema/orchestrator
already enforce this; this module inherits it by construction, since every
fact reported below is a direct, unmodified `AttributionResult.status` value,
never a Phase-6-invented inference layered on top.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from attribution.schema import (
    ATTRIBUTION_EXPOSURE,
    ATTRIBUTION_INFLUENCE,
    ATTRIBUTION_LINEAGE,
    ATTRIBUTION_ORIGIN,
    ATTRIBUTION_PROPAGATION,
    ATTRIBUTION_REFERENCES,
    STATUS_EXPOSURE_ESTABLISHED,
    STATUS_INFLUENCE_ESTABLISHED,
    STATUS_INFLUENCE_NOT_ESTABLISHED,
    STATUS_NO_ATTACK_ORIGIN,
    STATUS_NO_LINEAGE_ANCESTOR,
    STATUS_UNIQUE,
    AttributionResult,
)
from attribution.wiring.orchestrator import attribute_memory
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase5.schema.event_ledger import Phase5EventLedger
from phase6.defense.policy.records import MGPDecisionRecord
from phase6.defense.policy.states import ALLOW, BLOCK, QUARANTINE


@dataclass(frozen=True)
class DefenseMitigationReport:
    memory_id: str
    defense_action: str
    defense_reason: str
    attribution_results: Tuple[AttributionResult, ...]
    mitigation_narrative: Tuple[str, ...]


def _result_for(results: Sequence[AttributionResult], attribution_type: str) -> Optional[AttributionResult]:
    matches = [r for r in results if r.attribution_type == attribution_type]
    return matches[0] if matches else None


def _build_narrative(decision: MGPDecisionRecord, results: Sequence[AttributionResult]) -> Tuple[str, ...]:
    lines = [f"Defense action on {decision.candidate_memory_id!r}: {decision.action} ({decision.reason})"]

    origin = _result_for(results, ATTRIBUTION_ORIGIN)
    if origin is not None:
        if origin.status == STATUS_UNIQUE:
            lines.append(f"Origin: real, unique attack origin found -- attack_id={origin.attack_id!r} (evidence: {origin.evidence_event_ids}).")
        elif origin.status == STATUS_NO_ATTACK_ORIGIN:
            lines.append(
                "Origin: no real attack_injection event claims this memory. This is either a "
                "genuinely benign memory, OR (if the defense action was BLOCK at admission) a "
                "memory that was never actually written -- in the latter case, absence of an "
                "origin event reflects the memory never existing in the ledger, not a security finding."
            )
        else:
            lines.append(f"Origin: {origin.status} ({origin.rationale})")

    lineage = _result_for(results, ATTRIBUTION_LINEAGE)
    if lineage is not None:
        if lineage.status == STATUS_UNIQUE:
            lines.append(f"Lineage: real, one-hop parent {lineage.source_id!r} (path: {lineage.lineage_path}).")
        elif lineage.status == STATUS_NO_LINEAGE_ANCESTOR:
            lines.append("Lineage: no real 'derived' event names this memory as a child -- root/foundation memory, or never created.")
        else:
            lines.append(f"Lineage: {lineage.status} ({lineage.rationale})")

    propagation = _result_for(results, ATTRIBUTION_PROPAGATION)
    if propagation is not None:
        lines.append(f"Propagation: {propagation.status} ({propagation.rationale})")

    exposure = _result_for(results, ATTRIBUTION_EXPOSURE)
    if exposure is not None:
        if exposure.status == STATUS_EXPOSURE_ESTABLISHED:
            lines.append("Exposure: CONFIRMED -- a real agent_decision event shows this memory was in the rendered, agent-visible context.")
        else:
            lines.append(f"Exposure: {exposure.status} -- no real event shows this memory reached the agent-visible context for the checked decision.")
    elif decision.action in (BLOCK, QUARANTINE):
        lines.append(
            "Exposure: NOT CHECKED -- no decision_id was supplied, and given this memory's own "
            f"defense action ({decision.action}), no real exposure event would exist to check "
            "even if one were supplied, since the memory was excluded before context assembly."
        )

    influence = _result_for(results, ATTRIBUTION_INFLUENCE)
    if influence is not None:
        if influence.status == STATUS_INFLUENCE_ESTABLISHED:
            lines.append(
                f"Influence: CONFIRMED by real counterfactual evidence ({influence.evidence_event_ids}) -- "
                "masking this memory changed the generated answer."
            )
        elif influence.status == STATUS_INFLUENCE_NOT_ESTABLISHED:
            lines.append(
                "Influence: NOT ESTABLISHED. This is an absence of evidence, not evidence of "
                "absence -- it means no real counterfactual test was ever run for this memory/task, "
                "OR one was run and found no effect. "
                + (
                    f"THE DEFENSE ACTION ({decision.action}) DOES NOT, BY ITSELF, ESTABLISH THIS "
                    "RESULT -- 'the defense blocked/quarantined this memory, therefore it prevented "
                    "influence' is exactly the fallacy this report refuses to assert. Only a real "
                    "counterfactual finding could confirm influence either way, and for a memory "
                    "excluded before exposure, no such test is even meaningful to run."
                    if decision.action in (BLOCK, QUARANTINE)
                    else "For a memory that was ALLOWED, this status means no counterfactual test was "
                    "run for it in this run/task -- not that it was proven harmless."
                )
            )
        else:
            lines.append(f"Influence: {influence.status} ({influence.rationale})")

    references = _result_for(results, ATTRIBUTION_REFERENCES)
    if references is not None:
        lines.append(f"References (structural citation only, never behavioral): {references.status}")

    return tuple(lines)


def explain_defense_mitigation(
    decision: MGPDecisionRecord,
    *,
    run_id: str,
    event_ledger: CanonicalEventLedger,
    phase5_event_ledger: Phase5EventLedger,
    memory_ledger: Optional[CanonicalMemoryLedger] = None,
    attack_memory_ids: Optional[Sequence[str]] = None,
    decision_id: Optional[str] = None,
    action_id: Optional[str] = None,
    task_id: Optional[str] = None,
    full_lineage_chain: bool = False,
) -> DefenseMitigationReport:
    """The one entry point this module exposes. Calls Attribution's real,
    unmodified `attribute_memory()` orchestrator and composes a narrative
    that never asserts more than the real `AttributionResult` objects
    themselves establish.
    """
    results = attribute_memory(
        decision.candidate_memory_id,
        run_id=run_id,
        event_ledger=event_ledger,
        phase5_event_ledger=phase5_event_ledger,
        memory_ledger=memory_ledger,
        attack_memory_ids=attack_memory_ids,
        decision_id=decision_id,
        action_id=action_id,
        task_id=task_id,
        full_lineage_chain=full_lineage_chain,
    )
    narrative = _build_narrative(decision, results)
    return DefenseMitigationReport(
        memory_id=decision.candidate_memory_id,
        defense_action=decision.action,
        defense_reason=decision.reason,
        attribution_results=results,
        mitigation_narrative=narrative,
    )
