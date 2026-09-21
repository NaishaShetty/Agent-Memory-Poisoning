"""Phase 11 -- calibrating Baseline C (the untrained sum of the 9 sanctioned
features, `phase11/gnn/lofo.py::baseline_c_frozen_feature_sum`) into a real
detector, and a natural, minimal extension of it, per the LOFO report's own
next-step recommendation: "is a properly calibrated frozen-feature score a
more honest cross-family detector than the GNN at this data scale."

TWO REAL CONFIGURATIONS, KEPT SEPARATE, NEVER SILENTLY MIXED
--------------------------------------------------------------------------------
1. **Threshold-calibrated raw sum** (`RAW_SUM`): the exact same
   zero-training score `baseline_c_frozen_feature_sum()` already computes
   (sum of the 9 sanctioned feature values, no fitting of any kind), with
   ONE addition -- a real decision threshold, fitted fold-locally and
   in-sample using the SAME `_threshold_for_target_fpr()` function the GNN
   already uses (`phase11/gnn/train.py`, unmodified, reused not
   reimplemented). This is the most literal reading of "calibrate Baseline
   C into a detector": a score alone is a ranking, not a detector; adding a
   threshold is the smallest possible addition.
2. **A from-scratch linear/logistic detector** (`LINEAR`): `nn.Linear(9, 1)`
   -- ONE linear layer over the same 9 raw sanctioned features, NO message
   passing, NO graph, trained with the SAME optimization protocol
   (`Adam`, `lr=0.05`, `weight_decay=0.0`, `300` epochs,
   `BCEWithLogitsLoss`) `phase11/gnn/train.py::train_model()` already uses
   for the GNN -- the only architectural difference from `MinimalGNN` is
   the absence of the two `MessagePassingLayer`s. This isolates the
   specific question the LOFO report's Section I raised but did not
   answer: does FITTING (any fitting, without graph structure) do better
   than the GNN's graph-message-passing fitting, or does simple linear
   fitting over these particular 9 features also fail to generalize the
   same way? Threshold selection for this config is fold-local and
   in-sample, identically to `RAW_SUM` and to the existing GNN.

WHY THIS IS NOT A CHANGE TO THE FROZEN GNN
--------------------------------------------------------------------------------
`MinimalGNN`, `phase11/gnn/train.py`, and `phase11/gnn/lofo.py` are
untouched -- `LinearDetector` below is a new, separate, additive model
class. `_threshold_for_target_fpr()` is imported and reused verbatim, never
copied or modified.

FEATURE COMPUTATION -- SAME SOURCE, ONE DISCLOSED N DIFFERENCE
--------------------------------------------------------------------------------
Features come from the SAME `phase11.gnn.features.pools_node_features()`
call the GNN itself uses. One real, disclosed consequence: this module
never builds a graph, so the synthetic ancestor nodes `graph_build.py`
adds (3 extra all-zero-feature benign nodes, present in every GNN
held-out evaluation) are ABSENT here -- this module's benign n is 41 real
scenarios, not the GNN's 44 (41 real + 3 synthetic). Reported explicitly
wherever a direct GNN comparison is made, never silently reconciled by
adding fabricated nodes to match.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

import torch
from torch import nn

from phase11.data import split
from phase11.gnn.features import FEATURE_KEYS, pools_node_features
from phase11.gnn.lofo import filter_pools_excluding_family, family_map_for_pools, _discover_families
from phase11.gnn.self_supervised import auroc as _auroc
from phase11.gnn.train import TARGET_TRAIN_FALSE_POSITIVE_RATE, _threshold_for_target_fpr
from phase6.defense.orchestration.pipeline import ScenarioPool

SEEDS: Tuple[int, ...] = tuple(range(11, 21))  # identical protocol to the GNN LOFO study

EPOCHS = 300
LEARNING_RATE = 0.05
WEIGHT_DECAY = 0.0


@dataclass(frozen=True)
class RawDataset:
    node_ids: Tuple[str, ...]
    features: torch.Tensor  # [n, 9]
    labels: torch.Tensor  # [n]


def build_raw_dataset(pools: Sequence[ScenarioPool]) -> RawDataset:
    """The 9 sanctioned feature values per real scenario, NO graph build --
    same feature source as the GNN (`pools_node_features`), but no
    synthetic ancestor nodes (those only exist inside `graph_build.py`)."""
    feature_map = pools_node_features(pools)
    labels_by_id: Dict[str, bool] = {}
    for pool in pools:
        for m in pool.memories:
            labels_by_id[m.scenario_id] = m.is_poison_ground_truth

    node_ids = tuple(feature_map.keys())
    features = torch.tensor([feature_map[nid] for nid in node_ids], dtype=torch.float32)
    labels = torch.tensor([1.0 if labels_by_id[nid] else 0.0 for nid in node_ids], dtype=torch.float32)
    return RawDataset(node_ids, features, labels)


class LinearDetector(nn.Module):
    """A from-scratch, single-linear-layer detector over the 9 sanctioned
    features -- deliberately the GNN's own architecture with both
    `MessagePassingLayer`s removed, nothing else changed."""

    def __init__(self, in_dim: int = len(FEATURE_KEYS), seed: int = 11):
        super().__init__()
        torch.manual_seed(seed)
        self.linear = nn.Linear(in_dim, 1)

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.linear(features).squeeze(-1)

    def predict_proba(self, features: torch.Tensor) -> torch.Tensor:
        with torch.no_grad():
            return torch.sigmoid(self(features))


def train_linear_detector(train_ds: RawDataset, *, seed: int = 11) -> LinearDetector:
    model = LinearDetector(seed=seed)
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)
    loss_fn = nn.BCEWithLogitsLoss()
    for _ in range(EPOCHS):
        optimizer.zero_grad()
        logits = model(train_ds.features)
        loss = loss_fn(logits, train_ds.labels)
        loss.backward()
        optimizer.step()
    return model


def raw_sum_scores(ds: RawDataset) -> List[float]:
    return ds.features.sum(dim=1).tolist()


def _evaluate_scores(scores: Sequence[float], labels: Sequence[float], threshold: float) -> dict:
    poison = [s for s, y in zip(scores, labels) if y == 1.0]
    benign = [s for s, y in zip(scores, labels) if y == 0.0]
    detected = sum(1 for s in poison if s >= threshold)
    flagged = sum(1 for s in benign if s >= threshold)
    combined = torch.tensor(list(scores))
    combined_labels = torch.tensor(list(labels))
    return {
        "n_poison": len(poison), "n_benign": len(benign),
        "detection_rate": detected / len(poison) if poison else float("nan"),
        "false_positive_rate": flagged / len(benign) if benign else float("nan"),
        "auroc": _auroc(combined, combined_labels),
        "threshold": threshold,
    }


# ----------------------------------------------------------------------------
# Configuration 1: pooled-family evaluation (directly comparable to Baseline
# A / B9 / B10 -- all_dev_pools() -> held_out_pools(), no family excluded)
# ----------------------------------------------------------------------------

def run_pooled_family_raw_sum() -> dict:
    """Deterministic -- no training happens, so no seed dependency."""
    train_ds = build_raw_dataset(split.all_dev_pools())
    held_out_ds = build_raw_dataset(split.held_out_pools())

    train_scores = raw_sum_scores(train_ds)
    threshold = _threshold_for_target_fpr(train_scores, train_ds.labels.tolist(), TARGET_TRAIN_FALSE_POSITIVE_RATE)

    held_out_scores = raw_sum_scores(held_out_ds)
    return _evaluate_scores(held_out_scores, held_out_ds.labels.tolist(), threshold)


def run_pooled_family_linear(*, seeds: Sequence[int] = SEEDS) -> List[dict]:
    train_ds = build_raw_dataset(split.all_dev_pools())
    held_out_ds = build_raw_dataset(split.held_out_pools())

    results = []
    for seed in seeds:
        model = train_linear_detector(train_ds, seed=seed)
        train_scores = model.predict_proba(train_ds.features).tolist()
        threshold = _threshold_for_target_fpr(train_scores, train_ds.labels.tolist(), TARGET_TRAIN_FALSE_POSITIVE_RATE)
        held_out_scores = model.predict_proba(held_out_ds.features).tolist()
        result = _evaluate_scores(held_out_scores, held_out_ds.labels.tolist(), threshold)
        result["seed"] = seed
        results.append(result)
    return results


# ----------------------------------------------------------------------------
# Configuration 2: LOFO (same protocol as phase11/gnn/lofo.py, applied to
# these two non-graph scorers instead of the GNN)
# ----------------------------------------------------------------------------

def run_lofo_fold_raw_sum(family: str) -> dict:
    """Deterministic per fold -- no training, so no seed loop needed."""
    train_pools = filter_pools_excluding_family(split.all_dev_pools(), family)
    train_ds = build_raw_dataset(train_pools)

    held_out_pools = split.held_out_pools()
    held_out_ds = build_raw_dataset(held_out_pools)
    held_out_family_map = family_map_for_pools(held_out_pools)

    train_scores = raw_sum_scores(train_ds)
    threshold = _threshold_for_target_fpr(train_scores, train_ds.labels.tolist(), TARGET_TRAIN_FALSE_POSITIVE_RATE)

    held_out_scores = raw_sum_scores(held_out_ds)
    held_out_labels = held_out_ds.labels.tolist()

    family_scores, benign_scores = [], []
    for nid, score, label in zip(held_out_ds.node_ids, held_out_scores, held_out_labels):
        if label == 1.0 and held_out_family_map.get(nid) == family:
            family_scores.append(score)
        elif label == 0.0:
            benign_scores.append(score)

    result = _evaluate_scores(family_scores + benign_scores, [1.0] * len(family_scores) + [0.0] * len(benign_scores), threshold)
    result["family"] = family
    return result


def run_lofo_fold_linear(family: str, *, seeds: Sequence[int] = SEEDS) -> List[dict]:
    train_pools = filter_pools_excluding_family(split.all_dev_pools(), family)
    train_ds = build_raw_dataset(train_pools)

    held_out_pools = split.held_out_pools()
    held_out_ds = build_raw_dataset(held_out_pools)
    held_out_family_map = family_map_for_pools(held_out_pools)

    results = []
    for seed in seeds:
        model = train_linear_detector(train_ds, seed=seed)
        train_scores = model.predict_proba(train_ds.features).tolist()
        threshold = _threshold_for_target_fpr(train_scores, train_ds.labels.tolist(), TARGET_TRAIN_FALSE_POSITIVE_RATE)

        held_out_scores = model.predict_proba(held_out_ds.features).tolist()
        held_out_labels = held_out_ds.labels.tolist()

        family_scores, benign_scores = [], []
        for nid, score, label in zip(held_out_ds.node_ids, held_out_scores, held_out_labels):
            if label == 1.0 and held_out_family_map.get(nid) == family:
                family_scores.append(score)
            elif label == 0.0:
                benign_scores.append(score)

        result = _evaluate_scores(family_scores + benign_scores, [1.0] * len(family_scores) + [0.0] * len(benign_scores), threshold)
        result["family"] = family
        result["seed"] = seed
        results.append(result)
    return results


def run_all_lofo_folds_linear(*, seeds: Sequence[int] = SEEDS) -> Dict[str, List[dict]]:
    families = _discover_families(split.all_dev_pools())
    return {family: run_lofo_fold_linear(family, seeds=seeds) for family in families}


def run_all_lofo_folds_raw_sum() -> Dict[str, dict]:
    families = _discover_families(split.all_dev_pools())
    return {family: run_lofo_fold_raw_sum(family) for family in families}


def summarize_linear_seeds(results: List[dict]) -> dict:
    detections = [r["detection_rate"] for r in results]
    fprs = [r["false_positive_rate"] for r in results]
    aurocs = [r["auroc"] for r in results]
    return {
        "family": results[0].get("family"),
        "n_poison": results[0]["n_poison"], "n_benign": results[0]["n_benign"],
        "detection_rate_mean": statistics.mean(detections), "detection_rate_min": min(detections), "detection_rate_max": max(detections),
        "false_positive_rate_mean": statistics.mean(fprs),
        "auroc_mean": statistics.mean(aurocs), "auroc_min": min(aurocs), "auroc_max": max(aurocs),
    }


if __name__ == "__main__":
    import json

    print("=== Config 1: RAW_SUM, pooled-family (Baseline-A-comparable) ===")
    print(json.dumps(run_pooled_family_raw_sum(), indent=2))

    print("\n=== Config 2: LINEAR, pooled-family (Baseline-A-comparable) ===")
    linear_pooled = run_pooled_family_linear()
    print(json.dumps(summarize_linear_seeds(linear_pooled), indent=2))

    print("\n=== RAW_SUM, LOFO per family ===")
    raw_lofo = run_all_lofo_folds_raw_sum()
    for family, result in raw_lofo.items():
        print(family, json.dumps(result, indent=2))

    print("\n=== LINEAR, LOFO per family ===")
    linear_lofo = run_all_lofo_folds_linear()
    for family, results in linear_lofo.items():
        print(family, json.dumps(summarize_linear_seeds(results), indent=2))
