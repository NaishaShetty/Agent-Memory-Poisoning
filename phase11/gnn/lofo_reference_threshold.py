"""Phase 11 -- second, real attempt at fixing the threshold-selection
protocol, after the first attempt (median/MAD robust statistic,
`phase11/gnn/lofo_robust_threshold.py`) was measured and found to fail for
the OPPOSITE reason it was built to fix.

WHAT THE FIRST ATTEMPT ACTUALLY MEASURED (real, disclosed, not hidden)
--------------------------------------------------------------------------------
`median(benign) + k*MAD(benign)`, swept over k in [1, 5] and weight_decay
in {0.0, 0.005}, was NOT an improvement: macro FPR rose to 44%-76% (worse
than the order-statistic rule's own 24%-45%), while macro AUROC was
unchanged (median/MAD only changes the THRESHOLD, never the underlying
score ranking, so AUROC -- a threshold-free metric -- could not and did
not move). Root cause, diagnosed directly: at 8-11 training-benign
examples, MOST scores cluster tightly near zero and only 1-2 real
near-miss examples (`DEV-PROPAGATION-BENIGN-TRUSTED-PARENT`,
`DEV-NEARDUP-TRUTH`) sit far above them. Median and MAD are correctly
robust to those 1-2 outliers -- but that robustness comes at the cost of
UNDERESTIMATING the benign score distribution's true spread, because MAD
is computed from a sample where the bulk is artificially tight. The
resulting threshold sits too low relative to the real, more varied
44-node held-out benign population, and the failure mode flips from
"threshold too high, near-zero detection" to "threshold too low, 44%-76%
of real benign examples flagged." This is reported as a genuine, disclosed
negative result for `lofo_robust_threshold.py`'s own approach, not deleted
or silently abandoned.

THE ROOT CAUSE, RESTATED PRECISELY
--------------------------------------------------------------------------------
Neither attempt (order statistic, median/MAD) actually fixes anything --
both are different ways of estimating a quantile/scale from the SAME
8-11 real training-benign examples. That is a real, hard sample-size
floor: no re-weighting of 8-11 numbers can reliably predict the spread of
a 44-example population if the smaller sample under-represents it.

THE SECOND, REAL ATTEMPT
--------------------------------------------------------------------------------
Score a MUCH LARGER, already-real, already-legitimate, already-disjoint
real benign reference -- `phase11/data/real_corpus.py::real_benign_scenarios()`
(135 real LoCoMo turns, tasks 1-9, already proven disjoint from
`held_out_pools()` by `test_gnn_gln_corpus_is_disjoint.py`) -- with the
SAME fold-trained model, and pick the target-FPR order statistic from
THAT much larger benign score population instead of the 8-11 tiny
training-benign scores. This is training-side only (the reference is
never poison-labeled, never used to fit the model's WEIGHTS, only to
estimate the threshold after training) -- no new leakage path, and no
change to `held_out_pools()` or the excluded family's own data.

A REAL, DISCLOSED RISK BEFORE RUNNING THIS, NOT AFTER
--------------------------------------------------------------------------------
`real_benign_scenarios()`'s 9 pools (15-member real LoCoMo cliques) have a
DIFFERENT graph topology than the tiny hand-authored training pools
(3-9 members) -- exactly the cross-corpus pool-size-convention mismatch
`docs/phase11/PHASE11_X_OPTION2_EXPANDED_FEATURES_REPORT.md` Section 15
already diagnosed for a different feature set. `consensus_divergence_score`
(the one sanctioned feature that is pool-composition-sensitive) could
behave differently on this reference than on the fold's own training
pools -- disclosed here BEFORE the result is seen, exactly so it cannot be
quietly used to explain away a bad result after the fact.
"""

from __future__ import annotations

import statistics
from typing import Dict, List, Sequence

import torch

from phase11.data import split
from phase11.data.real_corpus import real_benign_scenarios
from phase11.gnn.lofo import SEEDS, _discover_families, filter_pools_excluding_family, family_map_for_pools
from phase11.gnn.self_supervised import auroc as _auroc
from phase11.gnn.train import build_dataset, train_model, TARGET_TRAIN_FALSE_POSITIVE_RATE, _threshold_for_target_fpr


def _evaluate(scores: Sequence[float], labels: Sequence[float], threshold: float) -> dict:
    poison = [s for s, y in zip(scores, labels) if y == 1.0]
    benign = [s for s, y in zip(scores, labels) if y == 0.0]
    detected = sum(1 for s in poison if s >= threshold)
    flagged = sum(1 for s in benign if s >= threshold)
    return {
        "n_poison": len(poison), "n_benign": len(benign),
        "detection_rate": detected / len(poison) if poison else float("nan"),
        "false_positive_rate": flagged / len(benign) if benign else float("nan"),
        "auroc": _auroc(torch.tensor(list(scores)), torch.tensor(list(labels))),
        "threshold": threshold,
    }


def run_lofo_fold_reference_threshold(
    family: str, *, weight_decay: float, target_fpr: float = TARGET_TRAIN_FALSE_POSITIVE_RATE,
    seeds: Sequence[int] = SEEDS,
) -> List[dict]:
    train_pools = filter_pools_excluding_family(split.all_dev_pools(), family)
    train_ds = build_dataset(train_pools)

    # The larger real benign reference -- training-side only, never used to
    # fit model weights, only scored post-hoc for threshold calibration.
    reference_ds = build_dataset(real_benign_scenarios())

    held_out_pools = split.held_out_pools()
    held_out_ds = build_dataset(held_out_pools)
    held_out_family_map = family_map_for_pools(held_out_pools)

    results = []
    for seed in seeds:
        model = train_model(train_ds, seed=seed, weight_decay=weight_decay)

        reference_scores = model.predict_proba(reference_ds.features, reference_ds.mean_adj).tolist()
        reference_labels = reference_ds.labels.tolist()  # all 0.0 -- real_benign_scenarios() is benign-only
        threshold = _threshold_for_target_fpr(reference_scores, reference_labels, target_fpr)

        held_out_scores = model.predict_proba(held_out_ds.features, held_out_ds.mean_adj).tolist()
        held_out_labels = held_out_ds.labels.tolist()

        family_scores, benign_scores = [], []
        for nid, score, label in zip(held_out_ds.node_ids, held_out_scores, held_out_labels):
            if label == 1.0 and held_out_family_map.get(nid) == family:
                family_scores.append(score)
            elif label == 0.0:
                benign_scores.append(score)

        result = _evaluate(family_scores + benign_scores, [1.0] * len(family_scores) + [0.0] * len(benign_scores), threshold)
        result.update(family=family, seed=seed, weight_decay=weight_decay,
                       n_reference_benign=len(reference_scores))
        results.append(result)
    return results


def summarize(results: List[dict]) -> dict:
    detections = [r["detection_rate"] for r in results]
    fprs = [r["false_positive_rate"] for r in results]
    aurocs = [r["auroc"] for r in results]
    return {
        "family": results[0]["family"], "weight_decay": results[0]["weight_decay"],
        "n_reference_benign": results[0]["n_reference_benign"],
        "n_poison": results[0]["n_poison"], "n_benign": results[0]["n_benign"],
        "detection_rate_mean": statistics.mean(detections),
        "false_positive_rate_mean": statistics.mean(fprs),
        "auroc_mean": statistics.mean(aurocs), "auroc_min": min(aurocs), "auroc_max": max(aurocs),
    }


def run_all_families(*, weight_decay: float, seeds: Sequence[int] = SEEDS) -> Dict[str, dict]:
    families = _discover_families(split.all_dev_pools())
    return {
        family: summarize(run_lofo_fold_reference_threshold(family, weight_decay=weight_decay, seeds=seeds))
        for family in families
    }


def macro_summary(per_family: Dict[str, dict]) -> dict:
    return {
        "macro_auroc": statistics.mean(s["auroc_mean"] for s in per_family.values()),
        "macro_detection_rate": statistics.mean(s["detection_rate_mean"] for s in per_family.values()),
        "macro_false_positive_rate": statistics.mean(s["false_positive_rate_mean"] for s in per_family.values()),
    }


if __name__ == "__main__":
    import json

    for wd in (0.0, 0.005):
        print(f"\n############ weight_decay={wd} ############")
        per_family = run_all_families(weight_decay=wd)
        for family, summary_result in per_family.items():
            print(f"  {family}: n_ref_benign={summary_result['n_reference_benign']} "
                  f"auroc_mean={summary_result['auroc_mean']:.4f} "
                  f"detection_mean={summary_result['detection_rate_mean']:.4f} "
                  f"fpr_mean={summary_result['false_positive_rate_mean']:.4f}")
        print("Macro:", json.dumps(macro_summary(per_family), indent=2))
