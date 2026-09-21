"""Phase 11.x Option 2 -- anomaly scoring for the expanded-feature datasets,
mirroring the Option-1 investigation's own methodology
(`phase11/gnn/self_supervised.py`) exactly, but generalized to an arbitrary
input dimension (since configs A/B/C/D/S/M have different feature widths)
rather than the Option-1 module's hardcoded 9-dim `FEATURE_KEYS`. This
package does not import or alter `self_supervised.py`'s training functions
(a real, deliberate duplication of ~20 lines, kept for isolation per Section
2), but DOES reuse its `auroc()` metric function directly (read-only reuse
of a pure math utility, not the investigation's substantive logic) and its
already-existing, unmodified `RelationAwareEncoder`/`ReconstructionDecoder`
classes from `phase11/gnn/relation_model.py`.
"""

from __future__ import annotations

import torch

from phase11.expanded_features.dataset import ExpandedGraphDataset
from phase11.gnn.relation_model import ReconstructionDecoder, RelationAwareEncoder
from phase11.gnn.self_supervised import auroc  # read-only reuse of a pure metric function

SVDD_EPOCHS = 300
SVDD_LEARNING_RATE = 0.05
AE_EPOCHS = 300
AE_LEARNING_RATE = 0.05

__all__ = ["auroc", "raw_centroid_scores", "train_svdd_encoder", "svdd_anomaly_scores",
           "train_autoencoder", "ae_anomaly_scores"]


def _benign_mask(dataset: ExpandedGraphDataset) -> torch.Tensor:
    return dataset.labels == 0.0


def raw_centroid_scores(repr_ds: ExpandedGraphDataset, eval_ds: ExpandedGraphDataset) -> torch.Tensor:
    """No-encoder baseline: Euclidean distance to the real benign training
    centroid, in whatever feature space `repr_ds`/`eval_ds` were built in."""
    benign_mask = _benign_mask(repr_ds)
    centroid = repr_ds.features[benign_mask].mean(dim=0)
    return ((eval_ds.features - centroid) ** 2).sum(dim=1).sqrt()


def train_svdd_encoder(dataset: ExpandedGraphDataset, *, seed: int, hidden_dim: int = 8):
    torch.manual_seed(seed)
    in_dim = dataset.features.shape[1]
    encoder = RelationAwareEncoder(in_dim=in_dim, hidden_dim=hidden_dim, seed=seed)
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


def svdd_anomaly_scores(encoder, center, dataset: ExpandedGraphDataset) -> torch.Tensor:
    with torch.no_grad():
        h = encoder(dataset.features, dataset.mean_adj_by_relation)
        return ((h - center) ** 2).sum(dim=1).sqrt()


def train_autoencoder(dataset: ExpandedGraphDataset, *, seed: int, hidden_dim: int = 8):
    torch.manual_seed(seed)
    in_dim = dataset.features.shape[1]
    encoder = RelationAwareEncoder(in_dim=in_dim, hidden_dim=hidden_dim, seed=seed)
    decoder = ReconstructionDecoder(hidden_dim=hidden_dim, out_dim=in_dim)
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


def ae_anomaly_scores(encoder, decoder, dataset: ExpandedGraphDataset) -> torch.Tensor:
    with torch.no_grad():
        h = encoder(dataset.features, dataset.mean_adj_by_relation)
        reconstructed = decoder(h)
        return ((reconstructed - dataset.features) ** 2).mean(dim=1)
