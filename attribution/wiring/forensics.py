"""Attribution -- FORENSICS (Phase 9, Stage 9.1).

WHAT THIS IS
--------------------------------------------------------------------------------
A new, purely COMPOSED result type and one backward-walk function that answers the
forensics question Phase 9's plan names: "starting from a real, flagged incident (a
Phase 6 QUARANTINE/BLOCK decision, or a Phase 7 propagation alert), reconstruct -- in
one coherent, ordered result -- the real chain of evidence EXPOSURE -> LINEAGE (full
chain) -> ORIGIN -> PROPAGATION that explains how the exposed content got there, with
one honestly-derived, worst-hop-wins confidence verdict for the whole chain."

This module invents NO new evidence-derivation logic, no new edge type, and no new
Phase 5 instrumentation. Every fact in a `ForensicReconstruction` is either a real,
unmodified `AttributionResult` this layer's own `attribute_exposure()`,
`attribute_lineage()`, `attribute_origin()`, and `attribute_propagation()` already
produce, or a plain composition (dict/tuple) of them. The only "new" work here is:
  1. Thin resolution -- reading a real `agent_decision`/`agent_action` Phase5Event's own
     `exposed_memory_ids` / `decision_id` fields to know WHICH memory ids and WHICH
     decision to run the existing attribute_* calls against (the exact same discipline
     `attribution/wiring/action.py` already uses to resolve action_id -> decision_id).
  2. The chain-confidence rule (`_compute_chain_confidence()`), a pure function over
     already-produced `AttributionResult.status` values -- never a new evidence fact.

WHY TARGET_TYPE ALSO ACCEPTS MEMORY, NOT ONLY DECISION/ACTION
--------------------------------------------------------------------------------
An earlier version of this module accepted only DECISION/ACTION targets, on the theory
that a backward walk is fundamentally decision-shaped (see
`phase5.schema.event.AGENT_DECISION`'s own `exposed_memory_ids` field). That theory does
not survive contact with this module's own real Stage 9.3 entry points
(`attribution/wiring/forensics_entrypoints.py`): a Phase 6 `MGPDecisionRecord` currently
carries only a `candidate_memory_id` (its own `decision_id` is a Phase-6-internal policy
id, unrelated to a real Phase 5 `agent_decision`/`agent_action` event -- confirmed by
reading `phase6/defense/policy/records.py` directly), and a Phase 7 campaign signal's
member ids are memory ids, not decision ids. Restricting this module to DECISION/ACTION
would make both of Phase 9's own named real entry points (plan Section 4.3) impossible
to wire up.

So `target_type=MEMORY` IS supported, with one honest difference: there is no decision
context to check EXPOSURE against, so the EXPOSURE hop is skipped entirely (not
fabricated as ESTABLISHED or NOT_ESTABLISHED) -- `exposure` is empty and the narrative
says plainly that exposure was not checked, mirroring
`phase6/defense/attribution_bridge/report.py`'s own "Exposure: NOT CHECKED" discipline
for a memory excluded before context assembly. The walk still proceeds LINEAGE (full
chain) -> ORIGIN -> PROPAGATION for that one memory id. For DECISION/ACTION targets, the
walk is unchanged: resolve every real `exposed_memory_ids` on the decision and walk each
one.

CHAIN CONFIDENCE -- A CLOSED, DISCLOSED VOCABULARY, NEVER A SCORE
--------------------------------------------------------------------------------
Per the Phase 9 plan Section 6/9.2 ("never claim more than the evidence establishes",
carried over unmodified from ATTRIBUTION_METHODOLOGY.md): `chain_confidence` is one of
four named, rule-derived verdicts (`CHAIN_CONFIDENCE_LEVELS` below), never a float. The
rule is "worst hop wins" -- a `ForensicReconstruction` is exactly as trustworthy as the
weakest `AttributionResult.status` it composes, never rounded up for presentation. Every
`ForensicReconstruction.narrative` names WHICH hop, specifically, is responsible for a
non-`SINGLE_ORIGIN_HIGH_CONFIDENCE` verdict -- mirroring
`phase6/defense/attribution_bridge/report.py::_build_narrative()`'s own
"explicitly refuse the inference, in words" discipline.

DETERMINISM
--------------------------------------------------------------------------------
Every attribute_* call this module makes is itself deterministic (verified by their own
test suites). This module never introduces nondeterminism: terminal ancestor ids and
`per_memory_*` dict keys are always iterated/inserted in `sorted()` order, and
`reconstruction_id` is a content-derived fingerprint (`generate_forensics_id()`), never
`uuid4()` -- re-running against unchanged ledger state produces a byte-identical result.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Sequence, Tuple

from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase3.evaluation.foundations.memory_versioning import SupersessionLedger
from phase3.evaluation.security.reproducibility import fingerprint

from phase5.schema.event import AGENT_ACTION, AGENT_DECISION
from phase5.schema.event_ledger import Phase5EventLedger

from attribution.schema import (
    STATUS_EXPOSURE_ESTABLISHED,
    STATUS_INSUFFICIENT_EVIDENCE,
    STATUS_MULTIPLE_POSSIBLE_SOURCES,
    STATUS_UNIQUE,
    TARGET_ACTION,
    TARGET_DECISION,
    TARGET_MEMORY,
    AttributionResult,
)
from attribution.wiring.exposure import attribute_exposure
from attribution.wiring.lineage import attribute_lineage
from attribution.wiring.origin import attribute_origin
from attribution.wiring.propagation import attribute_propagation

FORENSICS_ID_PREFIX = "FORENSIC"

# ---------------------------------------------------------------------------
# Chain-confidence vocabulary -- closed, disclosed, never a numeric score (see module
# docstring). Ordered here from strongest to weakest evidence shape only for readability;
# no ordinal comparison between them is ever performed in code.
# ---------------------------------------------------------------------------

CHAIN_SINGLE_ORIGIN_HIGH_CONFIDENCE = "SINGLE_ORIGIN_HIGH_CONFIDENCE"
CHAIN_MULTIPLE_PLAUSIBLE_ORIGINS = "MULTIPLE_PLAUSIBLE_ORIGINS"
CHAIN_NO_ATTACK_ORIGIN_FOUND = "NO_ATTACK_ORIGIN_FOUND"
CHAIN_INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
CHAIN_CONFIDENCE_LEVELS: Tuple[str, ...] = (
    CHAIN_SINGLE_ORIGIN_HIGH_CONFIDENCE, CHAIN_MULTIPLE_PLAUSIBLE_ORIGINS,
    CHAIN_NO_ATTACK_ORIGIN_FOUND, CHAIN_INSUFFICIENT_EVIDENCE,
)

_FORENSICS_TARGET_TYPES: Tuple[str, ...] = (TARGET_DECISION, TARGET_ACTION, TARGET_MEMORY)
_EXPOSURE_APPLICABLE_TARGET_TYPES: Tuple[str, ...] = (TARGET_DECISION, TARGET_ACTION)


def generate_forensics_id(**defining_fields: object) -> str:
    """Deterministic, content-derived -- same discipline as
    `attribution.schema.generate_attribution_id()`, never `uuid4()`."""
    return f"{FORENSICS_ID_PREFIX}-{fingerprint(dict(defining_fields))}"


@dataclass(frozen=True)
class ForensicReconstruction:
    """One full backward walk from a flagged decision/action to every real attack
    origin its exposed content can be traced to (or an honest report that none, or more
    than one, can be). Every field is a real, unmodified `AttributionResult` this
    module's own calls produced, or a plain composition of them -- see module
    docstring."""

    reconstruction_id: str
    run_id: str
    triggering_target_type: str
    triggering_target_id: str
    decision_id: Optional[str]
    walked_memory_ids: Tuple[str, ...]
    exposure: Mapping[str, AttributionResult]
    per_memory_lineage: Mapping[str, AttributionResult]
    per_memory_origin: Mapping[str, AttributionResult]
    per_memory_propagation: Mapping[str, AttributionResult]
    chain_confidence: str
    narrative: Tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "reconstruction_id": self.reconstruction_id,
            "run_id": self.run_id,
            "triggering_target_type": self.triggering_target_type,
            "triggering_target_id": self.triggering_target_id,
            "decision_id": self.decision_id,
            "walked_memory_ids": list(self.walked_memory_ids),
            "exposure": {k: v.to_dict() for k, v in self.exposure.items()},
            "per_memory_lineage": {k: v.to_dict() for k, v in self.per_memory_lineage.items()},
            "per_memory_origin": {k: v.to_dict() for k, v in self.per_memory_origin.items()},
            "per_memory_propagation": {k: v.to_dict() for k, v in self.per_memory_propagation.items()},
            "chain_confidence": self.chain_confidence,
            "narrative": list(self.narrative),
        }


def _resolve_decision_id(
    target_type: str, target_id: str, *, phase5_event_ledger: Phase5EventLedger,
) -> str:
    """Thin resolution only -- mirrors `attribution.wiring.action.attribute_action()`'s
    own `action_id -> decision_id` resolution verbatim (a real `agent_action` event
    already carries `decision_id`; no new fact is derived here)."""
    if target_type == TARGET_ACTION:
        action_event = next(
            (e for e in phase5_event_ledger.all_events() if e.event_type == AGENT_ACTION and e.action_id == target_id),
            None,
        )
        if action_event is None:
            raise ValueError(f"target_id {target_id!r} does not name any real agent_action event in this ledger.")
        return action_event.decision_id

    decision_event = next(
        (e for e in phase5_event_ledger.all_events() if e.event_type == AGENT_DECISION and e.decision_id == target_id),
        None,
    )
    if decision_event is None:
        raise ValueError(f"target_id {target_id!r} does not name any real agent_decision event in this ledger.")
    return target_id


def _terminal_ancestor_ids(lineage_result: AttributionResult) -> Tuple[str, ...]:
    """Which memory id(s) `attribute_origin()` should be checked against for one
    exposed memory's full lineage result. UNIQUE -> its one real root ancestor.
    MULTIPLE_POSSIBLE_SOURCES -> every distinct real ancestor found (never narrowed).
    NO_LINEAGE_ANCESTOR -> the memory is itself a root/foundation memory, so it is its
    own terminal node."""
    if lineage_result.status == STATUS_UNIQUE:
        return (lineage_result.source_id,)
    if lineage_result.status == STATUS_MULTIPLE_POSSIBLE_SOURCES:
        return lineage_result.candidate_source_ids
    return (lineage_result.target_id,)


def _compute_chain_confidence(
    exposure_applicable: bool,
    exposure_results: Sequence[AttributionResult],
    per_memory_lineage: Mapping[str, AttributionResult],
    per_memory_origin: Mapping[str, AttributionResult],
    per_memory_propagation: Mapping[str, AttributionResult],
) -> Tuple[str, str]:
    """Pure function over already-produced `AttributionResult.status` values -- the
    "worst hop wins" rule (Phase 9 plan Section 9.2). Returns (chain_confidence, reason)
    -- `reason` names the specific hop responsible whenever the verdict is not
    `SINGLE_ORIGIN_HIGH_CONFIDENCE`, never a bare label.

    `exposure_applicable=False` (a MEMORY-typed target -- see module docstring) skips
    the EXPOSURE hop's checks entirely rather than treating a deliberately-empty
    `exposure_results` as a gap; there is no decision context to have checked."""
    if exposure_applicable:
        if not exposure_results:
            return (
                CHAIN_INSUFFICIENT_EVIDENCE,
                "EXPOSURE hop: no real exposed_memory_ids were found on the triggering decision -- there is nothing to walk backward from.",
            )

        for exp in exposure_results:
            if exp.status != STATUS_EXPOSURE_ESTABLISHED:
                return (
                    CHAIN_INSUFFICIENT_EVIDENCE,
                    f"EXPOSURE hop: memory_id={exp.target_id!r} reported {exp.status!r}, not EXPOSURE_ESTABLISHED -- "
                    "inconsistent with the triggering decision's own exposed_memory_ids.",
                )

    insufficient_propagation = sorted(
        mid for mid, r in per_memory_propagation.items() if r.status == STATUS_INSUFFICIENT_EVIDENCE
    )
    if insufficient_propagation:
        return (
            CHAIN_INSUFFICIENT_EVIDENCE,
            f"PROPAGATION hop: memory_id(s) {tuple(insufficient_propagation)!r} reported INSUFFICIENT_EVIDENCE -- "
            "a real reachability path may exist but is not fully event-grounded.",
        )

    branching_memories = sorted(
        mid for mid, r in per_memory_lineage.items() if r.status == STATUS_MULTIPLE_POSSIBLE_SOURCES
    )
    confirmed_origin_ids = sorted(
        oid for oid, r in per_memory_origin.items() if r.status == STATUS_UNIQUE
    )

    if branching_memories:
        return (
            CHAIN_MULTIPLE_PLAUSIBLE_ORIGINS,
            f"LINEAGE hop: memory_id(s) {tuple(branching_memories)!r} reported MULTIPLE_POSSIBLE_SOURCES "
            "(a real branching/diamond ancestry) -- more than one plausible ancestor exists structurally, "
            "regardless of how many resolve to the same confirmed attack origin.",
        )

    if len(confirmed_origin_ids) > 1:
        return (
            CHAIN_MULTIPLE_PLAUSIBLE_ORIGINS,
            f"ORIGIN hop: {len(confirmed_origin_ids)} distinct real attack-origin memories were confirmed "
            f"across the exposed memories' ancestor chains: {tuple(confirmed_origin_ids)!r}.",
        )

    if len(confirmed_origin_ids) == 1:
        return (
            CHAIN_SINGLE_ORIGIN_HIGH_CONFIDENCE,
            f"Every hop resolved cleanly to exactly one confirmed real attack origin, memory_id={confirmed_origin_ids[0]!r}.",
        )

    return (
        CHAIN_NO_ATTACK_ORIGIN_FOUND,
        "ORIGIN hop: every terminal ancestor's attribute_origin() reported NO_ATTACK_ORIGIN -- the exposed "
        "content is real, but nothing in it is attack-produced by this evidence.",
    )


def _build_narrative(
    *,
    triggering_target_type: str,
    triggering_target_id: str,
    decision_id: Optional[str],
    exposure_applicable: bool,
    walked_memory_ids: Tuple[str, ...],
    exposure: Mapping[str, AttributionResult],
    per_memory_lineage: Mapping[str, AttributionResult],
    per_memory_origin: Mapping[str, AttributionResult],
    per_memory_propagation: Mapping[str, AttributionResult],
    chain_confidence: str,
    confidence_reason: str,
) -> Tuple[str, ...]:
    lines = [f"Forensic reconstruction for {triggering_target_type} {triggering_target_id!r}."]

    if not exposure_applicable:
        lines.append(
            "Exposure: NOT CHECKED -- this is a memory-only target with no decision context to "
            "check exposure against (mirrors phase6/defense/attribution_bridge/report.py's own "
            "'no decision_id supplied' discipline)."
        )
    elif not exposure:
        lines.append(f"Exposure: no real exposed_memory_ids on decision_id={decision_id!r} -- nothing to walk.")
    else:
        lines.append(f"Exposure: {len(exposure)} real memory id(s) exposed to decision_id={decision_id!r}.")

    for mid in walked_memory_ids:
        exp = exposure.get(mid)
        if exp is not None:
            lines.append(f"  - {mid!r}: exposure={exp.status}")
        else:
            lines.append(f"  - {mid!r}:")
        lineage = per_memory_lineage.get(mid)
        if lineage is not None:
            if lineage.status == STATUS_UNIQUE:
                lines.append(f"    Lineage: single real ancestor chain, root={lineage.source_id!r}, path={lineage.lineage_path}.")
            elif lineage.status == STATUS_MULTIPLE_POSSIBLE_SOURCES:
                lines.append(f"    Lineage: MULTIPLE_POSSIBLE_SOURCES, candidates={lineage.candidate_source_ids}.")
            else:
                lines.append(f"    Lineage: {lineage.status} -- {mid!r} is itself a root/foundation memory.")
        propagation = per_memory_propagation.get(mid)
        if propagation is not None:
            lines.append(f"    Propagation: {propagation.status} ({propagation.rationale})")

    for ancestor_id in sorted(per_memory_origin):
        origin = per_memory_origin[ancestor_id]
        if origin.status == STATUS_UNIQUE:
            lines.append(f"  Origin of {ancestor_id!r}: CONFIRMED attack_id={origin.attack_id!r} (evidence: {origin.evidence_event_ids}).")
        else:
            lines.append(f"  Origin of {ancestor_id!r}: {origin.status}.")

    lines.append(f"Chain confidence: {chain_confidence} -- {confidence_reason}")
    return tuple(lines)


def reconstruct_attack_origin(
    target_type: str,
    target_id: str,
    *,
    run_id: str,
    event_ledger: CanonicalEventLedger,
    phase5_event_ledger: Phase5EventLedger,
    memory_ledger: Optional[CanonicalMemoryLedger] = None,
    attack_memory_ids: Optional[Sequence[str]] = None,
    supersession_ledger: Optional[SupersessionLedger] = None,
) -> ForensicReconstruction:
    """The one entry point this module exposes (Phase 9 Stage 9.1 acceptance criteria).

    `target_type` must be `TARGET_DECISION`, `TARGET_ACTION`, or `TARGET_MEMORY` -- see
    module docstring for why all three are real, needed starting points (DECISION/ACTION
    walk every real `exposed_memory_ids` on that decision; MEMORY walks that one memory
    directly, with the EXPOSURE hop skipped rather than fabricated). `PROPAGATION` runs
    per walked memory only when both `memory_ledger` and `attack_memory_ids` are
    supplied (same optionality convention as
    `attribution.wiring.orchestrator.attribute_memory()`).

    Raises `ValueError` if `target_id` does not name a real event/memory-worthy id in
    this ledger, and if `target_type` is not one of the three supported values -- an
    attribution question about an incident that never happened is a caller error, not a
    negative finding to report silently.
    """
    if target_type not in _FORENSICS_TARGET_TYPES:
        raise ValueError(
            f"target_type {target_type!r} is not supported for a forensic reconstruction "
            f"(must be one of {_FORENSICS_TARGET_TYPES!r} -- see module docstring)."
        )

    exposure_applicable = target_type in _EXPOSURE_APPLICABLE_TARGET_TYPES

    if exposure_applicable:
        decision_id: Optional[str] = _resolve_decision_id(target_type, target_id, phase5_event_ledger=phase5_event_ledger)
        decision_event = next(
            e for e in phase5_event_ledger.all_events() if e.event_type == AGENT_DECISION and e.decision_id == decision_id
        )
        walked_memory_ids: Tuple[str, ...] = tuple(decision_event.exposed_memory_ids or ())
        exposure = {
            mid: attribute_exposure(mid, decision_id, run_id=run_id, phase5_event_ledger=phase5_event_ledger)
            for mid in walked_memory_ids
        }
    else:
        decision_id = None
        walked_memory_ids = (target_id,)
        exposure = {}

    per_memory_lineage: dict = {}
    terminal_ids_by_memory: dict = {}
    for mid in walked_memory_ids:
        lineage_result = attribute_lineage(mid, run_id=run_id, event_ledger=event_ledger, full_chain=True)
        per_memory_lineage[mid] = lineage_result
        terminal_ids_by_memory[mid] = _terminal_ancestor_ids(lineage_result)

    all_terminal_ids = sorted({tid for ids in terminal_ids_by_memory.values() for tid in ids})
    per_memory_origin = {
        tid: attribute_origin(tid, run_id=run_id, phase5_event_ledger=phase5_event_ledger)
        for tid in all_terminal_ids
    }

    per_memory_propagation: dict = {}
    if memory_ledger is not None and attack_memory_ids:
        for mid in walked_memory_ids:
            per_memory_propagation[mid] = attribute_propagation(
                mid, run_id=run_id, memory_ledger=memory_ledger, event_ledger=event_ledger,
                attack_memory_ids=attack_memory_ids, supersession_ledger=supersession_ledger,
            )

    chain_confidence, confidence_reason = _compute_chain_confidence(
        exposure_applicable, tuple(exposure.values()), per_memory_lineage, per_memory_origin, per_memory_propagation,
    )
    narrative = _build_narrative(
        triggering_target_type=target_type, triggering_target_id=target_id, decision_id=decision_id,
        exposure_applicable=exposure_applicable, walked_memory_ids=walked_memory_ids, exposure=exposure,
        per_memory_lineage=per_memory_lineage, per_memory_origin=per_memory_origin,
        per_memory_propagation=per_memory_propagation,
        chain_confidence=chain_confidence, confidence_reason=confidence_reason,
    )

    return ForensicReconstruction(
        reconstruction_id=generate_forensics_id(
            run_id=run_id, target_type=target_type, target_id=target_id, decision_id=decision_id,
        ),
        run_id=run_id, triggering_target_type=target_type, triggering_target_id=target_id,
        decision_id=decision_id, walked_memory_ids=walked_memory_ids, exposure=exposure,
        per_memory_lineage=per_memory_lineage, per_memory_origin=per_memory_origin,
        per_memory_propagation=per_memory_propagation, chain_confidence=chain_confidence, narrative=narrative,
    )


__all__ = [
    "CHAIN_SINGLE_ORIGIN_HIGH_CONFIDENCE", "CHAIN_MULTIPLE_PLAUSIBLE_ORIGINS",
    "CHAIN_NO_ATTACK_ORIGIN_FOUND", "CHAIN_INSUFFICIENT_EVIDENCE", "CHAIN_CONFIDENCE_LEVELS",
    "FORENSICS_ID_PREFIX", "generate_forensics_id", "ForensicReconstruction", "reconstruct_attack_origin",
]
