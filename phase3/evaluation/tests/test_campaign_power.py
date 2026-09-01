"""Phase 3.3-F UNIT_TESTs for `phase3.evaluation.agent_runtime.campaign_power` -- the
McNemar paired sample-size/power calculations."""

from __future__ import annotations

import pytest

from phase3.evaluation.agent_runtime.campaign_power import (
    PowerScenario,
    mcnemar_sample_size,
    recommend_n_tasks,
    sensitivity_table,
)


class TestMcNemarSampleSize:
    def test_matches_hand_computed_value_for_a_documented_scenario(self):
        """Independently hand-computed (not from an external citation, to avoid
        asserting an unverified 'textbook' number): alpha=0.05 two-sided
        (z=1.959964), power=0.80 (z=0.841621), p10=0.30, p01=0.10 ->
        psum=0.40, d=0.20, n = [1.959964*sqrt(0.40) + 0.841621*sqrt(0.40-0.04)]^2 / 0.04
        ~= 76.1."""
        n = mcnemar_sample_size(p10=0.30, p01=0.10, alpha=0.05, power=0.80)
        assert 74 <= n <= 79

    def test_larger_effect_size_requires_fewer_tasks(self):
        n_small_effect = mcnemar_sample_size(p10=0.15, p01=0.05, alpha=0.05, power=0.80)
        n_large_effect = mcnemar_sample_size(p10=0.35, p01=0.05, alpha=0.05, power=0.80)
        assert n_large_effect < n_small_effect

    def test_higher_power_requires_more_tasks(self):
        n_80 = mcnemar_sample_size(p10=0.30, p01=0.10, alpha=0.05, power=0.80)
        n_90 = mcnemar_sample_size(p10=0.30, p01=0.10, alpha=0.05, power=0.90)
        assert n_90 > n_80

    def test_zero_effect_size_raises(self):
        with pytest.raises(ValueError):
            mcnemar_sample_size(p10=0.2, p01=0.2)

    def test_unsupported_alpha_power_combination_raises(self):
        with pytest.raises(ValueError):
            mcnemar_sample_size(p10=0.3, p01=0.1, alpha=0.05, power=0.5)

    def test_n_is_always_positive(self):
        n = mcnemar_sample_size(p10=0.1, p01=0.05)
        assert n > 0


class TestSensitivityTable:
    def test_table_has_one_row_per_scenario(self):
        scenarios = [PowerScenario("a", 0.2, 0.1), PowerScenario("b", 0.3, 0.05)]
        table = sensitivity_table(scenarios)
        assert len(table) == 2

    def test_table_reports_effect_size_as_absolute_difference(self):
        scenarios = [PowerScenario("a", 0.2, 0.1)]
        table = sensitivity_table(scenarios)
        assert table[0]["effect_size"] == pytest.approx(0.1)


class TestRecommendation:
    def test_recommendation_returns_a_range_not_a_single_number(self):
        """This is the load-bearing guard: the mission explicitly forbids
        manufacturing a single point-estimate N from insufficient pilot data --
        recommend_n_tasks() must always return a min/max range plus the full table."""
        result = recommend_n_tasks()
        assert result["n_tasks_min_across_scenarios"] < result["n_tasks_max_across_scenarios"]
        assert len(result["table"]) >= 3

    def test_recommendation_documents_bonferroni_correction(self):
        result = recommend_n_tasks(num_comparisons=3)
        assert "bonferroni" in result["note"].lower() or "0.0167" in result["note"]
        assert result["used_alpha_from_table"] == 0.01

    def test_single_comparison_uses_uncorrected_alpha(self):
        result = recommend_n_tasks(num_comparisons=1)
        assert result["used_alpha_from_table"] == 0.05
