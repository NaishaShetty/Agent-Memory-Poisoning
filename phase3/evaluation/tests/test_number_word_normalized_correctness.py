"""Tests for the number-word normalization metric: the real 'Ten years ago' (answer)
vs '10 years ago' (gold) gap found in the SHARED_REASONING_LOSS quantification pass,
plus compound numbers, and confirmation it never over-credits beyond that."""

from __future__ import annotations

from phase3.evaluation.agent.number_word_normalized_correctness import evaluate_answer_correctness_number_word_normalized
from phase3.evaluation.agent.outcomes import EXECUTION_STATUS_SUCCESS, AgentExecutionResult


def _result(answer):
    return AgentExecutionResult(
        task_id="t1", condition="B_GOLD_EVIDENCE", answer=answer,
        execution_status=EXECUTION_STATUS_SUCCESS, selected_memory_ids=(), used_memory_ids=None, execution_metadata={},
    )


def test_real_case_ten_years_ago_credited():
    r = evaluate_answer_correctness_number_word_normalized(
        _result("Ten years ago [10:37 am on 27 June, 2023]."), "10 years ago"
    )
    assert r.status == "ANSWER_CORRECT"


def test_compound_number_word_twenty_three():
    r = evaluate_answer_correctness_number_word_normalized(_result("She is twenty-three years old."), "23 years old")
    assert r.status == "ANSWER_CORRECT"


def test_compound_number_word_space_separated():
    r = evaluate_answer_correctness_number_word_normalized(_result("twenty three apples"), "23 apples")
    assert r.status == "ANSWER_CORRECT"


def test_never_credits_a_genuinely_different_number():
    r = evaluate_answer_correctness_number_word_normalized(_result("Twelve years ago."), "10 years ago")
    assert r.status == "ANSWER_INCORRECT"


def test_no_number_word_present_behaves_like_plain_normalized_match():
    r = evaluate_answer_correctness_number_word_normalized(_result("Vancouver."), "Vancouver")
    assert r.status == "ANSWER_CORRECT"


def test_no_number_word_present_behaves_like_plain_normalized_miss():
    r = evaluate_answer_correctness_number_word_normalized(_result("Toronto."), "Vancouver")
    assert r.status == "ANSWER_INCORRECT"


def test_ordinal_words_not_touched():
    """'third' is deliberately out of scope (closed cardinal-only vocabulary) --
    must not be silently mis-mapped to a cardinal digit."""
    r = evaluate_answer_correctness_number_word_normalized(_result("her third child"), "3rd child")
    assert r.status == "ANSWER_INCORRECT"


def test_none_answer_or_gold_returns_undefined():
    assert evaluate_answer_correctness_number_word_normalized(_result(None), "10").status == "EVALUATION_UNDEFINED"
    assert evaluate_answer_correctness_number_word_normalized(_result("10"), None).status == "EVALUATION_UNDEFINED"
