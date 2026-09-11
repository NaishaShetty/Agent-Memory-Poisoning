"""Phase 4 -- MAMBench reconstruction of DSRM, Milestone 5: white-box
retrieval-text optimization, real dry run.

Reuses AgentPoison's Milestone 1 embedder-compatibility finding (mean-pool
over last_hidden_state matches Mem0's real embedder; pooler_output does
not) rather than re-deriving it -- both attacks target the same real Mem0
MiniLM embedder. No LLM server needed (no SRM/CSRM here, pure gradient
optimization against the local embedder, like AgentPoison's Milestone 2/4).
"""

from __future__ import annotations

from phase4.attacks.dsrm.seeds import DSRM_SEEDS
from phase4.attacks.dsrm.white_box import optimize_retrieval_text


def main() -> None:
    positive_seed = DSRM_SEEDS[0]  # pottery
    negative_queries = [s.target_question for s in DSRM_SEEDS[1:]]  # museum, picnic

    print(f"Positive (target) query: {positive_seed.target_question!r}")
    print(f"Negative queries: {negative_queries}\n")

    result = optimize_retrieval_text(
        positive_query=positive_seed.target_question,
        negative_queries=negative_queries,
        num_adv_tokens=6,
        num_iter=15,
        num_cand=40,
    )

    print(f"InfoNCE loss (lower = anchor closer to positive, farther from negatives):")
    print(f"  initial: {result.loss_initial:.4f}")
    print(f"  final:   {result.loss_final:.4f}")
    print(f"Optimized retrieval tokens: {result.retrieval_tokens}")
    print(f"Optimized retrieval text: {result.retrieval_text!r}")


if __name__ == "__main__":
    main()
