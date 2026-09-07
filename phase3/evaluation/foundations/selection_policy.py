"""Phase 3.3-DATASET -- the real, threshold-based selection policy, per
`PHASE3_SELECTION_AND_CREATION_POLICY_DESIGN_REVIEW.md` sections 2.2/2.3 (decided:
threshold-based selection over a benchmark-owned cosine-similarity score, retrieval
pool size N=20 fixed benchmark-wide).

NOT WIRED INTO ANY LIVE CAMPAIGN PATH
--------------------------------------------------------------------------------
This module is a new, additive, OPT-IN capability. `runner.py::select_from_retrieved()`
-- the existing provisional identity-slice policy every currently-passing test and
every already-executed real campaign (including the 120x2 dataset campaign this
session ran) depends on -- is NOT modified and NOT replaced by anything here. Wiring
this policy into `campaign_formal_runner.py`'s live conditions (which would require
re-running every affected campaign under a new mechanism) is a separate, later
decision this module does not make on its own.

THRESHOLD CALIBRATION
--------------------------------------------------------------------------------
`calibrate_threshold_from_gold_evidence()` implements the exact empirical procedure
recommended when the design review's four decisions were reviewed: compute cosine
similarity between each task's question and its own real gold-evidence content, then
pick the threshold that keeps ~95% of real gold evidence above it -- a data-driven
number, not a literature default and not a value picked without justification.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Mapping, Sequence, Tuple

from phase3.evaluation.foundations.similarity import ScoredCandidate, score_candidates

RETRIEVAL_POOL_SIZE_N = 20  # fixed, benchmark-wide -- design review section 2.3
DEFAULT_MAX_SELECTED_K = 5  # safety cap, matches the existing top_k=5 used throughout
GOLD_EVIDENCE_COVERAGE_TARGET = 0.95  # design review section 2.2's calibration target

# Real, empirically calibrated threshold -- computed by
# calibrate_threshold_from_gold_evidence() against all 125 real (question, gold
# evidence) pairs from the frozen 120-task LoCoMo formal sample (seed 33005), at the
# default 95% coverage target, using the real sentence-transformers/all-MiniLM-L6-v2
# model (not a fake/estimated score). Raw scores and the full calibration result are
# preserved, uncompressed, at
# phase3/experiments/results/canonical_store/selection_threshold_calibration.json --
# this constant is never the only record of how it was derived. Real score
# distribution observed: min=0.1072, p5=0.2599 (~= this threshold), median=0.4891,
# max=0.8351 -- i.e. the calibrated threshold sits just above the 5th percentile of
# real gold-evidence similarity, exactly matching the 95%-coverage definition.
CALIBRATED_THRESHOLD_LOCOMO = 0.2632820487022401


@dataclass(frozen=True)
class SelectionResult:
    selected: Tuple[ScoredCandidate, ...]
    rejected: Tuple[ScoredCandidate, ...]
    threshold: float


def select_by_threshold(
    query: str,
    candidates: Sequence[Tuple[str, str]],
    threshold: float,
    max_k: int = DEFAULT_MAX_SELECTED_K,
) -> SelectionResult:
    """Score every `(memory_id, content)` candidate against `query`, keep everything
    scoring >= `threshold`, capped at the top `max_k` by score (never a fixed-k
    guarantee -- a pool with fewer than `max_k` candidates above threshold selects
    fewer than `max_k`, and a pool with NONE above threshold selects zero, per the
    design review section 2.2's explicit rejection of fixed-k). Every candidate not
    selected is returned in `rejected`, in the SAME scored form, so a caller can emit a
    real `rejected` CanonicalEvent for each with its own real score attached.
    """
    scored = score_candidates(query, candidates)
    scored_sorted = sorted(scored, key=lambda c: c.score, reverse=True)

    selected: List[ScoredCandidate] = []
    rejected: List[ScoredCandidate] = []
    for candidate in scored_sorted:
        if candidate.score >= threshold and len(selected) < max_k:
            selected.append(candidate)
        else:
            rejected.append(candidate)

    return SelectionResult(selected=tuple(selected), rejected=tuple(rejected), threshold=threshold)


def calibrate_threshold_from_gold_evidence(
    query_evidence_pairs: Sequence[Tuple[str, str]],
    coverage_target: float = GOLD_EVIDENCE_COVERAGE_TARGET,
) -> Mapping[str, object]:
    """Empirical threshold calibration: `query_evidence_pairs` is
    `[(task_question, gold_evidence_content), ...]` -- ONE real (question, gold
    evidence) pair per real task (a task with multiple gold evidence ids contributes
    multiple pairs). Computes the cosine similarity for every pair, then returns the
    threshold at the `(1 - coverage_target)` percentile of that real score
    distribution -- i.e. the highest threshold that still keeps `coverage_target`
    (default 95%) of real gold evidence scoring at or above it.

    Returns `{"threshold": float, "n_pairs": int, "coverage_target": float,
    "scores": [float, ...]}` -- the raw scores are included, never discarded, so the
    calibration is independently re-checkable against the real numbers that produced
    it, not just the single resulting threshold.
    """
    import numpy as np

    if not query_evidence_pairs:
        raise ValueError("query_evidence_pairs must be non-empty to calibrate a threshold.")

    scores: List[float] = []
    for question, evidence_content in query_evidence_pairs:
        scored = score_candidates(question, [("evidence", evidence_content)])
        scores.append(scored[0].score)

    percentile = (1.0 - coverage_target) * 100.0
    threshold = float(np.percentile(scores, percentile))

    return {
        "threshold": threshold,
        "n_pairs": len(scores),
        "coverage_target": coverage_target,
        "scores": scores,
    }


__all__ = [
    "RETRIEVAL_POOL_SIZE_N",
    "DEFAULT_MAX_SELECTED_K",
    "GOLD_EVIDENCE_COVERAGE_TARGET",
    "CALIBRATED_THRESHOLD_LOCOMO",
    "SelectionResult",
    "select_by_threshold",
    "calibrate_threshold_from_gold_evidence",
]
