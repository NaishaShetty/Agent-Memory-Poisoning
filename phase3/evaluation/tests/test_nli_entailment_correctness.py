"""Tests for the NLI-entailment metric. Uses the REAL pretrained cross-encoder
(cross-encoder/nli-deberta-v3-base, already cached locally) -- no mocking, since
the whole point of this metric is its specific, validated behavior on real
entailment classification, not a reimplementation of that logic in the test."""

from __future__ import annotations


from phase3.evaluation.agent.nli_entailment_correctness import (
    check_entailment_equivalence,
    evaluate_answer_correctness_nli_entailment,
)
from phase3.evaluation.agent.outcomes import EXECUTION_STATUS_SUCCESS, AgentExecutionResult


def _result(answer):
    return AgentExecutionResult(
        task_id="t1", condition="B_GOLD_EVIDENCE", answer=answer,
        execution_status=EXECUTION_STATUS_SUCCESS, selected_memory_ids=(), used_memory_ids=None, execution_metadata={},
    )


def test_paraphrase_with_question_context_is_credited():
    """A real gap case pulled from this session's own V5 campaign data (normalized
    wrongly scored this incorrect, LLM-judge scored it correct) -- verified
    directly against the real model before being hardcoded here, not assumed."""
    r = evaluate_answer_correctness_nli_entailment(
        _result("John left his IT job because he wanted something that made a difference and aligned with his values and passions."),
        "to focus on things that align with his values and passions",
        question="What made John leave his IT job?",
    )
    assert r.status == "ANSWER_CORRECT"


def test_genuinely_different_answer_is_not_credited():
    r = evaluate_answer_correctness_nli_entailment(
        _result("Toronto."), "Vancouver",
        question="Where did James plan to visit after Toronto?",
    )
    assert r.status == "ANSWER_INCORRECT"


def test_falls_back_to_bare_text_when_no_question_given():
    result = check_entailment_equivalence("Vancouver", "Vancouver.")
    assert result["used_question_context"] is False
    assert result["is_equivalent"] is True


def test_detail_exposes_both_raw_labels_for_auditability():
    r = evaluate_answer_correctness_nli_entailment(
        _result("James planned to visit Vancouver."), "Vancouver",
        question="Where did James plan to visit after Toronto?",
    )
    assert "forward_label" in r.detail
    assert "backward_label" in r.detail
    assert r.detail["forward_label"] in ("entailment", "neutral", "contradiction")


def test_none_answer_or_gold_returns_undefined_no_model_load_needed():
    assert evaluate_answer_correctness_nli_entailment(_result(None), "x").status == "EVALUATION_UNDEFINED"
    assert evaluate_answer_correctness_nli_entailment(_result("x"), None).status == "EVALUATION_UNDEFINED"


def test_execution_failure_short_circuits_no_model_load_needed():
    er = AgentExecutionResult(
        task_id="t1", condition="x", answer=None, execution_status="ERROR",
        selected_memory_ids=(), used_memory_ids=None, execution_metadata={},
    )
    assert evaluate_answer_correctness_nli_entailment(er, "gold").status == "EXECUTION_FAILURE"
