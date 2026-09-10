"""Tests for V5's bounded draft->verify->[revise] reasoning pipeline. Verifies the
call-count bound (never more than 3), that disabling verification reproduces V1-V4's
plain single-pass behavior exactly, and that a REVISE verdict triggers exactly one
revision call, never a loop."""

from __future__ import annotations

import json

from phase3.evaluation.agent_runtime.v5_reasoning_pipeline import generate_verified_answer
from phase3.evaluation.llm.provider import GenerationResult


class _ScriptedProvider:
    """Returns a scripted sequence of (text, finish_reason) pairs, one per call, in
    order -- lets a test assert exactly how many calls happened and with what."""

    def __init__(self, script):
        self._script = list(script)
        self.calls = 0
        self.seen_messages = []

    def generate(self, messages, config):
        self.calls += 1
        self.seen_messages.append(messages)
        text, finish_reason = self._script[self.calls - 1]
        return GenerationResult(
            text=text, finish_reason=finish_reason, prompt_tokens=None,
            completion_tokens=None, latency_sec=0.0, server_fingerprint=None, raw_response={},
        )


def _accept_json():
    return json.dumps({"commits_to_answer": True, "grounded": True, "verdict": "ACCEPT", "instruction": ""})


def _revise_json(instruction="State the exact duration."):
    return json.dumps({"commits_to_answer": False, "grounded": True, "verdict": "REVISE", "instruction": instruction})


def test_verification_disabled_makes_exactly_one_call_identical_to_v1_v4():
    provider = _ScriptedProvider([("Vancouver.", "stop")])
    result = generate_verified_answer("Q?", "evidence", provider, generation_config=None, enable_verification=False)
    assert provider.calls == 1
    assert result.final_answer == "Vancouver."
    assert result.was_revised is False
    assert result.verification is None
    assert len(result.stage_calls) == 1
    assert result.stage_calls[0].stage == "DRAFT"


def test_accept_verdict_makes_exactly_two_calls_no_revision():
    provider = _ScriptedProvider([
        ("The memory does not mention it.", "stop"),
        (_accept_json(), "stop"),
    ])
    result = generate_verified_answer("Q?", "evidence", provider, generation_config=None, enable_verification=True)
    assert provider.calls == 2
    assert result.final_answer == "The memory does not mention it."
    assert result.was_revised is False
    assert result.verification["verdict"] == "ACCEPT"


def test_revise_verdict_makes_exactly_three_calls_never_more():
    provider = _ScriptedProvider([
        ("The memory does not specify the duration. It only mentions 'a few months.'", "stop"),
        (_revise_json(), "stop"),
        ("A few months.", "stop"),
    ])
    result = generate_verified_answer("How long?", "evidence", provider, generation_config=None, enable_verification=True)
    assert provider.calls == 3  # bounded: draft, verify, exactly one revise -- never a loop
    assert result.final_answer == "A few months."
    assert result.was_revised is True
    assert result.draft_answer.startswith("The memory does not specify")


def test_malformed_verification_json_falls_back_to_draft_never_crashes():
    provider = _ScriptedProvider([
        ("Vancouver.", "stop"),
        ("not valid json", "stop"),
    ])
    result = generate_verified_answer("Q?", "evidence", provider, generation_config=None, enable_verification=True)
    assert provider.calls == 2  # never attempts a revision when verification itself is unparseable
    assert result.final_answer == "Vancouver."
    assert result.verification is None
    assert result.verification_parse_error is not None


def test_draft_generation_failure_short_circuits_before_verification():
    provider = _ScriptedProvider([(None, "length")])
    result = generate_verified_answer("Q?", "evidence", provider, generation_config=None, enable_verification=True)
    assert provider.calls == 1  # never calls verify on a failed/empty draft
    assert result.final_answer is None


def test_finish_reason_is_recorded_per_stage_for_truncation_detection():
    provider = _ScriptedProvider([
        ("truncated draf", "length"),
        (_accept_json(), "stop"),
    ])
    result = generate_verified_answer("Q?", "evidence", provider, generation_config=None, enable_verification=True)
    assert result.stage_calls[0].finish_reason == "length"
    assert result.stage_calls[1].finish_reason == "stop"
