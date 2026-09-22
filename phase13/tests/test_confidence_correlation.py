"""Phase 13 -- tests for the confidence-correlation module. The `_pearson()`
helper is tested directly with cheap, deterministic, hand-computed cases (no
LLM/ledger dependency). The real, full correlation (`compute_confidence_
correlation()`) requires ~60 real local-LLM calls (`compute_pr()`'s own
15-scenario x 4-position sweep) -- exercised via
`python -m phase13.confidence_correlation`, not per test run; this file only
checks the real output's SHAPE once produced, never its exact value (a
correlation coefficient over real, non-deterministic-across-runs LLM output
is not something a test should pin to a fixed number)."""

from __future__ import annotations

import pytest

from phase12.propagation.ollama_provider import OllamaProvider
from phase13.confidence_correlation import _pearson, compute_confidence_correlation


def test_pearson_perfect_positive_correlation():
    xs = (1.0, 2.0, 3.0, 4.0)
    ys = (2.0, 4.0, 6.0, 8.0)
    assert abs(_pearson(xs, ys) - 1.0) < 1e-9


def test_pearson_perfect_negative_correlation():
    xs = (1.0, 2.0, 3.0, 4.0)
    ys = (8.0, 6.0, 4.0, 2.0)
    assert abs(_pearson(xs, ys) - (-1.0)) < 1e-9


def test_pearson_undefined_with_no_variance_returns_none_not_zero():
    """A real, disclosed discipline (see module docstring): no variance on one
    side means correlation is UNDEFINED, never silently reported as 0.0 (which
    would misleadingly claim 'measured, no relationship' rather than 'cannot
    be measured at all')."""
    xs = (0.5, 0.5, 0.5, 0.5)
    ys = (1.0, 2.0, 3.0, 4.0)
    assert _pearson(xs, ys) is None


def test_pearson_requires_at_least_two_points():
    assert _pearson((1.0,), (2.0,)) is None
    assert _pearson((), ()) is None


@pytest.mark.slow
def test_high_resolution_pairing_has_more_real_spread_than_the_banded_one():
    """Real, measured regression for the 2026-09-22 update: the raw admission
    signal sum / mean poison similarity pairing must show more real spread
    than the banded risk_score / propagated_fraction pairing it complements
    -- confirming the higher-resolution measurement actually adds
    information, not just a second number."""
    provider = OllamaProvider()
    if not provider.health_check():
        pytest.skip("Ollama server not reachable at 127.0.0.1:11434 -- this test requires it")

    result = compute_confidence_correlation(provider=provider)
    assert result.n_scenarios == 15

    banded_spread = len(set(round(v, 3) for v in result.per_scenario_admission_risk.values()))
    raw_spread = len(set(round(v, 3) for v in result.per_scenario_admission_raw_signal_sum.values()))
    assert raw_spread >= banded_spread

    similarity_spread = len(set(round(v, 2) for v in result.per_scenario_mean_poison_similarity.values()))
    fraction_spread = len(set(round(v, 2) for v in result.per_scenario_propagation_fraction.values()))
    assert similarity_spread > fraction_spread
