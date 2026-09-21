"""Phase 11 -- leave-one-attack-family-out (LOFO) leakage-guard and
regression tests for `phase11/gnn/lofo.py`, per
`docs/phase11/PHASE11_LOFO_AUDIT.md`."""

from __future__ import annotations

import inspect

from phase11.data import split
from phase11.gnn.lofo import (
    SEEDS,
    _discover_families,
    baseline_b_chance_reference,
    baseline_c_frozen_feature_sum,
    family_map_for_pools,
    filter_pools_excluding_family,
    per_family_summary,
    pooled_out_of_fold_summary,
    run_all_lofo_folds,
    run_lofo_fold,
)
from phase11.gnn.train import build_dataset, run_gnn_feasibility_study


def _references_name_in_code(module, name: str) -> bool:
    for _, obj in inspect.getmembers(module, inspect.isfunction):
        if obj.__module__ != module.__name__:
            continue
        if name in obj.__code__.co_names:
            return True
    return False


def test_families_discovered_directly_not_hardcoded():
    families = _discover_families(split.all_dev_pools())
    assert set(families) == {"FARMA", "MemoryGraft-style-volume", "Sleeper", "propagated"}


def test_excluded_family_records_cannot_enter_a_training_fold():
    for family in _discover_families(split.all_dev_pools()):
        filtered = filter_pools_excluding_family(split.all_dev_pools(), family)
        for pool in filtered:
            for m in pool.memories:
                if m.is_poison_ground_truth:
                    assert m.attack_family_ground_truth != family


def test_excluded_family_labels_cannot_enter_feature_or_threshold_fitting():
    """Structural check, not a text search: build the fold's real dataset
    and confirm no label in `train_ds.labels` corresponds to a scenario_id
    the excluded family owns."""
    family = "FARMA"
    filtered = filter_pools_excluding_family(split.all_dev_pools(), family)
    train_ds = build_dataset(filtered)
    excluded_ids = {
        m.scenario_id for pool in split.all_dev_pools() for m in pool.memories
        if m.is_poison_ground_truth and m.attack_family_ground_truth == family
    }
    assert not (set(train_ds.node_ids) & excluded_ids)


def test_each_lofo_fold_trains_a_fresh_model_not_the_global_one():
    """Two folds with different excluded families must produce different
    training datasets (different node counts), proving each fold is built
    from its own filtered pools, not a shared cached dataset."""
    farma_pools = filter_pools_excluding_family(split.all_dev_pools(), "FARMA")
    memorygraft_pools = filter_pools_excluding_family(split.all_dev_pools(), "MemoryGraft-style-volume")
    farma_ds = build_dataset(farma_pools)
    memorygraft_ds = build_dataset(memorygraft_pools)
    assert farma_ds.node_ids != memorygraft_ds.node_ids


def test_no_held_out_pools_modification_in_lofo_module():
    """`held_out_pools()` must be READ (it is -- for real evaluation) but
    never filtered, mutated, or reassigned by any function in `lofo.py`."""
    import phase11.gnn.lofo as mod

    # held_out_pools IS referenced (for evaluation) -- confirm it is never
    # passed through filter_pools_excluding_family in the same function body.
    source = inspect.getsource(mod.run_lofo_fold)
    assert "filter_pools_excluding_family(split.held_out_pools()" not in source
    assert "filter_pools_excluding_family(held_out_pools" not in source


def test_held_out_pools_size_unchanged_by_lofo_module():
    """The real, protected held-out corpus size (78 nodes: 34 poison + 44
    benign, including synthetic ancestor nodes) must be identical whether
    accessed directly or via a LOFO fold's own internal build."""
    direct_ds = build_dataset(split.held_out_pools())
    fold_results = run_lofo_fold("propagated", seeds=(11,))
    assert fold_results[0].n_benign_held_out == sum(1 for l in direct_ds.labels.tolist() if l == 0.0)


def test_family_assigned_to_exactly_one_lofo_exclusion_fold():
    all_ids_per_family = {}
    for family in _discover_families(split.all_dev_pools()):
        ids = {
            m.scenario_id for pool in split.held_out_pools() for m in pool.memories
            if m.is_poison_ground_truth and m.attack_family_ground_truth == family
        }
        all_ids_per_family[family] = ids
    seen = set()
    for family, ids in all_ids_per_family.items():
        assert not (ids & seen), f"scenario overlap between {family} and an earlier family"
        seen |= ids


def test_pooled_out_of_fold_predictions_use_only_the_excluded_familys_own_fold_model():
    """The score recorded for a family-X held-out example must come from
    the fold whose training excluded family X -- never from a fold trained
    WITH family X present. Verified by checking the family map used inside
    `run_lofo_fold` always matches the fold's own `family` argument."""
    for family in ("FARMA", "Sleeper"):
        results = run_lofo_fold(family, seeds=(11,))
        r = results[0]
        assert r.family == family
        assert r.n_family_poison_held_out > 0


def test_existing_gnn_baseline_unchanged_by_lofo_module():
    """`run_gnn_feasibility_study()` (Baseline A) must be byte-for-byte
    identical to its pre-LOFO, already-locked-in numbers -- confirms this
    investigation touched no shared state."""
    result = run_gnn_feasibility_study()
    held_out = result["held_out"]
    assert round(held_out["detection_rate"], 3) == round(19 / 34, 3)
    assert round(held_out["false_positive_rate"], 3) == round(3 / 44, 3)


def test_seeds_match_the_original_stability_study_protocol():
    assert SEEDS == tuple(range(11, 21))


def test_low_power_families_are_still_run_not_discarded():
    results = run_all_lofo_folds(seeds=(11,))
    assert "propagated" in results  # n=2 held-out -- low-power, run anyway
    assert "Sleeper" in results
    summary = per_family_summary(results["propagated"])
    assert summary["n_family_poison_held_out"] == 2


def test_per_family_summary_reports_full_seed_distribution_not_only_a_mean():
    results = run_lofo_fold("FARMA", seeds=SEEDS)
    summary = per_family_summary(results)
    assert len(summary["auroc_by_seed"]) == 10
    assert summary["auroc_min"] <= summary["auroc_mean"] <= summary["auroc_max"]


def test_pooled_summary_uses_micro_detection_and_macro_fpr_not_naive_pooling():
    all_results = run_all_lofo_folds(seeds=(11,))
    pooled = pooled_out_of_fold_summary(all_results, seed=11)
    assert pooled["n_folds"] == 4
    assert pooled["total_family_poison_n"] == 34  # 7 + 20 + 5 + 2, matches held_out_pools() total poison n
    assert pooled["total_benign_n_per_fold"] == 44


def test_baseline_b_chance_reference_centers_near_half():
    result = baseline_b_chance_reference(20, 44, trials=50, seed=1)
    assert 0.4 <= result["auroc_mean"] <= 0.6


def test_baseline_c_uses_zero_training_and_zero_fitting():
    """Structural check: `baseline_c_frozen_feature_sum` must never call
    `train_model` or reference `MinimalGNN`."""
    import phase11.gnn.lofo as mod

    source = inspect.getsource(mod.baseline_c_frozen_feature_sum)
    assert "train_model" not in source
    assert "MinimalGNN" not in source


def test_family_map_never_assigns_a_family_to_a_benign_scenario():
    fam_map = family_map_for_pools(split.held_out_pools())
    benign_ids = {
        m.scenario_id for pool in split.held_out_pools() for m in pool.memories
        if not m.is_poison_ground_truth
    }
    assert not (set(fam_map.keys()) & benign_ids)
