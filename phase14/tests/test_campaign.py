"""Phase 14 -- structural tests for the campaign orchestration. Real, but
small-scale (n=3 Track A tasks, all 9 real Track B cases) to keep real LLM
cost low for a fast/CI-friendly check; the full n=40 pilot is run separately
via `python -m phase14.campaign` and its own real results are reported in
docs/phase14/PHASE14_UTILITY_METRICS_REPORT.md, not re-asserted here (an LLM
generation is not perfectly reproducible run-to-run at this project's own
observed rate -- these tests check STRUCTURE, never a pinned real number).
"""

from __future__ import annotations

from phase14.campaign import UTILITY_PILOT_CONFIGS, compute_urs, run_track_a, run_track_b


def test_run_track_a_returns_a_summary_per_real_config():
    summaries = run_track_a(pilot_size=3)
    assert set(summaries.keys()) == set(UTILITY_PILOT_CONFIGS)
    for config, summary in summaries.items():
        assert summary.n_tasks == 3
        assert 0.0 <= summary.task_success_rate <= 1.0
        assert summary.n_success == round(summary.task_success_rate * 3)


def test_run_track_b_returns_a_summary_per_real_config_for_all_nine_cases():
    summaries = run_track_b()
    assert set(summaries.keys()) == set(UTILITY_PILOT_CONFIGS)
    for config, summary in summaries.items():
        assert summary.n_tasks == 9
        assert 0.0 <= summary.gold_rate <= 1.0
        assert 0.0 <= summary.forged_rate <= 1.0
        assert 0.0 <= summary.exclusion_rate <= 1.0


def test_urs_is_computed_relative_to_the_real_b0_baseline():
    track_a = run_track_a(pilot_size=5)
    if track_a["B0"].task_success_rate == 0.0:
        # Real, disclosed edge case utility_retention_score() itself refuses
        # to silently paper over -- undefined, not a bug in compute_urs().
        import pytest

        with pytest.raises(ValueError):
            compute_urs(track_a)
        return
    urs = compute_urs(track_a)
    assert set(urs.keys()) == set(UTILITY_PILOT_CONFIGS) - {"B0"}
    for config, value in urs.items():
        expected = track_a[config].task_success_rate / track_a["B0"].task_success_rate
        assert abs(value - expected) < 1e-9
