"""Phase 6.6 (2026-09-14 semantic-escalation follow-up) -- the similarity-metric-
agnostic core of the dedup-dampened consensus mechanism.

This module exists because `signals.py`'s original lexical (Jaccard) divergence
function and this stage's new semantic (embedding) divergence function need to
share IDENTICAL clustering and dampening logic, differing ONLY in how pairwise
similarity is computed. Extracting that shared logic here, rather than
copy-pasting it into a second module, is what makes the lexical-vs-semantic
comparison in `test_semantic_vs_lexical_consensus.py` a genuinely controlled
experiment (same algorithm, one varied factor) rather than two independently
implemented mechanisms that merely resemble each other.

Nothing here computes similarity itself -- callers supply a precomputed n x n
similarity matrix (a `Sequence[Sequence[float]]`, symmetric, diagonal irrelevant
since self-comparisons are skipped). `signals.py` builds one from Jaccard token
overlap; `embedding_signals.py` builds one from cosine similarity of real sentence
embeddings.
"""

from __future__ import annotations

from typing import Dict, List, Sequence


def cluster_by_similarity_matrix(
    similarity_matrix: Sequence[Sequence[float]], threshold: float
) -> List[int]:
    """Greedy single-link clustering over a precomputed similarity matrix:
    assign each item to the first existing cluster whose REPRESENTATIVE (the
    first item assigned to that cluster) it is similar enough to; otherwise
    start a new cluster. Returns a list mapping each index to its cluster id
    (0-based, in first-seen order).

    Deterministic and order-dependent by design (matches this project's "pure,
    deterministic functions" discipline) -- re-ordering the input pool can
    change clustering, an accepted, documented property of greedy single-link
    clustering, not a bug.
    """
    n = len(similarity_matrix)
    representative_indices: List[int] = []
    cluster_of: List[int] = []
    for i in range(n):
        assigned = None
        for cluster_id, rep_idx in enumerate(representative_indices):
            if similarity_matrix[i][rep_idx] >= threshold:
                assigned = cluster_id
                break
        if assigned is None:
            assigned = len(representative_indices)
            representative_indices.append(i)
        cluster_of.append(assigned)
    return cluster_of


def has_real_majority_cluster(cluster_of: Sequence[int], min_cluster_size_to_flag: int) -> bool:
    """True iff at least one cluster has size >= `min_cluster_size_to_flag` --
    i.e., a real majority/consensus actually exists in the pool for anything to
    be divergent FROM. If every candidate is its own singleton cluster (a
    fully topically-diverse pool, the common ordinary case), there is no real
    majority, and "divergence from the rest of the pool" is not a meaningful
    concept -- see `dampened_divergence()`'s own docstring update below and
    `docs/phase6/DEFENSE_COMPOSITION_AND_ABLATION.md`'s "Major Finding" for the
    real, measured 100% false-positive rate this gate exists to close.
    """
    cluster_sizes: Dict[int, int] = {}
    for cluster_id in cluster_of:
        cluster_sizes[cluster_id] = cluster_sizes.get(cluster_id, 0) + 1
    return any(size >= min_cluster_size_to_flag for size in cluster_sizes.values())


def dampened_divergence(
    similarity_matrix: Sequence[Sequence[float]],
    cluster_of: Sequence[int],
    dampening_exponent: float,
) -> List[float]:
    """For each index i, compute `1 - weighted_mean_similarity(i, rest of pool)`,
    where each other index j's contribution is weighted by
    `1 / cluster_size(cluster_of[j]) ** dampening_exponent`.

    `dampening_exponent=0.0` recovers plain, undamped pairwise-average
    divergence exactly (every weight is 1.0). A pool of size 0 or 1 has no
    "rest of pool" to compare against -- every index gets divergence 0.0.
    """
    n = len(similarity_matrix)
    cluster_sizes: Dict[int, int] = {}
    for cluster_id in cluster_of:
        cluster_sizes[cluster_id] = cluster_sizes.get(cluster_id, 0) + 1

    results: List[float] = []
    for i in range(n):
        if n <= 1:
            results.append(0.0)
            continue
        weighted_similarity_sum = 0.0
        weight_sum = 0.0
        for j in range(n):
            if j == i:
                continue
            weight = 1.0 / (cluster_sizes[cluster_of[j]] ** dampening_exponent)
            weighted_similarity_sum += weight * similarity_matrix[i][j]
            weight_sum += weight
        results.append(1.0 - weighted_similarity_sum / weight_sum)
    return results
