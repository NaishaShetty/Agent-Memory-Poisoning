"""Phase 6.9, Item 1 -- the independent D1 (lexical) vs D2 (semantic)
threshold calibration sweep, run on development data only.

CALIBRATION CORPUS IS DISJOINT FROM THE REPORTED-METRICS CORPUS (P0 fix)
--------------------------------------------------------------------------------
This module used to import its dev pools from
`phase6.evaluation.ablations.corpus` -- the SAME module `run_b0_b7.py` draws
its reported B0-B7 metrics from. That meant a threshold chosen here by
inspecting performance on `corpus.py`'s pools was then reported as a B0-B7
metric measured on the identical pools -- calibration circularity (see
`docs/phase6/DEFENSE_COMPOSITION_AND_ABLATION.md`'s Section 3 correction note
and `dev_corpus.py`'s own module docstring for the full account). This module
now draws exclusively from `dev_corpus.py`, whose content is deliberately
disjoint (different literal text, same corpus shape) from `corpus.py`.
`test_calibration_corpus_is_disjoint.py` is the standing regression check
that this separation holds.

Both sweeps use the min-cluster-size-gated divergence function (this stage's
own fix for the diverse-benign-pool false positive -- see calibration.py and
docs/phase6/DEFENSE_COMPOSITION_AND_ABLATION.md), since sweeping the ungated
mechanism's threshold would only be re-discovering the same invalidated,
bug-inflated numbers at every point.
"""

from __future__ import annotations

from phase6.defense.retrieval.dedup_consensus import cluster_by_similarity_matrix, dampened_divergence
from phase6.defense.retrieval.embedding_signals import NEAR_DUPLICATE_THRESHOLD_SEMANTIC, _get_model
from phase6.defense.retrieval.signals import DEDUP_DAMPENING_EXPONENT, NEAR_DUPLICATE_THRESHOLD, _jaccard_similarity, _tokenize
from phase6.evaluation.ablations.dev_corpus import dev_pools_for_sweep

MIN_CLUSTER_SIZE = 2


def _gated_lexical(contents):
    tokenized = [_tokenize(t) for t in contents]
    n = len(tokenized)
    matrix = [[_jaccard_similarity(tokenized[i], tokenized[j]) for j in range(n)] for i in range(n)]
    cluster_of = cluster_by_similarity_matrix(matrix, NEAR_DUPLICATE_THRESHOLD)
    sizes = {}
    for c in cluster_of:
        sizes[c] = sizes.get(c, 0) + 1
    if not any(s >= MIN_CLUSTER_SIZE for s in sizes.values()):
        return [0.0] * n
    return dampened_divergence(matrix, cluster_of, DEDUP_DAMPENING_EXPONENT)


def _gated_semantic(contents):
    model = _get_model()
    embeddings = model.encode(list(contents), normalize_embeddings=True)
    n = len(contents)
    matrix = [[float(embeddings[i] @ embeddings[j]) for j in range(n)] for i in range(n)]
    cluster_of = cluster_by_similarity_matrix(matrix, NEAR_DUPLICATE_THRESHOLD_SEMANTIC)
    sizes = {}
    for c in cluster_of:
        sizes[c] = sizes.get(c, 0) + 1
    if not any(s >= MIN_CLUSTER_SIZE for s in sizes.values()):
        return [0.0] * n
    return dampened_divergence(matrix, cluster_of, DEDUP_DAMPENING_EXPONENT)


def _dev_pools():
    """Development corpus for THIS calibration exercise: the diverse benign
    pool (false-positive check), a uniform-benign paraphrase pool (another
    false-positive check), and both consensus-poison pools (security check).
    Distinct in kind from Stage 6.15's future held-out attack set, AND now
    distinct in literal content from `corpus.py`'s reported-metrics pools
    (P0 fix -- see module docstring above and `dev_corpus.py`)."""
    return dev_pools_for_sweep()


def sweep(divergence_fn, thresholds):
    """For each candidate threshold, compute poison detection rate and false
    positive rate across the dev corpus above."""
    pools = _dev_pools()
    results = []
    for threshold in thresholds:
        n_poison_detected = 0
        n_poison = 0
        n_benign_flagged = 0
        n_benign = 0
        for name, (contents, is_poison) in pools.items():
            scores = divergence_fn(contents)
            for score, poison in zip(scores, is_poison):
                flagged = score >= threshold
                if poison:
                    n_poison += 1
                    n_poison_detected += int(flagged)
                else:
                    n_benign += 1
                    n_benign_flagged += int(flagged)
        results.append(
            {
                "threshold": threshold,
                "poison_detection_rate": n_poison_detected / n_poison if n_poison else 0.0,
                "false_positive_rate": n_benign_flagged / n_benign if n_benign else 0.0,
            }
        )
    return results


if __name__ == "__main__":
    lexical_thresholds = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    semantic_thresholds = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]

    print("=== D1 (lexical, gated) threshold sweep ===")
    for r in sweep(_gated_lexical, lexical_thresholds):
        print(f"  threshold={r['threshold']:.1f}  poison_detect={r['poison_detection_rate']:.1%}  FPR={r['false_positive_rate']:.1%}")

    print("=== D2 (semantic, gated) threshold sweep ===")
    for r in sweep(_gated_semantic, semantic_thresholds):
        print(f"  threshold={r['threshold']:.1f}  poison_detect={r['poison_detection_rate']:.1%}  FPR={r['false_positive_rate']:.1%}")
