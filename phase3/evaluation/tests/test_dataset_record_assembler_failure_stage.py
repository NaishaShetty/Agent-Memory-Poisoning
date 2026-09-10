"""Regression test for the `_condition_c_summary()` failure_stage bug fix
(PHASE3_V4_DIAGNOSIS_AND_85_90_ROADMAP.md section 1.1): the assembled dataset must
report the identity-resolved failure_stage when available (Mem0's
STRATEGY_METADATA_LOOKUP path), and must still report the base failure_stage
unchanged when no resolution was performed (A-MEM's STRATEGY_DIRECT_ASSIGNMENT path,
or any record with no `resolved_evaluation` block)."""

from __future__ import annotations

from phase3.evaluation.agent_runtime.dataset_record_assembler import _condition_c_summary


def _base_trace(**overrides):
    trace = {
        "agent_output": "some answer",
        "evaluation_result": {"success_status": "ANSWER_INCORRECT", "success_value": 0.0},
        "failure_stage": "RETRIEVAL_FAILURE",  # the (wrong) unresolved base value
        "fingerprints": {"trace_fingerprint": "abc123"},
        "retrieved_memories": ["m1", "m2"],
        "selected_memories": ["m1"],
        "exposed_memories": ["m1"],
    }
    trace.update(overrides)
    return trace


def test_uses_resolved_failure_stage_when_present():
    result = {
        "status": "SUCCESSFUL_EVALUATION",
        "trace": _base_trace(resolved_evaluation={
            "failure_stage": "AGENT_FAILURE_WITH_EVIDENCE",  # the correct, resolved value
            "strict_tsr": {"value": 1.0, "status": "OK"},
        }),
    }
    summary = _condition_c_summary(result)
    assert summary["failure_stage"] == "AGENT_FAILURE_WITH_EVIDENCE"


def test_falls_back_to_base_failure_stage_when_no_resolution_present():
    """A-MEM's direct-assignment path (or any record with no resolved_evaluation block)
    must be completely unaffected by this fix -- same value as before."""
    result = {"status": "SUCCESSFUL_EVALUATION", "trace": _base_trace()}  # no resolved_evaluation key at all
    summary = _condition_c_summary(result)
    assert summary["failure_stage"] == "RETRIEVAL_FAILURE"


def test_falls_back_when_resolved_evaluation_present_but_missing_failure_stage_key():
    result = {
        "status": "SUCCESSFUL_EVALUATION",
        "trace": _base_trace(resolved_evaluation={"strict_tsr": {"value": 0.0, "status": "OK"}}),
    }
    summary = _condition_c_summary(result)
    assert summary["failure_stage"] == "RETRIEVAL_FAILURE"


def test_non_successful_result_unaffected():
    result = {"status": "EXECUTION_FAILURE", "error": "boom"}
    summary = _condition_c_summary(result)
    assert summary == {"status": "EXECUTION_FAILURE", "error": "boom"}


def test_none_result_unaffected():
    assert _condition_c_summary(None) == {"status": "NOT_RUN"}
