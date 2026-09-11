"""Phase 4 -- AgentPoison Milestone 2: domain-agnostic core extraction.

WHAT THIS MODULE IS
--------------------------------------------------------------------------------
Per PHASE4_4_3_AGENTPOISON_INTEGRATION_PLAN.md Section 1 finding 3, the reference
`algo/trigger_optimization.py` is not offered as a standalone library: its entire
optimization procedure lives inside `if __name__ == "__main__":`, entangled with
`agentdriver`-specific dataset loading, argparse, and wandb logging. Direct
inspection (this session) confirmed the actual PER-ITERATION MECHANICS --
Gaussian-kernel MMD, cluster-distance fitness, gradient-storage hooks, and the
HotFlip discrete-token search -- are pure PyTorch/embedding-space math with ZERO
dependency on any agent-specific dataset class or the `agentdriver` package. This
module ports exactly those pieces, verbatim in algorithmic substance (fitness
math, HotFlip scoring), attributed below, callable without importing
`agentdriver` anywhere.

SOURCE ATTRIBUTION (MIT License)
--------------------------------------------------------------------------------
Ported from AI-secure/AgentPoison, commit 7236bf43148211918fd6b84d862495525798ab3c
(`algo/trigger_optimization.py`, `algo/utils.py`), per
PHASE4_4_1_AGENTPOISON_DOSSIER.md's pinned commit. Original paper: Chen, Z.,
Xiang, Z., Xiao, C., Song, D., Li, B. "AgentPoison: Red-teaming LLM Agents via
Poisoning Memory or Knowledge Bases." NeurIPS 2024. This is a REFERENCE
IMPLEMENTATION INTEGRATION (algorithm reused, not a MAMBench reconstruction) --
the math below is the authors' own, ported with attribution, not reinvented.

WHAT IS NOT PORTED (deliberately -- domain-specific, per Milestone 1/2 plan)
--------------------------------------------------------------------------------
- `agentdriver`/`ReAct`/`EhrAgent`-specific dataset classes and file loaders
  (`load_db_ad`/`load_db_qa`/`load_db_ehr`, `AgentDriverDataset`, etc.) --
  replaced by MAMBench-native LoCoMo query/pool construction (a separate module,
  not this one, per the "domain-agnostic core stays generic" principle).
- `bert_get_emb`'s `.pooler_output` convention -- per Milestone 1's direct
  measurement (cosine 0.004 vs. the real Mem0 embedder), this does NOT transfer
  to Mem0's real `all-MiniLM-L6-v2` embedder. `minilm_mean_pool_emb` below
  replaces it -- a masked mean-pool over `last_hidden_state` + L2-normalize,
  directly verified (cosine 1.0) to reproduce Mem0's actual embedding function.
- target-gradient-guidance (GPT-3.5/LLaMA2 loss guidance), perplexity-filtered
  candidate selection, wandb logging, PCA plotting -- optional features of the
  reference implementation, out of scope for the domain-agnostic core; can be
  ported later if a specific campaign needs them, per the "smallest defensible
  next step" discipline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import torch
from torch import nn


# ---------------------------------------------------------------------------
# Fitness math -- ported verbatim (algorithmic substance) from
# trigger_optimization.py lines 46-115.
# ---------------------------------------------------------------------------


def gaussian_kernel_matrix(x: torch.Tensor, y: torch.Tensor, sigma: float = 1.0) -> torch.Tensor:
    """Gaussian Kernel between `x` and `y` with bandwidth `sigma`."""
    beta = 1.0 / (2.0 * (sigma**2))
    dist = torch.cdist(x, y) ** 2
    return torch.exp(-beta * dist)


def maximum_mean_discrepancy(x: torch.Tensor, y: torch.Tensor, sigma: float = 1.0) -> torch.Tensor:
    """MMD between samples `x` and `y` using a Gaussian kernel."""
    x_kernel = gaussian_kernel_matrix(x, x, sigma)
    y_kernel = gaussian_kernel_matrix(y, y, sigma)
    xy_kernel = gaussian_kernel_matrix(x, y, sigma)
    return torch.mean(x_kernel) + torch.mean(y_kernel) - 2 * torch.mean(xy_kernel)


def compute_variance(embeddings: torch.Tensor) -> torch.Tensor:
    """Standard deviation of a batch of embeddings from their mean."""
    mean_embedding = torch.mean(embeddings, dim=0, keepdim=True)
    distances = torch.norm(embeddings - mean_embedding, dim=1)
    return torch.mean(distances)


def compute_avg_cluster_distance(query_embedding: torch.Tensor, cluster_centers: torch.Tensor) -> torch.Tensor:
    """Average L2 distance of `query_embedding` to `cluster_centers` (the
    Gaussian-mixture cluster centroids of the real, benign candidate pool),
    minus a variance-tightening term. This is the "ap" (trigger-side) fitness:
    HIGHER is better -- the optimization pushes the trigger-augmented query
    embedding AWAY from where normal/benign content clusters, into a
    distinctive, low-variance region a separately-planted poisoned document
    can also occupy (the "cpa"/corpus-poisoning side, not ported here)."""
    expanded_query_embeddings = query_embedding.unsqueeze(1)
    distances = torch.norm(expanded_query_embeddings - cluster_centers, dim=2)
    avg_distances = torch.mean(distances, dim=1)
    overall_avg_distance = torch.mean(avg_distances)
    variance = compute_variance(query_embedding)
    return overall_avg_distance - 0.1 * variance


def compute_avg_embedding_similarity(query_embedding: torch.Tensor, db_embeddings: torch.Tensor) -> torch.Tensor:
    """Average cosine-style similarity of `query_embedding` to every row of
    `db_embeddings` -- the "cpa" (corpus-poisoning) fitness: HIGHER means the
    candidate document embedding is more similar to the target query cluster."""
    similarities = torch.mm(query_embedding, db_embeddings.T)
    avg_similarities = torch.mean(similarities, dim=1)
    return torch.mean(avg_similarities)


# ---------------------------------------------------------------------------
# Gradient storage + HotFlip -- ported verbatim (algorithmic substance) from
# trigger_optimization.py lines 145-220.
# ---------------------------------------------------------------------------


class GradientStorage:
    """Captures the gradient flowing into a module's output via a backward
    hook -- used here to read the gradient w.r.t. the trigger tokens' word
    embeddings, since PyTorch does not retain intermediate gradients by
    default."""

    def __init__(self, module: nn.Module, num_adv_passage_tokens: int) -> None:
        self._stored_gradient: Optional[torch.Tensor] = None
        self.num_adv_passage_tokens = num_adv_passage_tokens
        module.register_full_backward_hook(self.hook)

    def hook(self, module, grad_in, grad_out) -> None:
        if self._stored_gradient is None:
            self._stored_gradient = grad_out[0][:, -self.num_adv_passage_tokens :]
        else:
            self._stored_gradient += grad_out[0][:, -self.num_adv_passage_tokens :]

    def get(self) -> Optional[torch.Tensor]:
        return self._stored_gradient


def get_embeddings(model: nn.Module) -> nn.Module:
    """Returns the wordpiece embedding module of a HuggingFace encoder model
    (`model.get_input_embeddings()` -- the general-purpose accessor every
    `transformers` model exposes; more robust than the reference's own
    `getattr(model, config.model_type)` pattern, which assumes a `.bert`
    submodule that only exists for classification-head-wrapped models)."""
    return model.get_input_embeddings()


def hotflip_attack(
    averaged_grad: torch.Tensor,
    embedding_matrix: torch.Tensor,
    increase_loss: bool = False,
    num_candidates: int = 1,
    filter: Optional[torch.Tensor] = None,
    slice: Optional[int] = None,
) -> torch.Tensor:
    """Returns the top `num_candidates` token-id replacements for one trigger
    position, by the standard HotFlip first-order approximation: score every
    vocabulary token by its dot product with the accumulated gradient, then
    take the top (or bottom, if `increase_loss`) k."""
    with torch.no_grad():
        gradient_dot_embedding_matrix = torch.matmul(embedding_matrix, averaged_grad)
        if filter is not None:
            gradient_dot_embedding_matrix -= filter
        if not increase_loss:
            gradient_dot_embedding_matrix *= -1

        mask = torch.zeros_like(gradient_dot_embedding_matrix, dtype=torch.bool)
        if slice is not None:
            mask[: slice + 1] = True
        limit_value = float("-inf") if increase_loss else float("inf")
        gradient_dot_embedding_matrix.masked_fill_(mask, limit_value)

        _, top_k_ids = gradient_dot_embedding_matrix.topk(num_candidates)
    return top_k_ids


# ---------------------------------------------------------------------------
# MAMBench-native embedding function -- replaces `bert_get_emb`'s
# `.pooler_output` (per Milestone 1's finding) with masked mean-pooling,
# directly verified (cosine 1.0) to reproduce Mem0's real embedder output.
# ---------------------------------------------------------------------------


def minilm_mean_pool_emb(model: nn.Module, encoded_input) -> torch.Tensor:
    """Masked mean-pool over `last_hidden_state`, L2-normalized -- the
    sentence-transformers convention Mem0's real embedder actually uses.
    `encoded_input` is a HuggingFace `BatchEncoding`/mapping with `input_ids`
    and `attention_mask`, exactly as `bert_get_adv_emb`'s callers already
    construct (trigger tokens concatenated onto the tokenized query)."""
    output = model(**encoded_input)
    token_embeddings = output.last_hidden_state
    attention_mask = encoded_input["attention_mask"].unsqueeze(-1).expand(token_embeddings.size()).float()
    summed = torch.sum(token_embeddings * attention_mask, dim=1)
    counts = torch.clamp(attention_mask.sum(dim=1), min=1e-9)
    mean_pooled = summed / counts
    return torch.nn.functional.normalize(mean_pooled, p=2, dim=1)


@dataclass(frozen=True)
class TriggerOptimizationConfig:
    """The subset of the reference implementation's CLI args this port
    supports -- vanilla "ap" (trigger-side) configuration, no
    target-gradient-guidance, no perplexity filter, matching the reference's
    own stated defaults for those flags."""

    num_iter: int
    num_grad_iter: int
    num_cand: int
    num_adv_passage_tokens: int


__all__ = [
    "gaussian_kernel_matrix",
    "maximum_mean_discrepancy",
    "compute_variance",
    "compute_avg_cluster_distance",
    "compute_avg_embedding_similarity",
    "GradientStorage",
    "get_embeddings",
    "hotflip_attack",
    "minilm_mean_pool_emb",
    "TriggerOptimizationConfig",
]
