"""Phase 11.x -- relation-aware GNN encoder for self-supervised, benign-first
representation learning (redesign design doc Part 2.C).

Additive: does not modify `phase11/gnn/model.py`'s `MinimalGNN` (still used
unchanged by the shipped B10 pipeline). This module is a new encoder used
ONLY by the Phase 11.x investigation until/unless it is promoted per the
design doc's Part 2.J promotion criteria.

RELATION-AWARE, NOT ATTENTION-BASED (design doc Part 2.C / brief Section 7)
--------------------------------------------------------------------------------
`h_i' = ReLU( W_0 h_i + sum_r W_r . mean_{j in N_r(i)}(h_j) )` -- one
relation-specific linear transform per real edge type
(`RETRIEVED_WITH`, `DERIVED_FROM`), `alpha_ij^(r) = 1/|N_r(i)|` (plain mean,
no learned attention -- not justified at this project's real node/edge
count, per the brief's own instruction not to reach for attention by
default).

OUTPUT IS A REPRESENTATION, NOT A LOGIT
--------------------------------------------------------------------------------
`RelationAwareEncoder.forward()` returns `h_i` (dimension `hidden_dim`), the
learned structural representation the anomaly estimator (Step 2) consumes.
An optional `ClassifierHead` is provided separately, only for the Part 2.I
"supervised classifier" comparison ablation -- never the primary training
target for this encoder.
"""

from __future__ import annotations

from typing import Dict, Sequence

import torch
from torch import nn

from phase11.gnn.model import adjacency_to_mean_matrix

RELATION_TYPES = ("RETRIEVED_WITH", "DERIVED_FROM")


def relation_mean_matrices(
    relation_adjacency: Dict[str, Sequence[Sequence[int]]], n: int
) -> Dict[str, torch.Tensor]:
    """One real, dense row-normalized mean-adjacency matrix per real edge
    type -- reuses `model.py`'s existing, unchanged `adjacency_to_mean_matrix()`
    once per relation rather than reimplementing it."""
    return {
        relation: adjacency_to_mean_matrix(relation_adjacency.get(relation, [[] for _ in range(n)]), n)
        for relation in RELATION_TYPES
    }


class RelationAwareLayer(nn.Module):
    def __init__(self, in_dim: int, out_dim: int):
        super().__init__()
        self.self_linear = nn.Linear(in_dim, out_dim)
        self.relation_linears = nn.ModuleDict(
            {relation: nn.Linear(in_dim, out_dim) for relation in RELATION_TYPES}
        )
        self.activation = nn.ReLU()

    def forward(self, h: torch.Tensor, mean_adj_by_relation: Dict[str, torch.Tensor]) -> torch.Tensor:
        out = self.self_linear(h)
        for relation, linear in self.relation_linears.items():
            mean_adj = mean_adj_by_relation[relation]
            out = out + linear(mean_adj @ h)
        return self.activation(out)


class RelationAwareEncoder(nn.Module):
    """A disclosed, small (default 2-layer) relation-aware encoder. Outputs
    `h_i` (the representation), not a classification logit -- see module
    docstring."""

    ENCODER_VERSION = "phase11x-relation-encoder-0.1.0"

    def __init__(self, in_dim: int, hidden_dim: int = 8, num_layers: int = 2, seed: int = 11):
        super().__init__()
        torch.manual_seed(seed)
        dims = [in_dim] + [hidden_dim] * num_layers
        self.layers = nn.ModuleList(
            [RelationAwareLayer(dims[i], dims[i + 1]) for i in range(num_layers)]
        )

    def forward(self, features: torch.Tensor, mean_adj_by_relation: Dict[str, torch.Tensor]) -> torch.Tensor:
        h = features
        for layer in self.layers:
            h = layer(h, mean_adj_by_relation)
        return h


class ClassifierHead(nn.Module):
    """Only for the Part 2.I supervised-classifier comparison ablation --
    never used to train `RelationAwareEncoder` itself in the primary
    (benign-first, self-supervised) design."""

    def __init__(self, hidden_dim: int):
        super().__init__()
        self.readout = nn.Linear(hidden_dim, 1)

    def forward(self, h: torch.Tensor) -> torch.Tensor:
        return self.readout(h).squeeze(-1)


class ReconstructionDecoder(nn.Module):
    """Plain linear decoder back to the original 9-dim sanctioned-signal
    space, for the reconstruction-MSE self-supervised objective (design doc
    Part 2.C's dev-time alternative to the compactness/deep-SVDD objective)."""

    def __init__(self, hidden_dim: int, out_dim: int):
        super().__init__()
        self.decode = nn.Linear(hidden_dim, out_dim)

    def forward(self, h: torch.Tensor) -> torch.Tensor:
        return self.decode(h)
