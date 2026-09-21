"""Phase 11 -- ensemble-averaging the blend score across seeds, to address
the real, diagnosed cause of the remaining LOFO/real-corpus weaknesses:
single-seed threshold-selection noise at 8-11 training-benign examples.

WHY THIS IS A GENUINELY DIFFERENT LEVER THAN ANYTHING TRIED SO FAR
--------------------------------------------------------------------------------
Every fix in this investigation so far (weight decay, blend weight,
reference population, robust statistics) changed WHAT is thresholded or
HOW the threshold is picked from one model's own scores. None of them
addressed the fact that at this data scale, a SINGLE trained model's own
score distribution is itself a noisy draw -- `PHASE11_REPORT.md` Section 2
already showed 9 of 10 seeds saturate for the pure-fitted GNN. Averaging
the SAME blended score across the 10 already-trained seed-models (no new
training, no new data) is a standard, real variance-reduction technique,
distinct from anything tried before: it reduces noise in the SCORE itself,
not just in how the threshold is chosen from one score.

WHY THE EARLIER, DIFFERENT ENSEMBLE ATTEMPT DOES NOT PRE-ANSWER THIS
--------------------------------------------------------------------------------
`PHASE11_REPORT.md` already tried a 10-model seed ensemble and found it
WORSE (100% detection at 56.8% FPR) -- but that was the ORIGINAL,
unregularized, un-blended, 9-feature GNN. Every one of those conditions
has since changed (weight_decay=0.005, the raw-sum blend, the semantic
feature). Assuming the old negative result still holds without
re-measuring it under the current configuration would be exactly the kind
of stale-claim error this investigation already caught itself making once
this session (the FARMA mischaracterization) -- so it is re-tested
directly here, not assumed.
"""

from __future__ import annotations

import statistics
from typing import Dict, List, Sequence

import torch

from phase11.data import split
from phase11.data.poison_regeneration import regenerate_poison_batch
from phase11.data.real_corpus import real_poison_scenarios
from phase11.gnn.features import GNN_FEATURE_KEYS, pools_node_features_gnn
from phase11.gnn.lofo import SEEDS, _discover_families, family_map_for_pools, filter_pools_excluding_family
from phase11.gnn.self_supervised import auroc as _auroc
from phase11.gnn.train import build_dataset as _build_dataset_base, train_model, TARGET_TRAIN_FALSE_POSITIVE_RATE, _threshold_for_target_fpr
from phase6.defense.orchestration.pipeline import ScenarioPool

W = 0.50  # the same wired-in blend weight -- not re-tuned here
WEIGHT_DECAY = 0.005


def build_dataset(pools):
    return _build_dataset_base(pools, feature_keys=GNN_FEATURE_KEYS, feature_fn=pools_node_features_gnn)


def _raw_sum(features: torch.Tensor) -> torch.Tensor:
    return features.sum(dim=1)


def _zscore(values, mean, std):
    if std == 0.0:
        return torch.zeros_like(values)
    return (values - mean) / std


def _ensemble_blend_scores(train_ds, eval_ds, *, seeds: Sequence[int]) -> "list[float]":
    """Trains one model per seed (real, independent trainings -- not a
    single model re-scored), computes each one's own blended score on
    `eval_ds`, z-scored using THAT SAME model's own training-population
    statistics, then averages across seeds -- one ensemble score per node."""
    per_seed_scores = []
    for seed in seeds:
        model = train_model(train_ds, seed=seed, weight_decay=WEIGHT_DECAY)
        train_fitted = model.predict_proba(train_ds.features, train_ds.mean_adj)
        train_raw = _raw_sum(train_ds.features)
        fit_mean, fit_std = train_fitted.mean().item(), train_fitted.std(unbiased=False).item()
        raw_mean, raw_std = train_raw.mean().item(), train_raw.std(unbiased=False).item()

        eval_fitted = model.predict_proba(eval_ds.features, eval_ds.mean_adj)
        eval_raw = _raw_sum(eval_ds.features)
        z_fit = _zscore(eval_fitted, fit_mean, fit_std)
        z_raw = _zscore(eval_raw, raw_mean, raw_std)
        per_seed_scores.append((W * z_fit + (1 - W) * z_raw).tolist())

    n = len(per_seed_scores[0])
    return [statistics.mean(per_seed_scores[s][i] for s in range(len(seeds))) for i in range(n)]


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
        "threshold": threshold,
    }


# ----------------------------------------------------------------------------
# LOFO, ensembled
# ----------------------------------------------------------------------------

def run_lofo_fold_ensemble(family: str, *, seeds: Sequence[int] = SEEDS) -> dict:
    train_pools = filter_pools_excluding_family(split.all_dev_pools(), family)
    train_ds = build_dataset(train_pools)

    held_out_pools = split.held_out_pools()
    held_out_ds = build_dataset(held_out_pools)
    held_out_family_map = family_map_for_pools(held_out_pools)

    train_ensemble_scores = _ensemble_blend_scores(train_ds, train_ds, seeds=seeds)
    threshold = _threshold_for_target_fpr(train_ensemble_scores, train_ds.labels.tolist(), TARGET_TRAIN_FALSE_POSITIVE_RATE)

    held_out_ensemble_scores = _ensemble_blend_scores(train_ds, held_out_ds, seeds=seeds)
    held_out_labels = held_out_ds.labels.tolist()

    family_scores, benign_scores = [], []
    for nid, score, label in zip(held_out_ds.node_ids, held_out_ensemble_scores, held_out_labels):
        if label == 1.0 and held_out_family_map.get(nid) == family:
            family_scores.append(score)
        elif label == 0.0:
            benign_scores.append(score)

    result = _evaluate(family_scores + benign_scores, [1.0] * len(family_scores) + [0.0] * len(benign_scores), threshold)
    result["family"] = family
    return result


def run_all_lofo_ensemble(*, seeds: Sequence[int] = SEEDS) -> Dict[str, dict]:
    families = _discover_families(split.all_dev_pools())
    return {family: run_lofo_fold_ensemble(family, seeds=seeds) for family in families}


# ----------------------------------------------------------------------------
# Real-attack-corpus detector, ensembled
# ----------------------------------------------------------------------------

def _real_attack_poison_pool() -> ScenarioPool:
    old = list(real_poison_scenarios().memories)
    new_pool, _ = regenerate_poison_batch()
    return ScenarioPool("POOL-REAL-7-ATTACK-VALIDATION", tuple(old) + tuple(new_pool.memories))


def run_real_attack_corpus_ensemble(*, seeds: Sequence[int] = SEEDS) -> dict:
    train_ds = build_dataset(split.all_dev_pools())
    real_attack_pool = _real_attack_poison_pool()
    real_attack_ds = build_dataset((real_attack_pool,))
    real_attack_family_map = {m.scenario_id: m.attack_family_ground_truth for m in real_attack_pool.memories}
    held_out_benign_ds = build_dataset(split.held_out_pools())
    benign_node_ids = [nid for nid, y in zip(held_out_benign_ds.node_ids, held_out_benign_ds.labels.tolist()) if y == 0.0]

    train_ensemble_scores = _ensemble_blend_scores(train_ds, train_ds, seeds=seeds)
    threshold = _threshold_for_target_fpr(train_ensemble_scores, train_ds.labels.tolist(), TARGET_TRAIN_FALSE_POSITIVE_RATE)

    poison_scores = _ensemble_blend_scores(train_ds, real_attack_ds, seeds=seeds)
    benign_scores_all = _ensemble_blend_scores(train_ds, held_out_benign_ds, seeds=seeds)
    benign_scores = [s for nid, s in zip(held_out_benign_ds.node_ids, benign_scores_all) if nid in benign_node_ids]

    result = _evaluate(poison_scores + benign_scores, [1.0] * len(poison_scores) + [0.0] * len(benign_scores), threshold)

    by_family: Dict[str, List[float]] = {}
    for nid, s in zip(real_attack_ds.node_ids, poison_scores):
        by_family.setdefault(real_attack_family_map[nid], []).append(s >= threshold)
    result["per_family_detection_rate"] = {fam: sum(hits) / len(hits) for fam, hits in by_family.items()}
    return result


if __name__ == "__main__":
    import json

    print("=== LOFO, ensemble-averaged over seeds 11-20 ===")
    lofo = run_all_lofo_ensemble()
    for family, r in lofo.items():
        print(f"  {family}: n={r['n_poison']} auroc={r['auroc']:.4f} "
              f"detection={r['detection_rate']:.4f} fpr={r['false_positive_rate']:.4f}")

    print("\n=== Real-attack-corpus detector, ensemble-averaged ===")
    print(json.dumps(run_real_attack_corpus_ensemble(), indent=2))
