"""Tests for `agent_runtime.reference_agent_v2.run_agent_task_v2()` -- the bounded
V2 pipeline (retrieval -> selection -> reasoning -> optional one-time refinement).
Uses `MockMem0Adapter` + `FakeLLMProvider` + a monkeypatched `select_by_threshold`
(fast unit tests, no real model), matching this session's established convention."""

from __future__ import annotations

import phase3.evaluation.agent_runtime.reference_agent_v2 as rav2
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
    return foundation


def _select_all(monkeypatch):
    def _fake(query, candidates, threshold, max_k=5):
        selected = [ScoredCandidate(memory_id=mid, content=c, score=0.9) for mid, c in candidates]
        return SelectionResult(selected=tuple(selected), rejected=(), threshold=threshold)
    monkeypatch.setattr(rav2, "select_by_threshold", _fake)


def test_v2_no_refinement_when_answer_is_sufficient(monkeypatch):
    _select_all(monkeypatch)
    foundation = _seeded_foundation()
    provider = FakeLLMProvider(response_text="Caroline went on 7 May 2023.")
    outcome, state = rav2.run_agent_task_v2(
        AgentTaskInput(task_id="t1", prompt="When did Caroline go?", condition="RETRIEVED_MEMORY",
                        retrieval_query={"text": "support group"}, top_k=5),
        foundation=foundation, config=RunConfiguration(llm_provider=provider, generation_config=_config()),
    )
    assert outcome.execution_result.execution_status == EXECUTION_STATUS_SUCCESS
    assert state.refinement_triggered is False
    assert state.refinement_reason is None
    assert state.final_answer == "Caroline went on 7 May 2023."
    assert len(provider.calls) == 1  # exactly one generation call, no refinement


def test_v2_triggers_bounded_refinement_on_insufficient_answer(monkeypatch):
    _select_all(monkeypatch)
    foundation = _seeded_foundation()
    provider = FakeLLMProvider(response_text="I don't know based on the given information.")
    outcome, state = rav2.run_agent_task_v2(
        AgentTaskInput(task_id="t1", prompt="When did Caroline go?", condition="RETRIEVED_MEMORY",
                        retrieval_query={"text": "support group"}, top_k=5),
        foundation=foundation, config=RunConfiguration(llm_provider=provider, generation_config=_config()),
    )
    assert state.refinement_triggered is True
    assert state.refinement_reason == "i don't know"
    assert state.refinement_query is not None
    # exactly 2 generation calls -- pass 1 + the ONE bounded refinement, never more
    assert len(provider.calls) == 2
    assert outcome.execution_result.execution_status == EXECUTION_STATUS_SUCCESS


def test_v2_considered_memory_ids_includes_both_passes(monkeypatch):
    _select_all(monkeypatch)
    foundation = _seeded_foundation()
    provider = FakeLLMProvider(response_text="not enough information to answer")
    outcome, state = rav2.run_agent_task_v2(
        AgentTaskInput(task_id="t1", prompt="q", condition="RETRIEVED_MEMORY",
                        retrieval_query={"text": "support group"}, top_k=5),
        foundation=foundation, config=RunConfiguration(llm_provider=provider, generation_config=_config()),
    )
    assert set(state.considered_memory_ids) == {"m1", "m2"}
    assert state.used_memory_ids is not None  # citation diagnostic always computed when an answer exists


def test_v2_rejects_wrong_condition():
    import pytest
    foundation = _seeded_foundation()
    provider = FakeLLMProvider()
    with pytest.raises(ValueError):
        rav2.run_agent_task_v2(
            AgentTaskInput(task_id="t1", prompt="q", condition="NO_MEMORY"),
            foundation=foundation, config=RunConfiguration(llm_provider=provider, generation_config=_config()),
        )


def test_v2_refinement_never_fires_twice_even_if_second_answer_also_insufficient(monkeypatch):
    _select_all(monkeypatch)
    foundation = _seeded_foundation()
    provider = FakeLLMProvider(response_text="i do not know")  # both passes give an "insufficient" answer
    outcome, state = rav2.run_agent_task_v2(
        AgentTaskInput(task_id="t1", prompt="q", condition="RETRIEVED_MEMORY",
                        retrieval_query={"text": "support group"}, top_k=5),
        foundation=foundation, config=RunConfiguration(llm_provider=provider, generation_config=_config()),
    )
    assert state.refinement_triggered is True
    assert len(provider.calls) == 2  # structurally bounded -- never a 3rd call
