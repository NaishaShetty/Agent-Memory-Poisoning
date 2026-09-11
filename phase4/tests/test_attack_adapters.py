"""Unit tests for `phase4.shared.adapter.AttackAdapter` (the shared
execute()/collect() logic) and each attack's concrete adapter's validate/
prepare/inject wiring (Phase 4.7). Heavy real generation calls (AgentPoison's
trigger optimization, DSRM's SRM/CSRM loop) are NOT re-run here -- those are
already covered by each attack's own real campaign run logs; these tests
only confirm the adapter classes wire to the right real components, using
mocks/monkeypatching for the expensive parts."""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock

from phase3.evaluation.agent_runtime.messages import DEFAULT_SYSTEM_PROMPT
from phase3.evaluation.agent_runtime.runner import RunConfiguration
from phase3.evaluation.foundations.mocks.mock_mem0 import MockMem0Adapter
from phase3.evaluation.llm.provider import GenerationConfig, LlamaServerEndpoint, LlamaServerProvider, _RawHttpResponse

from phase4.shared.adapter import AttackAdapter, AttackCollectResult


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
    """Minimal concrete subclass for exercising the base class's shared
    execute()/collect() logic in isolation."""

    attack_id = "dummy"

    def validate(self, request):
        return True

    def prepare(self, request):
        return request

    def generate(self, context):
        return context

    def inject(self, artifacts, foundation, **kwargs):
        return foundation.add_memory(memory_id=None, content={"text": artifacts, "content_type": "GENERAL_FACT"}, metadata={})


class SharedExecuteCollectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.foundation = MockMem0Adapter()
        self.foundation.initialize({})
        self.adapter = _DummyAdapter()

    def test_execute_returns_a_real_agent_run_outcome(self) -> None:
        run_config = _run_config("The sky is blue.")
        outcome = self.adapter.execute(self.foundation, "What color is the sky?", run_config, user_id="u1", task_id="t1")
        self.assertEqual(outcome.execution_result.answer, "The sky is blue.")

    def test_collect_reports_not_selected_when_artifact_absent(self) -> None:
        run_config = _run_config("answer")
        outcome = self.adapter.execute(self.foundation, "q?", run_config, user_id="u1", task_id="t1")
        result = self.adapter.collect(outcome, "nonexistent-id", run_config)
        self.assertFalse(result.selected)
        self.assertIsNone(result.counterfactual_status)

    def test_collect_runs_counterfactual_mask_when_artifact_selected(self) -> None:
        field_result = self.foundation.add_memory(
            memory_id=None, content={"text": "The sky is blue.", "content_type": "GENERAL_FACT"},
            metadata={"user_id": "u1"},
        )
        mid = field_result.value["memory_id"]
        run_config = _run_config("The sky is blue.")
        outcome = self.adapter.execute(self.foundation, "What color is the sky?", run_config, user_id="u1", task_id="t1")
        self.assertIn(mid, outcome.selected_memory_ids)
        result = self.adapter.collect(outcome, mid, run_config)
        self.assertTrue(result.selected)
        self.assertIsNotNone(result.counterfactual_status)
        self.assertEqual(result.attack_id, "dummy")


class AgentPoisonAdapterTests(unittest.TestCase):
    def test_validate_always_true(self) -> None:
        from phase4.attacks.agentpoison.adapter import AgentPoisonAdapter
        self.assertTrue(AgentPoisonAdapter().validate(None))

    def test_inject_delegates_to_agentpoison_injector(self) -> None:
        from phase4.attacks.agentpoison.adapter import AgentPoisonAdapter
        from phase4.attacks.agentpoison.injector import ADMISSION_ADMITTED
        from phase4.attacks.agentpoison.trigger_run import AgentPoisonArtifact

        foundation = MockMem0Adapter()
        foundation.initialize({})
        artifact = AgentPoisonArtifact(
            poison_id="p1", trigger_tokens=["a"], trigger_text="a",
            malicious_demonstration="forged", fitness_score_initial=1.0, fitness_score_final=2.0,
            iterations_run=1, num_grad_iter=1, num_cand=1,
        )
        result = AgentPoisonAdapter().inject(artifact, foundation)
        self.assertEqual(result.admission_status, ADMISSION_ADMITTED)


class MINJAAdapterTests(unittest.TestCase):
    def test_generate_is_identity_passthrough(self) -> None:
        from phase4.attacks.minja.adapter import MINJAAdapter
        from phase4.attacks.minja.injector import QuerySequence, QuerySequenceStep

        seq = QuerySequence(
            sequence_id="s1",
            steps=(QuerySequenceStep("s1_q1", 0, "text", "full_bridging"),),
            victim_query="q?",
        )
        adapter = MINJAAdapter()
        self.assertIs(adapter.generate(adapter.prepare(seq)), seq)

    def test_inject_delegates_to_minja_injector(self) -> None:
        from phase4.attacks.minja.adapter import MINJAAdapter
        from phase4.attacks.minja.injector import ADMISSION_ADMITTED, QuerySequence, QuerySequenceStep

        foundation = MockMem0Adapter()
        foundation.initialize({})
        seq = QuerySequence(
            sequence_id="s1",
            steps=(QuerySequenceStep("s1_q1", 0, "text", "full_bridging"),),
            victim_query="q?",
        )
        results = MINJAAdapter().inject(seq, foundation)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].admission_status, ADMISSION_ADMITTED)


class FARMAAdapterTests(unittest.TestCase):
    def test_generate_returns_seed_plus_cycles(self) -> None:
        from phase4.attacks.farma.adapter import FARMAAdapter
        from phase4.attacks.farma.reasoning_trace import SEED_CAMPING

        adapter = FARMAAdapter()
        context = adapter.prepare({"seed": SEED_CAMPING, "num_cycles": 3})
        artifacts = adapter.generate(context)
        self.assertEqual(len(artifacts), 4)  # seed + 3 cycles
        self.assertIs(artifacts[0], SEED_CAMPING)

    def test_inject_writes_all_artifacts(self) -> None:
        from phase4.attacks.farma.adapter import FARMAAdapter
        from phase4.attacks.farma.injector import ADMISSION_ADMITTED
        from phase4.attacks.farma.reasoning_trace import SEED_CAMPING

        foundation = MockMem0Adapter()
        foundation.initialize({})
        adapter = FARMAAdapter()
        artifacts = adapter.generate(adapter.prepare({"seed": SEED_CAMPING, "num_cycles": 2}))
        results = adapter.inject(artifacts, foundation)
        self.assertEqual(len(results), 3)
        self.assertTrue(all(r.admission_status == ADMISSION_ADMITTED for r in results))


class DSRMAdapterTests(unittest.TestCase):
    def test_prepare_requires_seed_key(self) -> None:
        from phase4.attacks.dsrm.adapter import DSRMAdapter
        with self.assertRaises(TypeError):
            DSRMAdapter().prepare({})

    def test_generate_delegates_to_real_generate_function(self) -> None:
        from phase4.attacks.dsrm import adapter as dsrm_adapter_module
        from phase4.attacks.dsrm.adapter import DSRMAdapter
        from phase4.attacks.dsrm.seeds import SEED_POTTERY

        sentinel = object()
        dsrm_adapter_module.generate_decision_black_box = MagicMock(return_value=sentinel)
        adapter = DSRMAdapter()
        context = {"seed": SEED_POTTERY, "run_config": object(), "embedder": object()}
        result = adapter.generate(context)
        self.assertIs(result, sentinel)
        dsrm_adapter_module.generate_decision_black_box.assert_called_once()


class MPBenchPCFIAdapterTests(unittest.TestCase):
    def test_prepare_rejects_non_scenario_input(self) -> None:
        from phase4.attacks.mpbench.adapter import MPBenchPCFIAdapter
        with self.assertRaises(TypeError):
            MPBenchPCFIAdapter().prepare(["not a scenario"])

    def test_inject_writes_all_scenarios(self) -> None:
        from phase4.attacks.mpbench.adapter import MPBenchPCFIAdapter
        from phase4.attacks.mpbench.injector import ADMISSION_ADMITTED
        from phase4.attacks.mpbench.scenario import PCFI_SCENARIOS

        foundation = MockMem0Adapter()
        foundation.initialize({})
        adapter = MPBenchPCFIAdapter()
        results = adapter.inject(adapter.generate(adapter.prepare(PCFI_SCENARIOS)), foundation)
        self.assertEqual(len(results), 3)
        self.assertTrue(all(r.admission_status == ADMISSION_ADMITTED for r in results))


class MemoryGraftAdapterTests(unittest.TestCase):
    def test_validate_requires_foundation_label(self) -> None:
        from phase4.attacks.memorygraft.adapter_class import MemoryGraftAdapter
        adapter = MemoryGraftAdapter()
        self.assertFalse(adapter.validate({}))
        self.assertFalse(adapter.validate({"foundation_label": "not_a_real_one"}))
        self.assertTrue(adapter.validate({"foundation_label": "mem0"}))

    def test_prepare_requires_artifact_key(self) -> None:
        from phase4.attacks.memorygraft.adapter_class import MemoryGraftAdapter
        with self.assertRaises(TypeError):
            MemoryGraftAdapter().prepare({})


if __name__ == "__main__":
    unittest.main()
