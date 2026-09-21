"""Phase 11 -- leave-one-attack-family-out (LOFO) generalization audit for
the real, shipped GNN (`phase11/gnn/train.py`), per
`docs/phase11/PHASE11_LOFO_AUDIT.md`.

WHAT THIS DOES AND DOES NOT CHANGE
--------------------------------------------------------------------------------
The GNN architecture (`MinimalGNN`), its hyperparameters (`hidden_dim=8`,
`num_layers=2`, `WEIGHT_DECAY=0.0`, `LEARNING_RATE=0.05`, `EPOCHS=300`), the
9-feature sanctioned contract, the threshold-selection function
(`_threshold_for_target_fpr`), and `held_out_pools()` are all reused
UNMODIFIED from `phase11/gnn/train.py`/`features.py`/`model.py` -- this
module adds a fold-construction and pooled-reporting layer on top, per the
audit's own conclusion that no change to any of those is needed for
leakage-safe fold-local fitting.

THE 4 FAMILIES -- SCOPED TO THIS PROJECT'S ACTUAL GNN CORPUS
--------------------------------------------------------------------------------
Per the audit's Section 1: `split.all_dev_pools()`/`held_out_pools()` (the
ONLY corpus the shipped GNN ever trains/evaluates against) uses a 4-family
taxonomy (`FARMA`, `MemoryGraft-style-volume`, `Sleeper`, `propagated`) --
NOT the 7-attack Phase 4 taxonomy Phase 11.z's real-corpus work uses. This
module discovers the family set directly from the real data
(`_discover_families()`) rather than hardcoding it, so it cannot silently
drift out of sync with `dev_corpus.py`/`corpus.py`.

LEAKAGE-SAFETY, PER THE AUDIT
--------------------------------------------------------------------------------
Filtering happens at exactly one point -- `ScenarioPool.memories`, before
`build_dataset()` is ever called -- because the audit traced every
downstream stage (features, threshold, model init, seeds) and confirmed
none of them independently re-reads broader corpus data (Section 2). No
other change is required for a leakage-safe fold.
"""

from __future__ import annotations

import random
import statistics
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

import torch

from phase11.data import split
from phase11.gnn.features import FEATURE_KEYS, pools_node_features
from phase11.gnn.model import MinimalGNN
from phase11.gnn.self_supervised import auroc as _auroc
from phase11.gnn.train import (
    TARGET_TRAIN_FALSE_POSITIVE_RATE,
    GraphDataset,
    build_dataset,
    _threshold_for_target_fpr,
    train_model,
)
from phase6.defense.orchestration.pipeline import ScenarioPool

SEEDS: Tuple[int, ...] = tuple(range(11, 21))  # identical protocol to the original stability study


def _discover_families(pools: Sequence[ScenarioPool]) -> Tuple[str, ...]:
    families = set()
    for pool in pools:
        for m in pool.memories:
            if m.is_poison_ground_truth and m.attack_family_ground_truth:
                families.add(m.attack_family_ground_truth)
    return tuple(sorted(families))


def filter_pools_excluding_family(pools: Sequence[ScenarioPool], family: str) -> Tuple[ScenarioPool, ...]:
    """Real, additive filter: drops every poison `MemoryScenario` whose
    `attack_family_ground_truth == family` from each pool, keeping every
    other scenario (other-family poison, and all benign) untouched. Benign
    scenarios and non-`family` poison scenarios are never touched. Applied
    BEFORE `build_dataset()` -- per the audit, this single filter point is
    sufficient for leakage-safety since no downstream stage independently
    re-reads the unfiltered pools."""
    filtered = []
    for pool in pools:
        kept = tuple(
            m for m in pool.memories
            if not (m.is_poison_ground_truth and m.attack_family_ground_truth == family)
        )
        filtered.append(ScenarioPool(pool.pool_id, kept))
    return tuple(filtered)


def family_map_for_pools(pools: Sequence[ScenarioPool]) -> Dict[str, str]:
    """{scenario_id: attack_family_ground_truth} for every REAL poison
    scenario in `pools` -- synthetic ancestor nodes (added only inside
    `graph_build.py`, never present in `pool.memories`) are absent from
    this map by construction, and are never poison, so they never need a
    family assignment for this experiment's purposes."""
    out: Dict[str, str] = {}
    for pool in pools:
        for m in pool.memories:
            if m.is_poison_ground_truth and m.attack_family_ground_truth:
                out[m.scenario_id] = m.attack_family_ground_truth
    return out


@dataclass(frozen=True)
class FoldSeedResult:
    family: str
    seed: int
    n_family_poison_held_out: int
    n_benign_held_out: int
    family_scores: Tuple[float, ...]
    benign_scores: Tuple[float, ...]
    threshold: float
    detection_rate: float
    false_positive_rate: float
    auroc: float


def _assert_family_absent_from_training(train_ds_pools: Sequence[ScenarioPool], family: str) -> None:
    """Leakage guard, run inside every fold before training -- raises if
    the filter above ever failed to remove `family`'s poison scenarios."""
    for pool in train_ds_pools:
        for m in pool.memories:
            if m.is_poison_ground_truth and m.attack_family_ground_truth == family:
                raise AssertionError(
                    f"LOFO leakage: family {family!r} scenario {m.scenario_id!r} present in training pools"
                )


def run_lofo_fold(
    family: str, *, seeds: Sequence[int] = SEEDS, weight_decay: float = None,
) -> List[FoldSeedResult]:
    """One real, fresh GNN trained per seed, on `all_dev_pools()` with
    `family` entirely removed. Threshold selected fold-locally, in-sample,
    on that SAME filtered training set (Audit Section 5) -- never on
    `held_out_pools()`, never using `family`'s own labels. `held_out_pools()`
    itself is read UNMODIFIED (Audit Section 6) -- evaluation results are
    then restricted, by `attack_family_ground_truth`, to `family`'s own
    poison examples plus the full shared benign reference, per the
    protocol Part 8 of the governing task defined before this function was
    ever run.

    `weight_decay` (2026-09-20, additive, backward-compatible): `None` (the
    default) keeps the exact pre-existing behavior -- `train_model()`'s own
    default `WEIGHT_DECAY` constant. Passed through explicitly only by
    `phase11/gnn/lofo_weight_decay_sweep.py`, to test regularization
    against the family-generalization objective specifically (never tested
    before -- the original weight-decay sweep was measured only against the
    pooled-family held-out metric)."""
    train_pools = filter_pools_excluding_family(split.all_dev_pools(), family)
    _assert_family_absent_from_training(train_pools, family)
    train_ds = build_dataset(train_pools)

    held_out_pools = split.held_out_pools()  # unmodified, read fresh each call -- never filtered
    held_out_ds = build_dataset(held_out_pools)
    held_out_family_map = family_map_for_pools(held_out_pools)

    results: List[FoldSeedResult] = []
    for seed in seeds:
        model = train_model(train_ds, seed=seed, **({} if weight_decay is None else {"weight_decay": weight_decay}))
        train_scores = model.predict_proba(train_ds.features, train_ds.mean_adj).tolist()
        threshold = _threshold_for_target_fpr(
            train_scores, train_ds.labels.tolist(), TARGET_TRAIN_FALSE_POSITIVE_RATE,
        )

        held_out_scores = model.predict_proba(held_out_ds.features, held_out_ds.mean_adj).tolist()
        held_out_labels = held_out_ds.labels.tolist()

        family_scores = []
        benign_scores = []
        for node_id, score, label in zip(held_out_ds.node_ids, held_out_scores, held_out_labels):
            if label == 1.0 and held_out_family_map.get(node_id) == family:
                family_scores.append(score)
            elif label == 0.0:
                benign_scores.append(score)

        detected = sum(1 for s in family_scores if s >= threshold)
        flagged = sum(1 for s in benign_scores if s >= threshold)
        combined_scores = torch.tensor(family_scores + benign_scores)
        combined_labels = torch.tensor([1.0] * len(family_scores) + [0.0] * len(benign_scores))
        fold_auroc = _auroc(combined_scores, combined_labels)

        results.append(FoldSeedResult(
            family=family, seed=seed,
            n_family_poison_held_out=len(family_scores), n_benign_held_out=len(benign_scores),
            family_scores=tuple(family_scores), benign_scores=tuple(benign_scores),
            threshold=threshold,
            detection_rate=detected / len(family_scores) if family_scores else float("nan"),
            false_positive_rate=flagged / len(benign_scores) if benign_scores else float("nan"),
            auroc=fold_auroc,
        ))
    return results


def run_all_lofo_folds(*, seeds: Sequence[int] = SEEDS) -> Dict[str, List[FoldSeedResult]]:
    families = _discover_families(split.all_dev_pools())
    return {family: run_lofo_fold(family, seeds=seeds) for family in families}


# ----------------------------------------------------------------------------
# Aggregation, per Audit Section 8 -- defined here exactly as pre-registered,
# never adjusted after seeing results.
# ----------------------------------------------------------------------------

def per_family_summary(fold_results: List[FoldSeedResult]) -> dict:
    detections = [r.detection_rate for r in fold_results]
    fprs = [r.false_positive_rate for r in fold_results]
    aurocs = [r.auroc for r in fold_results]
    return {
        "family": fold_results[0].family,
        "n_family_poison_held_out": fold_results[0].n_family_poison_held_out,
        "n_benign_held_out": fold_results[0].n_benign_held_out,
        "seeds": [r.seed for r in fold_results],
        "detection_rate_by_seed": detections,
        "false_positive_rate_by_seed": fprs,
        "auroc_by_seed": aurocs,
        "detection_rate_mean": statistics.mean(detections),
        "false_positive_rate_mean": statistics.mean(fprs),
        "auroc_mean": statistics.mean(aurocs),
        "auroc_min": min(aurocs),
        "auroc_max": max(aurocs),
    }


def pooled_out_of_fold_summary(all_fold_results: Dict[str, List[FoldSeedResult]], *, seed: int) -> dict:
    """Audit Section 8's pooling rule, applied at one specific seed (the
    shipped default, SEED=11, unless the caller asks for another) so the
    pooled numbers are computed over one consistent set of 4 fold models,
    not mixed across seeds. Micro-averaged detection rate; macro-averaged
    FPR (see Audit Section 8 Item 2 for why); pooled AUROC reported with its
    benign-repetition caveat, per Item 3."""
    per_seed = {family: next(r for r in results if r.seed == seed) for family, results in all_fold_results.items()}

    total_detected = sum(round(r.detection_rate * r.n_family_poison_held_out) for r in per_seed.values())
    total_poison = sum(r.n_family_poison_held_out for r in per_seed.values())

    macro_fpr = statistics.mean(r.false_positive_rate for r in per_seed.values())

    pooled_scores: List[float] = []
    pooled_labels: List[float] = []
    for r in per_seed.values():
        pooled_scores.extend(r.family_scores)
        pooled_labels.extend([1.0] * len(r.family_scores))
        pooled_scores.extend(r.benign_scores)
        pooled_labels.extend([0.0] * len(r.benign_scores))
    pooled_auroc = _auroc(torch.tensor(pooled_scores), torch.tensor(pooled_labels))

    macro_auroc = statistics.mean(r.auroc for r in per_seed.values())

    return {
        "seed": seed,
        "n_folds": len(per_seed),
        "total_family_poison_n": total_poison,
        "total_benign_n_per_fold": next(iter(per_seed.values())).n_benign_held_out,
        "pooled_detection_rate_micro": total_detected / total_poison if total_poison else float("nan"),
        "macro_false_positive_rate": macro_fpr,
        "pooled_auroc_benign_repeated_per_fold": pooled_auroc,
        "macro_auroc_unweighted_mean_of_family_aurocs": macro_auroc,
    }


# ----------------------------------------------------------------------------
# Baselines, per Audit Section 9 -- fixed before any LOFO fold is run.
# ----------------------------------------------------------------------------

def baseline_b_chance_reference(n_poison: int, n_benign: int, *, trials: int = 100, seed: int = 0) -> dict:
    """Real, measured (not assumed) chance-level AUROC: uniform-random
    scores over the same evaluation population size, repeated `trials`
    times."""
    rng = random.Random(seed)
    aurocs = []
    for _ in range(trials):
        scores = [rng.random() for _ in range(n_poison + n_benign)]
        labels = [1.0] * n_poison + [0.0] * n_benign
        aurocs.append(_auroc(torch.tensor(scores), torch.tensor(labels)))
    return {
        "n_poison": n_poison, "n_benign": n_benign, "trials": trials,
        "auroc_mean": statistics.mean(aurocs), "auroc_min": min(aurocs), "auroc_max": max(aurocs),
    }


def baseline_c_frozen_feature_sum(family: str) -> dict:
    """A real, zero-training, zero-fitting baseline: the raw sum of the 9
    sanctioned feature values per node (no GNN, no message passing, no
    threshold-fitting beyond the SAME `_threshold_for_target_fpr` in-sample
    rule applied directly to this simple score) -- isolates whether ANY
    detection signal survives from the frozen features alone, independent
    of whether the GNN's own trained weights generalize."""
    held_out_pools = split.held_out_pools()
    held_out_family_map = family_map_for_pools(held_out_pools)
    feature_map = pools_node_features(held_out_pools)

    node_ids = list(feature_map.keys())
    scores = {nid: sum(feature_map[nid]) for nid in node_ids}

    # is_poison_ground_truth per node, for scoring -- read once, directly, not fabricated
    labels: Dict[str, bool] = {}
    for pool in held_out_pools:
        for m in pool.memories:
            labels[m.scenario_id] = m.is_poison_ground_truth

    family_scores = [scores[nid] for nid in node_ids if labels.get(nid) and held_out_family_map.get(nid) == family]
    benign_scores = [scores[nid] for nid in node_ids if nid in labels and not labels[nid]]

    combined_scores = torch.tensor(family_scores + benign_scores)
    combined_labels = torch.tensor([1.0] * len(family_scores) + [0.0] * len(benign_scores))
    return {
        "family": family,
        "n_family_poison": len(family_scores), "n_benign": len(benign_scores),
        "auroc": _auroc(combined_scores, combined_labels),
    }


if __name__ == "__main__":
    import json

    all_results = run_all_lofo_folds()
    for family, fold_results in all_results.items():
        print(f"\n=== {family} ===")
        summary = per_family_summary(fold_results)
        print(json.dumps(summary, indent=2))
        print("Baseline C (frozen features, no GNN):", baseline_c_frozen_feature_sum(family))

    print("\n=== Pooled out-of-fold (SEED=11) ===")
    print(json.dumps(pooled_out_of_fold_summary(all_results, seed=11), indent=2))
