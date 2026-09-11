"""Unit test for `phase4.shared.campaign_runner.retrieve_select_generate` --
the function extracted from five near-identical copies across AgentPoison/
MINJA/FARMA/DSRM/MPBench's real campaign scripts (Phase 4.7). Uses
`MockMem0Adapter` and a scripted LLM transport (same pattern as
test_persistence_gate.py) so this runs fast, without real infrastructure --
the real-infrastructure behavior is already covered by each attack's own
real campaign run logs; this test only confirms the extraction preserved
behavior against a controllable foundation/LLM pair."""

from __future__ import annotations

import json
import unittest

from phase3.evaluation.agent_runtime.messages import DEFAULT_SYSTEM_PROMPT
from phase3.evaluation.agent_runtime.runner import RunConfiguration
from phase3.evaluation.foundations.mocks.mock_mem0 import MockMem0Adapter
from phase3.evaluation.llm.provider import GenerationConfig, LlamaServerEndpoint, LlamaServerProvider, _RawHttpResponse

from phase4.shared.campaign_runner import retrieve_select_generate


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


class RetrieveSelectGenerateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.foundation = MockMem0Adapter()
        self.foundation.initialize({})

    def test_empty_pool_still_generates_an_answer(self) -> None:
        run_config = _run_config("I don't know.")
        outcome = retrieve_select_generate(
            self.foundation, "What color is the sky?", run_config, user_id="u1", task_id="t1",
        )
        self.assertEqual(outcome.execution_result.answer, "I don't know.")
        self.assertEqual(outcome.selected_memory_ids, ())

    def test_ingested_memory_is_retrieved_selected_and_exposed(self) -> None:
        self.foundation.add_memory(
            memory_id=None,
            content={"text": "The sky is blue.", "content_type": "CONVERSATIONAL_FACT"},
            metadata={"user_id": "u1"},
        )
        run_config = _run_config("The sky is blue.")
        outcome = retrieve_select_generate(
            self.foundation, "What color is the sky?", run_config, user_id="u1", task_id="t1",
        )
        self.assertEqual(len(outcome.selected_memory_ids), 1)
        self.assertEqual(outcome.execution_result.answer, "The sky is blue.")
        self.assertEqual(outcome.agent_visible_context["task"]["task_id"], "t1")

    def test_task_id_flows_through_to_execution_result(self) -> None:
        run_config = _run_config("answer")
        outcome = retrieve_select_generate(
            self.foundation, "q?", run_config, user_id="u1", task_id="custom-task-id",
        )
        self.assertEqual(outcome.task_id, "custom-task-id")
        self.assertEqual(outcome.execution_result.task_id, "custom-task-id")


if __name__ == "__main__":
    unittest.main()
