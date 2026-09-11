"""Unit tests for `phase4.attacks.agentpoison.locomo_pool` (AgentPoison Milestone 3:
the `load_db_locomo` loader and its `DomainTranslationRecord`)."""

from __future__ import annotations

import unittest

from phase4.attacks.agentpoison.locomo_pool import (
    AGENTPOISON_LOCOMO_TRANSLATION,
    load_db_locomo,
    load_locomo_questions,
)


class LoadDbLocomoTests(unittest.TestCase):
    def test_returns_requested_number_of_turns(self) -> None:
        pool = load_db_locomo(max_turns=5)
        self.assertEqual(len(pool), 5)

    def test_turns_are_speaker_prefixed_real_text(self) -> None:
        pool = load_db_locomo(max_turns=3)
        for turn in pool:
            self.assertIn(":", turn)
            speaker = turn.split(":", 1)[0]
            self.assertIn(speaker, ("Caroline", "Melanie"))

    def test_default_pool_size_is_17(self) -> None:
        pool = load_db_locomo()
        self.assertEqual(len(pool), 17)


class LoadLocomoQuestionsTests(unittest.TestCase):
    def test_returns_requested_number_of_questions(self) -> None:
        questions = load_locomo_questions(max_questions=4)
        self.assertEqual(len(questions), 4)
        for q in questions:
            self.assertIsInstance(q, str)
            self.assertGreater(len(q), 0)


class DomainTranslationRecordTests(unittest.TestCase):
    def test_agentpoison_translation_record_is_pilot_validated(self) -> None:
        self.assertEqual(AGENTPOISON_LOCOMO_TRANSLATION.attack_id, "agentpoison")
        self.assertEqual(AGENTPOISON_LOCOMO_TRANSLATION.validation_status, "PILOT_VALIDATED")
        self.assertGreater(len(AGENTPOISON_LOCOMO_TRANSLATION.mechanism_preserved), 0)
        self.assertGreater(len(AGENTPOISON_LOCOMO_TRANSLATION.mechanism_reinterpreted), 0)


if __name__ == "__main__":
    unittest.main()
