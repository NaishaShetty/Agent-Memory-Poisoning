"""Phase 7.11 -- tests for mpbench_study.py: a real MPBench-PCFI-specific
crowding study, closing part of Report Limitation 5.2 for this attack. See
module docstring for the real, measured finding (crowding DOES occur, for a
reason distinct from FARMA's self-reinforcement) -- this module's own first
prediction (low crowding) was wrong and is disclosed as such, not rewritten.
"""

from __future__ import annotations

import pytest

from phase7.propagation.mpbench_study import run_mpbench_crowding_study


def test_mpbench_crowding_study_runs_a_real_trial_and_reports_a_real_measurement(tmp_path):
    result = run_mpbench_crowding_study(storage_dir=tmp_path / "mpbench-crowding")

    assert result.top_k == 8
    assert len(result.scenario_memory_ids) == 3  # the three real PCFI_SCENARIOS
    assert len(result.benign_candidate_memory_ids) == 8  # 11 total vs top_k=8 -- real competition
    assert len(result.selected_memory_ids) == result.top_k
    assert 0 <= result.mpbench_slots_occupied <= result.top_k
    assert result.mpbench_slot_fraction == pytest.approx(result.mpbench_slots_occupied / result.top_k)
    assert result.footprint.member_ids == tuple(sorted(result.scenario_memory_ids))


def test_all_three_scenarios_crowd_the_shared_task_together(tmp_path):
    # The real, measured outcome (module docstring): all three real,
    # independent, unmarked-fact scenarios crowd together even though none
    # of them derives from or references another.
    result = run_mpbench_crowding_study(storage_dir=tmp_path / "mpbench-crowding-2")
    assert result.mpbench_slots_occupied == 3
    assert result.re_entry_rate.value == pytest.approx(1.0)


def test_crowding_holds_under_a_query_specific_to_only_one_scenarios_topic(tmp_path):
    # Verifies the crowding is not an artifact of a query engineered to favor
    # all three scenarios equally.
    result = run_mpbench_crowding_study(
        storage_dir=tmp_path / "mpbench-crowding-3",
        query="What fields would Caroline be likely to pursue in her educaton?",
    )
    assert result.mpbench_slots_occupied == 3


def test_crowding_study_is_deterministic_given_the_same_real_inputs(tmp_path):
    r1 = run_mpbench_crowding_study(storage_dir=tmp_path / "run1")
    r2 = run_mpbench_crowding_study(storage_dir=tmp_path / "run2")
    assert r1.mpbench_slots_occupied == r2.mpbench_slots_occupied
    assert r1.re_entry_rate.value == r2.re_entry_rate.value
