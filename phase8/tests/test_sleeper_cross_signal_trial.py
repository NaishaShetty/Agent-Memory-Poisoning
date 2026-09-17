"""Phase 8.6 -- tests for the real cross-signal trial.

Requires `C:\\h4venv`'s interpreter (real `mem0ai`, real sentence-transformer
embeddings); self-skips elsewhere, mirroring every other real-pipeline Phase 7/8 test.
"""

from __future__ import annotations

import pytest

from phase6.defense.policy.states import ALLOW

from phase8.detection.sleeper_cross_signal_trial import is_real_mem0_available, run_cross_signal_real_trial


def _skip_if_unavailable():
    if not is_real_mem0_available():
        pytest.skip(
            "RealMem0Adapter unavailable in this environment -- this test is written in full for a "
            "real-Mem0-stack session (C:\\h4venv's interpreter); NOT VALIDATED here."
        )


def test_real_cross_signal_trial_before_during_after(tmp_path):
    _skip_if_unavailable()
    result = run_cross_signal_real_trial(tmp_path)

    readings_by_condition = {r.condition_name: r for r in result.task_readings}
    assert list(readings_by_condition) == ["distant", "partial", "near", "paraphrased", "exact"]

    # BEFORE: the real "distant" task -- not selected, zero real prior retrievals, no
    # real POISON_SELECTED_TOP_K transition exists yet.
    before = readings_by_condition["distant"]
    assert before.real_selected is False
    assert before.real_prior_retrieval_count == 0
    assert before.dormancy_window_ever_selected is False
    assert before.dormancy_window_elapsed_seconds is None

    # DURING: the real "partial" task -- the first real selection in this trial's
    # chronological ordering. One real prior scored candidacy (the distant task).
    during = readings_by_condition["partial"]
    assert during.real_selected is True
    assert during.real_prior_retrieval_count == 1
    assert during.dormancy_window_ever_selected is True
    assert during.dormancy_window_tasks_scored_before_first_selection == 1
    assert during.dormancy_window_elapsed_seconds == pytest.approx(120.0)  # admission (00:00) -> partial task (00:02)

    # AFTER: the real "exact" task -- still selected, real prior count has grown, and the
    # dormancy window's own first-selection anchor stays pinned to "partial" (the real
    # first activation), never silently drifting to a later task.
    after = readings_by_condition["exact"]
    assert after.real_selected is True
    assert after.real_prior_retrieval_count == 4
    assert after.dormancy_window_ever_selected is True
    assert after.dormancy_window_tasks_scored_before_first_selection == 1
    assert after.dormancy_window_elapsed_seconds == pytest.approx(120.0)  # unchanged from "during" -- pinned to the real first activation

    # The disclosed Stage 8.3 finding, reconfirmed here end to end: the real campaign
    # artifact's content never scores as a directive, so evaluate_sleeper_retrieval_risk()
    # never escalates past ALLOW for it, REGARDLESS of how activated the retrieval pattern
    # becomes -- the content term gates the whole product to zero every time.
    assert result.content_directive_score == 0.0
    for reading in result.task_readings:
        assert reading.retrieval_risk_gated_score == 0.0
        assert reading.retrieval_risk_action == ALLOW

    # The real activation-shape result, reusing this trial's own five real per-task
    # outcomes (no second pipeline run) -- same clean step Stage 8.5 already measured.
    assert result.activation_shape_selected_sequence == (True, True, True, True, False)
    assert result.activation_shape_transition_count == 1
