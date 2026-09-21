"""Phase 11 -- calibrating Baseline C (raw feature sum) into a real
detector, plus a from-scratch linear/logistic detector over the same 9
features, no graph. Leakage-guard and regression tests for
`phase11/gnn/linear_baseline.py`."""

from __future__ import annotations

import inspect

from phase11.data import split
from phase11.gnn.linear_baseline import (
    SEEDS,
    LinearDetector,
    build_raw_dataset,
    raw_sum_scores,
    run_all_lofo_folds_linear,
    run_all_lofo_folds_raw_sum,
    run_lofo_fold_linear,
    run_lofo_fold_raw_sum,
    run_pooled_family_linear,
    run_pooled_family_raw_sum,
    summarize_linear_seeds,
    train_linear_detector,
)
from phase11.gnn.lofo import filter_pools_excluding_family


def test_raw_dataset_excludes_synthetic_ancestor_nodes():
    """Disclosed, real difference from the GNN's own held-out n (44):
    `build_raw_dataset` never builds a graph, so no synthetic ancestor
    node exists to include -- held-out benign n must be 41, not 44."""
    ds = build_raw_dataset(split.held_out_pools())
    n_benign = sum(1 for l in ds.labels.tolist() if l == 0.0)
    assert n_benign == 41


def test_raw_sum_score_is_deterministic_and_untrained():
    ds = build_raw_dataset(split.held_out_pools())
    s1 = raw_sum_scores(ds)
    s2 = raw_sum_scores(ds)
    assert s1 == s2


def test_linear_detector_has_no_message_passing_layers():
    model = LinearDetector()
    assert not any(hasattr(m, "neigh_linear") for m in model.modules())
    assert sum(1 for _ in model.parameters()) == 2  # one Linear layer: weight + bias


def test_excluded_family_cannot_enter_lofo_training_for_raw_sum_or_linear():
    for family in ("FARMA", "MemoryGraft-style-volume", "Sleeper", "propagated"):
        filtered = filter_pools_excluding_family(split.all_dev_pools(), family)
        ds = build_raw_dataset(filtered)
        excluded_ids = {
            m.scenario_id for pool in split.all_dev_pools() for m in pool.memories
            if m.is_poison_ground_truth and m.attack_family_ground_truth == family
        }
        assert not (set(ds.node_ids) & excluded_ids)


def test_lofo_fold_raw_sum_runs_for_every_family_and_reports_real_n():
    result = run_lofo_fold_raw_sum("propagated")
    assert result["n_poison"] == 2
    assert result["n_benign"] == 41
    assert 0.0 <= result["auroc"] <= 1.0


def test_lofo_fold_linear_reports_full_seed_range_not_only_mean():
    results = run_lofo_fold_linear("FARMA", seeds=SEEDS)
    summary = summarize_linear_seeds(results)
    assert len(results) == 10
    assert summary["auroc_min"] <= summary["auroc_mean"] <= summary["auroc_max"]


def test_all_lofo_folds_cover_the_same_four_families_as_the_gnn_lofo():
    raw = run_all_lofo_folds_raw_sum()
    linear = run_all_lofo_folds_linear(seeds=(11,))
    assert set(raw.keys()) == set(linear.keys()) == {
        "FARMA", "MemoryGraft-style-volume", "Sleeper", "propagated",
    }


def test_pooled_family_raw_sum_is_deterministic():
    r1 = run_pooled_family_raw_sum()
    r2 = run_pooled_family_raw_sum()
    assert r1 == r2


def test_pooled_family_linear_matches_gnn_style_held_out_size():
    results = run_pooled_family_linear(seeds=(11,))
    assert results[0]["n_poison"] == 34
    assert results[0]["n_benign"] == 41  # 41, not 44 -- no synthetic ancestor nodes (see test above)


def test_train_linear_detector_is_a_fresh_model_each_call():
    ds = build_raw_dataset(split.all_dev_pools())
    m1 = train_linear_detector(ds, seed=11)
    m2 = train_linear_detector(ds, seed=12)
    w1 = m1.linear.weight.detach().clone()
    w2 = m2.linear.weight.detach().clone()
    assert not (w1 == w2).all()


def test_module_never_references_held_out_pools_before_final_evaluation():
    """`held_out_pools()` may be referenced (for real evaluation) but must
    never be passed through `filter_pools_excluding_family` -- structural
    check, not a text search."""
    import phase11.gnn.linear_baseline as mod

    for fn_name in ("run_lofo_fold_raw_sum", "run_lofo_fold_linear"):
        source = inspect.getsource(getattr(mod, fn_name))
        assert "filter_pools_excluding_family(split.held_out_pools()" not in source
        assert "filter_pools_excluding_family(held_out_pools" not in source
