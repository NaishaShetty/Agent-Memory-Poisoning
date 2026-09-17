"""Phase 7.5 -- tests for the per-attack footprint study: run_attack_footprint_trial()/
run_seven_attack_footprint_study(), exercised against the real, frozen live attack
injectors (Stage 5.4's live_attack_runs.py, unmodified) for all seven attacks.
"""

from __future__ import annotations

import pytest

from phase7.propagation.attack_study import (
    SEVEN_FROZEN_ATTACK_IDS,
    run_attack_footprint_trial,
    run_seven_attack_footprint_study,
)


def test_seven_frozen_attack_ids_matches_the_real_phase4_attack_directories():
    import os
    real_dirs = {
        d for d in os.listdir("phase4/attacks")
        if os.path.isdir(os.path.join("phase4/attacks", d)) and not d.startswith("__")
    }
    assert set(SEVEN_FROZEN_ATTACK_IDS) == real_dirs


@pytest.mark.parametrize("attack_id", SEVEN_FROZEN_ATTACK_IDS)
def test_each_attack_admits_and_yields_a_non_trivial_footprint(tmp_path, attack_id):
    trial = run_attack_footprint_trial(attack_id, storage_dir=tmp_path / attack_id)

    assert trial.attack_id == attack_id
    assert trial.admitted is True, f"{attack_id} did not admit under default parameters: {trial.note}"
    assert trial.poisoned_memory_id is not None
    assert trial.footprint is not None
    assert trial.poisoned_memory_id in trial.footprint.member_ids

    # The synthetic downstream chain seeds exactly one DERIVED_FROM child off
    # the poisoned root and one crowded co-selection task -- every signal must
    # reflect that real structure, not a trivial single-node footprint.
    assert trial.fan_out_rate.value == pytest.approx(1.0)
    assert trial.cycle_reinforcement_depth.value == pytest.approx(1.0)
    assert trial.re_entry_rate.value == pytest.approx(0.5)  # 1 of 2 real tasks is crowded
    assert trial.cross_task_bleed.value == pytest.approx(2.0)  # both real tasks touch the footprint


def test_run_attack_footprint_trial_rejects_unknown_attack_id(tmp_path):
    with pytest.raises(ValueError, match="unknown attack_id"):
        run_attack_footprint_trial("not_a_real_attack", storage_dir=tmp_path / "bogus")


def test_run_attack_footprint_trial_rejects_gate_reply_for_attacks_without_a_gate(tmp_path):
    with pytest.raises(ValueError, match="gate_reply is only accepted"):
        run_attack_footprint_trial("farma", storage_dir=tmp_path / "farma", gate_reply="DECISION: KEEP")


def test_sleeper_discard_is_reported_as_not_admitted_not_a_failure(tmp_path):
    trial = run_attack_footprint_trial(
        "sleeper_memory_poisoning", storage_dir=tmp_path / "sleeper-discard",
        gate_reply="DECISION: DISCARD\nRATIONALE: Not legitimate.",
    )
    assert trial.admitted is False
    assert trial.poisoned_memory_id is None
    assert trial.footprint is None
    assert trial.fan_out_rate is None
    assert "DISCARD" in trial.note or "rejection" in trial.note


def test_run_seven_attack_footprint_study_covers_every_attack(tmp_path):
    results = run_seven_attack_footprint_study(storage_dir=tmp_path)
    assert set(results.keys()) == set(SEVEN_FROZEN_ATTACK_IDS)
    for attack_id, trial in results.items():
        assert trial.admitted is True, f"{attack_id} unexpectedly did not admit: {trial.note}"
        assert trial.footprint is not None
