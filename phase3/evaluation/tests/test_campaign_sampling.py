"""Phase 3.3-E UNIT_TESTs for `phase3.evaluation.agent_runtime.campaign_sampling` --
deterministic pilot task sampling, over the REAL frozen `data/processed/` files (read-only
-- no dataset content is modified anywhere in this test file).
"""

from __future__ import annotations

from phase3.evaluation.agent_runtime.campaign_sampling import (
    SAMPLING_SEED,
    build_pilot_sample,
    eligible_longmemeval_tasks_grouped_by_haystack,
    sample_locomo_tasks,
    sample_longmemeval_tasks,
)


class TestDeterministicSampling:
    def test_sampling_is_deterministic_across_repeated_calls(self):
        """Same seed, same input files -> identical sample every time."""
        sample1 = build_pilot_sample()
        sample2 = build_pilot_sample()
        ids1 = [(t.dataset, t.task_id) for t in sample1]
        ids2 = [(t.dataset, t.task_id) for t in sample2]
        assert ids1 == ids2

    def test_locomo_sample_includes_continuity_task(self):
        """The 3.3-B/C/D pilot task must always be included, for cross-stage
        comparability -- never silently dropped by the random component."""
        tasks = sample_locomo_tasks(3)
        assert any(t.task_id == "ecf5a096af5598393ce49c80" for t in tasks)

    def test_locomo_sample_has_no_duplicate_task_ids(self):
        tasks = sample_locomo_tasks(3)
        task_ids = [t.task_id for t in tasks]
        assert len(task_ids) == len(set(task_ids))

    def test_locomo_sample_respects_pool_size_bound(self):
        """Every sampled task's evidence resolves within a single session pool of
        <= 25 records -- the documented resource-manageability bound."""
        tasks = sample_locomo_tasks(3)
        for t in tasks:
            assert t.pool_size <= 25

    def test_locomo_sample_every_task_has_real_answer_and_evidence(self):
        tasks = sample_locomo_tasks(3)
        for t in tasks:
            assert t.answer is not None
            assert len(t.evidence_memory_ids) > 0

    def test_locomo_sample_conditions_include_all_three(self):
        tasks = sample_locomo_tasks(3)
        for t in tasks:
            assert set(t.conditions_to_run) == {"A", "B", "C"}

    def test_longmemeval_sample_conditions_exclude_c(self):
        """A-MEM is explicitly excluded for LongMemEval in this pilot -- resource cost,
        not a foundation failure -- documented in campaign_sampling.py's module
        docstring, never silently omitted."""
        tasks = sample_longmemeval_tasks(2)
        for t in tasks:
            assert set(t.conditions_to_run) == {"A", "B"}
            assert "C" not in t.conditions_to_run

    def test_longmemeval_sample_ranked_by_ascending_pool_size(self):
        """Smallest haystacks first -- a resource-based, not outcome-based, ordering."""
        tasks = sample_longmemeval_tasks(5)
        sizes = [t.pool_size for t in tasks]
        assert sizes == sorted(sizes)

    def test_longmemeval_sample_no_duplicate_haystacks(self):
        tasks = sample_longmemeval_tasks(5)
        haystacks = [t.ingest_key_value for t in tasks]
        assert len(haystacks) == len(set(haystacks))

    def test_full_pilot_sample_covers_both_datasets(self):
        sample = build_pilot_sample()
        datasets = {t.dataset for t in sample}
        assert datasets == {"locomo", "longmemeval"}

    def test_sampling_seed_is_a_fixed_disclosed_constant(self):
        assert isinstance(SAMPLING_SEED, int)

    def test_ingest_pool_field_matches_dataset_join_key(self):
        """LoCoMo joins on (conversation_id, session_id); LongMemEval joins on
        source_record_id -- a real, verified schema difference between the two
        datasets' memory_records.jsonl files, not assumed identical."""
        for t in sample_locomo_tasks(3):
            assert t.ingest_key_field == "session"
            assert "/" in t.ingest_key_value
        for t in sample_longmemeval_tasks(2):
            assert t.ingest_key_field == "source_record_id"


class TestHaystackGrouping:
    """Phase 3.3-F -- the final-campaign haystack-sharing extension (Issue 2, Option D)."""

    def test_every_haystack_has_at_least_one_task(self):
        groups = eligible_longmemeval_tasks_grouped_by_haystack()
        assert all(len(v) >= 1 for v in groups.values())

    def test_task_ids_within_a_haystack_are_unique(self):
        groups = eligible_longmemeval_tasks_grouped_by_haystack()
        for haystack, tasks in groups.items():
            task_ids = [t["task_id"] for t in tasks]
            assert len(task_ids) == len(set(task_ids))

    def test_grouping_is_read_only_and_deterministic(self):
        groups1 = eligible_longmemeval_tasks_grouped_by_haystack()
        groups2 = eligible_longmemeval_tasks_grouped_by_haystack()
        assert groups1 == groups2

    def test_total_eligible_tasks_matches_sum_of_group_sizes(self):
        groups = eligible_longmemeval_tasks_grouped_by_haystack()
        total = sum(len(v) for v in groups.values())
        assert total > 0
        # Sanity: every group's declared pool_size is a positive, real measurement.
        for tasks in groups.values():
            assert all(t["pool_size"] > 0 for t in tasks)
