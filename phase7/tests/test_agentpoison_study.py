"""Phase 7.12 -- tests for agentpoison_study.py: a real AgentPoison backdoor
trigger-sweep study using the REAL, genuinely gradient-optimized artifact
(`milestone4_artifact_2026-09-11_v2.json`), not the generic ["a","b","c"]
wiring stand-in `live_attack_runs.py` uses elsewhere.

See module docstring for the disclosed, measured limitation: this harness's
real result (selected in BOTH conditions) does NOT match the real, already-
recorded milestone-5 campaign result (selected ONLY in the trigger condition)
-- a structural gap (this harness never exercises the real embedding-based
retrieval-pool-narrowing stage), not a bug, and not silently forced to agree.
"""

from __future__ import annotations

from phase7.propagation.agentpoison_study import run_agentpoison_trigger_sweep_study


def test_agentpoison_trigger_sweep_runs_a_real_trial_with_the_real_optimized_artifact(tmp_path):
    result = run_agentpoison_trigger_sweep_study(storage_dir=tmp_path / "agentpoison")

    assert result.poison_memory_id  # a real memory was admitted
    assert len(result.benign_selected_memory_ids) <= 8
    assert len(result.trigger_selected_memory_ids) <= 8
    assert result.footprint.member_ids == (result.poison_memory_id,)


def test_disclosed_limitation_this_harness_selects_in_both_conditions_unlike_the_real_campaign(tmp_path):
    # The real, measured (not forced) outcome for THIS harness -- see module
    # docstring for why it differs from the real recorded milestone-5 result.
    result = run_agentpoison_trigger_sweep_study(storage_dir=tmp_path / "agentpoison-2")
    assert result.selected_in_benign_condition is True
    assert result.selected_in_trigger_condition is True
    assert result.cross_task_bleed.value == 2.0  # present in both real tasks


def test_trigger_sweep_is_deterministic_given_the_same_real_inputs(tmp_path):
    r1 = run_agentpoison_trigger_sweep_study(storage_dir=tmp_path / "run1")
    r2 = run_agentpoison_trigger_sweep_study(storage_dir=tmp_path / "run2")
    assert r1.selected_in_benign_condition == r2.selected_in_benign_condition
    assert r1.selected_in_trigger_condition == r2.selected_in_trigger_condition
