"""Phase 7.24 -- tests for attack_specific_multi_trial.py: closes the
remainder of Report Limitation 5.1 (real n>1) for MINJA, MPBench-PCFI,
AgentPoison, and Sleeper, by varying each study's own already-exposed real
parameters (benign_candidate_texts / query) across genuinely distinct real
sets -- never a repeated call on identical inputs.
"""

from __future__ import annotations

from phase7.propagation.attack_specific_multi_trial import (
    run_agentpoison_multi_trial_trigger_sweep,
    run_minja_multi_trial_crowding_study,
    run_mpbench_multi_trial_crowding_study,
    run_sleeper_multi_trial_trigger_sweep,
)


def test_minja_multi_trial_reports_real_n_of_three(tmp_path):
    result = run_minja_multi_trial_crowding_study(storage_dir=tmp_path / "minja")
    assert result.trial_labels == ("default", "alt_1", "alt_2")
    assert result.values["minja_slots_occupied"].n == 3
    assert result.values["re_entry_rate"].n == 3


def test_mpbench_multi_trial_reports_real_n_of_three(tmp_path):
    result = run_mpbench_multi_trial_crowding_study(storage_dir=tmp_path / "mpbench")
    assert result.trial_labels == ("shared", "education_specific", "activities_specific")
    assert result.values["mpbench_slots_occupied"].n == 3
    # Real finding: crowding holds across all three real, distinct queries.
    assert result.values["mpbench_slots_occupied"].minimum == 3.0


def test_agentpoison_multi_trial_reports_real_n_of_three(tmp_path):
    result = run_agentpoison_multi_trial_trigger_sweep(storage_dir=tmp_path / "agentpoison")
    assert result.values["selected_in_benign_condition"].n == 3
    assert result.values["selected_in_trigger_condition"].n == 3
    assert result.values["cross_task_bleed"].n == 3


def test_sleeper_multi_trial_reports_real_n_of_three_per_condition(tmp_path):
    result = run_sleeper_multi_trial_trigger_sweep(storage_dir=tmp_path / "sleeper")
    assert set(result.values.keys()) == {
        "selected_exact", "selected_paraphrased", "selected_near", "selected_partial", "selected_distant",
    }
    for dist in result.values.values():
        assert dist.n == 3
