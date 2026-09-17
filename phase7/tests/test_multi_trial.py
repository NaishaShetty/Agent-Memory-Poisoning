"""Phase 7.5/7.6 multi-trial extension -- tests for multi_trial.py. Partially
closes Report Limitation 5.1 (every original number was n=1) by exercising real,
distinct topologies/parameter sets and checking the resulting distributions are
real (not fabricated repeats) -- see multi_trial.py's own module docstring for
what this does and does not claim to fix.
"""

from __future__ import annotations

import pytest

from phase7.propagation.multi_trial import (
    CROWDING_PARAMETER_SWEEP,
    DOWNSTREAM_TOPOLOGIES,
    run_attack_multi_topology_trial,
    run_farma_crowding_multi_parameter_study,
    run_seven_attack_multi_topology_study,
)


def test_downstream_topologies_are_four_distinct_real_shapes():
    assert DOWNSTREAM_TOPOLOGIES == ("single_child", "two_siblings", "chain_depth_2", "no_children")


def test_farma_multi_topology_trial_admits_all_four_and_shows_real_variation(tmp_path):
    result = run_attack_multi_topology_trial("farma", storage_dir=tmp_path / "farma")

    assert result.attack_id == "farma"
    assert result.admitted_count == 4  # FARMA has no admission gate -- every topology admits
    assert result.fan_out_rate.n == 4
    # Real topology-driven variation, not a repeated identical number: two_siblings
    # and chain_depth_2 both fan out to 2 children (fan_out_rate=2.0), single_child
    # fans out to 1 (1.0), no_children has none (0.0) -- not all four values equal.
    assert len(set(result.fan_out_rate.values)) > 1
    # chain_depth_2 (a real 2-hop derivation chain) is the only topology with
    # cycle_reinforcement_depth == 2.0 -- the depth signal actually distinguishes
    # a chain from siblings, which is the reason this topology was added.
    assert 2.0 in result.cycle_reinforcement_depth.values
    assert result.cycle_reinforcement_depth.maximum == pytest.approx(2.0)


def test_no_children_topology_yields_a_bare_admitted_only_footprint(tmp_path):
    result = run_attack_multi_topology_trial(
        "farma", storage_dir=tmp_path / "farma-solo", topologies=("no_children",),
    )
    assert result.admitted_count == 1
    assert result.fan_out_rate.values == (0.0,)
    assert result.cycle_reinforcement_depth.values == (0.0,)
    # Only one real retrieval task exists for this topology (solo) -- cross_task_bleed
    # must reflect that, not the two-task value the other topologies produce.
    assert result.cross_task_bleed.values == (1.0,)


def test_gate_reply_is_rejected_for_an_attack_without_a_gate(tmp_path):
    with pytest.raises(ValueError, match="gate_reply is only accepted"):
        run_attack_multi_topology_trial("farma", storage_dir=tmp_path / "farma-bad-gate", gate_reply="DECISION: KEEP")


def test_sleeper_discard_across_every_topology_is_reported_as_zero_admitted_not_a_failure(tmp_path):
    result = run_attack_multi_topology_trial(
        "sleeper_memory_poisoning", storage_dir=tmp_path / "sleeper-discard",
        gate_reply="DECISION: DISCARD\nRATIONALE: Not legitimate.",
    )
    assert result.admitted_count == 0
    # n=0 distributions -- nan, never a fabricated 0.0, mirroring benign_baseline.py's
    # own discipline for a signal with no real denominator to measure.
    assert result.fan_out_rate.n == 0


def test_run_seven_attack_multi_topology_study_covers_every_attack(tmp_path):
    results = run_seven_attack_multi_topology_study(storage_dir=tmp_path, topologies=("single_child", "two_siblings"))
    assert set(results.keys()) == set(
        ["agentpoison", "dsrm", "farma", "memorygraft", "minja", "mpbench", "sleeper_memory_poisoning"]
    )
    for attack_id, result in results.items():
        assert result.admitted_count == 2, f"{attack_id} did not admit both topologies"


def test_crowding_parameter_sweep_is_five_real_distinct_combinations():
    assert len(CROWDING_PARAMETER_SWEEP) == 5
    assert len(set(tuple(sorted(p.items())) for p in CROWDING_PARAMETER_SWEEP)) == 5  # no duplicate combos


def test_farma_crowding_multi_parameter_study_shows_real_variation_by_cycle_count(tmp_path):
    result = run_farma_crowding_multi_parameter_study(
        storage_dir=tmp_path / "crowding",
        parameter_sets=({"num_amplification_cycles": 5}, {"num_amplification_cycles": 10}),
    )
    assert result.farma_slot_fraction.n == 2
    # Fewer amplification cycles means a smaller, less dominant FARMA cluster --
    # this is a real, measured finding, not assumed: 5 cycles is not guaranteed
    # to hit the full 8/8 the paper's own 10-cycle default reproduces.
    assert result.farma_slot_fraction.values[1] == pytest.approx(1.0)  # 10-cycle default: 8/8, matches Stage 7.6
    assert result.farma_slot_fraction.values[0] <= result.farma_slot_fraction.values[1]
