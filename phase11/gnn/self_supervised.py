"""Phase 11.x Step 1/2 -- benign-first self-supervised representation
training and anomaly scoring for `RelationAwareEncoder` (redesign design doc
Part 2.C/2.D).

Two real, disclosed training objectives are implemented and compared on
`dev_pools()` (never `held_out_pools()`), per the design doc's own
instruction not to assume either is automatically better:

1. **Deep-SVDD-style compactness**: a fixed center `c` (the mean initial
   forward pass over benign training representations, computed once and
   detached -- the standard deep-SVDD initialization, chosen specifically
   because training `c` jointly with the encoder is the well-known
   hypersphere-collapse failure mode) and a loss that pulls benign `h_i`
   toward `c`. Anomaly score = Euclidean distance to `c`.
2. **Reconstruction MSE**: an encoder + linear decoder trained to
   reconstruct the real 9-dim sanctioned-signal input from `h_i`, loss
   computed on benign training nodes only. Anomaly score = reconstruction
   error.

Both are trained EXCLUSIVELY on benign representations
(`is_poison_ground_truth == False`), per the redesign's "benign-first"
principle (brief Section 5) -- poison nodes in the training pool are
present in the graph (so real structural edges to/from them still shape
message passing) but never contribute to either loss.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import torch

from phase11.gnn.features import FEATURE_KEYS, pools_node_features
from phase11.gnn.graph_build import build_pools_graph, node_order_and_relation_adjacency
from phase11.gnn.relation_model import ReconstructionDecoder, RelationAwareEncoder, relation_mean_matrices

SVDD_EPOCHS = 300
SVDD_LEARNING_RATE = 0.05
AE_EPOCHS = 300
AE_LEARNING_RATE = 0.05


@dataclass(frozen=True)
class RelationGraphDataset:
    node_ids: Tuple[str, ...]
    features: torch.Tensor
    mean_adj_by_relation: Dict[str, torch.Tensor]
    labels: torch.Tensor  # 1.0 = real poison ground truth, 0.0 = benign


def build_relation_dataset(pools) -> RelationGraphDataset:
    graph = build_pools_graph(pools)
    node_ids, relation_adjacency = node_order_and_relation_adjacency(graph)
    feature_map = pools_node_features(pools)
    features = torch.tensor(
        [feature_map.get(nid, tuple(0.0 for _ in FEATURE_KEYS)) for nid in node_ids],
        dtype=torch.float32,
    )
    labels = torch.tensor(
        [1.0 if graph.nodes[nid].get("is_poison_ground_truth") else 0.0 for nid in node_ids],
        dtype=torch.float32,
    )
    mean_adj_by_relation = relation_mean_matrices(relation_adjacency, len(node_ids))
    return RelationGraphDataset(node_ids, features, mean_adj_by_relation, labels)


def _benign_mask(dataset: RelationGraphDataset) -> torch.Tensor:
    return dataset.labels == 0.0


def train_svdd_encoder(dataset: RelationGraphDataset, *, seed: int, hidden_dim: int = 8):
    torch.manual_seed(seed)
    encoder = RelationAwareEncoder(in_dim=len(FEATURE_KEYS), hidden_dim=hidden_dim, seed=seed)
    benign_mask = _benign_mask(dataset)

    with torch.no_grad():
        initial_h = encoder(dataset.features, dataset.mean_adj_by_relation)
        center = initial_h[benign_mask].mean(dim=0).detach()

    optimizer = torch.optim.Adam(encoder.parameters(), lr=SVDD_LEARNING_RATE)
    for _ in range(SVDD_EPOCHS):
        optimizer.zero_grad()
        h = encoder(dataset.features, dataset.mean_adj_by_relation)
        benign_h = h[benign_mask]
        loss = ((benign_h - center) ** 2).sum(dim=1).mean()
        loss.backward()
        optimizer.step()
    return encoder, center


def svdd_anomaly_scores(encoder, center, dataset: RelationGraphDataset) -> torch.Tensor:
    with torch.no_grad():
        h = encoder(dataset.features, dataset.mean_adj_by_relation)
        return ((h - center) ** 2).sum(dim=1).sqrt()


def train_autoencoder(dataset: RelationGraphDataset, *, seed: int, hidden_dim: int = 8):
    torch.manual_seed(seed)
    encoder = RelationAwareEncoder(in_dim=len(FEATURE_KEYS), hidden_dim=hidden_dim, seed=seed)
    decoder = ReconstructionDecoder(hidden_dim=hidden_dim, out_dim=len(FEATURE_KEYS))
    benign_mask = _benign_mask(dataset)

    params = list(encoder.parameters()) + list(decoder.parameters())
    optimizer = torch.optim.Adam(params, lr=AE_LEARNING_RATE)
    loss_fn = torch.nn.MSELoss()
    for _ in range(AE_EPOCHS):
        optimizer.zero_grad()
        h = encoder(dataset.features, dataset.mean_adj_by_relation)
        reconstructed = decoder(h)
        loss = loss_fn(reconstructed[benign_mask], dataset.features[benign_mask])
        loss.backward()
        optimizer.step()
    return encoder, decoder


def ae_anomaly_scores(encoder, decoder, dataset: RelationGraphDataset) -> torch.Tensor:
    with torch.no_grad():
        h = encoder(dataset.features, dataset.mean_adj_by_relation)
        reconstructed = decoder(h)
        return ((reconstructed - dataset.features) ** 2).mean(dim=1)


def auroc(scores: torch.Tensor, labels: torch.Tensor) -> float:
    """Real, from-scratch AUROC via the Mann-Whitney U statistic -- no new
    dependency (sklearn) introduced for one metric."""
    scores = scores.tolist()
    labels = labels.tolist()
    poison_scores = [s for s, y in zip(scores, labels) if y == 1.0]
    benign_scores = [s for s, y in zip(scores, labels) if y == 0.0]
    if not poison_scores or not benign_scores:
        return float("nan")
    wins = 0.0
    for p in poison_scores:
        for b in benign_scores:
            if p > b:
                wins += 1.0
            elif p == b:
                wins += 0.5
    return wins / (len(poison_scores) * len(benign_scores))
