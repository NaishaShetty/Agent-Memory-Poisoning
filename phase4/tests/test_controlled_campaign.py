"""Unit tests for `phase4.shared.controlled_campaign.run_controlled_campaign`
(Phase 4.8) -- confirms it correctly composes `AttackAdapter.execute()` +
`.collect()` into one `ControlledCampaignRecord`, using a real
`MockMem0Adapter` and a scripted LLM transport."""

from __future__ import annotations

import json
import unittest

from phase3.evaluation.agent_runtime.messages import DEFAULT_SYSTEM_PROMPT
from phase3.evaluation.agent_runtime.runner import RunConfiguration
from phase3.evaluation.foundations.mocks.mock_mem0 import MockMem0Adapter
from phase3.evaluation.llm.provider import GenerationConfig, LlamaServerEndpoint, LlamaServerProvider, _RawHttpResponse

from phase4.shared.adapter import AttackAdapter
from phase4.shared.controlled_campaign import ControlledCampaignRecord, run_controlled_campaign


def _scripted_provider(reply_text: str) -> LlamaServerProvider:
    def post_json(url: str, body: bytes, timeout: float) -> _RawHttpResponse:
        payload = {
            "choices": [{"message": {"content": reply_text}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "system_fingerprint": "b10717-a32af33de",
        }
        return _RawHttpResponse(status=200, body=json.dumps(payload).encode("utf-8"))

    return LlamaServerProvider(endpoint=LlamaServerEndpoint(), post_json=post_json)


def _run_config(reply_text: str) -> RunConfiguration:
    return RunConfiguration(
        llm_provider=_scripted_provider(reply_text),
        generation_config=GenerationConfig(temperature=0.0, seed=42, max_tokens=64, enable_thinking=False, n_ctx=1024),
        system_prompt=DEFAULT_SYSTEM_PROMPT, max_retries=0,
    )


class _DummyAdapter(AttackAdapter):
    attack_id = "dummy_controlled"

    def validate(self, request):
        return True

    def prepare(self, request):
        return request

    def generate(self, context):
        return context

    def inject(self, artifacts, foundation, **kwargs):
        return foundation.add_memory(memory_id=None, content={"text": artifacts, "content_type": "GENERAL_FACT"}, metadata=kwargs.get("extra_metadata") or {})


class RunControlledCampaignTests(unittest.TestCase):
    def setUp(self) -> None:
        self.foundation = MockMem0Adapter()
        self.foundation.initialize({})
        self.adapter = _DummyAdapter()

    def test_selected_and_influential_record(self) -> None:
        field_result = self.adapter.inject(
            "The sky is blue.", self.foundation, extra_metadata={"user_id": "u1"},
        )
        mid = field_result.value["memory_id"]
        run_config = _run_config("The sky is blue.")
        record = run_controlled_campaign(
            self.adapter, self.foundation, "What color is the sky?", mid, run_config,
            user_id="u1", task_id="t1", gold_answer="blue",
        )
        self.assertIsInstance(record, ControlledCampaignRecord)
        self.assertEqual(record.attack_id, "dummy_controlled")
        self.assertTrue(record.selected)
        self.assertEqual(record.baseline_answer, "The sky is blue.")
        self.assertIsNotNone(record.counterfactual_status)
        self.assertEqual(record.gold_answer, "blue")

    def test_not_selected_record_has_no_counterfactual_status(self) -> None:
        run_config = _run_config("I don't know.")
        record = run_controlled_campaign(
            self.adapter, self.foundation, "unrelated query", "nonexistent-id", run_config,
            user_id="u1", task_id="t1",
        )
        self.assertFalse(record.selected)
        self.assertIsNone(record.masked_answer)
        self.assertIsNone(record.counterfactual_status)


if __name__ == "__main__":
    unittest.main()
