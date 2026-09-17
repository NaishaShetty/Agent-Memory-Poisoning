"""Phase 7.15 -- tests for sleeper_study.py: a real Sleeper dormant/trigger
sweep using the real, frozen SleeperInjector/SEED_DESTRESS artifact and the
real 5 trigger conditions from trigger_sensitivity.py, via MockMem0Adapter
(no live LLM/RealMem0Adapter needed). See module docstring for the disclosed,
measured divergence from the real recorded campaign (this harness selects the
poison in all 5 conditions, including "distant" -- the same structural
retrieval-pool-narrowing gap already disclosed for AgentPoison).
"""

from __future__ import annotations

from phase7.propagation.sleeper_study import TRIGGER_CONDITIONS, run_sleeper_trigger_sweep_study


def test_trigger_sweep_runs_all_five_real_conditions(tmp_path):
    result = run_sleeper_trigger_sweep_study(storage_dir=tmp_path / "sleeper")
    assert set(result.selected_by_condition.keys()) == {name for name, _ in TRIGGER_CONDITIONS}
    assert result.poison_memory_id


def test_disclosed_divergence_all_five_conditions_select_the_poison(tmp_path):
    # The real, measured (not forced) outcome for THIS harness -- see module
    # docstring for why it diverges from the real recorded campaign, which
    # correctly excluded the "distant" condition.
    result = run_sleeper_trigger_sweep_study(storage_dir=tmp_path / "sleeper-2")
    assert all(result.selected_by_condition.values())
    assert result.cross_task_bleed.value == 5.0


def test_trigger_sweep_is_deterministic_given_the_same_real_inputs(tmp_path):
    r1 = run_sleeper_trigger_sweep_study(storage_dir=tmp_path / "run1")
    r2 = run_sleeper_trigger_sweep_study(storage_dir=tmp_path / "run2")
    assert r1.selected_by_condition == r2.selected_by_condition
