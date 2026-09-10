"""Tests for the multi-reference correctness metric: reuses normalized's own
bidirectional-substring rule, just checked against gold PLUS aliases; falls back
to gold-only (identical to normalized) when no aliases are supplied."""

from __future__ import annotations

from phase3.evaluation.agent.multi_reference_correctness import evaluate_answer_correctness_multi_reference
from phase3.evaluation.agent.outcomes import EXECUTION_STATUS_SUCCESS, AgentExecutionResult


def _result(answer):
    return AgentExecutionResult(
        task_id="t1", condition="B_GOLD_EVIDENCE", answer=answer,
        execution_status=EXECUTION_STATUS_SUCCESS, selected_memory_ids=(), used_memory_ids=None, execution_metadata={},
    )


def test_matches_gold_directly_no_aliases_needed():
    r = evaluate_answer_correctness_multi_reference(_result("Vancouver."), "Vancouver")
    assert r.status == "ANSWER_CORRECT"
    assert r.detail["matched_via_alias"] is False


def test_real_case_credited_via_alias_not_gold():
    """The real 'quit'/'give up' case -- fails plain normalized, passes via alias."""
    r = evaluate_answer_correctness_multi_reference(
        _result("Jon tells Gina he won't give up."), "quit",
        aliases=["give up", "stop trying", "abandon it"],
    )
    assert r.status == "ANSWER_CORRECT"
    assert r.detail["matched_via_alias"] is True
    assert r.detail["matched_reference"] == "give up"


def test_falls_back_to_gold_only_when_no_aliases_given_identical_to_normalized():
    r = evaluate_answer_correctness_multi_reference(_result("give up"), "quit", aliases=None)
    assert r.status == "ANSWER_INCORRECT"
    assert r.detail["used_aliases"] is False


def test_genuinely_wrong_answer_not_credited_even_with_aliases_present():
    r = evaluate_answer_correctness_multi_reference(
        _result("Toronto."), "Vancouver", aliases=["Vancouver, Canada", "the city of Vancouver"],
    )
    assert r.status == "ANSWER_INCORRECT"


def test_num_references_checked_counts_gold_plus_all_aliases():
    r = evaluate_answer_correctness_multi_reference(
        _result("nope"), "quit", aliases=["give up", "stop trying"],
    )
    assert r.detail["num_references_checked"] == 3  # gold + 2 aliases


def test_none_answer_or_gold_returns_undefined():
    assert evaluate_answer_correctness_multi_reference(_result(None), "x").status == "EVALUATION_UNDEFINED"
    assert evaluate_answer_correctness_multi_reference(_result("x"), None).status == "EVALUATION_UNDEFINED"


def test_execution_failure_short_circuits():
    er = AgentExecutionResult(
        task_id="t1", condition="x", answer=None, execution_status="ERROR",
        selected_memory_ids=(), used_memory_ids=None, execution_metadata={},
    )
    assert evaluate_answer_correctness_multi_reference(er, "gold").status == "EXECUTION_FAILURE"
