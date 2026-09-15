"""Phase 6.9, Item 1 -- independent D1/D2 threshold calibration, PLUS a real,
unplanned discovery this exercise surfaced: the shipped Stage 6.6 retrieval
consensus mechanism produces a 100% false-positive rate on a completely
ordinary, topically-diverse benign retrieval pool (three unrelated but
individually benign facts) -- see `docs/phase6/DEFENSE_COMPOSITION_AND_
ABLATION.md`'s "Major Finding" section for the full account. This module
implements and tests the fix candidate (a minimum-cluster-size gate) as a
NEW, EXPERIMENTAL variant -- it does NOT modify `consensus_guard.py` or
`signals.py`'s shipped Stage 6.6 defaults, per explicit instruction to accept
6.6 as documented and not silently change it. This is a Stage 6.9
recommendation, pending explicit authorization to adopt it as the new default.
"""

from __future__ import annotations

from typing import Dict, Sequence, Tuple

from phase6.defense.retrieval.dedup_consensus import cluster_by_similarity_matrix, dampened_divergence
from phase6.defense.retrieval.signals import DEDUP_DAMPENING_EXPONENT, NEAR_DUPLICATE_THRESHOLD, _jaccard_similarity, _tokenize


def pool_consensus_divergence_signals_with_min_cluster_gate(
    contents: Sequence[str],
    *,
    near_duplicate_threshold: float = NEAR_DUPLICATE_THRESHOLD,
    dampening_exponent: float = DEDUP_DAMPENING_EXPONENT,
    min_cluster_size_to_flag: int = 2,
) -> Tuple[Dict[str, float], ...]:
    """EXPERIMENTAL variant (Stage 6.9, not shipped as a Stage 6.6 default):
    identical to `signals.pool_consensus_divergence_signals`, except a
    candidate is only assigned a nonzero divergence score if the POOL
    contains at least one cluster of size >= `min_cluster_size_to_flag` --
    i.e., a real majority/consensus actually exists to be divergent FROM. If
    every candidate in the pool is its own singleton cluster (no majority
    exists at all), every candidate's score is forced to 0.0, rather than the
    meaningless-but-nonzero values the ungated mechanism produces in that
    regime (see module docstring)."""
    tokenized = [_tokenize(text) for text in contents]
    n = len(tokenized)
    similarity_matrix = [[_jaccard_similarity(tokenized[i], tokenized[j]) for j in range(n)] for i in range(n)]
    cluster_of = cluster_by_similarity_matrix(similarity_matrix, near_duplicate_threshold)

    cluster_sizes: Dict[int, int] = {}
    for c in cluster_of:
        cluster_sizes[c] = cluster_sizes.get(c, 0) + 1
    a_real_majority_exists = any(size >= min_cluster_size_to_flag for size in cluster_sizes.values())

    if not a_real_majority_exists:
        return tuple({"consensus_divergence_score": 0.0} for _ in range(n))

    divergences = dampened_divergence(similarity_matrix, cluster_of, dampening_exponent)
    return tuple({"consensus_divergence_score": d} for d in divergences)
