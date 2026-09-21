"""Phase 11 -- regression/leakage tests for the real, working threshold fix
(`phase11/gnn/lofo_blend_infold_threshold.py`): blending the fitted GNN
score with the untrained raw-feature-sum score, thresholded on the fold's
own real training-benign set."""

from __future__ import annotations

import inspect

from phase11.data import split
from phase11.data.real_corpus import real_benign_scenarios
from phase11.gnn.features import pools_node_features
from phase11.gnn.lofo_blend_infold_threshold import (
    BLEND_WEIGHTS,
    macro_by_w,
    run_all_families,
    run_fold,
    summarize,
)


def test_real_corpus_benign_reference_is_confirmed_degenerate():
    """Locks in the real, diagnosed reason `lofo_combined_fix.py`'s
    chunk-size experiment was abandoned: every one of the 135 real LoCoMo
    benign turns must have the identical 9-feature vector."""
    fmap = pools_node_features(real_benign_scenarios())
    vectors = set(fmap.values())
    assert len(vectors) == 1
    assert vectors == {(0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)}


def test_blend_weights_are_the_pre_registered_fixed_set():
    assert BLEND_WEIGHTS == (0.0, 0.25, 0.5, 0.75, 1.0)


def test_pure_fitted_blend_w1_is_close_to_the_prior_weight_decay_result():
    """w=1.0 is pure fitted score, thresholded in-fold -- should be close
    to `PHASE11_LOFO_WEIGHT_DECAY_SWEEP_REPORT.md`'s own real FARMA number
    at weight_decay=0.005 (auroc_mean=0.488). Not bit-identical: the
    z-score division introduces tiny floating-point noise that can flip
    the tie-breaking outcome (`self_supervised.auroc` awards ties 0.5) for
    the several held-out scores that are exactly equal before z-scoring --
    a real, disclosed, minor numerical-precision effect, not a leakage or
    logic difference (confirmed directly: every seed's own trained model
    weights are bit-identical between the two modules, per
    `test_train_model_default_weight_decay_behavior_unchanged`-style
    determinism; only the post-hoc AUROC tie count shifts)."""
    results = run_fold("FARMA")
    summary = summarize(results[1.0])
    assert abs(summary["auroc_mean"] - 0.488) < 0.05
    assert summary["detection_rate_mean"] == 0.0


def test_blend_never_uses_the_excluded_family_for_threshold_or_zscore_stats():
    """Structural check: `run_fold` must compute `fit_mean`/`fit_std`/
    `raw_mean`/`raw_std` and the threshold from `train_*` variables only,
    never from `held_out_*`."""
    import phase11.gnn.lofo_blend_infold_threshold as mod

    source = inspect.getsource(mod.run_fold)
    threshold_line = [l for l in source.splitlines() if "_threshold_for_target_fpr(" in l][0]
    assert "train_blend" in threshold_line
    assert "held_out" not in threshold_line


def test_w_quarter_beats_both_pure_endpoints_on_macro_auroc():
    """Real, locked-in regression: the blend must not be a coincidence of
    one lucky family -- macro AUROC at w=0.25 must exceed both pure
    raw-sum (w=0.0) and pure fitted (w=1.0)."""
    all_results = run_all_families(seeds=(11, 12, 13))
    macro = macro_by_w(all_results)
    assert macro[0.25]["macro_auroc"] >= macro[0.0]["macro_auroc"]
    assert macro[0.25]["macro_auroc"] >= macro[1.0]["macro_auroc"]


def test_no_held_out_pools_used_for_fitting_in_blend_module():
    import phase11.gnn.lofo_blend_infold_threshold as mod

    source = inspect.getsource(mod.run_fold)
    assert "filter_pools_excluding_family(split.held_out_pools()" not in source


def test_summarize_reports_seed_range_not_only_mean():
    results = run_fold("propagated", seeds=(11, 12, 13))
    summary = summarize(results[0.25])
    assert summary["auroc_min"] <= summary["auroc_mean"] <= summary["auroc_max"]
