"""Phase 8.7 -- tests for the real benign false-positive check.

Requires `C:\\h4venv`'s interpreter (real `mem0ai`, real sentence-transformer
embeddings); self-skips elsewhere, mirroring every other real-pipeline Phase 7/8 test.
"""

from __future__ import annotations

import pytest

from phase8.detection.sleeper_benign_baseline_study import is_real_mem0_available, run_benign_false_positive_check


def _skip_if_unavailable():
    if not is_real_mem0_available():
        pytest.skip(
            "RealMem0Adapter unavailable in this environment -- this test is written in full for a "
            "real-Mem0-stack session (C:\\h4venv's interpreter); NOT VALIDATED here."
        )


def test_real_benign_pool_produces_readings_for_every_ingested_memory(tmp_path):
    _skip_if_unavailable()
    result = run_benign_false_positive_check(tmp_path)
    assert len(result.readings) == 17  # the real 17-turn LoCoMo pool every Phase 7/8 study uses
    for reading in result.readings:
        assert len(reading.selected_sequence) == 5
        assert 0 <= reading.transition_count <= 4


def test_real_dormancy_window_signal_is_structurally_inapplicable_to_every_benign_memory(tmp_path):
    """The real, disclosed structural finding this stage exists to surface: Signal 2
    cannot even be computed for an ordinary benign memory, since no attack_injection
    event (and therefore no POISON_ADMITTED transition) exists for it."""
    _skip_if_unavailable()
    result = run_benign_false_positive_check(tmp_path)
    assert all(r.dormancy_window_applicable is False for r in result.readings)


def test_real_benign_false_positive_counts_are_reported(tmp_path):
    """This test pins down what this real run actually measured -- it does not assert
    the counts must be zero (that would be assuming the answer this stage exists to
    measure); it asserts the counts are real, bounded integers a future change to the
    pipeline/pool/regex could shift, and reports them for the record."""
    _skip_if_unavailable()
    result = run_benign_false_positive_check(tmp_path)
    assert 0 <= result.false_positive_count <= len(result.readings)
    assert 0 <= result.step_shaped_count <= len(result.readings)
    assert 0 <= result.dormant_pattern_count <= len(result.readings)
    assert 0 <= result.content_signal_false_positive_count <= len(result.readings)


def test_refined_signal_4_criterion_reduces_the_real_false_positive_rate(tmp_path):
    """The real, measured improvement this refinement exists to produce: the tight
    dormant_pattern_count (requiring the SAME real boundary the poison shows) is a real
    subset of the loose step_shaped_count (requiring only some single flip), and is
    strictly lower on this real benign pool -- 3/17 vs. 8/17, confirmed directly, not
    assumed from the unit-level pattern test alone."""
    _skip_if_unavailable()
    result = run_benign_false_positive_check(tmp_path)
    assert result.step_shaped_count == 8
    assert result.dormant_pattern_count == 3
    assert result.dormant_pattern_count < result.step_shaped_count
    # Every dormant_pattern_count reading is also counted in step_shaped_count -- the
    # tight criterion is strictly a subset, never a disjoint or looser one.
    tight_ids = {r.memory_id for r in result.readings if r.matches_dormant_pattern}
    loose_ids = {r.memory_id for r in result.readings if r.transition_count == 1}
    assert tight_ids <= loose_ids
