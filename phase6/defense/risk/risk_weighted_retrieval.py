"""Phase 10.3 -- risk-weighted retrieval-ranking penalty, generalizing
`consensus_guard.py`'s existing fixed-shape, threshold-gated downrank.

WHAT THIS GENERALIZES, PRECISELY
--------------------------------------------------------------------------------
`phase6/defense/retrieval/consensus_guard.py`'s `evaluate_retrieval_defense()`
applies a query-local DOWNRANK penalty ONLY when `consensus_divergence_score
>= THRESHOLD_DOWNRANK` (0.3) -- a candidate at divergence 0.29 gets NO
penalty at all, while one at 0.30 gets a real one. Below that gate, the
penalty magnitude itself is already continuously scaled
(`min(MAX_DOWNRANK_PENALTY, MAX_DOWNRANK_PENALTY * divergence)`) -- it is
specifically the GATE (did it cross the line at all) that is binary, not the
shape above it.

This module replaces that gate with a real `RiskEstimate` (Stage 10.1): the
penalty is `MAX_DOWNRANK_PENALTY * risk_score` for every eligible candidate,
continuously, with no threshold cutoff -- a candidate at divergence 0.05
gets a small but real penalty rather than exactly zero, and (the genuine new
capability this unlocks) a candidate whose divergence alone is unremarkable
but who ALSO carries real, corroborating evidence from another guard (e.g. an
admission-time signal already on record for the same memory, supplied via
`additional_signals_for`) can be penalized more than divergence alone would
justify -- real cross-guard corroboration, not just a smoother curve on the
same single signal.

WHY WEIGHTED_SUM WITH EQUAL WEIGHTS OVER *PRESENT* SIGNALS, NOT
GROUPED_GATED, DRIVES THIS PENALTY
--------------------------------------------------------------------------------
`risk_score.GROUPED_GATED` splits weight EQUALLY ACROSS THE FOUR GUARD
GROUPS (0.25 each), regardless of how many groups actually have evidence --
by design, so admission's five finer-grained signals cannot outweigh
retrieval's one just by having more keys. But the retrieval-ranking case
this module serves typically has evidence from ONE guard only (just
`consensus_divergence_score`, exactly what `consensus_guard.py` already
computes). Feeding a single-group estimate through `GROUPED_GATED` would
silently CAP the achievable penalty at `GROUP_WEIGHT` (0.25) regardless of
how large that one real signal is -- a divergence of 1.0 (the strongest
possible real evidence) would only ever produce a risk_score of 0.25, a real
regression from `consensus_guard.py`'s own existing 0.5 ceiling
(`MAX_DOWNRANK_PENALTY`). That would not be "risk-weighted ranking
generalizing the existing mechanism" -- it would be quietly weakening it.
`compute_candidate_risk_estimate()` below instead builds an EQUAL-WEIGHT
`WEIGHTED_SUM` over whichever real signals are actually present for this
candidate (1/n each, n = however many are supplied) -- with only
`consensus_divergence_score` present (the common case), this reduces
EXACTLY to `risk_score == consensus_divergence_score`, reproducing
`consensus_guard.py`'s own scaling precisely; when real additional signals
are supplied, each gets a fair, undiluted share rather than being
structurally capped by cross-guard groups that have no evidence at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Mapping, Optional, Sequence, Tuple

from phase6.defense.policy.records import MGPDecisionRecord, build_decision
from phase6.defense.policy.states import BLOCKED, DOWNRANK, QUARANTINE, QUARANTINED, validate_transition
from phase6.defense.retrieval.consensus_guard import (
    DivergenceFn,
    MIN_TOTAL_FLAGS_FOR_ESCALATION,
    RetrievalCandidate,
    THRESHOLD_ESCALATE_TO_QUARANTINE,
)
from phase6.defense.retrieval.signals import pool_consensus_divergence_signals
from phase6.defense.risk.risk_score import LOW, RiskEstimate, WEIGHTED_SUM, compute_memory_risk_score

GUARD_VERSION = "risk-weighted-retrieval-10.3.0"

# Same ceiling as consensus_guard.py's own MAX_DOWNRANK_PENALTY -- kept as a
# separate, disclosed constant here (not imported) because this module's job
# is to be directly A/B-comparable against the fixed-threshold mechanism at
# the SAME ceiling, not to silently drift from it.
MAX_DOWNRANK_PENALTY = 0.5

_INELIGIBLE_STATES = frozenset({QUARANTINED, BLOCKED})


def _equal_weights_for_present_signals(signals: Mapping[str, float]) -> Dict[str, float]:
    if not signals:
        return {}
    w = 1.0 / len(signals)
    return {k: w for k in signals}


def compute_candidate_risk_estimate(
    memory_id: str,
    consensus_divergence_score: float,
    additional_signals: Optional[Mapping[str, float]] = None,
) -> RiskEstimate:
    """Build the `RiskEstimate` that drives this candidate's ranking penalty.
    See module docstring for why `WEIGHTED_SUM` with equal weights over only
    the PRESENT signals is used here rather than `GROUPED_GATED`."""
    signals = {"consensus_divergence_score": consensus_divergence_score}
    if additional_signals:
        signals.update(additional_signals)
    weights = _equal_weights_for_present_signals(signals)
    return compute_memory_risk_score(memory_id, signals, rule=WEIGHTED_SUM, weights=weights)


def risk_weighted_downrank_penalty(estimate: RiskEstimate, *, max_penalty: float = MAX_DOWNRANK_PENALTY) -> float:
    """The continuous replacement for consensus_guard.py's threshold-gated
    penalty: proportional to `risk_score` for EVERY estimate, no cutoff."""
    return min(max_penalty, max_penalty * estimate.risk_score)


@dataclass(frozen=True)
class RiskAdjustedCandidate:
    memory_id: str
    eligible: bool
    adjusted_blended_score: float
    risk_score: float
    risk_band: str
    penalty_applied: float


@dataclass(frozen=True)
class RiskWeightedRetrievalResult:
    adjusted_candidates: Tuple[RiskAdjustedCandidate, ...]
    downrank_decisions: Tuple[MGPDecisionRecord, ...]
    escalation_decisions: Tuple[MGPDecisionRecord, ...]


def evaluate_retrieval_defense_risk_weighted(
    candidates: Sequence[RetrievalCandidate],
    *,
    run_id: str,
    episode_id: str,
    timestamp: str,
    evidence_refs_for: Callable[[str], Sequence[str]],
    additional_signals_for: Callable[[str], Mapping[str, float]] = lambda memory_id: {},
    prior_downrank_count_for: Callable[[str], int] = lambda memory_id: 0,
    divergence_fn: DivergenceFn = pool_consensus_divergence_signals,
) -> RiskWeightedRetrievalResult:
    """The risk-weighted counterpart to `consensus_guard.evaluate_retrieval_
    defense()`. Same eligibility rule (already-QUARANTINED/BLOCKED candidates
    excluded outright, same as before), same pool-level divergence
    computation (`divergence_fn`, defaulting to the identical lexical
    signal), same escalation-to-persistent-QUARANTINE mechanism at the same
    `THRESHOLD_ESCALATE_TO_QUARANTINE` / `MIN_TOTAL_FLAGS_FOR_ESCALATION`
    (Stage 10.3 is scoped to the query-local RANKING penalty only -- escalation
    policy is untouched). The ONLY behavioral difference is the downrank
    penalty's shape: continuous, risk-estimate-driven, no threshold gate --
    see module docstring.

    `additional_signals_for(memory_id)` lets a caller supply real, already-
    computed sanctioned signals for this candidate from OTHER guards (e.g. an
    admission-time `signals_used` already on record) -- optional, defaults to
    none, in which case this function's behavior for that candidate is driven
    by `consensus_divergence_score` alone, exactly mirroring
    `consensus_guard.py`'s own single-signal design.
    """
    eligible_indices = [i for i, c in enumerate(candidates) if c.security_state not in _INELIGIBLE_STATES]
    eligible_contents = [candidates[i].content_text for i in eligible_indices]
    divergence_signals = divergence_fn(eligible_contents)
    divergence_by_index: Dict[int, float] = {
        eligible_indices[k]: divergence_signals[k]["consensus_divergence_score"]
        for k in range(len(eligible_indices))
    }

    adjusted: list = []
    downrank_decisions: list = []
    escalation_decisions: list = []

    for i, candidate in enumerate(candidates):
        if candidate.security_state in _INELIGIBLE_STATES:
            adjusted.append(
                RiskAdjustedCandidate(
                    memory_id=candidate.memory_id, eligible=False, adjusted_blended_score=0.0,
                    risk_score=0.0, risk_band=LOW, penalty_applied=1.0,
                )
            )
            continue

        divergence = divergence_by_index[i]
        estimate = compute_candidate_risk_estimate(
            candidate.memory_id, divergence, additional_signals_for(candidate.memory_id)
        )
        penalty = risk_weighted_downrank_penalty(estimate)
        adjusted_score = candidate.raw_blended_score * (1.0 - penalty)

        if penalty > 0.0:
            signals_used = dict(estimate.contributing_signals)
            reason = (
                f"risk_score={estimate.risk_score:.3f} ({GUARD_VERSION}); "
                f"band={estimate.risk_band}; query-local downrank penalty={penalty:.3f} "
                "(continuous, no threshold gate)"
            )
            downrank_decisions.append(
                build_decision(
                    candidate_memory_id=candidate.memory_id, signals_used=signals_used, action=DOWNRANK,
                    reason=reason, run_id=run_id, episode_id=episode_id, timestamp=timestamp,
                    evidence_refs=evidence_refs_for(candidate.memory_id),
                )
            )
            if divergence >= THRESHOLD_ESCALATE_TO_QUARANTINE:
                total_flags = prior_downrank_count_for(candidate.memory_id) + 1
                if total_flags >= MIN_TOTAL_FLAGS_FOR_ESCALATION:
                    validate_transition(candidate.security_state, QUARANTINE)
                    escalation_reason = (
                        f"consensus_divergence_score={divergence:.3f} >= "
                        f"{THRESHOLD_ESCALATE_TO_QUARANTINE} ({GUARD_VERSION}); "
                        f"total_flags={total_flags} >= {MIN_TOTAL_FLAGS_FOR_ESCALATION}; "
                        "escalating to persistent QUARANTINE"
                    )
                    escalation_decisions.append(
                        build_decision(
                            candidate_memory_id=candidate.memory_id, signals_used=signals_used, action=QUARANTINE,
                            reason=escalation_reason, run_id=run_id, episode_id=episode_id, timestamp=timestamp,
                            evidence_refs=evidence_refs_for(candidate.memory_id),
                        )
                    )

        adjusted.append(
            RiskAdjustedCandidate(
                memory_id=candidate.memory_id, eligible=True, adjusted_blended_score=adjusted_score,
                risk_score=estimate.risk_score, risk_band=estimate.risk_band, penalty_applied=penalty,
            )
        )

    return RiskWeightedRetrievalResult(
        adjusted_candidates=tuple(adjusted),
        downrank_decisions=tuple(downrank_decisions),
        escalation_decisions=tuple(escalation_decisions),
    )
