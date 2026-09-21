"""Phase 11 -- regression tests for `phase11/gln/lofo_gln.py`."""

from __future__ import annotations

import inspect

from phase11.gln.lofo_gln import baseline_pooled_family, run_all_families, run_lofo_fold


def test_gln_lofo_covers_the_same_four_families_as_the_gnn_lofo():
    results = run_all_families()
    assert set(results.keys()) == {"FARMA", "MemoryGraft-style-volume", "Sleeper", "propagated"}


def test_gln_lofo_never_updates_weights_on_the_excluded_family():
    """Structural check: the held-out scoring loop must call `model.predict`
    (inference only), never `model.predict_and_update`."""
    source = inspect.getsource(run_lofo_fold)
    held_out_section = source.split("for stream in held_out_streams:")[1]
    assert "predict_and_update" not in held_out_section
    assert "model.predict(" in held_out_section


def test_gln_lofo_reports_real_n_and_valid_auroc():
    result = run_lofo_fold("propagated")
    assert result["n_poison"] == 2
    assert 0.0 <= result["auroc"] <= 1.0


def test_gln_pooled_family_baseline_covers_all_families_present_in_held_out():
    pooled = baseline_pooled_family()
    assert set(pooled.keys()) == {"FARMA", "MemoryGraft-style-volume", "Sleeper", "propagated"}
    for family, r in pooled.items():
        assert 0.0 <= r["auroc"] <= 1.0


def test_gln_lofo_locks_in_the_real_measured_sleeper_collapse():
    """Real, measured finding: Sleeper's GLN zero-shot AUROC collapses to
    exactly 0.0 under LOFO (every benign example outscores the single real
    Sleeper poison example) -- locked in as a regression, not smoothed
    over."""
    result = run_lofo_fold("Sleeper")
    assert result["auroc"] == 0.0
