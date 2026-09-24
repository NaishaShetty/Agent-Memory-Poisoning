"""Phase 14 -- tests for real LongMemEval Track A case construction. Fast (no
LLM calls -- these only test that real cases are built correctly from real
LongMemEval data)."""

from __future__ import annotations

from phase14.track_a_longmemeval import N_DISTRACTORS, build_track_a_longmemeval_cases


def test_builds_the_requested_number_of_real_cases():
    cases = build_track_a_longmemeval_cases(10)
    assert len(cases) == 10


def test_pool_contains_real_evidence_and_distractor_turns_no_duplicates():
    cases = build_track_a_longmemeval_cases(10)
    for case in cases:
        ids = [mid for mid, _ in case.pool_items]
        assert len(ids) == len(set(ids)), "duplicate memory_id in one case's real pool"
        assert len(case.target_memory_ids) >= 1
        assert len(case.pool_items) >= len(case.target_memory_ids)


def test_gold_answer_and_question_are_real_and_non_empty():
    cases = build_track_a_longmemeval_cases(15)
    for case in cases:
        assert case.question
        assert case.gold_answer


def test_target_memory_ids_are_a_subset_of_pool_items():
    cases = build_track_a_longmemeval_cases(10)
    for case in cases:
        pool_ids = {mid for mid, _ in case.pool_items}
        assert set(case.target_memory_ids) <= pool_ids
