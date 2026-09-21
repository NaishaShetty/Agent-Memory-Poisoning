"""Phase 11 -- the complete, multi-seed LOFO evaluation using the combined
untrained score (`combined_untrained_score.py`: MAX(z(raw_sum),
z(grouped_raw))) blended with the fitted GNN score, at `w_fit=0.25` (the
same blend weight already established elsewhere in this LOFO track).
"""

from __future__ import annotations

import statistics
from typing import Dict, List, Sequence

import torch

from phase11.data import split
from phase11.gnn.combined_untrained_score import blended_score, combined_untrained_score, grouped_raw_tensor
from phase11.gnn.features import GNN_FEATURE_KEYS, pools_node_features_gnn
from phase11.gnn.lofo import SEEDS, _discover_families, family_map_for_pools, filter_pools_excluding_family
from phase11.gnn.self_supervised import auroc as _auroc
from phase11.gnn.train import build_dataset as _build_dataset_base, train_model, TARGET_TRAIN_FALSE_POSITIVE_RATE, _threshold_for_target_fpr

W_FIT = 0.25
WEIGHT_DECAY = 0.005


def build_dataset(pools):
    return _build_dataset_base(pools, feature_keys=GNN_FEATURE_KEYS, feature_fn=pools_node_features_gnn)


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


def run_fold(family: str, *, seeds: Sequence[int] = SEEDS, w_fit: float = W_FIT) -> List[dict]:
    train_pools = filter_pools_excluding_family(split.all_dev_pools(), family)
    train_ds = build_dataset(train_pools)

    held_out_pools = split.held_out_pools()
    held_out_ds = build_dataset(held_out_pools)
    held_out_family_map = family_map_for_pools(held_out_pools)

    train_grouped = grouped_raw_tensor(train_pools, train_ds.node_ids)
    held_grouped = grouped_raw_tensor(held_out_pools, held_out_ds.node_ids)
    train_untrained = combined_untrained_score(train_ds.features, train_grouped, train_ds.features, train_grouped)
    held_untrained = combined_untrained_score(train_ds.features, train_grouped, held_out_ds.features, held_grouped)

    results = []
    for seed in seeds:
        model = train_model(train_ds, seed=seed, weight_decay=WEIGHT_DECAY)
        train_fitted = model.predict_proba(train_ds.features, train_ds.mean_adj)
        fit_mean, fit_std = train_fitted.mean().item(), train_fitted.std(unbiased=False).item()

        train_blend = blended_score(train_fitted, train_untrained, w_fit=w_fit, fit_mean=fit_mean, fit_std=fit_std).tolist()
        threshold = _threshold_for_target_fpr(train_blend, train_ds.labels.tolist(), TARGET_TRAIN_FALSE_POSITIVE_RATE)

        held_fitted = model.predict_proba(held_out_ds.features, held_out_ds.mean_adj)
        held_blend = blended_score(held_fitted, held_untrained, w_fit=w_fit, fit_mean=fit_mean, fit_std=fit_std).tolist()
        held_labels = held_out_ds.labels.tolist()

        family_scores, benign_scores = [], []
        for nid, score, label in zip(held_out_ds.node_ids, held_blend, held_labels):
            if label == 1.0 and held_out_family_map.get(nid) == family:
                family_scores.append(score)
            elif label == 0.0:
                benign_scores.append(score)

        result = _evaluate(family_scores + benign_scores, [1.0] * len(family_scores) + [0.0] * len(benign_scores), threshold)
        result.update(family=family, seed=seed, w_fit=w_fit)
        results.append(result)
    return results


def summarize(results: List[dict]) -> dict:
    detections = [r["detection_rate"] for r in results]
    fprs = [r["false_positive_rate"] for r in results]
    aurocs = [r["auroc"] for r in results]
    return {
        "family": results[0]["family"],
        "n_poison": results[0]["n_poison"], "n_benign": results[0]["n_benign"],
        "detection_rate_mean": statistics.mean(detections), "detection_rate_min": min(detections), "detection_rate_max": max(detections),
        "false_positive_rate_mean": statistics.mean(fprs), "false_positive_rate_min": min(fprs), "false_positive_rate_max": max(fprs),
        "auroc_mean": statistics.mean(aurocs), "auroc_min": min(aurocs), "auroc_max": max(aurocs),
    }


def run_all_families(*, seeds: Sequence[int] = SEEDS, w_fit: float = W_FIT) -> Dict[str, List[dict]]:
    families = _discover_families(split.all_dev_pools())
    return {family: run_fold(family, seeds=seeds, w_fit=w_fit) for family in families}


def macro_summary(all_results: Dict[str, List[dict]]) -> dict:
    summaries = [summarize(results) for results in all_results.values()]
    return {
        "macro_auroc": statistics.mean(s["auroc_mean"] for s in summaries),
        "macro_detection_rate": statistics.mean(s["detection_rate_mean"] for s in summaries),
        "macro_false_positive_rate": statistics.mean(s["false_positive_rate_mean"] for s in summaries),
    }


if __name__ == "__main__":
    import json

    all_results = run_all_families()
    for family, results in all_results.items():
        s = summarize(results)
        print(f"{family}: n={s['n_poison']} auroc={s['auroc_mean']:.4f} [{s['auroc_min']:.4f},{s['auroc_max']:.4f}] "
              f"detection={s['detection_rate_mean']:.4f} [{s['detection_rate_min']:.4f},{s['detection_rate_max']:.4f}] "
              f"fpr={s['false_positive_rate_mean']:.4f} [{s['false_positive_rate_min']:.4f},{s['false_positive_rate_max']:.4f}]")
    print("\nMACRO:", json.dumps(macro_summary(all_results), indent=2))
