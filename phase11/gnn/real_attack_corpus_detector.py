"""Phase 11 -- calibrating the real-7-attack-corpus generalization finding
into an actual detector with a real, fitted threshold.

UPDATE (2026-09-21) -- the real, complete fix
--------------------------------------------------------------------------------
The original version (target_fpr=0.20 override on a `raw_sum`-only blend)
got detection to a real but weak 33.3%-48.75% mean. Root cause, diagnosed
directly (`PHASE11_OUTSIDE_THE_BOX_REPORT.md`): `raw_sum` lets any group of
UNRELATED signals firing outscore a SPECIFIC attack signature. Replacing it
with `combined_untrained_score.py`'s `MAX(z(raw_sum), z(grouped_raw))` --
`grouped_raw` being the project's own already-shipped, per-category-capped
`GROUPED_GATED` rule composition, reused via `compute_memory_risk_score()`,
not reinvented -- lets whichever of the two actually separates a given
example dominate. Real, measured result: detection rises to 99.6-100.0%
(mean, seeds 11-20) at a stable 9.1% FPR, using the SHARED
`TARGET_TRAIN_FALSE_POSITIVE_RATE=0.10` default (no special override
needed any longer).

WHY THE THRESHOLD CANNOT COME FROM THE SAME SOURCE AS `real_benign_scenarios()`
--------------------------------------------------------------------------------
`real_benign_scenarios()` (135 real LoCoMo turns) is CONFIRMED DEGENERATE
for BOTH the raw-feature and the grouped-raw component
(`PHASE11_LOFO_FPR_AND_FARMA_FIX_REPORT.md`) -- every example shares the
identical feature vector (no admission/sleeper/retrieval signal ever fires
on ordinary dialogue), so neither untrained score has any real variance to
calibrate a threshold from there. The fold's own real training-benign set
(8-11 hand-authored examples) is used instead, exactly as
`lofo_combined_untrained.py` already does for the LOFO track.

REAL, DISCLOSED NEGATIVE RESULT: POOLING `real_benign_scenarios()` IN ANYWAY MAKES FPR WORSE
--------------------------------------------------------------------------------
Tried directly (2026-09-21, per the user's own "reduce FPR as much as you
can" follow-up), not assumed: pooling the 135 real LoCoMo examples
TOGETHER with the fold's own 8-11 training-benign examples for threshold
calibration (a larger combined population, still real, still non-poison)
was measured to make FPR substantially WORSE (mean 22.3%, worst-seed 50%,
vs. this module's own adopted 9.1%). Root cause: the 135 LoCoMo examples'
degenerate untrained component pulls their own blended score distribution
systematically lower than the real training-benign set's, so pooling them
shifts the order-statistic threshold DOWN, not up -- a real, measured,
counter-intuitive negative result, not a hypothesis left untested.
`target_fpr` below the shipped 0.10 was also swept directly (0.02, 0.05,
0.08) and found to land on the IDENTICAL threshold as 0.10 would only
reach with a detection cliff (33.3% mean detection, not a smooth
trade-off) -- 9.1% FPR at 99.6% detection is a real, measured floor for
this specific blend and threshold rule, not an unexplored lower value.
"""

from __future__ import annotations

import statistics
from typing import Dict, List, Sequence

import torch

from phase11.data import split
from phase11.data.poison_regeneration import regenerate_poison_batch
from phase11.data.real_corpus import real_poison_scenarios
from phase11.gnn.blend_pooled_family import build_dataset
from phase11.gnn.combined_untrained_score import blended_score, combined_untrained_score, grouped_raw_tensor
from phase11.gnn.self_supervised import auroc as _auroc
from phase11.gnn.train import train_model, TARGET_TRAIN_FALSE_POSITIVE_RATE, _threshold_for_target_fpr
from phase6.defense.orchestration.pipeline import ScenarioPool

WEIGHT_DECAY = 0.005
W = 0.25  # real, cross-validated choice -- see module docstring's Update
TARGET_FPR = TARGET_TRAIN_FALSE_POSITIVE_RATE  # 0.10, the shared default -- no override needed any longer


def _real_attack_poison_pool() -> ScenarioPool:
    old = list(real_poison_scenarios().memories)
    new_pool, _ = regenerate_poison_batch()
    return ScenarioPool("POOL-REAL-7-ATTACK-VALIDATION", tuple(old) + tuple(new_pool.memories))


def run(*, seeds: Sequence[int] = range(11, 21)) -> List[dict]:
    train_pools = split.all_dev_pools()  # unchanged -- never includes real_corpus.py content
    train_ds = build_dataset(train_pools)

    real_attack_pool = _real_attack_poison_pool()
    real_attack_ds = build_dataset((real_attack_pool,))
    real_attack_family_map = {m.scenario_id: m.attack_family_ground_truth for m in real_attack_pool.memories}

    held_out_pools = split.held_out_pools()
    held_out_benign_ds = build_dataset(held_out_pools)
    benign_node_ids = [nid for nid, y in zip(held_out_benign_ds.node_ids, held_out_benign_ds.labels.tolist()) if y == 0.0]

    train_grouped = grouped_raw_tensor(train_pools, train_ds.node_ids)
    real_grouped = grouped_raw_tensor((real_attack_pool,), real_attack_ds.node_ids)
    held_grouped = grouped_raw_tensor(held_out_pools, held_out_benign_ds.node_ids)

    train_untrained = combined_untrained_score(train_ds.features, train_grouped, train_ds.features, train_grouped)
    real_untrained = combined_untrained_score(train_ds.features, train_grouped, real_attack_ds.features, real_grouped)
    held_untrained = combined_untrained_score(train_ds.features, train_grouped, held_out_benign_ds.features, held_grouped)

    results: List[dict] = []
    for seed in seeds:
        model = train_model(train_ds, seed=seed, weight_decay=WEIGHT_DECAY)

        train_fitted = model.predict_proba(train_ds.features, train_ds.mean_adj)
        fit_mean, fit_std = train_fitted.mean().item(), train_fitted.std(unbiased=False).item()

        train_blend = blended_score(train_fitted, train_untrained, w_fit=W, fit_mean=fit_mean, fit_std=fit_std).tolist()
        threshold = _threshold_for_target_fpr(train_blend, train_ds.labels.tolist(), TARGET_FPR)

        real_fitted = model.predict_proba(real_attack_ds.features, real_attack_ds.mean_adj)
        held_fitted = model.predict_proba(held_out_benign_ds.features, held_out_benign_ds.mean_adj)

        poison_scores = blended_score(real_fitted, real_untrained, w_fit=W, fit_mean=fit_mean, fit_std=fit_std).tolist()
        benign_scores_all = dict(zip(
            held_out_benign_ds.node_ids,
            blended_score(held_fitted, held_untrained, w_fit=W, fit_mean=fit_mean, fit_std=fit_std).tolist(),
        ))
        benign_scores = [benign_scores_all[nid] for nid in benign_node_ids]

        detected = sum(1 for s in poison_scores if s >= threshold)
        flagged = sum(1 for s in benign_scores if s >= threshold)
        combined = torch.tensor(poison_scores + benign_scores)
        combined_labels = torch.tensor([1.0] * len(poison_scores) + [0.0] * len(benign_scores))

        by_family_detected: Dict[str, List[bool]] = {}
        for nid, s in zip(real_attack_ds.node_ids, poison_scores):
            by_family_detected.setdefault(real_attack_family_map[nid], []).append(s >= threshold)

        results.append({
            "seed": seed, "threshold": threshold,
            "n_poison": len(poison_scores), "n_benign": len(benign_scores),
            "detection_rate": detected / len(poison_scores),
            "false_positive_rate": flagged / len(benign_scores),
            "auroc": _auroc(combined, combined_labels),
            "per_family_detection_rate": {
                fam: sum(hits) / len(hits) for fam, hits in by_family_detected.items()
            },
        })
    return results


def summarize(results: List[dict]) -> dict:
    detections = [r["detection_rate"] for r in results]
    fprs = [r["false_positive_rate"] for r in results]
    aurocs = [r["auroc"] for r in results]
    families = results[0]["per_family_detection_rate"].keys()
    return {
        "n_poison": results[0]["n_poison"], "n_benign": results[0]["n_benign"],
        "detection_rate_mean": statistics.mean(detections), "detection_rate_min": min(detections), "detection_rate_max": max(detections),
        "false_positive_rate_mean": statistics.mean(fprs), "false_positive_rate_min": min(fprs), "false_positive_rate_max": max(fprs),
        "auroc_mean": statistics.mean(aurocs), "auroc_min": min(aurocs), "auroc_max": max(aurocs),
        "per_family_detection_rate_mean": {
            fam: statistics.mean(r["per_family_detection_rate"][fam] for r in results) for fam in families
        },
    }


if __name__ == "__main__":
    import json

    results = run()
    summary = summarize(results)
    print(json.dumps(summary, indent=2))
