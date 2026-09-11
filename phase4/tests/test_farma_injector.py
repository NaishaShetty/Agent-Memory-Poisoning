"""Unit tests for `phase4.attacks.farma.injector.FARMAInjector` and
`phase4.attacks.farma.reasoning_trace`, exercised against the real
`MockMem0Adapter` (same discipline as `test_minja_injector.py`/
`test_memorygraft_adapter.py`)."""

from __future__ import annotations

import unittest

from phase3.evaluation.foundations.mocks.mock_mem0 import MockMem0Adapter

from phase4.attacks.farma.injector import ADMISSION_ADMITTED, FARMAInjector
from phase4.attacks.farma.reasoning_trace import (
    CONTENT_TYPE_REASONING_TRACE,
    SEED_CAMPING,
    SEED_TRACES,
    generate_amplification_sequence,
    render_content_text,
)
from phase4.attacks.farma.variants import CONTENT_TYPE_STORE_EVASION, store_evasion_artifact
from phase4.attacks.farma.reasoning_trace import SEQUENCE_TYPE_SEED_AND_AMPLIFICATION


class FARMAInjectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.foundation = MockMem0Adapter()
        self.foundation.initialize({})
        self.injector = FARMAInjector(self.foundation)

    def test_seed_admitted_and_written_verbatim(self) -> None:
        result = self.injector.inject(SEED_CAMPING)

        self.assertEqual(result.admission_status, ADMISSION_ADMITTED)
        self.assertTrue(result.attacker_originated)
        self.assertIsNotNone(result.canonical_memory_id)
        stored = self.foundation._store[result.canonical_memory_id]
        self.assertEqual(stored.content["text"], SEED_CAMPING.forged_claim)
        self.assertEqual(stored.content["content_type"], CONTENT_TYPE_REASONING_TRACE)
        self.assertTrue(stored.metadata["attacker_originated"])
        self.assertEqual(stored.metadata["attack_id"], "farma")
        self.assertEqual(stored.metadata["precedent_count"], 1)
        self.assertEqual(stored.metadata["cites"], [])

    def test_no_judgment_gate_all_seeds_written_unconditionally(self) -> None:
        results = self.injector.inject_many(SEED_TRACES)
        self.assertEqual(len(results), 3)
        self.assertTrue(all(r.admission_status == ADMISSION_ADMITTED for r in results))
        self.assertEqual(len(self.foundation._store), 3)

    def test_content_type_is_not_a_self_incriminating_label(self) -> None:
        # Per the AgentPoison Milestone 6 lesson: content_type is a legitimate,
        # disclosed schema category, not an attack-identifying string -- the
        # attack's own identity belongs in metadata only.
        result = self.injector.inject(SEED_CAMPING)
        stored = self.foundation._store[result.canonical_memory_id]
        self.assertNotIn("farma", stored.content["content_type"].lower())
        self.assertNotIn("malicious", stored.content["content_type"].lower())


class SequenceIdentityTests(unittest.TestCase):
    """Per Milestone 7's contract re-validation: the contract's own
    InjectionSequence schema (sequence_id/sequence_type=SEED_AND_AMPLIFICATION)
    was explicitly motivated by FARMA, but the first implementation never
    populated it -- fixed by deriving sequence_id from cites."""

    def setUp(self) -> None:
        self.foundation = MockMem0Adapter()
        self.foundation.initialize({})
        self.injector = FARMAInjector(self.foundation)

    def test_seed_sequence_id_is_its_own_artifact_id(self) -> None:
        result = self.injector.inject(SEED_CAMPING)
        stored = self.foundation._store[result.canonical_memory_id]
        self.assertEqual(stored.metadata["sequence_id"], SEED_CAMPING.artifact_id)
        self.assertEqual(stored.metadata["sequence_type"], SEQUENCE_TYPE_SEED_AND_AMPLIFICATION)

    def test_amplification_cycles_share_seed_sequence_id(self) -> None:
        cycles = generate_amplification_sequence(SEED_CAMPING, num_cycles=3)
        results = self.injector.inject_many(cycles)
        for result in results:
            stored = self.foundation._store[result.canonical_memory_id]
            self.assertEqual(stored.metadata["sequence_id"], SEED_CAMPING.artifact_id)


class StoreEvasionVariantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.foundation = MockMem0Adapter()
        self.foundation.initialize({})
        self.injector = FARMAInjector(self.foundation)

    def test_store_evasion_uses_conversational_fact_content_type(self) -> None:
        artifact = store_evasion_artifact(SEED_CAMPING)
        result = self.injector.inject(artifact, content_type=CONTENT_TYPE_STORE_EVASION)
        stored = self.foundation._store[result.canonical_memory_id]
        self.assertEqual(stored.content["content_type"], "CONVERSATIONAL_FACT")
        self.assertNotEqual(stored.content["content_type"], CONTENT_TYPE_REASONING_TRACE)

    def test_store_evasion_same_forged_claim_as_base(self) -> None:
        artifact = store_evasion_artifact(SEED_CAMPING)
        self.assertEqual(artifact.forged_claim, SEED_CAMPING.forged_claim)
        self.assertNotEqual(artifact.artifact_id, SEED_CAMPING.artifact_id)

    def test_default_inject_still_uses_reasoning_trace(self) -> None:
        # Confirms the content_type override is opt-in, not a behavior change
        # to the base variant's default.
        result = self.injector.inject(SEED_CAMPING)
        stored = self.foundation._store[result.canonical_memory_id]
        self.assertEqual(stored.content["content_type"], CONTENT_TYPE_REASONING_TRACE)


class AmplificationSequenceTests(unittest.TestCase):
    def test_ten_cycles_by_default(self) -> None:
        cycles = generate_amplification_sequence(SEED_CAMPING)
        self.assertEqual(len(cycles), 10)

    def test_precedent_count_increments_per_cycle(self) -> None:
        cycles = generate_amplification_sequence(SEED_CAMPING)
        counts = [c.precedent_count for c in cycles]
        self.assertEqual(counts, list(range(2, 12)))  # seed itself is precedent_count=1

    def test_each_cycle_cites_seed_and_all_prior_cycles(self) -> None:
        cycles = generate_amplification_sequence(SEED_CAMPING, num_cycles=3)
        self.assertEqual(cycles[0].cites, (SEED_CAMPING.artifact_id,))
        self.assertEqual(cycles[1].cites, (SEED_CAMPING.artifact_id, cycles[0].artifact_id))
        self.assertEqual(
            cycles[2].cites,
            (SEED_CAMPING.artifact_id, cycles[0].artifact_id, cycles[1].artifact_id),
        )

    def test_amplification_entries_render_with_precedent_count_phrase(self) -> None:
        cycles = generate_amplification_sequence(SEED_CAMPING, num_cycles=1)
        text = render_content_text(cycles[0])
        self.assertIn(SEED_CAMPING.forged_claim, text)
        self.assertIn("precedent count: 2", text)

    def test_seed_renders_without_precedent_count_phrase(self) -> None:
        # A bare seed (no citations yet) should not claim reconfirmation that
        # hasn't happened.
        text = render_content_text(SEED_CAMPING)
        self.assertEqual(text, SEED_CAMPING.forged_claim)
        self.assertNotIn("precedent count", text)


if __name__ == "__main__":
    unittest.main()
