"""Phase 17 -- evaluation arenas: (pools, ground-truth) pairs an ablation runs on.

- `isolated_arena`: each poison record in its own pool with 3 real LoCoMo
  distractors (the live-path/Track B shape). Poison here can only be caught
  by per-memory evidence -- there is no crowd for retrieval consensus.
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


__all__ = ["coordinated_arena", "isolated_arena", "frozen_arena", "dataset_arena", "N_DISTRACTORS", "BENIGN_LOCOMO"]
