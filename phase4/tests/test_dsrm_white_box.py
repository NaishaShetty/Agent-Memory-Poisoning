"""Unit tests for `phase4.attacks.dsrm.white_box` -- the InfoNCE loss
sanity checks (synthetic vectors, no model load) and a real, small-scale
optimization smoke test (loads the real MiniLM/BERT pair, like
test_agentpoison_core.py's MinilmMeanPoolTests already do)."""

from __future__ import annotations

import unittest

import torch

from phase4.attacks.dsrm.white_box import info_nce_loss, optimize_retrieval_text


class InfoNCELossTests(unittest.TestCase):
    def test_anchor_matching_positive_scores_lower_than_matching_negative(self) -> None:
        positive = torch.tensor([[1.0, 0.0]])
        negative = torch.tensor([[0.0, 1.0]])

        anchor_near_positive = torch.tensor([[0.99, 0.01]])
        anchor_near_negative = torch.tensor([[0.01, 0.99]])

        loss_near_positive = info_nce_loss(anchor_near_positive, positive, negative)
        loss_near_negative = info_nce_loss(anchor_near_negative, positive, negative)

        self.assertLess(loss_near_positive.item(), loss_near_negative.item())

    def test_more_negatives_does_not_change_ordering(self) -> None:
        positive = torch.tensor([[1.0, 0.0]])
        negatives = torch.tensor([[0.0, 1.0], [-1.0, 0.0], [0.0, -1.0]])

        anchor_near_positive = torch.tensor([[0.99, 0.01]])
        anchor_near_negative = torch.tensor([[0.0, 0.99]])

        loss_near_positive = info_nce_loss(anchor_near_positive, positive, negatives)
        loss_near_negative = info_nce_loss(anchor_near_negative, positive, negatives)

        self.assertLess(loss_near_positive.item(), loss_near_negative.item())


class OptimizeRetrievalTextSmokeTest(unittest.TestCase):
    def test_real_small_scale_run_produces_expected_token_count(self) -> None:
        result = optimize_retrieval_text(
            positive_query="When did Melanie sign up for a pottery class?",
            negative_queries=[
                "When did Melanie go to the museum?",
                "When did Caroline have a picnic?",
            ],
            num_adv_tokens=4,
            num_iter=2,
            num_cand=10,
        )
        self.assertEqual(len(result.retrieval_tokens), 4)
        self.assertIsInstance(result.retrieval_text, str)
        self.assertIsNotNone(result.loss_initial)
        self.assertIsNotNone(result.loss_final)


if __name__ == "__main__":
    unittest.main()
