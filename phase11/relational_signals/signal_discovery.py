"""Phase 11.y Section 8 -- signal-DISCOVERY only, isolated from any model
training. Computes simple, auditable metrics (AUROC, effect size, per-family
breakdown) for each candidate signal, using ONLY training-side real data
(`real_corpus.py`'s poison + `real_benign_scenarios()`'s benign, plus one
read-only task-0 diagnostic fetch, per `semantic_relations.py`'s own
disclosure) and the existing dev-time evaluation set for reporting
context. `held_out_pools()` is never referenced.

Run directly: `python -m phase11.relational_signals.signal_discovery`
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from phase11.data.real_corpus import real_benign_scenarios, real_poison_scenarios
from phase11.data.poison_regeneration import regenerate_poison_batch
from phase11.data.clean_expansion import clean_expansion_pools
from phase11.gnn.self_supervised import auroc as _auroc
from phase11.relational_signals.graph_relations import pool_coherence
from phase11.relational_signals.provenance_relations import provenance_format_signal
from phase11.relational_signals.semantic_relations import (
    POISON_SOURCE_TASK_MAP,
    _task0_diagnostic_benign_turns,
    compute_neighborhood_agreement,
)

import torch


def _build_task_neighborhoods() -> Dict[int, List[str]]:
    neighborhoods: Dict[int, List[str]] = {0: _task0_diagnostic_benign_turns()}
    for pool in real_benign_scenarios():
        # pool_id looks like POOL-REAL-CLEAN-... no -- real_corpus.py's own naming:
        # POOL-REAL-BENIGN-LOCOMO-T{task_index}
        task_index = int(pool.pool_id.rsplit("T", 1)[1])
        neighborhoods[task_index] = [m.content_text for m in pool.memories]
    return neighborhoods


def _poison_candidates_with_known_task(poison_memories, minimum_basis="declared"):
    out = []
    for m in poison_memories:
        task_id, basis = POISON_SOURCE_TASK_MAP.get(m.scenario_id, (None, "none"))
        if task_id is None:
            continue
        if minimum_basis == "declared" and basis != "declared":
            continue
        out.append((m, task_id, basis))
    return out


def _benign_self_agreement(task_neighborhoods: Dict[int, List[str]]):
    """Leave-one-out agreement scores for real benign turns themselves,
    against the rest of their own real task's turns -- the fair benign
    comparison distribution for the poison neighborhood-agreement signal."""
    from phase6.defense.orchestration.pipeline import MemoryScenario

    candidates = []
    for task_id, texts in task_neighborhoods.items():
        for i, text in enumerate(texts):
            scenario = MemoryScenario(f"BENIGN-SELF-T{task_id}-{i}", text, is_poison_ground_truth=False)
            candidates.append((scenario, task_id, "declared"))
    return compute_neighborhood_agreement(candidates, task_neighborhoods)


def run_semantic_neighborhood_experiment() -> dict:
    old_poison = list(real_poison_scenarios().memories)
    new_poison_pool, _ = regenerate_poison_batch()
    new_poison = list(new_poison_pool.memories)
    all_poison = old_poison + new_poison

    task_neighborhoods = _build_task_neighborhoods()

    poison_candidates = _poison_candidates_with_known_task(all_poison, minimum_basis="any")
    poison_results = compute_neighborhood_agreement(poison_candidates, task_neighborhoods)
    benign_results = _benign_self_agreement(task_neighborhoods)

    scores = [r.mean_similarity for r in poison_results] + [r.mean_similarity for r in benign_results]
    labels = [1.0] * len(poison_results) + [0.0] * len(benign_results)
    # LOWER agreement is the poison hypothesis -> invert so higher score = more anomalous
    inverted_scores = [1.0 - s for s in scores]
    overall_auroc = _auroc(torch.tensor(inverted_scores), torch.tensor(labels))

    declared_only_poison = [r for r in poison_results if r.task_basis == "declared"]
    declared_scores = [1.0 - r.mean_similarity for r in declared_only_poison] + \
        [1.0 - r.mean_similarity for r in benign_results]
    declared_labels = [1.0] * len(declared_only_poison) + [0.0] * len(benign_results)
    declared_auroc = _auroc(torch.tensor(declared_scores), torch.tensor(declared_labels)) if declared_only_poison else float("nan")

    by_family: Dict[str, List[float]] = {}
    for r in poison_results:
        by_family.setdefault(r.attack_family_ground_truth, []).append(r.mean_similarity)

    return {
        "n_poison_scored": len(poison_results),
        "n_poison_excluded_no_task": len(all_poison) - len(poison_results),
        "n_benign_scored": len(benign_results),
        "poison_mean_agreement": sum(r.mean_similarity for r in poison_results) / len(poison_results),
        "benign_mean_agreement": sum(r.mean_similarity for r in benign_results) / len(benign_results),
        "overall_auroc_all_poison": overall_auroc,
        "overall_auroc_declared_task_only": declared_auroc,
        "n_declared_only": len(declared_only_poison),
        "per_family_mean_agreement": {k: sum(v) / len(v) for k, v in by_family.items()},
        "per_family_n": {k: len(v) for k, v in by_family.items()},
        "poison_results": poison_results,
        "benign_results": benign_results,
    }


def run_graph_coherence_experiment() -> dict:
    old_poison_pool = real_poison_scenarios()
    new_poison_pool, _ = regenerate_poison_batch()
    clean_pools, _ = clean_expansion_pools()
    benign_locomo_pools = real_benign_scenarios()

    def summarize(name, pools):
        all_results = []
        for p in pools:
            all_results.extend(pool_coherence(p))
        valid = [r.coherence for r in all_results if r.coherence == r.coherence]  # filter NaN
        return {
            "name": name, "n_pools": len(pools), "n_scored": len(valid),
            "mean_coherence": sum(valid) / len(valid) if valid else float("nan"),
        }

    return {
        "old_poison_pool": summarize("old_poison_pool (POOL-REAL-POISON-ATTACKS)", [old_poison_pool]),
        "new_poison_pool": summarize("new_poison_pool (POOL-REGEN-POISON-TRACK-B)", [new_poison_pool]),
        "benign_locomo_pools": summarize("real_benign_scenarios (9 per-task pools)", benign_locomo_pools),
        "clean_expansion_pools": summarize("Track A clean pools (30 pools)", clean_pools),
    }


def run_provenance_confound_check() -> dict:
    _, provenance_map = clean_expansion_pools()
    old_poison = list(real_poison_scenarios().memories)
    new_poison_pool, _ = regenerate_poison_batch()
    new_poison = list(new_poison_pool.memories)
    clean_pools, _ = clean_expansion_pools()
    clean_memories = [m for p in clean_pools for m in p.memories]

    all_scenarios = old_poison + new_poison + clean_memories
    results = [provenance_format_signal(s, provenance_map) for s in all_scenarios]

    tp = sum(1 for r in results if r.is_poison_ground_truth and not r.has_real_source_dataset_provenance)
    fn = sum(1 for r in results if r.is_poison_ground_truth and r.has_real_source_dataset_provenance)
    tn = sum(1 for r in results if not r.is_poison_ground_truth and r.has_real_source_dataset_provenance)
    fp = sum(1 for r in results if not r.is_poison_ground_truth and not r.has_real_source_dataset_provenance)

    detection_rate = tp / (tp + fn) if (tp + fn) else float("nan")
    fpr = fp / (fp + tn) if (fp + tn) else float("nan")
    return {"detection_rate": detection_rate, "false_positive_rate": fpr, "n_poison": tp + fn, "n_benign": tn + fp}


if __name__ == "__main__":
    import json

    print("=== Semantic neighborhood-agreement experiment ===")
    sem = run_semantic_neighborhood_experiment()
    print(f"n_poison_scored={sem['n_poison_scored']} (excluded, no real task={sem['n_poison_excluded_no_task']}) "
          f"n_benign_scored={sem['n_benign_scored']}")
    print(f"poison mean agreement={sem['poison_mean_agreement']:.4f}  benign mean agreement={sem['benign_mean_agreement']:.4f}")
    print(f"overall AUROC (all poison, weak+declared task basis)={sem['overall_auroc_all_poison']:.4f}")
    print(f"overall AUROC (declared-task-only poison, n={sem['n_declared_only']})={sem['overall_auroc_declared_task_only']:.4f}")
    print("per-family mean agreement:", json.dumps(sem["per_family_mean_agreement"], indent=2))
    print("per-family n:", sem["per_family_n"])

    print("\n=== Graph neighborhood-coherence experiment ===")
    coh = run_graph_coherence_experiment()
    for k, v in coh.items():
        print(f"  {v['name']}: n_pools={v['n_pools']} n_scored={v['n_scored']} mean_coherence={v['mean_coherence']:.4f}")

    print("\n=== Provenance-format confound check ===")
    prov = run_provenance_confound_check()
    print(prov)
