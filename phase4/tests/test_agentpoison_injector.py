"""Unit tests for `phase4.attacks.agentpoison.injector` -- the injector
class added during Phase 4.7 to close the one real gap found while
consolidating all six attacks' integration surfaces (AgentPoison was the
only attack without a dedicated Injector class)."""

from __future__ import annotations

import unittest

from phase3.evaluation.foundations.mocks.mock_mem0 import MockMem0Adapter

from phase4.attacks.agentpoison.injector import (
    ADMISSION_ADMITTED,
    CONTENT_TYPE_CONVERSATIONAL_FACT,
    AgentPoisonInjector,
)
from phase4.attacks.agentpoison.trigger_run import AgentPoisonArtifact


def _artifact() -> AgentPoisonArtifact:
    return AgentPoisonArtifact(
        poison_id="agentpoison_test_001",
        trigger_tokens=["a", "b", "c"],
        trigger_text="a b c",
        malicious_demonstration="Regarding a b c: some forged claim.",
        fitness_score_initial=1.0,
        fitness_score_final=2.0,
        iterations_run=5,
        num_grad_iter=3,
        num_cand=20,
    )


class AgentPoisonInjectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.foundation = MockMem0Adapter()
        self.foundation.initialize({})
        self.injector = AgentPoisonInjector(self.foundation)

    def test_admitted_and_content_type_not_self_incriminating(self) -> None:
        result = self.injector.inject(_artifact())
        self.assertEqual(result.admission_status, ADMISSION_ADMITTED)
        stored = self.foundation._store[result.canonical_memory_id]
        self.assertEqual(stored.content["content_type"], CONTENT_TYPE_CONVERSATIONAL_FACT)
        self.assertNotIn("agentpoison", stored.content["content_type"].lower())
        self.assertNotIn("attack_label", stored.metadata)
        self.assertEqual(stored.metadata["attack_id"], "agentpoison")
        self.assertTrue(stored.metadata["attacker_originated"])

    def test_stored_text_is_the_malicious_demonstration_verbatim(self) -> None:
        artifact = _artifact()
        result = self.injector.inject(artifact)
        stored = self.foundation._store[result.canonical_memory_id]
        self.assertEqual(stored.content["text"], artifact.malicious_demonstration)


if __name__ == "__main__":
    unittest.main()
