"""Tests for `agent_runtime.gold_evidence_runner.run_gold_evidence_task()` -- the real
Condition B (GOLD_EVIDENCE) execution path added for the clean-agent behavioral dataset.
Uses a fake `LLMProvider`, no real network/GPU -- mirrors `test_agent_runtime.py`'s own
fixture style, never a live-server test."""

from __future__ import annotations

from phase3.evaluation.agent.conditions import CONDITION_GOLD_EVIDENCE
from phase3.evaluation.agent.outcomes import EXECUTION_STATUS_ERROR, EXECUTION_STATUS_SUCCESS
from phase3.evaluation.agent_runtime.gold_evidence_runner import (
    GoldEvidenceRuntimeLeakageError,
    GoldEvidenceTaskInput,
    run_gold_evidence_task,
)
from phase3.evaluation.agent_runtime.runner import RunConfiguration
from phase3.evaluation.llm.provider import GenerationConfig
from phase3.evaluation.tests.test_agent_runtime import FakeLLMProvider


def _config(provider):
    generation_config = GenerationConfig(
        temperature=0.0, seed=42, max_tokens=32, enable_thinking=False, n_ctx=2048
    )
    return RunConfiguration(llm_provider=provider, generation_config=generation_config)


def test_run_gold_evidence_task_success():
    task = GoldEvidenceTaskInput(
        task_id="t1", prompt="What did X say?",
        evidence_items=[{"gold_evidence_id": "ev-1", "content": "X said hello."}],
    )
    outcome = run_gold_evidence_task(task, _config(FakeLLMProvider()))

    assert outcome.condition == CONDITION_GOLD_EVIDENCE
    assert outcome.execution_result.execution_status == EXECUTION_STATUS_SUCCESS
    assert outcome.execution_result.answer == "fake answer"
    assert outcome.retrieved_memory_ids == ()
    assert outcome.selected_memory_ids == ()
    assert outcome.foundation_identity is None
    assert outcome.exposed_memory_ids == ("evidence-slot-1",)


def test_run_gold_evidence_task_never_leaks_literal_gold_evidence_id():
    task = GoldEvidenceTaskInput(
        task_id="t1", prompt="What did X say?",
        evidence_items=[{"gold_evidence_id": "SECRET-EVAL-ONLY-ID", "content": "X said hello."}],
    )
    outcome = run_gold_evidence_task(task, _config(FakeLLMProvider()))

    import json
    serialized = json.dumps(outcome.agent_visible_context)
    assert "SECRET-EVAL-ONLY-ID" not in serialized
    assert outcome.agent_visible_context["memory_content"][0]["memory_id"] == "evidence-slot-1"


def test_run_gold_evidence_task_generation_failure_reports_error():
    task = GoldEvidenceTaskInput(
        task_id="t1", prompt="What did X say?",
        evidence_items=[{"gold_evidence_id": "ev-1", "content": "X said hello."}],
    )
    outcome = run_gold_evidence_task(task, _config(FakeLLMProvider(fail=True, fail_times=99)))

    assert outcome.execution_result.execution_status == EXECUTION_STATUS_ERROR
    assert outcome.execution_result.answer is None


def test_run_gold_evidence_task_no_evidence_items_still_runs():
    task = GoldEvidenceTaskInput(task_id="t1", prompt="What did X say?", evidence_items=[])
    outcome = run_gold_evidence_task(task, _config(FakeLLMProvider()))

    assert outcome.agent_visible_context["memory_content"] == []
    assert outcome.execution_result.execution_status == EXECUTION_STATUS_SUCCESS
