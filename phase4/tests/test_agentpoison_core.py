"""Unit tests for `phase4.attacks.agentpoison.core` -- the ported domain-agnostic
AgentPoison mechanics (fitness math, GradientStorage, HotFlip) and the new
Milestone-1-motivated `minilm_mean_pool_emb` pooling function."""

from __future__ import annotations

import unittest

import torch
from torch import nn

from phase4.attacks.agentpoison.core import (
    GradientStorage,
    compute_avg_cluster_distance,
    compute_avg_embedding_similarity,
    compute_variance,
    gaussian_kernel_matrix,
    get_embeddings,
    hotflip_attack,
    maximum_mean_discrepancy,
    minilm_mean_pool_emb,
)


class FitnessMathTests(unittest.TestCase):
    def test_mmd_of_identical_distributions_is_near_zero(self) -> None:
        x = torch.randn(20, 8)
        mmd = maximum_mean_discrepancy(x, x.clone())
        self.assertAlmostEqual(mmd.item(), 0.0, places=4)

    def test_mmd_of_far_apart_distributions_is_positive(self) -> None:
        x = torch.randn(20, 8)
        y = torch.randn(20, 8) + 50.0
        mmd = maximum_mean_discrepancy(x, y)
        self.assertGreater(mmd.item(), 0.0)

    def test_variance_of_identical_points_is_zero(self) -> None:
        x = torch.ones(10, 4)
        self.assertAlmostEqual(compute_variance(x).item(), 0.0, places=6)

    def test_compute_avg_cluster_distance_shape_and_monotonic_direction(self) -> None:
        query = torch.randn(5, 4)
        close_centers = query.mean(dim=0, keepdim=True).unsqueeze(0).expand(1, 3, 4).clone()
        far_centers = close_centers + 100.0
        close_score = compute_avg_cluster_distance(query, close_centers)
        far_score = compute_avg_cluster_distance(query, far_centers)
        # Higher score = farther from cluster centers (AgentPoison's "ap" fitness
        # wants to INCREASE this, per core.py's own docstring).
        self.assertGreater(far_score.item(), close_score.item())

    def test_compute_avg_embedding_similarity_prefers_aligned_vectors(self) -> None:
        aligned = torch.tensor([[1.0, 0.0]])
        db_aligned = torch.tensor([[1.0, 0.0], [1.0, 0.0]])
        db_orthogonal = torch.tensor([[0.0, 1.0], [0.0, 1.0]])
        sim_aligned = compute_avg_embedding_similarity(aligned, db_aligned)
        sim_orthogonal = compute_avg_embedding_similarity(aligned, db_orthogonal)
        self.assertGreater(sim_aligned.item(), sim_orthogonal.item())


class GradientStorageAndHotflipTests(unittest.TestCase):
    def test_gradient_storage_captures_backward_gradient(self) -> None:
        embedding = nn.Embedding(10, 4)
        num_adv_tokens = 2
        storage = GradientStorage(embedding, num_adv_tokens)

        ids = torch.tensor([[0, 1, 2, 3]])
        out = embedding(ids)
        loss = out.sum()
        loss.backward()

        grad = storage.get()
        self.assertIsNotNone(grad)
        self.assertEqual(grad.shape, (1, num_adv_tokens, 4))

    def test_hotflip_attack_returns_requested_candidate_count(self) -> None:
        vocab_size, dim = 50, 8
        embedding_matrix = torch.randn(vocab_size, dim)
        averaged_grad = torch.randn(dim)
        candidates = hotflip_attack(averaged_grad, embedding_matrix, increase_loss=True, num_candidates=5)
        self.assertEqual(candidates.shape, (5,))
        self.assertTrue(((candidates >= 0) & (candidates < vocab_size)).all())

    def test_hotflip_attack_slice_excludes_masked_range(self) -> None:
        vocab_size, dim = 20, 4
        embedding_matrix = torch.eye(vocab_size, dim if dim <= vocab_size else vocab_size)[:, :dim]
        averaged_grad = torch.ones(dim)
        candidates = hotflip_attack(
            averaged_grad, embedding_matrix, increase_loss=True, num_candidates=3, slice=9
        )
        # Excluded range is [0, slice] inclusive -- no candidate should fall in it.
        self.assertTrue((candidates > 9).all())


class MinilmMeanPoolTests(unittest.TestCase):
    def test_mean_pool_output_is_unit_normalized(self) -> None:
        from transformers import BertModel, BertTokenizer

        model_id = "sentence-transformers/all-MiniLM-L6-v2"
        tokenizer = BertTokenizer.from_pretrained(model_id)
        model = BertModel.from_pretrained(model_id)
        model.eval()

        enc = tokenizer("A short test sentence.", return_tensors="pt")
        with torch.no_grad():
            emb = minilm_mean_pool_emb(model, enc)

        norm = torch.norm(emb, p=2, dim=1).item()
        self.assertAlmostEqual(norm, 1.0, places=5)
        self.assertEqual(emb.shape, (1, 384))


class GetEmbeddingsTests(unittest.TestCase):
    def test_get_embeddings_returns_input_embedding_module(self) -> None:
        from transformers import BertModel

        model = BertModel.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
        emb_module = get_embeddings(model)
        self.assertIs(emb_module, model.get_input_embeddings())


if __name__ == "__main__":
    unittest.main()
