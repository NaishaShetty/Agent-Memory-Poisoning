"""Unit tests for `phase4.attacks.minja.injector.MINJAInjector`, exercised against the
real `MockMem0Adapter` (same discipline as `test_memorygraft_adapter.py`)."""

from __future__ import annotations

import unittest

from phase3.evaluation.foundations.mocks.mock_mem0 import MockMem0Adapter

from phase4.attacks.minja.injector import (
    ADMISSION_ADMITTED,
    CONTENT_TYPE_CONVERSATIONAL_FACT,
    MINJAInjector,
    QuerySequence,
    QuerySequenceStep,
)


def _sequence() -> QuerySequence:
    return QuerySequence(
        sequence_id="test_seq",
        steps=(
            QuerySequenceStep("step_1", 0, "Full bridging query text.", "full_bridging"),
            QuerySequenceStep("step_2", 1, "Compressed query text.", "compressed"),
            QuerySequenceStep("step_3", 2, "Minimal query text.", "minimal"),
        ),
        victim_query="Minimal query text?",
    )


class MINJAInjectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.foundation = MockMem0Adapter()
        self.foundation.initialize({})
        self.injector = MINJAInjector(self.foundation)

    def test_all_steps_admitted_and_written_verbatim(self) -> None:
        seq = _sequence()
        results = self.injector.inject(seq)

        self.assertEqual(len(results), 3)
        for step, result in zip(seq.steps, results):
            self.assertEqual(result.admission_status, ADMISSION_ADMITTED)
            self.assertTrue(result.attacker_originated)
            self.assertIsNotNone(result.canonical_memory_id)
            stored = self.foundation._store[result.canonical_memory_id]
            self.assertEqual(stored.content["text"], step.text)
            self.assertEqual(stored.content["content_type"], CONTENT_TYPE_CONVERSATIONAL_FACT)
            self.assertTrue(stored.metadata["attacker_originated"])
            self.assertEqual(stored.metadata["attack_id"], "minja")
            self.assertEqual(stored.metadata["sequence_id"], "test_seq")
            self.assertEqual(stored.metadata["step_kind"], step.step_kind)

    def test_no_judgment_gate_all_content_written_unconditionally(self) -> None:
        # Unlike MemoryGraft's persistence_gate, MINJA's own mechanism has no
        # judgment step to model -- every step is written, regardless of content.
        seq = _sequence()
        self.injector.inject(seq)
        self.assertEqual(len(self.foundation._store), 3)


if __name__ == "__main__":
    unittest.main()
