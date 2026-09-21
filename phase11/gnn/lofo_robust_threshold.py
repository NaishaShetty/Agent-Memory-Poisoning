"""SUPERSEDED (2026-09-20) -- kept for the real, disclosed negative result
it produced, per this project's own "preserve negative findings, don't
delete them" discipline, not as a recommended approach. The median/MAD
threshold below was measured (`docs/phase11/PHASE11_LOFO_THRESHOLD_FIX_REPORT.md`
Attempt 1) to make macro FPR WORSE (44%-76%, vs. the order-statistic
baseline's 24%-45%) -- it correctly resists the 1-2 extreme benign
training examples, but that same resistance underestimates the true
benign score spread. The REAL, adopted fix is
`phase11/gnn/lofo_blend_infold_threshold.py` (blend the fitted score with
the untrained raw-feature-sum score, threshold on the fold's own real
training-benign set) -- see `docs/phase11/PHASE11_LOFO_FPR_AND_FARMA_FIX_REPORT.md`
for the real, measured, adopted result, now wired into `run_b10.py`
(`docs/phase11/PHASE11_BLEND_WIRING_REPORT.md`).

--- Original module docstring below, unmodified ---

Phase 11 -- fixing the threshold-selection protocol itself, per the
user's own direct request ("fix the threshold-selection protocol") and the
root cause diagnosed in `PHASE11_LOFO_WEIGHT_DECAY_SWEEP_REPORT.md`.

THE DIAGNOSED ROOT CAUSE, CONFIRMED DIRECTLY (NOT ASSUMED)
--------------------------------------------------------------------------------
`_threshold_for_target_fpr()` (`phase11/gnn/train.py`) picks
`benign_scores[allowed_false_positives]` from the SORTED training-benign
scores -- an order statistic. At this project's real training scale
(8-11 benign examples per LOFO fold), `int(0.10 * n)` is 0 or 1, so the
threshold is either the single highest or second-highest benign training
score, verbatim. Direct inspection (this investigation's own diagnostic,
not assumed) found the SAME real scenario --
`DEV-PROPAGATION-BENIGN-TRUSTED-PARENT`, a real, structurally-hard
near-miss (it carries a real `TRUSTED`-ancestor lineage reference, giving
it a nonzero `lineage_taint_score`-adjacent feature profile even though it
is genuinely benign) -- lands as the 2nd-highest benign score in
essentially every fold, regardless of which family is excluded. Because
this ONE example is never poison (so never removed by family filtering),
it structurally dominates the order-statistic threshold across every fold,
dragging the cutoff above every FARMA/Sleeper held-out poison score even
when the underlying ranking (AUROC) is good.

THE FIX -- A ROBUST-STATISTICS THRESHOLD, NOT A SPECIAL CASE FOR THIS EXAMPLE
--------------------------------------------------------------------------------
Excluding or down-weighting `DEV-PROPAGATION-BENIGN-TRUSTED-PARENT` by name
would be tuning the protocol to this one known example -- exactly the kind
of after-the-fact cherry-picking this project's own discipline forbids.
Instead, `threshold_via_median_mad()` below replaces the fragile order
statistic with `median(benign_scores) + k * MAD(benign_scores)` --
median and median-absolute-deviation are both classical ROBUST statistics
(bounded breakdown point: up to ~50% of the sample can be extreme outliers
before either one moves substantially), so a single hard near-miss no
longer dominates the threshold, without needing to know which example it
is or removing it. `k` is swept over a small, fixed, pre-registered set
(1.0-5.0, standard robust-statistics multiplier range) BEFORE any result
is seen, exactly as `WEIGHT_DECAY_VALUES` was pre-registered in the prior
sweep.

ADDITIVE, NOT A REPLACEMENT
--------------------------------------------------------------------------------
`_threshold_for_target_fpr()` itself is untouched -- `run_gnn_feasibility_study()`
(Baseline A) and every existing test still use it exactly as before. This
module adds a second, clearly-labeled threshold function and its own fold
runner, evaluated against the SAME leakage-safe LOFO harness already
audited (`PHASE11_LOFO_AUDIT.md`) and reused, not duplicated with new
leakage risk: `filter_pools_excluding_family`/`family_map_for_pools` are
imported from `phase11/gnn/lofo.py` verbatim.
"""

from __future__ import annotations

import statistics
from typing import Dict, List, Sequence, Tuple

import torch

from phase11.data import split
from phase11.gnn.lofo import SEEDS, _discover_families, filter_pools_excluding_family, family_map_for_pools
from phase11.gnn.self_supervised import auroc as _auroc
from phase11.gnn.train import build_dataset, train_model

K_VALUES = (1.0, 2.0, 3.0, 4.0, 5.0)  # standard robust-statistics multiplier range, fixed before any result seen


def threshold_via_median_mad(scores: Sequence[float], labels: Sequence[float], k: float) -> float:
    """`median(benign) + k * MAD(benign)` -- robust to a single extreme
    benign score, unlike an order-statistic pick at tiny n. Falls back to
    the median itself if MAD is exactly 0 (a real, disclosed edge case: no
    spread in the benign training scores at all -- any positive k would
    otherwise threshold at exactly the median, flagging half the training
    benign set, which is worse than just returning the median as a
    minimal, honest cutoff)."""
    benign = [s for s, y in zip(scores, labels) if y == 0.0]
    if not benign:
        return 0.5
    med = statistics.median(benign)
    mad = statistics.median(abs(b - med) for b in benign)
    if mad == 0.0:
        return med
    return med + k * mad


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


def run_lofo_fold_robust(family: str, *, k: float, weight_decay: float, seeds: Sequence[int] = SEEDS) -> List[dict]:
    train_pools = filter_pools_excluding_family(split.all_dev_pools(), family)
    train_ds = build_dataset(train_pools)

    held_out_pools = split.held_out_pools()
    held_out_ds = build_dataset(held_out_pools)
    held_out_family_map = family_map_for_pools(held_out_pools)

    results = []
    for seed in seeds:
        model = train_model(train_ds, seed=seed, weight_decay=weight_decay)
        train_scores = model.predict_proba(train_ds.features, train_ds.mean_adj).tolist()
        threshold = threshold_via_median_mad(train_scores, train_ds.labels.tolist(), k)

        held_out_scores = model.predict_proba(held_out_ds.features, held_out_ds.mean_adj).tolist()
        held_out_labels = held_out_ds.labels.tolist()

        family_scores, benign_scores = [], []
        for nid, score, label in zip(held_out_ds.node_ids, held_out_scores, held_out_labels):
            if label == 1.0 and held_out_family_map.get(nid) == family:
                family_scores.append(score)
            elif label == 0.0:
                benign_scores.append(score)

        result = _evaluate(family_scores + benign_scores, [1.0] * len(family_scores) + [0.0] * len(benign_scores), threshold)
        result.update(family=family, seed=seed, k=k, weight_decay=weight_decay)
        results.append(result)
    return results


def summarize(results: List[dict]) -> dict:
    detections = [r["detection_rate"] for r in results]
    fprs = [r["false_positive_rate"] for r in results]
    aurocs = [r["auroc"] for r in results]
    return {
        "family": results[0]["family"], "k": results[0]["k"], "weight_decay": results[0]["weight_decay"],
        "n_poison": results[0]["n_poison"], "n_benign": results[0]["n_benign"],
        "detection_rate_mean": statistics.mean(detections),
        "false_positive_rate_mean": statistics.mean(fprs),
        "auroc_mean": statistics.mean(aurocs), "auroc_min": min(aurocs), "auroc_max": max(aurocs),
    }


def run_k_sweep(*, weight_decay: float, k_values: Sequence[float] = K_VALUES, seeds: Sequence[int] = SEEDS) -> Dict[float, Dict[str, dict]]:
    families = _discover_families(split.all_dev_pools())
    out: Dict[float, Dict[str, dict]] = {}
    for k in k_values:
        out[k] = {}
        for family in families:
            results = run_lofo_fold_robust(family, k=k, weight_decay=weight_decay, seeds=seeds)
            out[k][family] = summarize(results)
    return out


def macro_summary(sweep_results: Dict[float, Dict[str, dict]]) -> Dict[float, dict]:
    out = {}
    for k, per_family in sweep_results.items():
        out[k] = {
            "macro_auroc": statistics.mean(s["auroc_mean"] for s in per_family.values()),
            "macro_detection_rate": statistics.mean(s["detection_rate_mean"] for s in per_family.values()),
            "macro_false_positive_rate": statistics.mean(s["false_positive_rate_mean"] for s in per_family.values()),
        }
    return out


if __name__ == "__main__":
    import json

    for wd in (0.0, 0.005):
        print(f"\n############ weight_decay={wd} ############")
        sweep = run_k_sweep(weight_decay=wd)
        for k, per_family in sweep.items():
            print(f"\n=== k={k} ===")
            for family, summary_result in per_family.items():
                print(f"  {family}: n={summary_result['n_poison']} "
                      f"auroc_mean={summary_result['auroc_mean']:.4f} "
                      f"detection_mean={summary_result['detection_rate_mean']:.4f} "
                      f"fpr_mean={summary_result['false_positive_rate_mean']:.4f}")
        print("\nMacro summary by k:")
        print(json.dumps(macro_summary(sweep), indent=2))
