"""Phase 12 -- fast, Ollama-independent unit test for the threshold
calibration ALGORITHM itself (`best_threshold()`), separate from
`run_calibration()`'s own real-data collection (which needs a real LLM
call per Track B scenario and is exercised directly by actually running
`phase12/propagation/threshold_calibration.py`, not by a fast unit test).
"""

from __future__ import annotations

from phase12.propagation.threshold_calibration import CalibrationSample, best_threshold


def test_best_threshold_finds_a_clean_separator_with_zero_errors():
    samples = [
        CalibrationSample("pos-1", True, 0.9),
        CalibrationSample("pos-2", True, 0.8),
        CalibrationSample("pos-3", True, 0.7),
        CalibrationSample("neg-1", False, 0.3),
        CalibrationSample("neg-2", False, 0.2),
        CalibrationSample("neg-3", False, 0.1),
    ]
    result = best_threshold(samples)
    assert result["errors"] == 0
    assert 0.3 < result["threshold"] <= 0.7


def test_best_threshold_prefers_the_higher_threshold_on_ties():
    """Ties are broken toward the higher (more conservative, fewer false
    positives) threshold -- consistent with this project's stated
    preference for precision over recall on structural guards."""
    samples = [
        CalibrationSample("pos-1", True, 0.9),
        CalibrationSample("pos-2", True, 0.5),
        CalibrationSample("neg-1", False, 0.5),
        CalibrationSample("neg-2", False, 0.1),
    ]
    result = best_threshold(samples)
    # At threshold=0.5: fn=0 (both positives >= 0.5), fp=1 (neg-1 >= 0.5) -> 1 error.
    # At threshold=0.9 (or anything > 0.5, <= 0.9): fn=1 (pos-2 < threshold), fp=0 -> 1 error.
    # Both achieve the same minimum error count (1) -- the tie-break must prefer the higher one.
    assert result["errors"] == 1
    assert result["threshold"] > 0.5


def test_best_threshold_reports_real_summary_statistics():
    samples = [
        CalibrationSample("pos-1", True, 0.9),
        CalibrationSample("pos-2", True, 0.7),
        CalibrationSample("neg-1", False, 0.2),
        CalibrationSample("neg-2", False, 0.4),
    ]
    result = best_threshold(samples)
    assert result["n_positive"] == 2
    assert result["n_negative"] == 2
    assert result["positive_mean"] == 0.8
    assert result["positive_min"] == 0.7
    assert result["positive_max"] == 0.9
    assert round(result["negative_mean"], 10) == 0.3
    assert result["negative_min"] == 0.2
    assert result["negative_max"] == 0.4
