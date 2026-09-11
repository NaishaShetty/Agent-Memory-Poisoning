"""Unit tests for `phase4.attacks.dsrm` -- the CSRM justification parser, the
SRM convergence/history logic (with a scripted fake embedder, not the real
BERT model -- that fidelity question is covered separately by a real dry
run, not by these fast unit tests), and the injector's metadata/content_type
schema compliance (mirroring FARMA's Milestone 2 boundary-violation lesson)."""

from __future__ import annotations

import json
import unittest
from typing import Iterator, List

from phase3.evaluation.foundations.mocks.mock_mem0 import MockMem0Adapter
from phase3.evaluation.llm.provider import (
    GenerationConfig, LlamaServerEndpoint, LlamaServerProvider, _RawHttpResponse,
)
from phase3.evaluation.agent_runtime.messages import DEFAULT_SYSTEM_PROMPT
from phase3.evaluation.agent_runtime.runner import RunConfiguration as _RC

from phase4.attacks.dsrm.csrm import CSRMParseError, generate_csrm_justification
from phase4.attacks.dsrm.decision import (
    CONTENT_TYPE_ADVERSARIAL_DECISION,
    AdversarialDecisionArtifact,
    CSRMJustification,
    render_content_text,
)
from phase4.attacks.dsrm.injector import ADMISSION_ADMITTED, DSRMInjector
from phase4.attacks.dsrm.srm import SRMIteration, run_self_refine


def _scripted_provider(replies: List[str]) -> LlamaServerProvider:
    it: Iterator[str] = iter(replies)

    def post_json(url: str, body: bytes, timeout: float) -> _RawHttpResponse:
        reply_text = next(it)
        payload = {
            "choices": [{"message": {"content": reply_text}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "system_fingerprint": "b10717-a32af33de",
        }
        return _RawHttpResponse(status=200, body=json.dumps(payload).encode("utf-8"))

    return LlamaServerProvider(endpoint=LlamaServerEndpoint(), post_json=post_json)


def _run_config(provider: LlamaServerProvider) -> _RC:
    return _RC(
        llm_provider=provider,
        generation_config=GenerationConfig(temperature=0.0, seed=42, max_tokens=64, enable_thinking=False, n_ctx=1024),
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        max_retries=0,
    )


class CSRMTests(unittest.TestCase):
    def test_parses_valid_json_response(self) -> None:
        reply = json.dumps({
            "why_applies": "A", "why_effective": "B", "expected_impact": "C",
        })
        provider = _scripted_provider([reply])
        result = generate_csrm_justification("Q?", "claim", _run_config(provider))
        self.assertEqual(result.why_applies, "A")
        self.assertEqual(result.why_effective, "B")
        self.assertEqual(result.expected_impact, "C")

    def test_parses_json_embedded_in_surrounding_text(self) -> None:
        reply = "Sure, here is the JSON:\n" + json.dumps({
            "why_applies": "A", "why_effective": "B", "expected_impact": "C",
        }) + "\nHope that helps."
        provider = _scripted_provider([reply])
        result = generate_csrm_justification("Q?", "claim", _run_config(provider))
        self.assertEqual(result.why_applies, "A")

    def test_missing_key_raises(self) -> None:
        reply = json.dumps({"why_applies": "A", "why_effective": "B"})
        provider = _scripted_provider([reply])
        with self.assertRaises(CSRMParseError):
            generate_csrm_justification("Q?", "claim", _run_config(provider))

    def test_non_json_raises(self) -> None:
        provider = _scripted_provider(["not json at all"])
        with self.assertRaises(CSRMParseError):
            generate_csrm_justification("Q?", "claim", _run_config(provider))

    def test_undersized_max_tokens_is_bumped_not_left_truncating(self) -> None:
        # Regression test for the real bug caught during Milestone 2/3's first
        # dry run: a shared RunConfiguration sized for SRM's short refinements
        # (max_tokens=96) truncated CSRM's JSON response mid-string. The fix
        # bumps CSRM's own request, not the caller's shared config -- confirmed
        # here by checking the request body actually sent carries the bumped
        # value, not the caller's original 96.
        captured = {}

        def post_json(url, body, timeout):
            payload = json.loads(body)
            captured["max_tokens"] = payload.get("max_tokens")
            reply = json.dumps({"why_applies": "A", "why_effective": "B", "expected_impact": "C"})
            resp_payload = {
                "choices": [{"message": {"content": reply}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                "system_fingerprint": "b10717-a32af33de",
            }
            return _RawHttpResponse(status=200, body=json.dumps(resp_payload).encode("utf-8"))

        provider = LlamaServerProvider(endpoint=LlamaServerEndpoint(), post_json=post_json)
        small_config = _RC(
            llm_provider=provider,
            generation_config=GenerationConfig(temperature=0.0, seed=42, max_tokens=96, enable_thinking=False, n_ctx=1024),
            system_prompt=DEFAULT_SYSTEM_PROMPT, max_retries=0,
        )
        result = generate_csrm_justification("Q?", "claim", small_config)
        self.assertEqual(result.why_applies, "A")
        self.assertGreaterEqual(captured["max_tokens"], 320)
        self.assertEqual(small_config.generation_config.max_tokens, 96)  # caller's config untouched


class _FakeEmbedder:
    """Duck-typed stand-in for srm._Embedder -- scripted similarity sequence,
    no real model load, for fast logic-only tests."""

    def __init__(self, similarities: List[float]) -> None:
        self._similarities = iter(similarities)
        self.calls = 0

    def cosine_similarity(self, text_a: str, text_b: str) -> float:
        self.calls += 1
        return next(self._similarities)


class SRMTests(unittest.TestCase):
    def test_already_converged_seed_does_zero_iterations(self) -> None:
        embedder = _FakeEmbedder([0.75])
        provider = _scripted_provider([])  # should never be called
        result = run_self_refine("Q?", "already similar text", _run_config(provider), embedder, tau=0.6)
        self.assertTrue(result.converged)
        self.assertEqual(result.iterations_used, 0)

    def test_converges_after_refinement(self) -> None:
        embedder = _FakeEmbedder([0.1, 0.4, 0.7])
        provider = _scripted_provider(["revision 1", "revision 2"])
        result = run_self_refine("Q?", "generic seed", _run_config(provider), embedder, tau=0.6, max_iterations=5)
        self.assertTrue(result.converged)
        self.assertEqual(result.iterations_used, 2)
        self.assertEqual(result.final_planning_text, "revision 2")
        self.assertAlmostEqual(result.final_similarity, 0.7)

    def test_reports_non_convergence_at_max_iterations(self) -> None:
        embedder = _FakeEmbedder([0.1, 0.2, 0.3])
        provider = _scripted_provider(["revision 1", "revision 2"])
        result = run_self_refine("Q?", "generic seed", _run_config(provider), embedder, tau=0.6, max_iterations=2)
        self.assertFalse(result.converged)
        self.assertEqual(result.iterations_used, 2)
        self.assertEqual(len(result.history), 3)  # seed + 2 refinements


class RenderContentTextTests(unittest.TestCase):
    def _artifact(self, retrieval_text=None) -> AdversarialDecisionArtifact:
        return AdversarialDecisionArtifact(
            artifact_id="dsrm_test_1", task_id=0,
            target_question="Q?", gold_answer="gold",
            forged_claim="forged claim text",
            planning_text="final planning text",
            initial_planning_text="seed text",
            csrm_justification=CSRMJustification("A", "B", "C"),
            srm_iterations_used=2, srm_converged=True, srm_final_similarity=0.7,
            variant="black_box", retrieval_text=retrieval_text,
        )

    def test_black_box_prepends_retrieval_text(self) -> None:
        artifact = self._artifact(retrieval_text="Q? forged claim text")
        text = render_content_text(artifact)
        self.assertTrue(text.startswith("Q? forged claim text"))
        self.assertIn("final planning text", text)
        self.assertIn("forged claim text", text)

    def test_no_retrieval_text_omits_prefix(self) -> None:
        artifact = self._artifact(retrieval_text=None)
        text = render_content_text(artifact)
        self.assertTrue(text.startswith("final planning text"))


class DSRMInjectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.foundation = MockMem0Adapter()
        self.foundation.initialize({})
        self.injector = DSRMInjector(self.foundation)

    def _artifact(self) -> AdversarialDecisionArtifact:
        return AdversarialDecisionArtifact(
            artifact_id="dsrm_test_inj", task_id=0,
            target_question="Q?", gold_answer="gold",
            forged_claim="forged claim text",
            planning_text="final planning text",
            initial_planning_text="seed text",
            csrm_justification=CSRMJustification("A", "B", "C"),
            srm_iterations_used=2, srm_converged=True, srm_final_similarity=0.7,
            variant="black_box", retrieval_text="Q? forged claim text",
        )

    def test_admitted_and_content_type_is_not_self_incriminating(self) -> None:
        result = self.injector.inject(self._artifact())
        self.assertEqual(result.admission_status, ADMISSION_ADMITTED)
        stored = self.foundation._store[result.canonical_memory_id]
        self.assertEqual(stored.content["content_type"], CONTENT_TYPE_ADVERSARIAL_DECISION)
        self.assertNotIn("dsrm", stored.content["content_type"].lower())
        self.assertNotIn("attack_label", stored.metadata)
        self.assertEqual(stored.metadata["attack_id"], "dsrm")
        self.assertTrue(stored.metadata["attacker_originated"])

    def test_metadata_carries_srm_provenance(self) -> None:
        result = self.injector.inject(self._artifact())
        stored = self.foundation._store[result.canonical_memory_id]
        self.assertTrue(stored.metadata["srm_converged"])
        self.assertEqual(stored.metadata["srm_iterations_used"], 2)


if __name__ == "__main__":
    unittest.main()
