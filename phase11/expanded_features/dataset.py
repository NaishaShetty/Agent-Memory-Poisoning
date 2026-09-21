"""Phase 11.x Option 2 -- feature-vector assembly for the four (plus two
standalone) experimental configurations, reusing existing, unmodified
machinery wherever it already exists:

- `phase11.gnn.features.pools_node_features` (the existing, unmodified 9
  sanctioned scalars).
- `phase11.expanded_features.structural_features.pools_structural_features`
  (this package's new structural features).
- `phase11.expanded_features.semantic_features` (this package's new,
  PCA-reduced MiniLM features, fit on training data only).
- `phase11.gnn.graph_build.build_pools_graph` /
  `node_order_and_relation_adjacency` (unmodified -- the SAME real graph
  construction the Option-1 investigation already uses).
- `phase11.gnn.relation_model.relation_mean_matrices` (unmodified).

CONFIGURATIONS
--------------------------------------------------------------------------------
A = baseline (9 sanctioned features only) -- must reproduce the Option-1
    investigation's own real numbers exactly, or something in this new
    package is wrong.
B = A + structural (17-dim: 9 + 8)
C = A + semantic  (9 + k, k = the PCA-selected dimension, fit on train only)
D = A + structural + semantic (9 + 8 + k)
S = structural only (8-dim)
M = semantic only (k-dim)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Sequence, Tuple

import numpy as np
import torch

from phase11.expanded_features.semantic_features import FittedPCA, apply_pca, embed_texts, fit_pca
from phase11.expanded_features.structural_features import STRUCTURAL_FEATURE_KEYS, pools_structural_features
from phase11.gnn.features import FEATURE_KEYS as SANCTIONED_FEATURE_KEYS
from phase11.gnn.features import pools_node_features
from phase11.gnn.graph_build import build_pools_graph, node_order_and_relation_adjacency
from phase11.gnn.relation_model import relation_mean_matrices

CONFIGS = ("A", "B", "C", "D", "S", "M")


@dataclass(frozen=True)
class ExpandedGraphDataset:
    config: str
    node_ids: Tuple[str, ...]
    feature_keys: Tuple[str, ...]
    features: torch.Tensor
    mean_adj_by_relation: Dict[str, torch.Tensor]
    labels: torch.Tensor


def _content_by_node(pools) -> Dict[str, str]:
    return {m.scenario_id: m.content_text for pool in pools for m in pool.memories}


def fit_semantic_pca_on_training_pools(training_pools: Sequence) -> FittedPCA:
    """The ONE place PCA is fit -- on real training-pool content only. Every
    other call site in this package only ever calls `apply_pca()` with the
    `FittedPCA` this function returns."""
    content_by_node = _content_by_node(training_pools)
    node_ids = sorted(content_by_node)  # deterministic order
    embeddings = embed_texts([content_by_node[nid] for nid in node_ids])
    return fit_pca(embeddings)


def build_expanded_dataset(pools: Sequence, config: str, *, fitted_pca: FittedPCA = None) -> ExpandedGraphDataset:
    if config not in CONFIGS:
        raise ValueError(f"unknown config {config!r}; must be one of {CONFIGS}")
    if config in ("C", "D", "M") and fitted_pca is None:
        raise ValueError(f"config {config!r} requires a fitted_pca (fit on training pools only)")

    graph = build_pools_graph(pools)
    node_ids, relation_adjacency = node_order_and_relation_adjacency(graph)

    sanctioned_map = pools_node_features(pools) if config in ("A", "B", "C", "D") else {}
    structural_map = pools_structural_features(pools) if config in ("B", "D", "S") else {}

    semantic_map: Dict[str, Tuple[float, ...]] = {}
    if config in ("C", "D", "M"):
        content_by_node = _content_by_node(pools)
        ordered_ids = [nid for nid in node_ids if nid in content_by_node]
        if ordered_ids:
            embeddings = embed_texts([content_by_node[nid] for nid in ordered_ids])
            reduced = apply_pca(embeddings, fitted_pca)
            for nid, vec in zip(ordered_ids, reduced):
                semantic_map[nid] = tuple(vec.tolist())
        semantic_dim = fitted_pca.n_components
    else:
        semantic_dim = 0

    feature_keys: Tuple[str, ...] = ()
    if config in ("A", "B", "C", "D"):
        feature_keys += SANCTIONED_FEATURE_KEYS
    if config in ("B", "D", "S"):
        feature_keys += STRUCTURAL_FEATURE_KEYS
    if config in ("C", "D", "M"):
        feature_keys += tuple(f"semantic_pca_{i}" for i in range(semantic_dim))

    rows = []
    for nid in node_ids:
        row: Tuple[float, ...] = ()
        if config in ("A", "B", "C", "D"):
            row += sanctioned_map.get(nid, tuple(0.0 for _ in SANCTIONED_FEATURE_KEYS))
        if config in ("B", "D", "S"):
            row += structural_map.get(nid, tuple(0.0 for _ in STRUCTURAL_FEATURE_KEYS))
        if config in ("C", "D", "M"):
            row += semantic_map.get(nid, tuple(0.0 for _ in range(semantic_dim)))
        rows.append(row)

    features = torch.tensor(rows, dtype=torch.float32)
    labels = torch.tensor(
        [1.0 if graph.nodes[nid].get("is_poison_ground_truth") else 0.0 for nid in node_ids],
        dtype=torch.float32,
    )
    mean_adj_by_relation = relation_mean_matrices(relation_adjacency, len(node_ids))
    return ExpandedGraphDataset(config, node_ids, feature_keys, features, mean_adj_by_relation, labels)
