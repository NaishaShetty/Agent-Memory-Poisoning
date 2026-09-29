"""Phase 17 -- evaluation arenas: (pools, ground-truth) pairs an ablation runs on.

- `isolated_arena`: each poison record in its own pool with 3 real LoCoMo
  distractors (the live-path/Track B shape). Poison here can only be caught
  by per-memory evidence -- there is no crowd for retrieval consensus.
- `realistic_arena`: same shape as `isolated_arena`, but with a configurable,
  much larger distractor count (default 100) -- see its own docstring for why.
- `frozen_arena`: `corpus.py`'s 75 scenarios, which INCLUDE coordinated
  near-duplicate / paraphrased poison pools -- the one place retrieval-only
  evidence can legitimately decide (what the corroboration gates suppress).
- `dataset_arena`: Phase 12's real benign pools for LoCoMo/LongMemEval/MSC/
  ConversationChronicles (502 records) -- benign only, for false positives.
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

from phase11.relational_signals.locomo_qa_counterfactuals import flat_counterfactual_pool
from phase12.eval_corpus import per_dataset_eval_corpora
from phase17.engine import Truth
from phase17.poison_sets import PoisonRecord
from phase6.defense.orchestration.pipeline import MemoryScenario, ScenarioPool
from phase6.evaluation.ablations.corpus import all_pools

N_DISTRACTORS = 3
BENIGN_LOCOMO = "benign_locomo"


def isolated_arena(records: Sequence[PoisonRecord]) -> Tuple[List[ScenarioPool], Dict[str, Truth]]:
    benign = flat_counterfactual_pool()
    pools, truth = [], {}
    for i, r in enumerate(records):
        mems = [MemoryScenario(r.scenario_id, r.text, is_poison_ground_truth=True,
                               attack_family_ground_truth=r.family)]
        truth[r.scenario_id] = Truth(True, r.family, r.split)
        for k in range(N_DISTRACTORS):
            d = benign[(i * N_DISTRACTORS + k) % len(benign)]
            mid = f"P17-DIST-{i}-{k}"
            mems.append(MemoryScenario(mid, d.declarative_text))
            truth[mid] = Truth(False, None, BENIGN_LOCOMO)
        pools.append(ScenarioPool(f"P17-ISO-{i}", tuple(mems)))
    return pools, truth


REALISTIC_N_DISTRACTORS = 100
BENIGN_REALISTIC = "benign_realistic_scale"


def _realistic_benign_pool() -> List[str]:
    """Real benign text drawn from two real sources, combined for diversity at scale --
    135 LoCoMo counterfactual items alone would mean heavy repetition across many
    100-distractor pools. `flat_counterfactual_pool()`'s 135 LoCoMo items are genuinely
    real dialogue; ConvoMem's ~718 messages are real-conversation-derived but carry
    documented "strong circumstantial evidence of LLM generation" (see
    `phase3/datasets/candidates/convomem/README.md`) -- disclosed here because it matters
    for a false-positive claim, though not for this arena's actual purpose (testing
    retrieval competition at realistic scale, where text authorship is not the variable
    under test)."""
    from phase17.extra_datasets import convomem_pools

    locomo = [d.declarative_text for d in flat_counterfactual_pool()]
    convomem_p, _ = convomem_pools()
    convomem = [m.content_text for p in convomem_p for m in p.memories]
    return locomo + convomem


def realistic_arena(
    records: Sequence[PoisonRecord], n_distractors: int = REALISTIC_N_DISTRACTORS,
) -> Tuple[List[ScenarioPool], Dict[str, Truth]]:
    """Same shape as `isolated_arena` (one pool per record, poison + real benign
    distractors), but with a configurable, much larger distractor count (default 100,
    vs. `isolated_arena`'s fixed 3).

    Added (external review round 4, 2026-09-28): every Phase 17 test before this used
    `N_DISTRACTORS = 3` -- a real assistant's memory store holds hundreds to thousands of
    memories, and neither attack success (is the poison even retrieved into the top-k
    among many real competitors) nor a per-memory-cost defense's expense at that scale had
    ever been measured. This is additive: `isolated_arena`'s own 3-distractor numbers are
    unchanged and remain the ones every other Phase 17 result traces to.
    """
    benign = _realistic_benign_pool()
    pools, truth = [], {}
    for i, r in enumerate(records):
        mems = [MemoryScenario(r.scenario_id, r.text, is_poison_ground_truth=True,
                               attack_family_ground_truth=r.family)]
        truth[r.scenario_id] = Truth(True, r.family, r.split)
        for k in range(n_distractors):
            d = benign[(i * n_distractors + k) % len(benign)]
            mid = f"P17-REAL-DIST-{i}-{k}"
            mems.append(MemoryScenario(mid, d))
            truth[mid] = Truth(False, None, BENIGN_REALISTIC)
        pools.append(ScenarioPool(f"P17-REALISTIC-{i}", tuple(mems)))
    return pools, truth


def coordinated_arena(records: Sequence[PoisonRecord]) -> Tuple[List[ScenarioPool], Dict[str, Truth]]:
    """Poison CO-POOLED the way Phase 12's corpus did (all original records in
    one pool, all regenerated records in another) -- the only arena where
    sibling-propagation and retrieval consensus can act on a poison cluster."""
    pools, truth = [], {}
    for split in sorted({r.split for r in records}):
        grp = [r for r in records if r.split == split]
        pools.append(ScenarioPool(f"P17-COORD-{split}", tuple(
            MemoryScenario(r.scenario_id, r.text, is_poison_ground_truth=True, attack_family_ground_truth=r.family)
            for r in grp)))
        for r in grp:
            truth[r.scenario_id] = Truth(True, r.family, r.split)
    return pools, truth


def frozen_arena() -> Tuple[List[ScenarioPool], Dict[str, Truth]]:
    pools = list(all_pools())
    truth = {}
    for p in pools:
        for m in p.memories:
            truth[m.scenario_id] = Truth(m.is_poison_ground_truth, m.attack_family_ground_truth, "frozen75")
    return pools, truth


def dataset_arena() -> Tuple[List[ScenarioPool], Dict[str, Truth]]:
    pools, truth = [], {}
    for name, corpus in per_dataset_eval_corpora().items():
        for p in corpus.benign_pools:
            pools.append(p)
            for m in p.memories:
                truth[m.scenario_id] = Truth(False, None, f"benign_{name}")
    return pools, truth


__all__ = ["coordinated_arena", "isolated_arena", "realistic_arena", "frozen_arena", "dataset_arena",
          "N_DISTRACTORS", "BENIGN_LOCOMO", "REALISTIC_N_DISTRACTORS", "BENIGN_REALISTIC"]
