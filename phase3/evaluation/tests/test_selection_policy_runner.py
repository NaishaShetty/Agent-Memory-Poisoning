"""Tests for `agent_runtime.selection_policy_runner.run_agent_task_with_selection_policy()`
-- the real threshold-based selection path, wired into an actual agent run for the
first time. Uses `MockMem0Adapter` (existing, real test infra) + `FakeLLMProvider`
+ a monkeypatched `select_by_threshold` (avoids loading the real embedding model in
a fast unit test, matching `test_selection_policy.py`'s own convention)."""

from __future__ import annotations

import phase3.evaluation.agent_runtime.selection_policy_runner as spr
from phase3.evaluation.agent.outcomes import EXECUTION_STATUS_SUCCESS
from phase3.evaluation.agent_runtime.runner import AgentTaskInput, RunConfiguration
from phase3.evaluation.foundations.mocks.mock_mem0 import MockMem0Adapter
from phase3.evaluation.foundations.selection_policy import SelectionResult
from phase3.evaluation.foundations.similarity import ScoredCandidate
from phase3.evaluation.llm.provider import GenerationConfig
from phase3.evaluation.tests.test_agent_runtime import FakeLLMProvider


def _config():
    return GenerationConfig(temperature=0.0, seed=42, max_tokens=32, enable_thinking=False, n_ctx=2048)


def _seeded_foundation():
    foundation = MockMem0Adapter()
    foundation.initialize({})
    foundation.add_memory("m1", {"text": "Caroline went to a support group on 7 May 2023."})
    foundation.add_memory("m2", {"text": "Melanie painted a sunrise in 2022."})
    foundation.add_memory("m3", {"text": "Unrelated content about weather."})
    return foundation


def test_selection_policy_runner_selects_only_above_threshold(monkeypatch):
    def _fake_select(query, candidates, threshold, max_k=5):
        selected = [ScoredCandidate(memory_id=mid, content=c, score=0.9) for mid, c in candidates if mid != "m3"]
        rejected = [ScoredCandidate(memory_id=mid, content=c, score=0.1) for mid, c in candidates if mid == "m3"]
        return SelectionResult(selected=tuple(selected), rejected=tuple(rejected), threshold=threshold)

    monkeypatch.setattr(spr, "select_by_threshold", _fake_select)

    foundation = _seeded_foundation()
    provider = FakeLLMProvider()
    outcome, rejected_ids, selection_result = spr.run_agent_task_with_selection_policy(
        AgentTaskInput(
            task_id="t1", prompt="When did Caroline go to the support group?",
            condition="RETRIEVED_MEMORY", retrieval_query={"text": "support group"}, top_k=5,
        ),
        foundation=foundation,
        config=RunConfiguration(llm_provider=provider, generation_config=_config()),
    )

    assert outcome.execution_result.execution_status == EXECUTION_STATUS_SUCCESS
    assert set(outcome.selected_memory_ids) == {"m1", "m2"}
    assert rejected_ids == ("m3",)
    assert selection_result is not None
    assert selection_result.threshold > 0


def test_selection_policy_runner_can_select_zero(monkeypatch):
    def _fake_select_none(query, candidates, threshold, max_k=5):
        rejected = [ScoredCandidate(memory_id=mid, content=c, score=0.1) for mid, c in candidates]
        return SelectionResult(selected=(), rejected=tuple(rejected), threshold=threshold)

    monkeypatch.setattr(spr, "select_by_threshold", _fake_select_none)

    foundation = _seeded_foundation()
    provider = FakeLLMProvider()
    outcome, rejected_ids, selection_result = spr.run_agent_task_with_selection_policy(
        AgentTaskInput(
            task_id="t1", prompt="Unrelated query", condition="RETRIEVED_MEMORY",
            retrieval_query={"text": "unrelated query"}, top_k=5,
        ),
        foundation=foundation,
        config=RunConfiguration(llm_provider=provider, generation_config=_config()),
    )

    assert outcome.selected_memory_ids == ()
    assert outcome.agent_visible_context["memory_content"] == []
    assert len(rejected_ids) == 3
    assert outcome.execution_result.execution_status == EXECUTION_STATUS_SUCCESS


def test_selection_policy_runner_rejects_wrong_condition():
    import pytest
    foundation = _seeded_foundation()
    provider = FakeLLMProvider()
    with pytest.raises(ValueError):
        spr.run_agent_task_with_selection_policy(
            AgentTaskInput(task_id="t1", prompt="q", condition="NO_MEMORY"),
            foundation=foundation,
            config=RunConfiguration(llm_provider=provider, generation_config=_config()),
        )
