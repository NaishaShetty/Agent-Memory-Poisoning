"""Phase 14 -- tests for real per-component latency measurement. Fast (no LLM
calls; the Consolidation Guard's own real signal functions are pure
regex/embedding calls)."""

from __future__ import annotations

from phase14.latency_measurement import measure_b1_latency, measure_b9_latency, measure_consolidation_guard_latency


def test_b1_latency_is_measured_and_positive():
    result = measure_b1_latency(n_trials=3)
    assert result.n_trials == 3
    assert result.mean_seconds > 0.0
    assert result.min_seconds <= result.mean_seconds <= result.max_seconds


def test_b9_latency_is_measured_and_positive():
    result = measure_b9_latency(n_trials=3)
    assert result.mean_seconds > 0.0


def test_consolidation_guard_latency_is_measured_and_positive():
    result = measure_consolidation_guard_latency(n_trials=3)
    assert result.mean_seconds > 0.0
