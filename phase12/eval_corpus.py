"""Phase 12 -- a new, separate real evaluation corpus for the security-metric
sweep (Plan Section 8.4, confirmed: authorize a new corpus rather than
reusing `held_out_pools()` alone).

NON-NEGOTIABLE GUARDRAILS (Plan Section 5)
--------------------------------------------------------------------------------
- Never touches, imports for modification, or reads-then-mutates
  `phase6.evaluation.ablations.corpus.all_pools()` /
  `phase11.data.split.held_out_pools()`. Both are read-only reference points
  elsewhere in this module tree (`dgs.py`), never inputs here.
- Every scenario is real content: real LoCoMo turns (`phase11.data.real_corpus`),
  real records from the 3 previously-unused unified-memory datasets
  (`phase11.data.clean_expansion`), and real output from each attack's own
  unmodified `Injector` class. No fabricated text.
- `is_poison_ground_truth`/`attack_family_ground_truth` are real, known
  ground truth (the attack that produced the content, or `False` for real
  clean records) -- never a manually-assigned "should detect" label.

CORPUS SHAPE
--------------------------------------------------------------------------------
One real poison pool (`real_poison_scenarios()`, 7 real attack families, 15
real forged memories, unchanged from `phase11.data.real_corpus`) is paired
with each of 4 datasets' own real benign pools, giving 4 dataset-scoped
corpora that share the same real poison but never share benign content
across datasets. This is the attack x dataset cell structure the Plan's
evaluation matrix (Section 7) calls for, with the workload axis dropped
(confirmed, Section 8.2) and the sample size per newly-included dataset
matching `clean_expansion.py`'s own already-validated controlled sample
(`CONTROLLED_POOLS_PER_DATASET = 10`, confirmed, Section 8.3).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

from phase6.defense.orchestration.pipeline import ScenarioPool
from phase6.evaluation.ablations.corpus import all_pools as _reported_corpus_pools
from phase11.data.clean_expansion import CONTROLLED_POOLS_PER_DATASET, real_session_pools
from phase11.data.real_corpus import real_benign_scenarios, real_poison_scenarios

DATASET_LOCOMO = "locomo"
DATASET_LONGMEMEVAL = "longmemeval"
DATASET_MSC = "msc"
DATASET_CONVERSATION_CHRONICLES = "conversation_chronicles"

ALL_DATASETS: Tuple[str, ...] = (
    DATASET_LOCOMO,
    DATASET_LONGMEMEVAL,
    DATASET_MSC,
    DATASET_CONVERSATION_CHRONICLES,
)


@dataclass(frozen=True)
class DatasetCorpus:
    dataset_name: str
    benign_pools: Tuple[ScenarioPool, ...]
    poison_pool: ScenarioPool

    @property
    def pools(self) -> Tuple[ScenarioPool, ...]:
        return self.benign_pools + (self.poison_pool,)

    @property
    def n_benign(self) -> int:
        return sum(len(p.memories) for p in self.benign_pools)


def per_dataset_eval_corpora(*, num_pools_per_new_dataset: int = CONTROLLED_POOLS_PER_DATASET) -> Dict[str, DatasetCorpus]:
    """One `DatasetCorpus` per real dataset -- real benign pools specific to
    that dataset, paired with the SAME shared real 7-family poison pool
    (attacks are not dataset-specific in this project's own real injector
    code, so there is exactly one real poison population to pair against
    each dataset's real benign population)."""
    poison_pool = real_poison_scenarios()
    corpora: Dict[str, DatasetCorpus] = {
        DATASET_LOCOMO: DatasetCorpus(DATASET_LOCOMO, real_benign_scenarios(), poison_pool),
    }
    for dataset_name in (DATASET_LONGMEMEVAL, DATASET_MSC, DATASET_CONVERSATION_CHRONICLES):
        pools, _provenance = real_session_pools(dataset_name, num_pools=num_pools_per_new_dataset)
        corpora[dataset_name] = DatasetCorpus(dataset_name, pools, poison_pool)
    return corpora


def combined_new_corpus_pools(corpora: Dict[str, DatasetCorpus] = None) -> Tuple[ScenarioPool, ...]:
    """Every real pool across every dataset, poison pool counted once (all
    4 `DatasetCorpus` entries share the identical `real_poison_scenarios()`
    object -- same 15 scenario ids -- so it is included only once here to
    avoid double-counting poison in a combined, cross-dataset metric)."""
    corpora = corpora or per_dataset_eval_corpora()
    pools = []
    poison_pool_ids_seen = set()
    for corpus in corpora.values():
        pools.extend(corpus.benign_pools)
        if corpus.poison_pool.pool_id not in poison_pool_ids_seen:
            pools.append(corpus.poison_pool)
            poison_pool_ids_seen.add(corpus.poison_pool.pool_id)
    return tuple(pools)


def assert_disjoint_from_held_out_pools(corpora: Dict[str, DatasetCorpus] = None) -> None:
    """Guardrail: this corpus's scenario ids must never intersect the
    reported `held_out_pools()`/`corpus.all_pools()` corpus -- verified
    directly, not just asserted in a docstring."""
    reported_ids = {m.scenario_id for pool in _reported_corpus_pools() for m in pool.memories}
    new_ids = {m.scenario_id for pool in combined_new_corpus_pools(corpora) for m in pool.memories}
    overlap = reported_ids & new_ids
    if overlap:
        raise AssertionError(f"Phase 12 eval corpus overlaps held_out_pools() scenario ids: {sorted(overlap)}")
