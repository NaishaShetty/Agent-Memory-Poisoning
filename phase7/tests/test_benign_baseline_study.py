"""Phase 7.8 (gap fix) -- tests for run_benign_baseline_study(): the committed,
reproducible entry point behind PHASE7_REPORT.md Sec 2's benign-baseline table.
"""

from __future__ import annotations

import pytest

from phase7.propagation.benign_baseline_study import run_benign_baseline_study


def test_benign_baseline_study_builds_the_reported_five_root_three_child_corpus(tmp_path):
    result = run_benign_baseline_study(storage_dir=tmp_path / "baseline-study")

    assert result.num_roots == 5
    assert result.roots_with_children == ("benign-root-0", "benign-root-2", "benign-root-4")
    # 5 roots + 3 derived children = 8 real seeds, matching the report's own
    # "n=8 real seeds: 5 roots, 3 with one derived child each."
    assert len(result.seed_memory_ids) == 8
    assert result.baseline.fan_out_rate.n == 8


def test_benign_baseline_study_reproduces_the_reported_numbers(tmp_path):
    result = run_benign_baseline_study(storage_dir=tmp_path / "baseline-study")
    b = result.baseline

    assert b.fan_out_rate.mean == pytest.approx(0.375)
    assert b.fan_out_rate.minimum == pytest.approx(0.0)
    assert b.fan_out_rate.maximum == pytest.approx(1.0)

    assert b.re_entry_rate.mean == pytest.approx(0.046875)  # 0.047 rounded in the report's prose
    assert b.re_entry_rate.minimum == pytest.approx(0.0)
    assert b.re_entry_rate.maximum == pytest.approx(0.125)

    assert b.cycle_reinforcement_depth.mean == pytest.approx(0.375)
    assert b.cycle_reinforcement_depth.minimum == pytest.approx(0.0)
    assert b.cycle_reinforcement_depth.maximum == pytest.approx(1.0)

    assert b.cross_task_bleed.mean == pytest.approx(1.375)
    assert b.cross_task_bleed.minimum == pytest.approx(1.0)
    assert b.cross_task_bleed.maximum == pytest.approx(2.0)


def test_benign_baseline_study_is_deterministic(tmp_path):
    r1 = run_benign_baseline_study(storage_dir=tmp_path / "run1")
    r2 = run_benign_baseline_study(storage_dir=tmp_path / "run2")
    assert r1.seed_memory_ids == r2.seed_memory_ids
    assert r1.baseline.fan_out_rate.values == r2.baseline.fan_out_rate.values
    assert r1.baseline.re_entry_rate.values == r2.baseline.re_entry_rate.values
    assert r1.baseline.cycle_reinforcement_depth.values == r2.baseline.cycle_reinforcement_depth.values
    assert r1.baseline.cross_task_bleed.values == r2.baseline.cross_task_bleed.values
