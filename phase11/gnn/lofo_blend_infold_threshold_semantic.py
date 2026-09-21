"""Phase 11 -- does the semantic-consensus-divergence feature
(`phase11/gnn/features.py::GNN_FEATURE_KEYS`) ALSO fix
MemoryGraft-style-volume's LOFO weak spot (50% detection, the one
remaining gap `PHASE11_LOFO_FPR_AND_FARMA_FIX_REPORT.md` disclosed after
the raw-sum blend fixed FARMA)?

WHY THIS IS THE RIGHT NEXT QUESTION, NOT A GUESS
--------------------------------------------------------------------------------
MemoryGraft-style-volume IS the near-duplicate/paraphrase consensus attack
family -- exactly the mechanism `semantic_consensus_divergence_score` was
added to detect (`PHASE11_PARAPHRASE_FIX_REPORT.md`). FARMA is an
admission/reasoning-guard attack (forged-confidence phrasing), unrelated
to consensus divergence -- so this signal is not expected to move FARMA's
already-resolved number, and that is checked directly below, not assumed.

SAME PROTOCOL, ONE FEATURE-SET CHANGE
--------------------------------------------------------------------------------
Identical to `lofo_blend_infold_threshold.py` (blend fitted+raw-sum,
threshold on the fold's own real training-benign set) -- the ONLY
difference is `build_dataset(..., feature_keys=GNN_FEATURE_KEYS,
feature_fn=pools_node_features_gnn)` instead of the original 9-feature
default. `lofo_blend_infold_threshold.py` itself is left completely
unmodified -- its own already-reported numbers stay exactly as measured.
"""

from __future__ import annotations

import statistics
from typing import Dict, List, Sequence

import torch

from phase11.data import split
from phase11.gnn.features import GNN_FEATURE_KEYS, pools_node_features_gnn
from phase11.gnn.lofo import SEEDS, _discover_families, filter_pools_excluding_family, family_map_for_pools
from phase11.gnn.self_supervised import auroc as _auroc
from phase11.gnn.train import build_dataset as _build_dataset_base, train_model, TARGET_TRAIN_FALSE_POSITIVE_RATE, _threshold_for_target_fpr

BLEND_WEIGHTS = (0.0, 0.25, 0.5, 0.75, 1.0)
WEIGHT_DECAY = 0.005


def build_dataset(pools):
    return _build_dataset_base(pools, feature_keys=GNN_FEATURE_KEYS, feature_fn=pools_node_features_gnn)


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


def run_fold(family: str, *, seeds: Sequence[int] = SEEDS) -> Dict[float, List[dict]]:
    train_pools = filter_pools_excluding_family(split.all_dev_pools(), family)
    train_ds = build_dataset(train_pools)

    held_out_pools = split.held_out_pools()
    held_out_ds = build_dataset(held_out_pools)
    held_out_family_map = family_map_for_pools(held_out_pools)

    results: Dict[float, List[dict]] = {w: [] for w in BLEND_WEIGHTS}

    for seed in seeds:
        model = train_model(train_ds, seed=seed, weight_decay=WEIGHT_DECAY)

        train_fitted = model.predict_proba(train_ds.features, train_ds.mean_adj)
        train_raw = _raw_sum(train_ds.features)
        fit_mean, fit_std = train_fitted.mean().item(), train_fitted.std(unbiased=False).item()
        raw_mean, raw_std = train_raw.mean().item(), train_raw.std(unbiased=False).item()

        train_z_fit = _zscore(train_fitted, fit_mean, fit_std)
        train_z_raw = _zscore(train_raw, raw_mean, raw_std)
        train_labels = train_ds.labels.tolist()

        held_out_fitted = model.predict_proba(held_out_ds.features, held_out_ds.mean_adj)
        held_out_raw = _raw_sum(held_out_ds.features)
        held_out_z_fit = _zscore(held_out_fitted, fit_mean, fit_std)
        held_out_z_raw = _zscore(held_out_raw, raw_mean, raw_std)
        held_out_labels = held_out_ds.labels.tolist()

        for w in BLEND_WEIGHTS:
            train_blend = (w * train_z_fit + (1 - w) * train_z_raw).tolist()
            threshold = _threshold_for_target_fpr(train_blend, train_labels, TARGET_TRAIN_FALSE_POSITIVE_RATE)

            held_out_blend = (w * held_out_z_fit + (1 - w) * held_out_z_raw).tolist()

            family_scores, benign_scores = [], []
            for nid, score, label in zip(held_out_ds.node_ids, held_out_blend, held_out_labels):
                if label == 1.0 and held_out_family_map.get(nid) == family:
                    family_scores.append(score)
                elif label == 0.0:
                    benign_scores.append(score)

            result = _evaluate(family_scores + benign_scores, [1.0] * len(family_scores) + [0.0] * len(benign_scores), threshold)
            result.update(family=family, seed=seed, w=w)
            results[w].append(result)

    return results


def summarize(results: List[dict]) -> dict:
    detections = [r["detection_rate"] for r in results]
    fprs = [r["false_positive_rate"] for r in results]
    aurocs = [r["auroc"] for r in results]
    return {
        "family": results[0]["family"], "w": results[0]["w"],
        "n_poison": results[0]["n_poison"], "n_benign": results[0]["n_benign"],
        "detection_rate_mean": statistics.mean(detections),
        "false_positive_rate_mean": statistics.mean(fprs),
        "auroc_mean": statistics.mean(aurocs), "auroc_min": min(aurocs), "auroc_max": max(aurocs),
    }


def run_all_families(*, seeds: Sequence[int] = SEEDS) -> Dict[str, Dict[float, List[dict]]]:
    families = _discover_families(split.all_dev_pools())
    return {family: run_fold(family, seeds=seeds) for family in families}


def macro_by_w(all_results: Dict[str, Dict[float, List[dict]]]) -> Dict[float, dict]:
    out = {}
    for w in BLEND_WEIGHTS:
        summaries = [summarize(all_results[family][w]) for family in all_results]
        out[w] = {
            "macro_auroc": statistics.mean(s["auroc_mean"] for s in summaries),
            "macro_detection_rate": statistics.mean(s["detection_rate_mean"] for s in summaries),
            "macro_false_positive_rate": statistics.mean(s["false_positive_rate_mean"] for s in summaries),
        }
    return out


if __name__ == "__main__":
    import json

    all_results = run_all_families()
    macro = macro_by_w(all_results)
    print("=== Macro summary by w (10-feature, semantic-inclusive) ===")
    for w, m in sorted(macro.items()):
        print(f"w={w:.2f}  macro_auroc={m['macro_auroc']:.4f} "
              f"macro_detection={m['macro_detection_rate']:.4f} macro_fpr={m['macro_false_positive_rate']:.4f}")

    print("\n=== Per-family detail ===")
    for family in all_results:
        for w in BLEND_WEIGHTS:
            s = summarize(all_results[family][w])
            print(f"  {family} w={w}: auroc_mean={s['auroc_mean']:.4f} "
                  f"detection_mean={s['detection_rate_mean']:.4f} fpr_mean={s['false_positive_rate_mean']:.4f}")
