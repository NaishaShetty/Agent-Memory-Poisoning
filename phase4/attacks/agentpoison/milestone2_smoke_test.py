"""Phase 4 -- AgentPoison Milestone 2 smoke test: proves the extracted
domain-agnostic core (core.py) actually runs, end-to-end, against real LoCoMo
data and Mem0's real embedder -- with ZERO import of `agentdriver`, `ReAct`, or
`EhrAgent` anywhere in the call path. This is a SMOKE TEST (small iteration/
candidate counts, CPU, a few real queries), not a full campaign-scale run --
that is a later milestone (the reference implementation's own defaults are
num_iter=1000, num_grad_iter=30, num_cand=100; this script intentionally uses
much smaller values to prove correctness quickly, not to reproduce the paper's
reported ASR figures, which requires the full-scale run this deliberately does
not attempt).

Uses `sentence-transformers/all-MiniLM-L6-v2` via `BertModel`/`BertTokenizer`
(confirmed loadable, Milestone 1) and `minilm_mean_pool_emb` (Milestone 1's
verified replacement for the reference's `.pooler_output` convention) in place
of `bert_get_adv_emb`'s embedding call -- everything else (fitness, gradient
storage, HotFlip) is `core.py`'s direct port of the reference algorithm.

Real candidate pool: the same 17 real LoCoMo turns (task 0, sessions 1-2) used
in MINJA's Milestone 3/4 work, for consistency across this session's real-data
usage.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import List, Tuple

import torch
from sklearn.mixture import GaussianMixture
from transformers import BertModel, BertTokenizer

from phase4.attacks.agentpoison.core import (
    GradientStorage,
    compute_avg_cluster_distance,
    get_embeddings,
    hotflip_attack,
    minilm_mean_pool_emb,
)

MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
LOCOMO_PATH = Path("data/raw/locomo/locomo10.json")
DEVICE = "cpu"

# Deliberately small relative to the reference's own defaults (1000/30/100/10)
# -- see module docstring.
NUM_ITER = 5
NUM_GRAD_ITER = 3
NUM_CAND = 20
NUM_ADV_PASSAGE_TOKENS = 6
SEED = 42


def load_real_pool_turns(max_turns: int = 17) -> List[str]:
    with open(LOCOMO_PATH, encoding="utf-8") as f:
        data = json.load(f)
    conv = data[0]["conversation"]
    turns: List[str] = []
    for session_key in ("session_1", "session_2"):
        for turn in conv.get(session_key, []):
            turns.append(f"{turn['speaker']}: {turn['text']}")
            if len(turns) >= max_turns:
                return turns
    return turns


def embed_texts(model, tokenizer, texts: List[str]) -> torch.Tensor:
    embs = []
    for text in texts:
        enc = tokenizer(text, return_tensors="pt", truncation=True, max_length=128).to(DEVICE)
        with torch.no_grad():
            embs.append(minilm_mean_pool_emb(model, enc))
    return torch.cat(embs, dim=0)


def query_embedding_with_trigger(
    model, tokenizer, query_text: str, adv_passage_ids: torch.Tensor, adv_passage_attention: torch.Tensor
) -> torch.Tensor:
    """MAMBench-native analogue of the reference's `bert_get_adv_emb`: tokenize
    the real query, concatenate the trigger tokens as a suffix, embed via
    `minilm_mean_pool_emb` (not `.pooler_output`)."""
    tokenized = tokenizer(query_text, truncation=True, max_length=64, return_tensors="pt").to(DEVICE)
    input_ids = torch.cat((tokenized["input_ids"], adv_passage_ids), dim=1)
    attention_mask = torch.cat((tokenized["attention_mask"], adv_passage_attention), dim=1)
    return minilm_mean_pool_emb(model, {"input_ids": input_ids, "attention_mask": attention_mask})


def main() -> None:
    random.seed(SEED)
    torch.manual_seed(SEED)

    print(f"Loading {MODEL_ID} via BertModel/BertTokenizer (no agentdriver import anywhere)...")
    tokenizer = BertTokenizer.from_pretrained(MODEL_ID)
    model = BertModel.from_pretrained(MODEL_ID).to(DEVICE)
    model.eval()

    real_pool = load_real_pool_turns(max_turns=17)
    print(f"Real candidate pool (db_embeddings source): {len(real_pool)} genuine LoCoMo turns.")
    db_embeddings = embed_texts(model, tokenizer, real_pool)
    print(f"db_embeddings shape: {tuple(db_embeddings.shape)}")

    gmm = GaussianMixture(n_components=3, covariance_type="full", random_state=SEED)
    gmm.fit(db_embeddings.detach().numpy())
    cluster_centers = torch.tensor(gmm.means_, dtype=torch.float32).unsqueeze(0)
    print(f"Fitted GaussianMixture: {cluster_centers.shape[1]} cluster centers.")

    # Real LoCoMo questions as the query stream (cycled to fill NUM_GRAD_ITER batches).
    real_queries = [
        "When is Caroline going camping?",
        "Did Caroline participate in a charity race?",
        "What did Caroline research?",
    ]

    # Initialize adversarial trigger as [MASK] tokens, per the reference's own
    # non-golden-trigger default.
    adv_passage_ids = torch.tensor(
        [tokenizer.mask_token_id] * NUM_ADV_PASSAGE_TOKENS, device=DEVICE
    ).unsqueeze(0)
    adv_passage_attention = torch.ones_like(adv_passage_ids)
    initial_trigger = tokenizer.convert_ids_to_tokens(adv_passage_ids.squeeze(0))
    print(f"Initial trigger tokens: {initial_trigger}")

    embeddings_module = get_embeddings(model)
    embedding_gradient = GradientStorage(embeddings_module, NUM_ADV_PASSAGE_TOKENS)

    any_update = False
    for it_ in range(NUM_ITER):
        model.zero_grad()
        grad = None
        loss_sum = 0.0

        for step in range(NUM_GRAD_ITER):
            query = real_queries[step % len(real_queries)]
            query_emb = query_embedding_with_trigger(model, tokenizer, query, adv_passage_ids, adv_passage_attention)
            loss = compute_avg_cluster_distance(query_emb, cluster_centers)
            loss_sum += loss.item()
            loss.backward()

            temp_grad = embedding_gradient.get()
            grad_sum = temp_grad.sum(dim=0)
            grad = grad_sum / NUM_GRAD_ITER if grad is None else grad + grad_sum / NUM_GRAD_ITER

        token_to_flip = random.randrange(NUM_ADV_PASSAGE_TOKENS)
        candidates = hotflip_attack(
            grad[token_to_flip], embeddings_module.weight, increase_loss=True, num_candidates=NUM_CAND
        )

        candidate_scores = torch.zeros(NUM_CAND)
        for step in range(NUM_GRAD_ITER):
            query = real_queries[step % len(real_queries)]
            for i, candidate in enumerate(candidates):
                temp_adv_passage = adv_passage_ids.clone()
                temp_adv_passage[:, token_to_flip] = candidate
                with torch.no_grad():
                    cand_emb = query_embedding_with_trigger(
                        model, tokenizer, query, temp_adv_passage, adv_passage_attention
                    )
                    can_loss = compute_avg_cluster_distance(cand_emb, cluster_centers)
                    candidate_scores[i] += can_loss.item()

        current_score = loss_sum
        best_score = candidate_scores.max().item()
        print(f"Iteration {it_}: current_score={current_score:.4f}, best_candidate_score={best_score:.4f}", end="  ")

        if (candidate_scores > current_score).any():
            best_idx = candidate_scores.argmax()
            old_token = tokenizer.convert_ids_to_tokens([adv_passage_ids[0, token_to_flip].item()])[0]
            adv_passage_ids[:, token_to_flip] = candidates[best_idx]
            new_token = tokenizer.convert_ids_to_tokens([adv_passage_ids[0, token_to_flip].item()])[0]
            print(f"UPDATED position {token_to_flip}: {old_token!r} -> {new_token!r}")
            any_update = True
        else:
            print("no improvement this iteration")

    final_trigger = tokenizer.convert_ids_to_tokens(adv_passage_ids.squeeze(0))
    print(f"\nInitial trigger: {initial_trigger}")
    print(f"Final trigger:   {final_trigger}")
    print(f"Trigger changed at least once: {any_update}")
    print(
        "\nThis confirms the extracted domain-agnostic core (fitness math, "
        "GradientStorage, HotFlip) runs end-to-end against real LoCoMo data and "
        "Mem0's real embedding function, entirely outside agentdriver's "
        "dataset/loading code. Iteration/candidate counts are smoke-test scale, "
        "not campaign scale -- see module docstring."
    )


if __name__ == "__main__":
    main()
