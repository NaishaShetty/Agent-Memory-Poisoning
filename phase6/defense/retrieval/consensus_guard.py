"""Phase 6.6 -- the Retrieval Consensus Guard: D3's own decision layer.

PIPELINE POSITION -- NEVER REPLACES PHASE 3 RETRIEVAL
--------------------------------------------------------------------------------
    20-candidate pool (Phase 3's real, unmodified retrieval)
          |
          v
    THIS MODULE: read persisted D2 state, compute pool consensus divergence,
                 filter ineligible candidates, apply query-local downrank
                 penalties to the remaining candidates' blended scores
          |
          v
    Phase 3's real, unmodified `hybrid_selection.select_by_hybrid_score()`
    (fed the FILTERED, RE-WEIGHTED candidate list this module produces --
    the same function, the same formula, never patched or re-implemented)
          |
          v
    top-8 -> agent-visible context

This module never calls or imports `phase3.evaluation.foundations.
hybrid_selection` -- wiring this module's output into that real call is Stage
6.10's integration job (Seven-Attack Defense Integration), exactly as Stage
6.4 deferred real ledger-reading wiring to later stages. This stage is
responsible for the DEFENSE DECISION LOGIC, testable in isolation, not for the
live integration.

RESOLVING THE STAGE 6.5 CONSISTENCY-SCREENING GAP
--------------------------------------------------------------------------------
`docs/phase6/ADMISSION_DEFENSE.md` disclosed that consistency screening
(component C: "compare a candidate against trusted existing memory") was
deferred from D1 to D3, to avoid duplicating retrieval logic before D3's
design existed. This module is where that gap is resolved: consensus
divergence (`signals.py`) IS the consistency check, computed against the
other members of the SAME retrieval's candidate pool (the closest analogue to
"trusted existing memory" D3 can cheaply access without a second, separate
retrieval pass over the whole store).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Sequence, Tuple

from phase6.defense.policy.records import MGPDecisionRecord, build_decision
from phase6.defense.policy.states import (
    BLOCKED,
    DOWNRANK,
    QUARANTINE,
    QUARANTINED,
    validate_transition,
)
from phase6.defense.retrieval.signals import pool_consensus_divergence_signals

# `DivergenceFn` is the pluggable seam between this decision layer (thresholds,
# actions, ledger recording -- the D-layer-agnostic "guard" logic) and the
# similarity METRIC used to compute divergence (D1 lexical vs. D2 semantic).
# This is what makes the D1-vs-D2 comparison a genuinely controlled
# experiment: identical guard logic, one varied factor. See
# `docs/phase6/RETRIEVAL_DEFENSE.md`'s "D0-D4 Framework" section.
DivergenceFn = Callable[[Sequence[str]], Tuple[Dict[str, float], ...]]


def semantic_divergence_fn(contents: Sequence[str]) -> Tuple[Dict[str, float], ...]:
    """Adapter: wraps `embedding_signals.pool_consensus_divergence_signals_
    semantic` (which also returns a real, measured `EmbeddingComputationCost`)
    down to the plain `DivergenceFn` shape `evaluate_retrieval_defense` expects.
    Import of `embedding_signals` is deferred into this function so that
    `consensus_guard`'s default (lexical) path never requires
    `sentence_transformers` to be installed -- only callers who explicitly
    select the semantic variant pay that dependency cost."""
    from phase6.defense.retrieval.embedding_signals import pool_consensus_divergence_signals_semantic

    signals, _cost = pool_consensus_divergence_signals_semantic(contents)
    return signals


GUARD_VERSION = "consensus-guard-1.1.0"

# Uncalibrated v1 thresholds (same disclosure discipline as
# reasoning_guard.py's THRESHOLD_* constants -- frozen starting defaults, not
# validated against real MAMBench attack content; Stage 6.9's job).
THRESHOLD_DOWNRANK = 0.6
THRESHOLD_ESCALATE_TO_QUARANTINE = 0.85

# Evidence-accumulation requirement for escalation (2026-09-14 fix): a SINGLE
# high-divergence event no longer escalates a memory to a persistent
# QUARANTINE on its own. `prior_downrank_count_for(memory_id)` -- backed by
# the caller's own GovernanceLedger, counting this memory's real prior
# DOWNRANK decisions -- must show at least this many PRIOR flags (i.e. this
# is at least the Nth time) before escalation fires. This directly replaces
# the original single-event design (see RETRIEVAL_DEFENSE.md's "Design
# Choices Worth Flagging" -- superseded by this fix) with one grounded in
# real, already-persisted decision history rather than unbuilt cross-run
# aggregation infrastructure.
MIN_TOTAL_FLAGS_FOR_ESCALATION = 2

# Maximum fraction a candidate's blended score can be reduced by, at
# divergence_score == 1.0 (full penalty scales linearly below that).
MAX_DOWNRANK_PENALTY = 0.5

_INELIGIBLE_STATES = frozenset({QUARANTINED, BLOCKED})


@dataclass(frozen=True)
class RetrievalCandidate:
    """Input: one candidate from Phase 3's real, unmodified candidate pool,
    plus its currently-persisted D2 security state (read from
    `GovernanceLedger.current_state()` by the caller -- this module does not
    read the ledger itself, consistent with the plain-data-carrier discipline
    Stage 6.4 established for `SignalContext`)."""

    memory_id: str
    content_text: str
    cosine_score: float
    token_overlap_score: float
    entity_overlap_score: float
    raw_blended_score: float
    security_state: str


@dataclass(frozen=True)
class AdjustedCandidate:
    """Output: what Stage 6.10's real integration would feed into Phase 3's
    unmodified `select_by_hybrid_score()` in place of the raw candidate list."""

    memory_id: str
    eligible: bool
    adjusted_blended_score: float
    consensus_divergence_score: float
    penalty_applied: float


@dataclass(frozen=True)
class RetrievalDefenseResult:
    adjusted_candidates: Tuple[AdjustedCandidate, ...]
    downrank_decisions: Tuple[MGPDecisionRecord, ...]
    escalation_decisions: Tuple[MGPDecisionRecord, ...]


def evaluate_retrieval_defense(
    candidates: Sequence[RetrievalCandidate],
    *,
    run_id: str,
    episode_id: str,
    timestamp: str,
    evidence_refs_for: Callable[[str], Sequence[str]],
    prior_downrank_count_for: Callable[[str], int] = lambda memory_id: 0,
    divergence_fn: DivergenceFn = pool_consensus_divergence_signals,
) -> RetrievalDefenseResult:
    """Evaluate one retrieval call's full candidate pool.

    `divergence_fn` selects the similarity METRIC (D1 lexical, the default,
    vs. D2 semantic via `semantic_divergence_fn`) while every threshold,
    action, and ledger-recording decision below is identical regardless of
    which is chosen -- this is what makes the D1-vs-D2 comparison controlled
    (see `test_semantic_consensus_guard.py`).

    `evidence_refs_for(memory_id)` lets the caller supply real evidence
    references per candidate (e.g. that candidate's own `retrieval_candidate_
    scored` Phase5Event id) without this module needing to read any ledger
    itself.

    `prior_downrank_count_for(memory_id)` lets the caller supply this
    memory's REAL prior DOWNRANK count from its own GovernanceLedger history
    (e.g. `len([d for d in ledger.decisions_for(memory_id) if d.action ==
    DOWNRANK])`). Escalation to a persistent QUARANTINE requires this count
    PLUS the current call to reach `MIN_TOTAL_FLAGS_FOR_ESCALATION` -- a
    single high-divergence event, on a memory with no prior flags, no longer
    escalates on its own (2026-09-14 fix; see that constant's docstring).
    The default (`lambda memory_id: 0`) is deliberately conservative: a
    caller that does not wire in real ledger history gets NO escalation
    ever (since 0 + 1 = 1 < 2), never an accidental over-eager one.

    Already-QUARANTINED/BLOCKED candidates (persisted D2 state) are excluded
    from the eligible set outright -- this enforces an EXISTING decision, so
    no new decision record is produced for that exclusion alone (nothing new
    was decided; Stage 6.3's ledger already recorded why that state was
    reached). Only NEW evidence produced at D3 itself (consensus divergence)
    generates new decision records here.
    """
    eligible_indices = [
        i for i, c in enumerate(candidates) if c.security_state not in _INELIGIBLE_STATES
    ]
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
                AdjustedCandidate(
                    memory_id=candidate.memory_id,
                    eligible=False,
                    adjusted_blended_score=0.0,
                    consensus_divergence_score=0.0,
                    penalty_applied=1.0,
                )
            )
            continue

        divergence = divergence_by_index[i]
        if divergence >= THRESHOLD_DOWNRANK:
            penalty = min(MAX_DOWNRANK_PENALTY, MAX_DOWNRANK_PENALTY * divergence)
            adjusted_score = candidate.raw_blended_score * (1.0 - penalty)
            signals_used = {"consensus_divergence_score": divergence}
            reason = (
                f"consensus_divergence_score={divergence:.3f} >= {THRESHOLD_DOWNRANK} "
                f"({GUARD_VERSION}); query-local downrank penalty={penalty:.3f}"
            )
            downrank_decisions.append(
                build_decision(
                    candidate_memory_id=candidate.memory_id,
                    signals_used=signals_used,
                    action=DOWNRANK,
                    reason=reason,
                    run_id=run_id,
                    episode_id=episode_id,
                    timestamp=timestamp,
                    evidence_refs=evidence_refs_for(candidate.memory_id),
                )
            )
            if divergence >= THRESHOLD_ESCALATE_TO_QUARANTINE:
                total_flags = prior_downrank_count_for(candidate.memory_id) + 1  # +1 = this call
                if total_flags >= MIN_TOTAL_FLAGS_FOR_ESCALATION:
                    # A persistent D2 escalation triggered by D3-observed,
                    # ACCUMULATED evidence (Charter Scope Matrix: "D2 ...
                    # reads trust state to inform D3" and vice versa -- D3
                    # evidence can escalate D2 state). validate_transition()
                    # re-confirms this edge is legal from the candidate's
                    # ACTUAL current state before it is ever attempted, per
                    # Stage 6.3's frozen transition table.
                    validate_transition(candidate.security_state, QUARANTINE)
                    escalation_reason = (
                        f"consensus_divergence_score={divergence:.3f} >= "
                        f"{THRESHOLD_ESCALATE_TO_QUARANTINE} ({GUARD_VERSION}); "
                        f"total_flags={total_flags} >= {MIN_TOTAL_FLAGS_FOR_ESCALATION}; "
                        "escalating to persistent QUARANTINE"
                    )
                    escalation_decisions.append(
                        build_decision(
                            candidate_memory_id=candidate.memory_id,
                            signals_used=signals_used,
                            action=QUARANTINE,
                            reason=escalation_reason,
                            run_id=run_id,
                            episode_id=episode_id,
                            timestamp=timestamp,
                            evidence_refs=evidence_refs_for(candidate.memory_id),
                        )
                    )
        else:
            adjusted_score = candidate.raw_blended_score
            penalty = 0.0

        adjusted.append(
            AdjustedCandidate(
                memory_id=candidate.memory_id,
                eligible=True,
                adjusted_blended_score=adjusted_score,
                consensus_divergence_score=divergence,
                penalty_applied=penalty,
            )
        )

    return RetrievalDefenseResult(
        adjusted_candidates=tuple(adjusted),
        downrank_decisions=tuple(downrank_decisions),
        escalation_decisions=tuple(escalation_decisions),
    )
