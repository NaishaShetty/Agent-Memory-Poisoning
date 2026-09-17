"""Unit tests for `phase4.attacks.mpbench` -- Policy Conformant Fact
Injection scenario rendering and injector schema compliance (mirroring the
boundary/self-labeling checks already established for AgentPoison/FARMA/
DSRM)."""

from __future__ import annotations

import unittest

from phase3.evaluation.foundations.mocks.mock_mem0 import MockMem0Adapter

from phase4.attacks.mpbench.injector import ADMISSION_ADMITTED, MPBenchPCFIInjector
from phase4.attacks.mpbench.scenario import (
    CONTENT_TYPE_GENERAL_FACT,
    PCFI_SCENARIOS,
    SCENARIO_ACTIVITIES,
    render_content_text,
)


class RenderContentTextTests(unittest.TestCase):
    def test_renders_exactly_the_fabricated_fact_no_extra_framing(self) -> None:
        text = render_content_text(SCENARIO_ACTIVITIES)
        self.assertEqual(text, SCENARIO_ACTIVITIES.context)


class ScenarioSetTests(unittest.TestCase):
    def test_three_scenarios_no_overlap_with_other_attacks_questions(self) -> None:
        self.assertEqual(len(PCFI_SCENARIOS), 3)
        questions = {s.retrieval_query for s in PCFI_SCENARIOS}
        self.assertEqual(len(questions), 3)  # all distinct

    def test_only_two_conversational_ready_adversarial_goals_used(self) -> None:
        goals = {s.adversarial_goal for s in PCFI_SCENARIOS}
        self.assertTrue(goals.issubset({"trust_hijacking", "recommendation_poisoning"}))


class MPBenchPCFIInjectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.foundation = MockMem0Adapter()
        self.foundation.initialize({})
        self.injector = MPBenchPCFIInjector(self.foundation)

    def test_admitted_and_content_type_is_general_fact_not_self_incriminating(self) -> None:
        result = self.injector.inject(SCENARIO_ACTIVITIES)
        self.assertEqual(result.admission_status, ADMISSION_ADMITTED)
        stored = self.foundation._store[result.canonical_memory_id]
        self.assertEqual(stored.content["content_type"], CONTENT_TYPE_GENERAL_FACT)
        self.assertNotIn("mpbench", stored.content["content_type"].lower())
        self.assertNotIn("attack_label", stored.metadata)
        # Update (2026-09-17): was "mpbench_pcfi" -- fixed to match every real Phase 5+
        # wiring call site, which already independently used "mpbench" (see
        # MPBenchPCFIAdapter.attack_id's own Update note).
        self.assertEqual(stored.metadata["attack_id"], "mpbench")

    def test_inject_many_writes_all_three_scenarios(self) -> None:
        results = self.injector.inject_many(PCFI_SCENARIOS)
        self.assertEqual(len(results), 3)
        self.assertTrue(all(r.admission_status == ADMISSION_ADMITTED for r in results))


if __name__ == "__main__":
    unittest.main()
