"""Phase 4 -- MAMBench reconstruction of DSRM, Milestone 5: white-box
retrieval-text optimization.

Per the dossier's Section 4: white-box DSRM optimizes the retrieval
component R (rather than the black-box's simple R = Q ⊕ T_m concatenation)
via HotFlip-style discrete token search against a contrastive loss (Eq. 5,
described in the dossier as "InfoNCE-style: maximize similarity to the
positive/target query, minimize similarity to n negative queries", 30
iterative steps, greedy top-100-candidate replacement per step).

DISCLOSED LIMITATION: the dossier reports Eq. 5's DESCRIPTION, not its
literal mathematical text (the dossier's Section 14 notes only two figure
discrepancies were flagged as unresolved -- the exact loss formula was
simply not transcribed in the 4.1 pass). `info_nce_loss` below is
MAMBench's OWN standard InfoNCE reconstruction of that description
(temperature-scaled softmax over one positive and N negatives) -- a
reasonable, standard instantiation of "InfoNCE-style," not a verbatim copy
of the paper's own equation. This must never be represented as "DSRM's
exact Eq. 5."

Reuses AgentPoison's `GradientStorage`/`hotflip_attack`/`get_embeddings`/
`minilm_mean_pool_emb` (phase4/attacks/agentpoison/core.py) unmodified --
the same mechanical HotFlip machinery, a different loss function. This
mirrors the dossier's own Section 10 observation that DSRM's white-box
optimization is "mechanically similar in spirit to AgentPoison's
gradient-based trigger optimization."

Scaled down from the paper's own 30-step/100-candidate default for the
same CPU-tractability reasons AgentPoison's Milestone 4 disclosed (see that
milestone's own iteration-count disclosure) -- a genuine, disclosed
reduction, not a hidden one.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Sequence

import torch
from transformers import BertModel, BertTokenizer

from phase4.attacks.agentpoison.core import GradientStorage, get_embeddings, hotflip_attack, minilm_mean_pool_emb

MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
DEVICE = "cpu"

NUM_ADV_TOKENS_DEFAULT = 6
NUM_ITER_DEFAULT = 10
NUM_CAND_DEFAULT = 40
TEMPERATURE_DEFAULT = 0.07  # standard InfoNCE default (SimCLR/CLIP-style)


def info_nce_loss(
    anchor_emb: torch.Tensor, positive_emb: torch.Tensor, negative_embs: torch.Tensor,
    temperature: float = TEMPERATURE_DEFAULT,
) -> torch.Tensor:
    """MAMBench's own standard InfoNCE reconstruction of the dossier's
    qualitative Eq. 5 description -- see module docstring's disclosed
    limitation. Returns the NEGATIVE log-softmax probability of the positive
    among {positive, negatives} -- LOWER is better (anchor closer to
    positive, farther from negatives), unlike AgentPoison's
    compute_avg_cluster_distance (which is maximized). Callers doing HotFlip
    search on this loss should use increase_loss=False."""
    pos_sim = torch.nn.functional.cosine_similarity(anchor_emb, positive_emb) / temperature
    neg_sims = torch.nn.functional.cosine_similarity(
        anchor_emb.expand(negative_embs.size(0), -1), negative_embs
    ) / temperature
    logits = torch.cat([pos_sim, neg_sims])
    log_probs = torch.log_softmax(logits, dim=0)
    return -log_probs[0]


@dataclass(frozen=True)
class WhiteBoxOptimizationResult:
    retrieval_tokens: List[str]
    retrieval_text: str
    loss_initial: float
    loss_final: float
    iterations_run: int


def optimize_retrieval_text(
    positive_query: str,
    negative_queries: Sequence[str],
    num_adv_tokens: int = NUM_ADV_TOKENS_DEFAULT,
    num_iter: int = NUM_ITER_DEFAULT,
    num_cand: int = NUM_CAND_DEFAULT,
    seed: int = 42,
) -> WhiteBoxOptimizationResult:
    random.seed(seed)
    torch.manual_seed(seed)

    tokenizer = BertTokenizer.from_pretrained(MODEL_ID)
    model = BertModel.from_pretrained(MODEL_ID).to(DEVICE)
    model.eval()

    def embed(text: str) -> torch.Tensor:
        enc = tokenizer(text, return_tensors="pt", truncation=True, max_length=128).to(DEVICE)
        with torch.no_grad():
            return minilm_mean_pool_emb(model, enc)

    positive_emb = embed(positive_query)
    negative_embs = torch.cat([embed(q) for q in negative_queries], dim=0)

    adv_ids = torch.tensor([tokenizer.mask_token_id] * num_adv_tokens, device=DEVICE).unsqueeze(0)
    adv_attention = torch.ones_like(adv_ids)

    embeddings_module = get_embeddings(model)
    embedding_gradient = GradientStorage(embeddings_module, num_adv_tokens)

    def anchor_embedding(ids: torch.Tensor) -> torch.Tensor:
        return minilm_mean_pool_emb(model, {"input_ids": ids, "attention_mask": adv_attention})

    loss_initial: float = None
    loss_final: float = None

    for it_ in range(num_iter):
        model.zero_grad()
        anchor_emb = anchor_embedding(adv_ids)
        loss = info_nce_loss(anchor_emb, positive_emb, negative_embs)
        if loss_initial is None:
            loss_initial = loss.item()
        loss.backward()
        grad = embedding_gradient.get().sum(dim=0)

        token_to_flip = random.randrange(num_adv_tokens)
        # increase_loss=False: InfoNCE loss should DECREASE (anchor gets
        # closer to positive, farther from negatives) -- opposite direction
        # from AgentPoison's cluster-distance fitness, which is maximized.
        candidates = hotflip_attack(grad[token_to_flip], embeddings_module.weight, increase_loss=False, num_candidates=num_cand)

        best_loss = loss.item()
        best_candidate = None
        with torch.no_grad():
            for candidate in candidates:
                temp_ids = adv_ids.clone()
                temp_ids[:, token_to_flip] = candidate
                cand_anchor = anchor_embedding(temp_ids)
                cand_loss = info_nce_loss(cand_anchor, positive_emb, negative_embs).item()
                if cand_loss < best_loss:
                    best_loss = cand_loss
                    best_candidate = candidate

        if best_candidate is not None:
            adv_ids[:, token_to_flip] = best_candidate
        loss_final = best_loss

    retrieval_tokens = tokenizer.convert_ids_to_tokens(adv_ids.squeeze(0))
    retrieval_text = tokenizer.convert_tokens_to_string(retrieval_tokens)

    return WhiteBoxOptimizationResult(
        retrieval_tokens=retrieval_tokens, retrieval_text=retrieval_text,
        loss_initial=loss_initial, loss_final=loss_final, iterations_run=num_iter,
    )


__all__ = ["info_nce_loss", "WhiteBoxOptimizationResult", "optimize_retrieval_text"]
