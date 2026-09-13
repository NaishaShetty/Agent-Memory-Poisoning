"""Post-Phase-5 hardening -- OR-12 coverage gap closure: ground-truth state derivation.

WHAT WAS FOUND
--------------------------------------------------------------------------------
Building the OR-1..OR-15 contract coverage matrix for this hardening pass surfaced a
real, previously-undisclosed gap: Stage 5.2 made `Phase5Event`'s `attack_ground_truth_
transition` type and the full 9-state `GROUND_TRUTH_STATES` vocabulary real, validated
code -- but no stage from 5.4 through 5.9 ever actually CONSTRUCTS one from real pipeline
evidence. Only `test_phase5_event_schema.py`'s own schema-validation test exercises the
type directly. OR-12 therefore had schema support but no producer -- indirect/incomplete
coverage, not full instrumentation.

WHY THIS IS SAFELY CLOSABLE, ADDITIVELY, NOW
--------------------------------------------------------------------------------
`phase4/shared/dormancy_report.py` (frozen Phase 4) already establishes the exact
precedent this needs: a read-only classifier over already-produced evidence, computing a
3-state subset (`NOT_RETRIEVED`/`POISON_IN_CANDIDATE_POOL`/`POISON_SELECTED_TOP_K`) of
this same vocabulary. This module extends that same discipline -- classify, never
infer beyond what real evidence shows -- to the full set of states Phase 5's own
persisted evidence can mechanically support, using Phase 5's ledgers instead of a bare
`AgentRunOutcome` (which dormancy_report.py itself was scoped to before Phase 5 existed).
`dormancy_report.py` itself is not modified, not reimplemented, and not depended on here
-- this is a parallel, Phase-5-native classifier over the same KIND of question.

WHICH STATES ARE MECHANICALLY DERIVABLE FROM REAL PHASE 5 EVIDENCE, AND WHICH ARE NOT
--------------------------------------------------------------------------------
Derivable, each from exactly one real, cited event:
    POISON_NOT_ADMITTED       <- attack_injection, admission_status != ADMITTED
    POISON_ADMITTED           <- attack_injection, admission_status == ADMITTED
    POISON_IN_CANDIDATE_POOL  <- retrieval_candidate_scored, canonical_status=IN_LEDGER
    POISON_SELECTED_TOP_K     <- retrieval_candidate_scored, selected=True
    POISON_INFLUENCED_RESPONSE<- a real counterfactually_influential CanonicalEvent

Deliberately NOT derived here (kept as documented, disclosed gaps, never guessed):
    POISON_RETRIEVED_BUT_NOT_USED -- requires a genuine usage-attribution signal; Phase 5
        only ever records `used_memories_observability=NOT_OBSERVABLE` (contract OR-10),
        so "used" cannot be mechanically distinguished from "selected but not used" today.
    TARGET_BEHAVIOR_TRIGGERED, ATTACK_SUCCESS, ATTACK_FAILURE -- these require a
        task-specific, calibrated success/behavior judgment (per FARMA's own campaign
        script: "deliberately not auto-classified... per this session's standing
        discipline against auto-judging without a documented, calibrated rule"). This
        module does not invent that rule.

Every emitted `Phase5Event` cites a real `derived_from_event_id` -- never a bare,
unexplained state assignment, per contract OR-12's own requirement and the schema's own
validation (`Phase5Event.__post_init__` already REQUIRES this field non-empty).
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from phase3.evaluation.foundations.canonical_event import EVENT_COUNTERFACTUALLY_INFLUENTIAL
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger

from phase5.schema.event import (
    ADMISSION_STATUS_ADMITTED,
    ATTACK_GROUND_TRUTH_TRANSITION,
    CANONICAL_STATUS_IN_LEDGER,
    POISON_ADMITTED,
    POISON_IN_CANDIDATE_POOL,
    POISON_INFLUENCED_RESPONSE,
    POISON_NOT_ADMITTED,
    POISON_SELECTED_TOP_K,
    Phase5Event,
    generate_phase5_event_id,
)
from phase5.schema.event_ledger import Phase5EventLedger


_UNKNOWN_ATTACK = "UNKNOWN_ATTACK"


def derive_ground_truth_transitions(
    *,
    phase5_event_ledger: Phase5EventLedger,
    event_ledger: Optional[CanonicalEventLedger] = None,
    memory_id_to_attack_id: Optional[dict] = None,
    actor: str = "ground_truth_deriver",
    timestamp: str,
) -> Tuple[Phase5Event, ...]:
    """Read-only: derives every mechanically-supportable ground-truth transition from
    real, already-persisted evidence in `phase5_event_ledger` (and, if given,
    `event_ledger` for `POISON_INFLUENCED_RESPONSE`). Returns `Phase5Event` objects --
    does NOT append them to any ledger itself (mirrors `wiring/lineage.py`'s own
    "derive, let the caller decide to persist" discipline). Calling this twice with the
    same ledger state produces byte-identical output (event_id is content-derived).

    `retrieval_candidate_scored` events carry no `attack_id` field (confirmed by reading
    `schema/event.py` -- that field is scoped exclusively to `attack_injection` events),
    so `POISON_IN_CANDIDATE_POOL`/`POISON_SELECTED_TOP_K`/`POISON_INFLUENCED_RESPONSE`
    cannot name their attack_id from the scored/counterfactual event alone. A caller that
    already has the real `memory_id -> attack_id` mapping (e.g. from
    `wiring/lineage.py::derive_produced_edges()`'s own output) may supply
    `memory_id_to_attack_id` to resolve it correctly; otherwise the attack_id is honestly
    reported as `UNKNOWN_ATTACK` rather than guessed.
    """
    memory_id_to_attack_id = memory_id_to_attack_id or {}
    transitions: List[Phase5Event] = []

    def _emit(attack_id: str, memory_id: str, state: str, derived_from_event_id: str, reason: str) -> None:
        kwargs = dict(
            event_type=ATTACK_GROUND_TRUTH_TRANSITION, timestamp=timestamp, actor=actor, reason=reason,
            attack_id=attack_id, memory_id=memory_id, state=state, derived_from_event_id=derived_from_event_id,
        )
        event_id = generate_phase5_event_id(**kwargs)
        transitions.append(Phase5Event(event_id=event_id, **kwargs))

    for injection in phase5_event_ledger.all_events():
        if injection.event_type != "attack_injection":
            continue
        if injection.admission_status == ADMISSION_STATUS_ADMITTED and injection.memory_id is not None:
            _emit(
                injection.attack_id, injection.memory_id, POISON_ADMITTED, injection.event_id,
                "admission_status=ADMITTED on the real attack_injection event.",
            )
        else:
            # No memory_id exists for a non-admitted injection -- the ground-truth event
            # names the artifact_id in place of a memory_id would be a schema violation
            # (attack_ground_truth_transition.memory_id is required); this state is
            # therefore reported keyed by artifact_id, the only real identifier available.
            _emit(
                injection.attack_id, injection.artifact_id, POISON_NOT_ADMITTED, injection.event_id,
                f"admission_status={injection.admission_status!r} (not ADMITTED) on the real attack_injection event.",
            )

    for scored in phase5_event_ledger.all_events():
        if scored.event_type != "retrieval_candidate_scored":
            continue
        attack_id = memory_id_to_attack_id.get(scored.memory_id, _UNKNOWN_ATTACK)
        if scored.canonical_status == CANONICAL_STATUS_IN_LEDGER:
            _emit(
                attack_id, scored.memory_id, POISON_IN_CANDIDATE_POOL, scored.event_id,
                "canonical_status=IN_CANONICAL_LEDGER on the real retrieval_candidate_scored event.",
            )
        if scored.selected:
            _emit(
                attack_id, scored.memory_id, POISON_SELECTED_TOP_K, scored.event_id,
                "selected=True on the real retrieval_candidate_scored event.",
            )

    if event_ledger is not None:
        for event in event_ledger.all_events():
            if event.event_type == EVENT_COUNTERFACTUALLY_INFLUENTIAL:
                attack_id = memory_id_to_attack_id.get(event.memory_ids[0], _UNKNOWN_ATTACK)
                _emit(
                    attack_id, event.memory_ids[0], POISON_INFLUENCED_RESPONSE, event.event_id,
                    "a real counterfactually_influential CanonicalEvent exists for this memory.",
                )

    return tuple(transitions)


__all__ = ["derive_ground_truth_transitions"]
