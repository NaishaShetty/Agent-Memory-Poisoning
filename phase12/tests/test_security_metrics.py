"""Phase 12 -- tests for PAR, SDR, AMR."""

from __future__ import annotations

import pytest

from phase12.eval_corpus import per_dataset_eval_corpora
from phase12.evaluation_matrix import ALL_RULE_BASED_CONFIGS
from phase12.security_metrics import compute_amr, compute_par, compute_pr_status, compute_sdr


@pytest.fixture(scope="module")
def pools_by_dataset():
    corpora = per_dataset_eval_corpora()
    return {name: corpus.pools for name, corpus in corpora.items()}


def test_par_covers_all_fifteen_real_seed_attempts():
    result = compute_par()
    assert result.n_attempts == 15  # dsrm 3 + farma 3 + mpbench 3 + minja 3 + agentpoison 1 + memorygraft 1 + sleeper 1
    assert 0.0 <= result.overall_par <= 1.0
    assert result.n_admitted <= result.n_attempts


def test_par_per_family_rates_are_bounded():
    result = compute_par()
    assert set(result.per_family_par.keys()) == {
        "dsrm", "farma", "mpbench", "minja", "agentpoison", "memorygraft", "sleeper_memory_poisoning",
    }
    for rate in result.per_family_par.values():
        assert 0.0 <= rate <= 1.0


def test_pr_status_points_to_the_real_computation():
    """UPDATE (2026-09-21): PR is now computed for real
    (`phase12.propagation.propagation_rate.compute_pr()`, a real local-LLM
    measurement) -- this status string is a pointer to that real function,
    not a "not computed" disclaimer any longer."""
    status = compute_pr_status()
    assert "COMPUTED" in status
    assert "NOT_COMPUTED" not in status


def test_sdr_reports_one_result_per_dataset_per_config(pools_by_dataset):
    results = compute_sdr(pools_by_dataset, ALL_RULE_BASED_CONFIGS)
    assert len(results) == len(pools_by_dataset) * len(ALL_RULE_BASED_CONFIGS)
    for r in results:
        assert 0.0 <= r.sleeper_detection_rate <= 1.0
        assert r.n_sleeper >= 0


def test_sdr_b0_no_defense_never_detects(pools_by_dataset):
    results = compute_sdr(pools_by_dataset, ALL_RULE_BASED_CONFIGS)
    b0_results = [r for r in results if r.config_name == "B0"]
    assert b0_results
    for r in b0_results:
        assert r.sleeper_detection_rate == 0.0  # B0 enables no component; nothing is ever flagged


def test_amr_only_counts_hard_mitigation_actions(pools_by_dataset):
    results = compute_amr(pools_by_dataset, ALL_RULE_BASED_CONFIGS)
    for r in results:
        assert r.n_confirmed_excluded_on_recheck <= r.n_hard_mitigation_actions
        if r.n_hard_mitigation_actions == 0:
            assert r.amr is None
        else:
            assert 0.0 <= r.amr <= 1.0


def test_amr_b0_has_no_hard_mitigation_actions(pools_by_dataset):
    results = compute_amr(pools_by_dataset, ALL_RULE_BASED_CONFIGS)
    b0 = next(r for r in results if r.config_name == "B0")
    assert b0.n_hard_mitigation_actions == 0
    assert b0.amr is None
