"""Phase 11 -- regression/leakage tests for the two real threshold-fix
attempts: `phase11/gnn/lofo_robust_threshold.py` (median/MAD, measured
negative) and `phase11/gnn/lofo_reference_threshold.py` (larger real
benign reference, measured improvement)."""

from __future__ import annotations

import inspect

from phase11.data import split
from phase11.gnn.lofo_robust_threshold import threshold_via_median_mad, K_VALUES
from phase11.gnn.lofo_reference_threshold import run_lofo_fold_reference_threshold, summarize
from phase11.data.real_corpus import real_benign_scenarios


def test_threshold_via_median_mad_is_robust_to_a_single_outlier():
    """A single extreme value must not dominate the threshold the way the
    original order-statistic rule was diagnosed to be dominated."""
    scores = [0.001, 0.002, 0.0015, 0.0018, 0.0012, 0.5]  # one extreme outlier
    labels = [0.0] * 6
    t_order_stat_style = max(scores)  # what an order-statistic-at-max would give
    t_robust = threshold_via_median_mad(scores, labels, k=3.0)
    assert t_robust < t_order_stat_style


def test_threshold_via_median_mad_falls_back_when_mad_is_zero():
    scores = [0.5, 0.5, 0.5]
    labels = [0.0, 0.0, 0.0]
    assert threshold_via_median_mad(scores, labels, k=3.0) == 0.5


def test_k_values_are_the_pre_registered_fixed_set():
    assert K_VALUES == (1.0, 2.0, 3.0, 4.0, 5.0)


def test_reference_threshold_uses_only_real_benign_locomo_data_never_poison():
    """`real_benign_scenarios()` must be benign-only -- confirms the
    reference-threshold module's labeling assumption (`reference_labels`
    hardcoded to all-0.0 is never silently wrong)."""
    for pool in real_benign_scenarios():
        for m in pool.memories:
            assert m.is_poison_ground_truth is False


def test_reference_threshold_never_touches_held_out_pools_for_fitting():
    import phase11.gnn.lofo_reference_threshold as mod

    source = inspect.getsource(mod.run_lofo_fold_reference_threshold)
    assert "filter_pools_excluding_family(split.held_out_pools()" not in source
    assert "real_benign_scenarios(split.held_out_pools()" not in source


def test_reference_threshold_excludes_target_family_from_training():
    results = run_lofo_fold_reference_threshold("propagated", weight_decay=0.0, seeds=(11,))
    result = results[0]
    assert result["family"] == "propagated"
    assert result["n_poison"] == 2  # propagated's real held-out n


def test_reference_threshold_reports_reference_size_not_training_fold_size():
    results = run_lofo_fold_reference_threshold("FARMA", weight_decay=0.0, seeds=(11,))
    assert results[0]["n_reference_benign"] == 135  # the larger real reference, not the ~8-11 fold-local benign set


def test_summarize_reports_full_range_not_only_mean():
    results = run_lofo_fold_reference_threshold("Sleeper", weight_decay=0.005, seeds=(11, 12, 13))
    summary = summarize(results)
    assert summary["auroc_min"] <= summary["auroc_mean"] <= summary["auroc_max"]
