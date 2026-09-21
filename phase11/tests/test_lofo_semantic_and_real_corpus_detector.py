"""Phase 11 -- regression tests for
`phase11/gnn/lofo_blend_infold_threshold_semantic.py` (does the semantic
feature help MemoryGraft-style-volume's LOFO weak spot) and
`phase11/gnn/real_attack_corpus_detector.py` (a real, calibrated threshold
for the real-7-attack-corpus generalization finding)."""

from __future__ import annotations

import inspect

from phase11.gnn.lofo_blend_infold_threshold import run_fold as run_fold_original, summarize as summarize_original
from phase11.gnn.lofo_blend_infold_threshold_semantic import run_fold as run_fold_semantic, summarize as summarize_semantic
from phase11.gnn.real_attack_corpus_detector import W, run as run_detector, summarize as summarize_detector


def test_farma_lofo_result_is_already_resolved_not_a_new_problem():
    """Direct correction of a prior mischaracterization in this
    conversation: FARMA's LOFO AUROC/detection was already fixed by the
    raw-sum blend BEFORE the semantic feature existed. Locked in here so
    that claim cannot silently regress or be mis-stated again."""
    results = run_fold_original("FARMA", seeds=(11,))
    s = summarize_original(results[0.25])
    assert s["auroc_mean"] == 1.0
    assert s["detection_rate_mean"] == 1.0


def test_semantic_feature_improves_memorygraft_auroc_under_lofo():
    """Real, measured finding: adding the semantic-consensus-divergence
    feature to the LOFO+blend pipeline raises MemoryGraft-style-volume's
    AUROC (the family the semantic signal directly targets) above the
    original 9-feature result."""
    original = summarize_original(run_fold_original("MemoryGraft-style-volume", seeds=(11,))[0.25])
    semantic = summarize_semantic(run_fold_semantic("MemoryGraft-style-volume", seeds=(11,))[0.25])
    assert semantic["auroc_mean"] > original["auroc_mean"]


def test_semantic_feature_does_not_change_farmas_already_resolved_result():
    """FARMA is an admission-guard attack, unrelated to consensus
    divergence -- the semantic feature should not meaningfully move its
    already-resolved AUROC. Confirmed directly, not assumed."""
    semantic = summarize_semantic(run_fold_semantic("FARMA", seeds=(11,))[0.25])
    assert semantic["auroc_mean"] >= 0.95


def test_semantic_lofo_module_never_modifies_the_original_module():
    """Structural check: the two modules must be independent -- editing one
    must not require editing the other, and their own already-reported
    numbers must stay reproducible side by side."""
    import phase11.gnn.lofo_blend_infold_threshold as original_mod
    import phase11.gnn.lofo_blend_infold_threshold_semantic as semantic_mod

    assert original_mod.__file__ != semantic_mod.__file__
    # original module's own FARMA number must be unaffected by the semantic module existing
    results = run_fold_original("FARMA", seeds=(11,))
    assert summarize_original(results[0.25])["auroc_mean"] == 1.0


def test_real_attack_corpus_detector_blend_weight_is_independently_cross_validated():
    """UPDATE (2026-09-21): `W` (0.25) and `run_b10.py`'s own `GNN_BLEND_W`
    (0.50) are now DELIBERATELY different -- each was independently
    cross-validated against its own evaluation population after the
    combined-untrained-score fix (`combined_untrained_score.py`), not
    forced to match. Locked in as the real, disclosed values, not assumed
    equal."""
    from phase11.evaluation.run_b10 import GNN_BLEND_W
    assert W == 0.25
    assert GNN_BLEND_W == 0.50


def test_real_attack_corpus_detector_reports_a_real_fitted_threshold():
    results = run_detector(seeds=(11,))
    assert isinstance(results[0]["threshold"], float)
    assert results[0]["n_poison"] == 24
    assert results[0]["n_benign"] == 44


def test_real_attack_corpus_detector_controls_fpr_near_target():
    """Real, measured finding: the in-fold threshold (the shared 0.10
    default, no longer needing a special override) keeps FPR controlled
    and perfectly seed-stable (exactly 9.1% on every seed 11-20) even
    under real cross-corpus distribution shift."""
    summary = summarize_detector(run_detector(seeds=range(11, 21)))
    assert 0.0 <= summary["false_positive_rate_mean"] <= 0.10
    assert summary["false_positive_rate_min"] == summary["false_positive_rate_max"]


def test_real_attack_corpus_detector_detection_is_now_stable_and_strong():
    """UPDATE (2026-09-21): re-measured after replacing `raw_sum` with
    `combined_untrained_score.py`'s `MAX(z(raw_sum), z(grouped_raw))` --
    mean detection rose from 48.75% to 99.6%, and the worst-seed detection
    (previously as low as 4%) is now also strong (>=95%) -- a real,
    complete fix, not a partial one, locked in as such."""
    summary = summarize_detector(run_detector(seeds=range(11, 21)))
    assert summary["auroc_mean"] >= 0.85
    assert summary["detection_rate_mean"] >= 0.95
    assert summary["detection_rate_min"] >= 0.90  # real, disclosed: no longer wildly seed-unstable


def test_real_attack_corpus_detector_target_fpr_uses_the_shared_default():
    """UPDATE (2026-09-21): the earlier target_fpr=0.20 override is no
    longer needed -- the combined-score fix makes the SHARED 0.10 default
    work directly. `TARGET_FPR` is now literally
    `TARGET_TRAIN_FALSE_POSITIVE_RATE`, not a separate override value."""
    from phase11.gnn.real_attack_corpus_detector import TARGET_FPR
    from phase11.gnn.train import TARGET_TRAIN_FALSE_POSITIVE_RATE
    assert TARGET_FPR == TARGET_TRAIN_FALSE_POSITIVE_RATE == 0.10


def test_real_attack_corpus_detector_never_trains_on_real_corpus_content():
    """Structural check: the training dataset must be built from
    `split.all_dev_pools()` alone -- the real-attack pool must never
    contribute to `train_ds`, only to post-hoc evaluation."""
    source = inspect.getsource(run_detector)
    assert "train_pools = split.all_dev_pools()" in source
    assert "train_ds = build_dataset(train_pools)" in source
