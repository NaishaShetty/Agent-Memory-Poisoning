"""Phase 5.6 -- tests for agent decision/action instrumentation."""

from __future__ import annotations

import json

import pytest

from phase3.evaluation.agent.outcomes import EXECUTION_STATUS_ERROR, EXECUTION_STATUS_SUCCESS
from phase3.evaluation.agent_runtime.messages import DEFAULT_SYSTEM_PROMPT
from phase3.evaluation.agent_runtime.runner import RunConfiguration
from phase3.evaluation.llm.provider import GenerationConfig, LlamaServerEndpoint, LlamaServerProvider, _RawHttpResponse

from phase5.identity.run_identity import EventRunMembershipLedger, ExperimentRunLedger, ExperimentRunRecord
from phase5.schema.event_ledger import Phase5EventLedger
from phase5.wiring.agent_decision_instrumentation import (
    ACTION_SUBMIT_ANSWER,
    FINISH_REASON_FAILED_ALL_ATTEMPTS,
    FINISH_REASON_GENERATED,
    USED_MEMORIES_NOT_OBSERVABLE,
    USED_MEMORIES_OBSERVED,
    instrument_agent_decision,
    record_agent_action,
    record_agent_decision,
)

TS = "2026-09-12T00:00:00+00:00"
CFG = "CFG-decision-test"


@pytest.fixture
def ledgers(tmp_path):
    run_ledger = ExperimentRunLedger(tmp_path / "runs")
    membership_ledger = EventRunMembershipLedger(tmp_path / "membership", run_ledger)
    phase5_ledger = Phase5EventLedger(tmp_path / "phase5_events")
    run = ExperimentRunRecord(
        experiment_id="exp-decision", run_id="RUN-decision-test", dataset="locomo",
        scope={}, started_at=TS, actor="test", reason="decision instrumentation test run",
    )
    run_ledger.register(run)
    return dict(membership_ledger=membership_ledger, phase5_ledger=phase5_ledger, run_id=run.run_id)


def test_record_agent_decision_marks_used_memories_not_observable(ledgers):
    event = record_agent_decision(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-1", decision_id="dec-1",
        exposed_memory_ids=("mem-1", "mem-2"), output="the answer",
        finish_reason=FINISH_REASON_GENERATED, model_identity="qwen3-8b", config_fingerprint=CFG,
        used_memories_observability=USED_MEMORIES_NOT_OBSERVABLE,
        actor="test", reason="generation completed", timestamp=TS,
    )
    assert event.used_memories_observability == USED_MEMORIES_NOT_OBSERVABLE
    assert event.exposed_memory_ids == ("mem-1", "mem-2")
    assert ledgers["phase5_ledger"].exists(event.event_id)
    assert ledgers["membership_ledger"].run_for_event(event.event_id).run_id == ledgers["run_id"]


def test_record_agent_decision_accepts_explicit_observed_when_caller_has_real_signal(ledgers):
    event = record_agent_decision(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-2", decision_id="dec-2",
        exposed_memory_ids=("mem-3",), output="the answer citing [mem-3]",
        finish_reason=FINISH_REASON_GENERATED, model_identity="qwen3-8b", config_fingerprint=CFG,
        used_memories_observability=USED_MEMORIES_OBSERVED,
        actor="test", reason="citation heuristic ran separately", timestamp=TS,
    )
    assert event.used_memories_observability == USED_MEMORIES_OBSERVED


def test_record_agent_action_links_to_decision(ledgers):
    event = record_agent_action(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-3", decision_id="dec-3", action_id="act-3",
        action=ACTION_SUBMIT_ANSWER, result=EXECUTION_STATUS_SUCCESS,
        actor="test", reason="answer submitted", timestamp=TS,
    )
    assert event.decision_id == "dec-3"
    assert event.result == EXECUTION_STATUS_SUCCESS


# ---------------------------------------------------------------------------
# Live: real generate_with_retries() against a scripted (never real-network) provider --
# same scripted-transport pattern Stage 5.4's live_attack_runs.py and this project's own
# frozen test suite (test_sleeper_memory_poisoning.py, test_persistence_gate.py) use.
# ---------------------------------------------------------------------------

def _scripted_provider(reply_text: str) -> LlamaServerProvider:
    def post_json(url: str, body: bytes, timeout: float) -> _RawHttpResponse:
        payload = {
            "choices": [{"message": {"content": reply_text}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "system_fingerprint": "b10717-a32af33de",
        }
        return _RawHttpResponse(status=200, body=json.dumps(payload).encode("utf-8"))
    return LlamaServerProvider(endpoint=LlamaServerEndpoint(), post_json=post_json)


def _run_config(reply_text: str, max_retries: int = 0) -> RunConfiguration:
    return RunConfiguration(
        llm_provider=_scripted_provider(reply_text),
        generation_config=GenerationConfig(temperature=0.0, seed=42, max_tokens=64, enable_thinking=False, n_ctx=1024),
        system_prompt=DEFAULT_SYSTEM_PROMPT, max_retries=max_retries,
    )


def test_live_instrument_agent_decision_success(ledgers):
    messages = [
        {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
        {"role": "user", "content": "Question: when did Melanie go camping?"},
    ]
    result = instrument_agent_decision(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-live", decision_id="dec-live", action_id="act-live",
        exposed_memory_ids=("mem-live-1",), messages=messages, run_config=_run_config("September 2023"),
        actor="test", timestamp=TS,
    )
    assert result.generation_text == "September 2023"
    assert result.decision_event.finish_reason == FINISH_REASON_GENERATED
    assert result.decision_event.output == "September 2023"
    assert result.decision_event.used_memories_observability == USED_MEMORIES_NOT_OBSERVABLE
    assert result.decision_event.exposed_memory_ids == ("mem-live-1",)
    assert result.action_event.decision_id == "dec-live"
    assert result.action_event.action == ACTION_SUBMIT_ANSWER
    assert result.action_event.result == EXECUTION_STATUS_SUCCESS

    # Real config_fingerprint/model_identity, reused verbatim from the real LLM provider,
    # not fabricated.
    assert result.decision_event.config_fingerprint  # non-empty
    assert result.decision_event.model_identity  # non-empty, real model_metadata JSON
    parsed_identity = json.loads(result.decision_event.model_identity)
    assert "repo_id" in parsed_identity

    assert ledgers["phase5_ledger"].exists(result.decision_event.event_id)
    assert ledgers["phase5_ledger"].exists(result.action_event.event_id)
    assert ledgers["membership_ledger"].run_for_event(result.decision_event.event_id).run_id == ledgers["run_id"]
    assert ledgers["membership_ledger"].run_for_event(result.action_event.event_id).run_id == ledgers["run_id"]


def test_live_instrument_agent_decision_succeeds_after_one_retry(ledgers):
    from phase3.evaluation.llm.provider import LLMProviderError

    call_count = {"n": 0}

    def fails_once_then_succeeds(url: str, body: bytes, timeout: float) -> _RawHttpResponse:
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise LLMProviderError("simulated transient transport failure")
        payload = {
            "choices": [{"message": {"content": "answer after retry"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "system_fingerprint": "b10717-a32af33de",
        }
        return _RawHttpResponse(status=200, body=json.dumps(payload).encode("utf-8"))

    run_config = RunConfiguration(
        llm_provider=LlamaServerProvider(endpoint=LlamaServerEndpoint(), post_json=fails_once_then_succeeds),
        generation_config=GenerationConfig(temperature=0.0, seed=42, max_tokens=64, enable_thinking=False, n_ctx=1024),
        system_prompt=DEFAULT_SYSTEM_PROMPT, max_retries=1,
    )
    messages = [{"role": "system", "content": DEFAULT_SYSTEM_PROMPT}, {"role": "user", "content": "Question: x?"}]

    result = instrument_agent_decision(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-retry", decision_id="dec-retry", action_id="act-retry",
        exposed_memory_ids=(), messages=messages, run_config=run_config,
        actor="test", timestamp=TS,
    )
    assert result.generation_text == "answer after retry"
    assert len(result.attempts) == 2
    assert result.attempts[0].succeeded is False
    assert result.attempts[1].succeeded is True
    assert result.decision_event.finish_reason == FINISH_REASON_GENERATED
    assert result.decision_event.output == "answer after retry"
    assert result.action_event.result == EXECUTION_STATUS_SUCCESS


def test_live_instrument_agent_decision_failure_after_exhausting_retries(ledgers):
    from phase3.evaluation.llm.provider import LLMProviderError

    def always_fails(url: str, body: bytes, timeout: float) -> _RawHttpResponse:
        raise LLMProviderError("simulated transport failure")

    run_config = RunConfiguration(
        llm_provider=LlamaServerProvider(endpoint=LlamaServerEndpoint(), post_json=always_fails),
        generation_config=GenerationConfig(temperature=0.0, seed=42, max_tokens=64, enable_thinking=False, n_ctx=1024),
        system_prompt=DEFAULT_SYSTEM_PROMPT, max_retries=1,
    )
    messages = [{"role": "system", "content": DEFAULT_SYSTEM_PROMPT}, {"role": "user", "content": "Question: x?"}]

    result = instrument_agent_decision(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-fail", decision_id="dec-fail", action_id="act-fail",
        exposed_memory_ids=(), messages=messages, run_config=run_config,
        actor="test", timestamp=TS,
    )
    assert result.generation_text is None
    assert len(result.attempts) == 2  # max_retries=1 -> up to 2 attempts
    assert all(not a.succeeded for a in result.attempts)
    assert result.decision_event.finish_reason == FINISH_REASON_FAILED_ALL_ATTEMPTS
    assert result.decision_event.output == ""
    assert result.decision_event.exposed_memory_ids == ()
    assert result.action_event.result == EXECUTION_STATUS_ERROR


def test_non_interference_generate_with_retries_behavior_unchanged(ledgers):
    """Confirms this module calls, rather than reimplements, generate_with_retries()."""
    from phase3.evaluation.agent_runtime.runner import generate_with_retries

    messages = [{"role": "system", "content": DEFAULT_SYSTEM_PROMPT}, {"role": "user", "content": "Question: x?"}]
    run_config = _run_config("baseline answer")
    baseline_text, baseline_attempts = generate_with_retries(messages, run_config)

    result = instrument_agent_decision(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-baseline", decision_id="dec-baseline", action_id="act-baseline",
        exposed_memory_ids=(), messages=messages, run_config=_run_config("baseline answer"),
        actor="test", timestamp=TS,
    )
    assert result.generation_text == baseline_text
    assert len(result.attempts) == len(baseline_attempts)
