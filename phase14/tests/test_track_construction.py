"""Phase 14 -- tests for real Track A/B case construction. Fast (no LLM
calls -- these only test that real cases are built correctly from real data)."""

from __future__ import annotations

import pytest

from phase14.track_a_benign import N_DISTRACTORS as A_N_DISTRACTORS, build_track_a_cases
from phase14.track_b_poison import build_track_b_cases


def test_track_a_builds_the_requested_number_of_real_cases():
    cases = build_track_a_cases(10)
    assert len(cases) == 10


def test_track_a_pool_contains_target_plus_distractors_no_duplicates():
    cases = build_track_a_cases(5)
    for case in cases:
        assert len(case.pool_items) == 1 + A_N_DISTRACTORS
        ids = [mid for mid, _ in case.pool_items]
        assert len(ids) == len(set(ids)), "duplicate memory_id in one case's real pool"
        assert case.pool_items[0][0] == case.target_memory_id


def test_track_a_target_content_actually_contains_the_real_gold_answer():
    """Sanity check: the target memory's real declarative_text must actually
    contain the real gold answer verbatim (it is built as f'{question}
    {answer}') -- otherwise a real, undefended B0 baseline could not even
    succeed, which would silently invalidate the whole pilot."""
    cases = build_track_a_cases(10)
    for case in cases:
        target_text = case.pool_items[0][1]
        assert case.gold_answer in target_text


def test_track_a_rejects_pilot_size_larger_than_real_pool():
    with pytest.raises(ValueError):
        build_track_a_cases(10_000)


def test_track_b_builds_nine_real_cases_across_three_families():
    cases = build_track_b_cases()
    assert len(cases) == 9
    families = {c.attack_family for c in cases}
    assert families == {"DSRM", "FARMA", "MPBENCH"}


def test_track_b_target_content_matches_the_real_persisted_poison_scenario():
    from phase11.data.real_corpus import real_poison_scenarios

    real_content = {m.scenario_id: m.content_text for m in real_poison_scenarios().memories}
    cases = build_track_b_cases()
    for case in cases:
        assert case.pool_items[0][0] == case.target_scenario_id
        assert case.pool_items[0][1] == real_content[case.target_scenario_id]


def test_track_b_gold_and_forged_answers_are_real_and_distinct():
    cases = build_track_b_cases()
    for case in cases:
        assert case.gold_answer
        assert case.forged_claim
        assert case.gold_answer != case.forged_claim
