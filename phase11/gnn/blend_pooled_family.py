"""Phase 11 -- validating the LOFO-discovered blend fix
(`phase11/gnn/lofo_blend_infold_threshold.py`) under the PRODUCTION training
regime: trained on ALL of `all_dev_pools()` (no family excluded), exactly
the regime `run_gnn_feasibility_study()` (Baseline A) and
`run_b10.py::_train_gnn_and_score_held_out()` already use. This is a
prerequisite check before wiring the blend into `run_b10.py` -- the blend
was only ever measured under LOFO (family-excluded training) before now;
whether it also helps (or at least does not hurt) the standard
pooled-family regime was unverified.

SAME BLEND, SAME PROTOCOL, DIFFERENT TRAINING POPULATION
--------------------------------------------------------------------------------
`w * z(fitted) + (1-w) * z(raw_sum)`, z-scored on the training set, `w`
fixed at 0.25 (the single best value found in the LOFO sweep -- not
re-swept here against this new evaluation population, since re-sweeping a
hyperparameter against a held-out metric after seeing it would be exactly
the calibration circularity this project's own discipline forbids;
`w ∈ {0.0, 0.5, 0.75, 1.0}` are also reported alongside 0.25 for
transparency, not to pick a new "best" from this run).
"""

from __future__ import annotations

import statistics
from typing import List, Sequence

import torch

from phase11.data import split
from phase11.gnn.features import GNN_FEATURE_KEYS, pools_node_features_gnn
from phase11.gnn.self_supervised import auroc as _auroc
from phase11.gnn.train import build_dataset as _build_dataset_base, train_model, TARGET_TRAIN_FALSE_POSITIVE_RATE, _threshold_for_target_fpr, SEED


def build_dataset(pools):
    """GNN-only 10-feature vocabulary (includes `semantic_consensus_divergence_score`)
    -- see `phase11/gnn/features.py`'s own docstring for why this is kept
    separate from the base `build_dataset()`'s default 9-feature behavior."""
    return _build_dataset_base(pools, feature_keys=GNN_FEATURE_KEYS, feature_fn=pools_node_features_gnn)

BLEND_WEIGHTS = (0.0, 0.25, 0.5, 0.75, 1.0)
WEIGHT_DECAY = 0.005


def _raw_sum(features: torch.Tensor) -> torch.Tensor:
    return features.sum(dim=1)


def _zscore(values: torch.Tensor, mean: float, std: float) -> torch.Tensor:
    if std == 0.0:
        return torch.zeros_like(values)
    return (values - mean) / std


def _evaluate(scores, labels, threshold) -> dict:
    poison = [s for s, y in zip(scores, labels) if y == 1.0]
    benign = [s for s, y in zip(scores, labels) if y == 0.0]
    detected = sum(1 for s in poison if s >= threshold)
    flagged = sum(1 for s in benign if s >= threshold)
    return {
        "n_poison": len(poison), "n_benign": len(benign),
        "detection_rate": detected / len(poison) if poison else float("nan"),
        "false_positive_rate": flagged / len(benign) if benign else float("nan"),
        "auroc": _auroc(torch.tensor(list(scores)), torch.tensor(list(labels))),
    }


def blended_score(model, ds, *, w: float, fit_mean, fit_std, raw_mean, raw_std) -> List[float]:
    fitted = model.predict_proba(ds.features, ds.mean_adj)
    raw = _raw_sum(ds.features)
    z_fit = _zscore(fitted, fit_mean, fit_std)
    z_raw = _zscore(raw, raw_mean, raw_std)
    return (w * z_fit + (1 - w) * z_raw).tolist()


def run_pooled_family(*, seeds: Sequence[int] = (SEED,), weight_decay: float = WEIGHT_DECAY):
    train_ds = build_dataset(split.all_dev_pools())
    held_out_ds = build_dataset(split.held_out_pools())

    results = {w: [] for w in BLEND_WEIGHTS}
    for seed in seeds:
        model = train_model(train_ds, seed=seed, weight_decay=weight_decay)

        train_fitted = model.predict_proba(train_ds.features, train_ds.mean_adj)
        train_raw = _raw_sum(train_ds.features)
        fit_mean, fit_std = train_fitted.mean().item(), train_fitted.std(unbiased=False).item()
        raw_mean, raw_std = train_raw.mean().item(), train_raw.std(unbiased=False).item()
        train_labels = train_ds.labels.tolist()

        for w in BLEND_WEIGHTS:
            train_blend = blended_score(model, train_ds, w=w, fit_mean=fit_mean, fit_std=fit_std, raw_mean=raw_mean, raw_std=raw_std)
            threshold = _threshold_for_target_fpr(train_blend, train_labels, TARGET_TRAIN_FALSE_POSITIVE_RATE)

            held_out_blend = blended_score(model, held_out_ds, w=w, fit_mean=fit_mean, fit_std=fit_std, raw_mean=raw_mean, raw_std=raw_std)
            result = _evaluate(held_out_blend, held_out_ds.labels.tolist(), threshold)
            result.update(seed=seed, w=w)
            results[w].append(result)
    return results


def summarize(results: List[dict]) -> dict:
    detections = [r["detection_rate"] for r in results]
    fprs = [r["false_positive_rate"] for r in results]
    aurocs = [r["auroc"] for r in results]
    return {
        "w": results[0]["w"], "n_poison": results[0]["n_poison"], "n_benign": results[0]["n_benign"],
        "detection_rate_mean": statistics.mean(detections),
        "false_positive_rate_mean": statistics.mean(fprs),
        "auroc_mean": statistics.mean(aurocs), "auroc_min": min(aurocs), "auroc_max": max(aurocs),
    }


if __name__ == "__main__":
    results = run_pooled_family(seeds=range(11, 21))
    print("=== Pooled-family (Baseline-A-comparable) blend result, weight_decay=0.005 ===")
    for w in BLEND_WEIGHTS:
        s = summarize(results[w])
        print(f"w={w:.2f}  auroc_mean={s['auroc_mean']:.4f} [{s['auroc_min']:.4f}, {s['auroc_max']:.4f}]  "
              f"detection_mean={s['detection_rate_mean']:.4f}  fpr_mean={s['false_positive_rate_mean']:.4f}  "
              f"n_poison={s['n_poison']} n_benign={s['n_benign']}")
