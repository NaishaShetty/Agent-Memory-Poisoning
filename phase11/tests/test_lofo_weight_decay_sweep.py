"""Phase 11 -- regression tests for the LOFO-objective weight-decay sweep
(`phase11/gnn/lofo_weight_decay_sweep.py`) and the additive, backward-
compatible `weight_decay` parameter it required on `train_model()`/
`run_lofo_fold()`."""

from __future__ import annotations

from phase11.data import split
from phase11.gnn.lofo import build_dataset, run_lofo_fold
from phase11.gnn.lofo_weight_decay_sweep import (
    WEIGHT_DECAY_VALUES,
    macro_auroc_by_weight_decay,
    run_weight_decay_sweep,
)
from phase11.gnn.train import WEIGHT_DECAY, run_gnn_feasibility_study, train_model


def test_train_model_default_weight_decay_behavior_unchanged():
    """The additive `weight_decay` parameter must default to the exact
    pre-existing module constant -- calling `train_model()` with no
    `weight_decay` argument must be identical to before this change."""
    ds = build_dataset(split.all_dev_pools())
    m1 = train_model(ds, seed=11)
    m2 = train_model(ds, seed=11, weight_decay=WEIGHT_DECAY)
    for p1, p2 in zip(m1.parameters(), m2.parameters()):
        assert (p1 == p2).all()


def test_run_gnn_feasibility_study_unchanged_by_the_weight_decay_parameter():
    result = run_gnn_feasibility_study()
    held_out = result["held_out"]
    assert round(held_out["detection_rate"], 3) == round(19 / 34, 3)
    assert round(held_out["false_positive_rate"], 3) == round(3 / 44, 3)


def test_run_lofo_fold_with_none_weight_decay_matches_default():
    r1 = run_lofo_fold("propagated", seeds=(11,))
    r2 = run_lofo_fold("propagated", seeds=(11,), weight_decay=None)
    assert r1[0] == r2[0]


def test_run_lofo_fold_explicit_weight_decay_differs_from_default():
    baseline = run_lofo_fold("FARMA", seeds=(11,))[0]
    regularized = run_lofo_fold("FARMA", seeds=(11,), weight_decay=0.005)[0]
    assert baseline.auroc != regularized.auroc


def test_sweep_reuses_the_exact_original_six_weight_decay_values():
    assert WEIGHT_DECAY_VALUES == (0.0, 0.001, 0.005, 0.01, 0.02, 0.05)


def test_sweep_covers_all_four_families_at_every_weight_decay():
    sweep = run_weight_decay_sweep(weight_decay_values=(0.0, 0.005), seeds=(11,))
    for wd, per_family in sweep.items():
        assert set(per_family.keys()) == {"FARMA", "MemoryGraft-style-volume", "Sleeper", "propagated"}


def test_macro_auroc_by_weight_decay_is_a_descriptive_secondary_statistic():
    sweep = run_weight_decay_sweep(weight_decay_values=(0.0, 0.005), seeds=(11,))
    macro = macro_auroc_by_weight_decay(sweep)
    assert set(macro.keys()) == {0.0, 0.005}
    for v in macro.values():
        assert 0.0 <= v <= 1.0
