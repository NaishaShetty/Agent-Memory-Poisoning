"""Phase 11.2 -- a real, minimal, disclosed graph neural network.

A from-scratch, 1-2 layer mean-aggregation message-passing network built on
plain `torch` tensors -- no `torch_geometric`/`dgl`. Plan Section 11.2/6: a
minimal, from-scratch implementation is tried before reaching for a heavier
dependency, and this project's real graphs (a handful of nodes per pool) do
not need one -- a dense adjacency matrix and a couple of `matmul`s are
sufficient.

Architecture (disclosed, not hidden): for each message-passing layer,
  h' = sigma(W_self . h + W_neigh . mean_{j in N(i)}(h_j) + b)
followed by one final linear layer to a single logit (real node-level binary
classification: is this real memory poisoned). Two layers by default (Plan
Section 11.2: "1-2 message-passing layers").
"""

from __future__ import annotations

from typing import Sequence

import torch
from torch import nn


def adjacency_to_mean_matrix(adjacency: Sequence[Sequence[int]], n: int) -> torch.Tensor:
    """A real, dense row-normalized adjacency matrix (mean aggregation over
    each node's real neighbors; isolated nodes get an all-zero row, so they
    simply receive no neighbor message, not a NaN)."""
    mat = torch.zeros((n, n), dtype=torch.float32)
    for i, neighbors in enumerate(adjacency):
        if neighbors:
            weight = 1.0 / len(neighbors)
            for j in neighbors:
                mat[i, j] = weight
    return mat


class MessagePassingLayer(nn.Module):
    def __init__(self, in_dim: int, out_dim: int):
        super().__init__()
        self.self_linear = nn.Linear(in_dim, out_dim)
        self.neigh_linear = nn.Linear(in_dim, out_dim)
        self.activation = nn.ReLU()

    def forward(self, h: torch.Tensor, mean_adj: torch.Tensor) -> torch.Tensor:
        neighbor_messages = mean_adj @ h
        return self.activation(self.self_linear(h) + self.neigh_linear(neighbor_messages))


class MinimalGNN(nn.Module):
    """A disclosed, small (default 2-layer) GNN. `hidden_dim` and
    `num_layers` are real, versioned constants, not tuned per call."""

    GNN_VERSION = "phase11-gnn-0.1.0"

    def __init__(self, in_dim: int, hidden_dim: int = 8, num_layers: int = 2, seed: int = 11):
        super().__init__()
        torch.manual_seed(seed)
        dims = [in_dim] + [hidden_dim] * num_layers
        self.layers = nn.ModuleList(
            [MessagePassingLayer(dims[i], dims[i + 1]) for i in range(num_layers)]
        )
        self.readout = nn.Linear(dims[-1], 1)

    def forward(self, features: torch.Tensor, mean_adj: torch.Tensor) -> torch.Tensor:
        h = features
        for layer in self.layers:
            h = layer(h, mean_adj)
        return self.readout(h).squeeze(-1)  # real logits, one per node

    def predict_proba(self, features: torch.Tensor, mean_adj: torch.Tensor) -> torch.Tensor:
        with torch.no_grad():
            return torch.sigmoid(self(features, mean_adj))
