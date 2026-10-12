"""Tests for the MAX-aggregating GNN variant (added 2026-10-12). MinimalGNN mean-pools; this variant
takes the elementwise max over neighbors, so a single high-signal neighbor (e.g. a poison ancestor)
propagates instead of being diluted. The frozen MinimalGNN is untouched."""
import torch

from phase11.gnn.model import MaxAggregatingGNN, MinimalGNN, masked_neighbor_max


def test_masked_neighbor_max_takes_the_max_over_neighbors():
    h = torch.tensor([[1.0, 5.0], [9.0, 2.0], [0.0, 0.0]])
    # node 0's neighbors: 1 and 2; node 1: none; node 2: 0
    mask = torch.tensor([[0.0, 1.0, 1.0], [0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
    out = masked_neighbor_max(h, mask)
    assert out[0].tolist() == [9.0, 2.0]        # max of rows 1 and 2
    assert out[1].tolist() == [0.0, 0.0]        # no neighbors -> zero message
    assert out[2].tolist() == [1.0, 5.0]        # neighbor 0


def test_max_gnn_forward_shape_and_determinism():
    feats = torch.randn(5, 4)
    mask = (torch.rand(5, 5) > 0.5).float()
    m = MaxAggregatingGNN(in_dim=4, seed=11)
    p1 = m.predict_proba(feats, mask)
    p2 = m.predict_proba(feats, mask)
    assert p1.shape == (5,)
    assert torch.allclose(p1, p2)              # deterministic
    assert ((p1 >= 0) & (p1 <= 1)).all()


def test_max_gnn_is_separate_from_minimal_gnn():
    # Different classes, different version strings -- the frozen GNN is not modified.
    assert MaxAggregatingGNN.GNN_VERSION != MinimalGNN.GNN_VERSION
    assert "max" in MaxAggregatingGNN.GNN_VERSION


def test_a_high_signal_neighbor_raises_a_nodes_message():
    # With an identity-ish self plus a strong neighbor, max aggregation lets the neighbor show through.
    h = torch.tensor([[0.0], [10.0]])
    linked = torch.tensor([[0.0, 1.0], [0.0, 0.0]])     # node 0 <- node 1
    isolated = torch.zeros(2, 2)
    assert masked_neighbor_max(h, linked)[0].item() == 10.0
    assert masked_neighbor_max(h, isolated)[0].item() == 0.0
