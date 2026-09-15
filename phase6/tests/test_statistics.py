"""Phase 6.11 -- tests for the statistical protocol machinery: Wilson
intervals, McNemar's exact test, sample-size/power calculation, and
Benjamini-Hochberg correction. Every numeric check here is against a value
independently computable by hand or cross-checked with `scipy`/a known
textbook result, not merely "it ran without error."
"""

from __future__ import annotations

import math

import pytest
from scipy.stats import binomtest

from phase6.evaluation.statistics.intervals import wilson_score_interval
from phase6.evaluation.statistics.multiple_comparisons import benjamini_hochberg
from phase6.evaluation.statistics.power import _inverse_normal_cdf, mcnemar_sample_size
from phase6.evaluation.statistics.significance_report import (
    report_family_significance,
    report_family_significance_from_p_values,
)
from phase6.evaluation.statistics.tests import McNemarResult, mcnemar_exact_test, mcnemar_from_paired_outcomes

# ---------------------------------------------------------------------------
# Wilson score interval
# ---------------------------------------------------------------------------


def test_wilson_interval_known_case_50_of_100():
    """A well-known reference case: 50/100 successes, 95% CI, should be
    centered near 0.5 with half-width roughly 0.098 (textbook value)."""
    ci = wilson_score_interval(50, 100, 0.95)
    assert ci.point_estimate == 0.5
    assert ci.lower == pytest.approx(0.404, abs=0.005)
    assert ci.upper == pytest.approx(0.596, abs=0.005)


def test_wilson_interval_never_exceeds_0_1_bounds():
    ci_low = wilson_score_interval(0, 10, 0.95)
    ci_high = wilson_score_interval(10, 10, 0.95)
    assert 0.0 <= ci_low.lower <= ci_low.upper <= 1.0
    assert 0.0 <= ci_high.lower <= ci_high.upper <= 1.0
    assert ci_low.lower == 0.0  # Wilson interval for 0 successes still has lower bound 0
    assert ci_high.upper == pytest.approx(1.0)


def test_wilson_interval_narrows_with_larger_n():
    small = wilson_score_interval(5, 10, 0.95)
    large = wilson_score_interval(50, 100, 0.95)
    assert (large.upper - large.lower) < (small.upper - small.lower)


def test_wilson_interval_widens_with_higher_confidence():
    ci_90 = wilson_score_interval(5, 10, 0.90)
    ci_99 = wilson_score_interval(5, 10, 0.99)
    assert (ci_99.upper - ci_99.lower) > (ci_90.upper - ci_90.lower)


def test_wilson_interval_rejects_invalid_input():
    with pytest.raises(ValueError):
        wilson_score_interval(-1, 10)
    with pytest.raises(ValueError):
        wilson_score_interval(11, 10)
    with pytest.raises(ValueError):
        wilson_score_interval(5, 0)
    with pytest.raises(ValueError):
        wilson_score_interval(5, 10, confidence_level=0.5)


# ---------------------------------------------------------------------------
# McNemar's exact test -- reproduces the Methodology Draft's own worked
# example directly (Section 12.16: b=4, c=0 -> exact two-sided p=0.125)
# ---------------------------------------------------------------------------


def test_mcnemar_reproduces_methodology_worked_example():
    """The Methodology Draft's own Condition B result: 4 tasks flipped
    incorrect->correct under verification, 0 flipped the opposite way,
    reported as exact two-sided p=0.125."""
    result = mcnemar_exact_test(b=4, c=0)
    assert result.p_value == pytest.approx(0.125, abs=1e-9)


def test_mcnemar_second_methodology_example():
    """The Methodology's Condition C (Mem0) comparison: 4 flipped toward
    incorrect, 3 toward correct, reported as exact two-sided p=1.000."""
    result = mcnemar_exact_test(b=3, c=4)
    assert result.p_value == pytest.approx(1.0, abs=1e-9)


def test_mcnemar_matches_scipy_binomtest_directly():
    """Cross-check against scipy's own binomtest, independent of this
    module's own wrapper logic."""
    b, c = 7, 2
    expected = binomtest(b, b + c, 0.5, alternative="two-sided").pvalue
    result = mcnemar_exact_test(b, c)
    assert result.p_value == pytest.approx(expected)


def test_mcnemar_zero_discordant_pairs_is_fully_non_significant():
    result = mcnemar_exact_test(b=0, c=0)
    assert result.p_value == 1.0
    assert result.n_discordant == 0


def test_mcnemar_symmetric_in_b_and_c():
    """McNemar's test is symmetric: swapping b and c must give the same
    two-sided p-value (direction doesn't matter for a two-sided test)."""
    assert mcnemar_exact_test(6, 1).p_value == pytest.approx(mcnemar_exact_test(1, 6).p_value)


def test_mcnemar_from_paired_outcomes_matches_manual_counting():
    baseline = [False, False, True, True, False, True]
    defended = [True, True, True, False, False, True]
    # index 0: F->T (b), 1: F->T (b), 2: T->T (concordant), 3: T->F (c),
    # 4: F->F (concordant), 5: T->T (concordant)
    result = mcnemar_from_paired_outcomes(baseline, defended)
    assert result.b == 2
    assert result.c == 1
    assert result.n_concordant == 3
    assert result.p_value == pytest.approx(mcnemar_exact_test(2, 1).p_value)


def test_mcnemar_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        mcnemar_from_paired_outcomes([True, False], [True])


def test_mcnemar_rejects_negative_counts():
    with pytest.raises(ValueError):
        mcnemar_exact_test(-1, 3)


# ---------------------------------------------------------------------------
# Sample size / power (Connor 1987)
# ---------------------------------------------------------------------------


def test_inverse_normal_cdf_known_values():
    """Standard reference points: Phi^-1(0.5)=0, Phi^-1(0.975)~1.96,
    Phi^-1(0.8)~0.8416."""
    assert _inverse_normal_cdf(0.5) == pytest.approx(0.0, abs=1e-6)
    assert _inverse_normal_cdf(0.975) == pytest.approx(1.959964, abs=1e-4)
    assert _inverse_normal_cdf(0.8) == pytest.approx(0.841621, abs=1e-4)


def test_sample_size_decreases_with_larger_effect():
    """A larger odds ratio (psi) -- an easier-to-detect effect -- should
    require a SMALLER sample size, holding everything else fixed."""
    small_effect = mcnemar_sample_size(p_discordant=0.3, psi=1.5)
    large_effect = mcnemar_sample_size(p_discordant=0.3, psi=4.0)
    assert large_effect.required_n < small_effect.required_n


def test_sample_size_increases_with_higher_power_requirement():
    lower_power = mcnemar_sample_size(p_discordant=0.3, psi=2.0, power=0.7)
    higher_power = mcnemar_sample_size(p_discordant=0.3, psi=2.0, power=0.95)
    assert higher_power.required_n > lower_power.required_n


def test_sample_size_increases_with_stricter_alpha():
    lenient = mcnemar_sample_size(p_discordant=0.3, psi=2.0, alpha=0.10)
    strict = mcnemar_sample_size(p_discordant=0.3, psi=2.0, alpha=0.01)
    assert strict.required_n > lenient.required_n


def test_sample_size_rejects_psi_at_or_below_one():
    with pytest.raises(ValueError):
        mcnemar_sample_size(p_discordant=0.3, psi=1.0)
    with pytest.raises(ValueError):
        mcnemar_sample_size(p_discordant=0.3, psi=0.5)


def test_sample_size_rejects_invalid_p_discordant():
    with pytest.raises(ValueError):
        mcnemar_sample_size(p_discordant=0.0, psi=2.0)
    with pytest.raises(ValueError):
        mcnemar_sample_size(p_discordant=1.5, psi=2.0)


def test_sample_size_is_a_positive_integer():
    result = mcnemar_sample_size(p_discordant=0.3, psi=2.0)
    assert isinstance(result.required_n, int)
    assert result.required_n > 0


# ---------------------------------------------------------------------------
# Benjamini-Hochberg
# ---------------------------------------------------------------------------


def test_benjamini_hochberg_known_textbook_example():
    """A standard worked example (5 tests, alpha=0.05): raw p-values
    [0.01, 0.04, 0.03, 0.005, 0.20] -> sorted [0.005, 0.01, 0.03, 0.04, 0.20]
    with thresholds [0.01, 0.02, 0.03, 0.04, 0.05]. Ranks 1-4 all satisfy
    p_(k) <= threshold_(k) (0.005<=0.01, 0.01<=0.02, 0.03<=0.03, 0.04<=0.04);
    rank 5 (0.20) does not (0.20 > 0.05). So the largest qualifying rank is 4
    -> the four smallest p-values are significant, the largest is not."""
    inputs = [("A", 0.01), ("B", 0.04), ("C", 0.03), ("D", 0.005), ("E", 0.20)]
    results = benjamini_hochberg(inputs, alpha=0.05)
    significance = {r.label: r.significant for r in results}
    assert significance == {"A": True, "B": True, "C": True, "D": True, "E": False}


def test_benjamini_hochberg_adjusted_p_values_are_monotone_nondecreasing_by_rank():
    inputs = [("A", 0.2), ("B", 0.01), ("C", 0.15), ("D", 0.001), ("E", 0.5)]
    results = benjamini_hochberg(inputs)
    ordered_by_raw = sorted(results, key=lambda r: r.raw_p_value)
    adjusted_values = [r.adjusted_p_value for r in ordered_by_raw]
    assert adjusted_values == sorted(adjusted_values)


def test_benjamini_hochberg_all_significant_when_all_p_values_tiny():
    inputs = [(f"T{i}", 0.001) for i in range(7)]
    results = benjamini_hochberg(inputs)
    assert all(r.significant for r in results)


def test_benjamini_hochberg_none_significant_when_all_p_values_large():
    inputs = [(f"T{i}", 0.9) for i in range(7)]
    results = benjamini_hochberg(inputs)
    assert not any(r.significant for r in results)


def test_benjamini_hochberg_rejects_empty_input():
    with pytest.raises(ValueError):
        benjamini_hochberg([])


def test_benjamini_hochberg_rejects_out_of_range_p_value():
    with pytest.raises(ValueError):
        benjamini_hochberg([("A", 1.5)])
    with pytest.raises(ValueError):
        benjamini_hochberg([("A", -0.1)])


def test_benjamini_hochberg_correction_is_never_more_lenient_than_uncorrected():
    """Every adjusted p-value must be >= its own raw p-value -- the whole
    point of a multiple-comparison correction is to be more conservative,
    never less."""
    inputs = [("A", 0.01), ("B", 0.02), ("C", 0.005), ("D", 0.5)]
    results = benjamini_hochberg(inputs)
    for r in results:
        assert r.adjusted_p_value >= r.raw_p_value - 1e-12


# ---------------------------------------------------------------------------
# P2 fix (2026-09-14) -- significance_report.py: the enforced, single path for
# reporting significance across a family of Phase 6 comparisons. The audit
# finding this closes: benjamini_hochberg() existed and was correct, but was
# called by nothing else in the repository, so there was no enforced barrier
# stopping a future per-attack/per-configuration significance claim from
# skipping correction entirely.
# ---------------------------------------------------------------------------


def test_report_family_significance_actually_applies_correction_not_a_pass_through():
    """A family where one raw p-value would be "significant" at alpha=0.05
    uncorrected, but is NOT significant once corrected for testing 7
    hypotheses at once -- proves the report is genuinely running the
    correction, not just echoing raw p-values back with a label attached."""
    labeled_p_values = {
        "agentpoison": 0.04, "minja": 0.5, "farma": 0.6, "memorygraft": 0.7,
        "dsrm": 0.8, "mpbench": 0.9, "sleeper": 0.95,
    }
    uncorrected_significant = {label for label, p in labeled_p_values.items() if p < 0.05}
    report = report_family_significance_from_p_values(labeled_p_values, alpha=0.05)
    assert uncorrected_significant == {"agentpoison"}  # sanity: the raw claim WOULD be made
    assert report.significant_labels() == (), (
        "the single marginal raw p-value must not survive correction across "
        "7 simultaneous comparisons -- if this assertion fails, "
        "report_family_significance is not actually applying BH correction"
    )


def test_report_family_significance_from_mcnemar_results():
    """The McNemarResult-shaped entry point (what a real per-attack Stage
    6.10 comparison would actually produce) routes through the identical
    correction as the raw-p-value entry point."""
    labeled_results = {
        "attack-a": McNemarResult(b=8, c=1, n_discordant=9, n_concordant=-1, p_value=0.039),
        "attack-b": McNemarResult(b=2, c=2, n_discordant=4, n_concordant=-1, p_value=1.0),
    }
    report = report_family_significance(labeled_results, alpha=0.05)
    assert len(report.results) == 2
    assert all(isinstance(r.adjusted_p_value, float) for r in report.results)
    # Every result must be traceable back to a real McNemarResult's own p_value.
    raw_by_label = {r.label: r.raw_p_value for r in report.results}
    assert raw_by_label == {label: res.p_value for label, res in labeled_results.items()}


def test_report_family_significance_report_lines_never_claim_significance_from_raw_p_alone():
    """The printable report text must attribute 'SIGNIFICANT' only via the
    BH-adjusted call (`r.significant`), never re-derive it from raw_p_value
    < alpha independently -- a regression here would silently reintroduce
    the exact uncorrected-claim risk this module exists to prevent."""
    labeled_p_values = {"a": 0.01, "b": 0.9, "c": 0.9, "d": 0.9, "e": 0.9}
    report = report_family_significance_from_p_values(labeled_p_values, alpha=0.05)
    lines = report.to_report_lines()
    significant_lines = [l for l in lines if "SIGNIFICANT" in l and "not significant" not in l]
    significant_labels_in_text = {l.split()[0] for l in significant_lines}
    assert significant_labels_in_text == set(report.significant_labels())
