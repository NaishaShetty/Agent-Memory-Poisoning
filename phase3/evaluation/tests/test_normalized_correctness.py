"""Tests for `agent.normalized_correctness.evaluate_answer_correctness_normalized()`
-- the additive, non-replacing correctness metric."""

from __future__ import annotations

from phase3.evaluation.agent.normalized_correctness import evaluate_answer_correctness_normalized
from phase3.evaluation.agent.outcomes import (
    EXECUTION_STATUS_ERROR,
    EXECUTION_STATUS_SUCCESS,
    SUCCESS_ANSWER_CORRECT,
    SUCCESS_ANSWER_INCORRECT,
    SUCCESS_EVALUATION_UNDEFINED,
    SUCCESS_EXECUTION_FAILURE,
    AgentExecutionResult,
)


def _result(answer, status=EXECUTION_STATUS_SUCCESS):
    return AgentExecutionResult(
        task_id="t1", condition="RETRIEVED_MEMORY", answer=answer, execution_status=status,
        selected_memory_ids=(), used_memory_ids=None, execution_metadata={},
    )


def test_real_dataset_case_extreme_sports_now_counts_correct():
    # The exact real case from PHASE3_3_DATASET_FULL_120x2_COMPLETION_REPORT.md
    # section 3 that the frozen exact-match grader marked incorrect.
    r = _result("extreme sports [evidence-slot-1]")
    result = evaluate_answer_correctness_normalized(r, "Extreme sports")
    assert result.status == SUCCESS_ANSWER_CORRECT
    assert result.value == 1.0


def test_genuinely_wrong_answer_still_incorrect():
    r = _result("The Beatles")
    result = evaluate_answer_correctness_normalized(r, "Extreme sports")
    assert result.status == SUCCESS_ANSWER_INCORRECT
    assert result.value == 0.0


def test_execution_failure_reported_as_such():
    r = _result(None, status=EXECUTION_STATUS_ERROR)
    result = evaluate_answer_correctness_normalized(r, "Extreme sports")
    assert result.status == SUCCESS_EXECUTION_FAILURE
    assert result.value is None


def test_no_expected_answer_is_undefined():
    r = _result("some answer")
    result = evaluate_answer_correctness_normalized(r, None)
    assert result.status == SUCCESS_EVALUATION_UNDEFINED


def test_case_and_punctuation_insensitive():
    r = _result("It's TRANSGENDER, definitely.")
    result = evaluate_answer_correctness_normalized(r, "Transgender")
    assert result.status == SUCCESS_ANSWER_CORRECT


def test_empty_expected_answer_never_counts_as_correct():
    r = _result("anything at all")
    result = evaluate_answer_correctness_normalized(r, "")
    assert result.status == SUCCESS_ANSWER_INCORRECT
