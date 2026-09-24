"""Phase 14 -- structural tests for the multi-dataset Track A campaign
extension. Real (small-scale real LLM calls) but structural, not pinned to
exact numbers subject to real LLM run-to-run variance."""

from __future__ import annotations

from phase14.campaign import (
    DATASETS_WITH_NO_REAL_TASK_LAYER,
    UTILITY_PILOT_CONFIGS,
    combine_track_a_summaries,
    run_track_a,
    run_track_a_longmemeval,
)


def test_datasets_with_no_real_task_layer_are_msc_and_conversation_chronicles():
    assert set(DATASETS_WITH_NO_REAL_TASK_LAYER) == {"msc", "conversation_chronicles"}


def test_run_track_a_longmemeval_returns_a_summary_per_real_config():
    summaries = run_track_a_longmemeval(pilot_size=3)
    assert set(summaries.keys()) == set(UTILITY_PILOT_CONFIGS)
    for config, summary in summaries.items():
        assert summary.n_tasks == 3
        assert 0.0 <= summary.task_success_rate <= 1.0


def test_combine_track_a_summaries_pools_real_counts_not_rates():
    locomo = run_track_a(pilot_size=3)
    longmemeval = run_track_a_longmemeval(pilot_size=3)
    combined = combine_track_a_summaries(locomo, longmemeval)
    for config in UTILITY_PILOT_CONFIGS:
        assert combined[config].n_tasks == locomo[config].n_tasks + longmemeval[config].n_tasks
        assert combined[config].n_success == locomo[config].n_success + longmemeval[config].n_success
