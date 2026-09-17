"""Phase 7.10 -- tests for minja_study.py: a real MINJA-specific crowding
study, closing part of Report Limitation 5.2 for this attack (see module
docstring for why a cluster footprint, not a generic proxy chain, is used).
"""

from __future__ import annotations

import pytest

from phase7.propagation.minja_study import run_minja_crowding_study


def test_minja_crowding_study_runs_a_real_trial_and_reports_a_real_measurement(tmp_path):
    result = run_minja_crowding_study(storage_dir=tmp_path / "minja-crowding")

    assert result.top_k == 8
    assert len(result.step_memory_ids) == 3  # the real 3-step bridging/compressed/minimal sequence
    assert len(result.benign_candidate_memory_ids) == 8  # 11 total vs top_k=8 -- real competition, not pool-size artifact
    assert len(result.selected_memory_ids) == result.top_k

    assert 0 <= result.minja_slots_occupied <= result.top_k
    assert result.minja_slot_fraction == pytest.approx(result.minja_slots_occupied / result.top_k)
    assert result.footprint.member_ids == tuple(sorted(result.step_memory_ids))


def test_all_three_minja_steps_crowd_the_shared_task_together(tmp_path):
    result = run_minja_crowding_study(storage_dir=tmp_path / "minja-crowding-2")
    # The real, measured outcome: all three real progressive-shortening steps
    # are selected together, fully crowding the task -- re_entry_rate = 1.0.
    assert result.minja_slots_occupied == 3
    assert result.re_entry_rate.value == pytest.approx(1.0)


def test_crowding_study_is_deterministic_given_the_same_real_inputs(tmp_path):
    r1 = run_minja_crowding_study(storage_dir=tmp_path / "run1")
    r2 = run_minja_crowding_study(storage_dir=tmp_path / "run2")
    assert r1.minja_slots_occupied == r2.minja_slots_occupied
    assert r1.re_entry_rate.value == r2.re_entry_rate.value
