"""Phase 11 -- validating the blend fix against Phase 11.z's real 7-attack
corpus (`real_corpus.py`), not just the hand-authored 4-family ablation
corpus every prior LOFO/blend investigation used. The pooled-family GNN
(trained on `all_dev_pools()` alone, exactly as `run_b10.py` already does)
has NEVER been trained on any `real_corpus.py` content -- so scoring its
24 real poison examples (from all 7 real Phase 4 attacks: DSRM, FARMA,
MPBench-PCFI, MemoryGraft, Sleeper, AgentPoison, MINJA) is a genuine,
clean generalization test, complementary to the LOFO investigation (which
only tested the 4 families the ablation corpus itself contains).

NEGATIVE CLASS: the same 44-node `held_out_pools()` benign reference every
other Phase 11 report already uses -- NOT `real_benign_scenarios()`
(confirmed degenerate for the raw-feature component,
`PHASE11_LOFO_FPR_AND_FARMA_FIX_REPORT.md` Section 2) and not a corpus this
model was ever trained on either way.
"""

from __future__ import annotations

import statistics
from typing import Dict, List, Sequence

import torch

from phase11.data import split
from phase11.data.poison_regeneration import regenerate_poison_batch
from phase11.data.real_corpus import real_poison_scenarios
from phase11.gnn.blend_pooled_family import BLEND_WEIGHTS, WEIGHT_DECAY, blended_score, build_dataset, _raw_sum
from phase11.gnn.self_supervised import auroc as _auroc
from phase11.gnn.train import train_model
from phase6.defense.orchestration.pipeline import ScenarioPool


def _real_attack_poison_pool() -> ScenarioPool:
    old = list(real_poison_scenarios().memories)
    new_pool, _ = regenerate_poison_batch()
    return ScenarioPool("POOL-REAL-7-ATTACK-VALIDATION", tuple(old) + tuple(new_pool.memories))


def run(*, seeds: Sequence[int] = range(11, 21), weight_decay: float = WEIGHT_DECAY) -> Dict[float, List[dict]]:
    train_pools = split.all_dev_pools()  # unchanged -- never includes real_corpus.py content
    train_ds = build_dataset(train_pools)

    real_attack_pool = _real_attack_poison_pool()
    real_attack_ds = build_dataset((real_attack_pool,))
    real_attack_family_map = {
        m.scenario_id: m.attack_family_ground_truth for m in real_attack_pool.memories
    }

    held_out_benign_ds = build_dataset(split.held_out_pools())
    benign_node_ids = [nid for nid, y in zip(held_out_benign_ds.node_ids, held_out_benign_ds.labels.tolist()) if y == 0.0]

    results: Dict[float, List[dict]] = {w: [] for w in BLEND_WEIGHTS}
    for seed in seeds:
        model = train_model(train_ds, seed=seed, weight_decay=weight_decay)

        train_fitted = model.predict_proba(train_ds.features, train_ds.mean_adj)
        train_raw = _raw_sum(train_ds.features)
        fit_mean, fit_std = train_fitted.mean().item(), train_fitted.std(unbiased=False).item()
        raw_mean, raw_std = train_raw.mean().item(), train_raw.std(unbiased=False).item()

        benign_blend_by_w = {}
        real_attack_blend_by_w = {}
        for w in BLEND_WEIGHTS:
            benign_blend_by_w[w] = dict(zip(
                held_out_benign_ds.node_ids,
                blended_score(model, held_out_benign_ds, w=w, fit_mean=fit_mean, fit_std=fit_std, raw_mean=raw_mean, raw_std=raw_std),
            ))
            real_attack_blend_by_w[w] = dict(zip(
                real_attack_ds.node_ids,
                blended_score(model, real_attack_ds, w=w, fit_mean=fit_mean, fit_std=fit_std, raw_mean=raw_mean, raw_std=raw_std),
            ))

        for w in BLEND_WEIGHTS:
            poison_scores = [real_attack_blend_by_w[w][nid] for nid in real_attack_ds.node_ids]
            benign_scores = [benign_blend_by_w[w][nid] for nid in benign_node_ids]
            combined = torch.tensor(poison_scores + benign_scores)
            combined_labels = torch.tensor([1.0] * len(poison_scores) + [0.0] * len(benign_scores))
            auroc = _auroc(combined, combined_labels)

            by_family: Dict[str, List[float]] = {}
            for nid, s in zip(real_attack_ds.node_ids, poison_scores):
                by_family.setdefault(real_attack_family_map[nid], []).append(s)

            results[w].append({
                "seed": seed, "w": w, "auroc": auroc,
                "n_poison": len(poison_scores), "n_benign": len(benign_scores),
                "by_family_mean_score": {k: statistics.mean(v) for k, v in by_family.items()},
            })
    return results


def summarize(results: List[dict]) -> dict:
    aurocs = [r["auroc"] for r in results]
    return {
        "w": results[0]["w"], "n_poison": results[0]["n_poison"], "n_benign": results[0]["n_benign"],
        "auroc_mean": statistics.mean(aurocs), "auroc_min": min(aurocs), "auroc_max": max(aurocs),
    }


if __name__ == "__main__":
    results = run()
    print("=== Real 7-attack corpus, blend AUROC by w (weight_decay=0.005) ===")
    for w in BLEND_WEIGHTS:
        s = summarize(results[w])
        print(f"w={w:.2f}  auroc_mean={s['auroc_mean']:.4f} [{s['auroc_min']:.4f}, {s['auroc_max']:.4f}]  "
              f"n_poison={s['n_poison']} n_benign={s['n_benign']}")

    print("\n=== Per-family mean score at w=0.25, seed=11 ===")
    for r in results[0.25]:
        if r["seed"] == 11:
            for fam, mean_score in sorted(r["by_family_mean_score"].items()):
                print(f"  {fam}: {mean_score:.4f}")
