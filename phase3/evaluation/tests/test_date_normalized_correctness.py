"""Tests for the date-normalization metric (roadmap Sec 15.1): digit zero-padding
and range-vs-point-estimate mismatches, using the real gold/answer pairs found
while hand-classifying the SHARED_REASONING_LOSS cases in the V4 diagnosis pass."""

from __future__ import annotations

from datetime import date

from phase3.evaluation.agent.date_normalized_correctness import (
    evaluate_answer_correctness_date_normalized,
    parse_gold_date_spec,
)
from phase3.evaluation.agent.outcomes import EXECUTION_STATUS_SUCCESS, AgentExecutionResult


def _result(answer):
    return AgentExecutionResult(
        task_id="t1", condition="B_GOLD_EVIDENCE", answer=answer,
        execution_status=EXECUTION_STATUS_SUCCESS, selected_memory_ids=(), used_memory_ids=None,
        execution_metadata={},
    )


def test_digit_padding_point_date_credited():
    r = evaluate_answer_correctness_date_normalized(_result("Calvin met local artists on 03 October 2023."), "October 3, 2023")
    assert r.status == "ANSWER_CORRECT"


def test_digit_padding_point_date_no_false_credit_wrong_date():
    r = evaluate_answer_correctness_date_normalized(_result("Calvin met local artists on 04 October 2023."), "October 3, 2023")
    assert r.status == "ANSWER_INCORRECT"


def test_week_before_window_credits_contained_point_estimate():
    r = evaluate_answer_correctness_date_normalized(
        _result("The flood occurred last week, which is approximately 09 May 2023."),
        "On a week before 16 May, 2023",
    )
    assert r.status == "ANSWER_CORRECT"


def test_week_before_window_rejects_point_outside_window():
    r = evaluate_answer_correctness_date_normalized(
        _result("The flood occurred on 01 May 2023."),
        "On a week before 16 May, 2023",
    )
    assert r.status == "ANSWER_INCORRECT"


def test_week_before_window_excludes_anchor_date_itself():
    """The anchor date itself is NOT "before" it -- boundary must be strict."""
    r = evaluate_answer_correctness_date_normalized(
        _result("It happened on 16 May 2023."),
        "On a week before 16 May, 2023",
    )
    assert r.status == "ANSWER_INCORRECT"


def test_weekday_before_resolves_to_exact_point():
    spec = parse_gold_date_spec("Wednesday before 9 February, 2023")
    assert spec is not None
    assert spec.kind == "POINT"
    assert spec.point == date(2023, 2, 8)  # 9 Feb 2023 is a Thursday; prior Wednesday is 8 Feb


def test_non_date_gold_returns_undefined_never_guesses():
    r = evaluate_answer_correctness_date_normalized(_result("Ten years ago."), "10 years ago")
    assert r.status == "EVALUATION_UNDEFINED"


def test_season_approximation_gold_returns_undefined():
    r = evaluate_answer_correctness_date_normalized(_result("June 2022."), "approximately summer of 2022")
    assert r.status == "EVALUATION_UNDEFINED"


def test_gold_date_but_answer_has_no_date_is_incorrect_not_undefined():
    r = evaluate_answer_correctness_date_normalized(_result("It is not mentioned."), "October 3, 2023")
    assert r.status == "ANSWER_INCORRECT"


def test_never_credits_a_genuinely_different_date_across_month_boundary():
    r = evaluate_answer_correctness_date_normalized(_result("It happened on 30 September 2023."), "October 3, 2023")
    assert r.status == "ANSWER_INCORRECT"
