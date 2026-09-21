"""Phase 12 -- tests for the attack x dataset x defense-configuration matrix."""

from __future__ import annotations

from phase12.evaluation_matrix import ALL_RULE_BASED_CONFIGS, cells_by_dataset, run_security_matrix


def test_matrix_has_one_cell_per_dataset_per_config():
    cells = run_security_matrix()
    grouped = cells_by_dataset(cells)
    assert len(grouped) == 4
    for dataset_cells in grouped.values():
        assert len(dataset_cells) == len(ALL_RULE_BASED_CONFIGS)


def test_b0_never_flags_anything():
    cells = run_security_matrix()
    b0_cells = [c for c in cells if c.config_name == "B0"]
    assert b0_cells
    for c in b0_cells:
        assert c.metrics.poison_detection_rate == 0.0
        assert c.metrics.benign_false_positive_rate == 0.0


def test_b8_detection_rate_is_bounded_and_uses_real_n():
    cells = run_security_matrix()
    b8_cells = [c for c in cells if c.config_name == "B8"]
    assert b8_cells
    for c in b8_cells:
        assert 0.0 <= c.metrics.poison_detection_rate <= 1.0
        assert 0.0 <= c.metrics.benign_false_positive_rate <= 1.0
        assert c.metrics.n_poison == 15  # every dataset cell shares the same 15-scenario real poison pool
        assert c.metrics.n_benign > 0


def test_per_attack_family_detection_present_for_all_seven_families():
    cells = run_security_matrix()
    b8_locomo = next(c for c in cells if c.config_name == "B8" and c.dataset_name == "locomo")
    assert set(b8_locomo.metrics.per_attack_family_detection.keys()) == {
        "dsrm", "farma", "mpbench", "minja", "agentpoison", "memorygraft", "sleeper_memory_poisoning",
    }
