"""Phase 11.1 -- the train/dev/held-out split for the GNN and GLN.

Extends the exact separation discipline `dev_corpus.py`/`corpus.py` already
established (Phase 6.9, reaffirmed by Section 21.9/Phase 10) to graph-shaped
data: training and dev graphs are built from `dev_corpus.py`'s own disjoint
pools (real content, never reported against), and the held-out evaluation
graphs are the SAME reported corpus (`corpus.py`) Section 21.9/Phase 10
already report numbers against, touched only once, at the end -- exactly the
non-circular discipline every prior phase's own evaluation held to.

No new scenario content is authored here. Every pool below is a real object
`dev_corpus.py`/`corpus.py` already define; this module's only job is to
group them into three disjoint sets and expose that grouping under one name,
plus wrap `dev_propagation_scenarios()`'s plain-tuple shape into
`MemoryScenario`/`ScenarioPool` (the shape every other pool already uses) so
`phase11/gnn/graph_build.py` has one uniform input type.
"""

from __future__ import annotations

from typing import Tuple

from phase6.defense.orchestration.pipeline import MemoryScenario, ScenarioPool
from phase6.evaluation.ablations import corpus as reported_corpus
from phase6.evaluation.ablations import dev_corpus


def _propagation_pool_from_dev_tuples(pool_id: str) -> ScenarioPool:
    memories = []
    for scenario_id, content, ancestors, is_poison in dev_corpus.dev_propagation_scenarios():
        memories.append(
            MemoryScenario(
                scenario_id,
                content,
                memory_type="derived",
                parent_ids=tuple(a.memory_id for a in ancestors),
                ancestors=ancestors,
                is_poison_ground_truth=is_poison,
                attack_family_ground_truth="propagated" if is_poison else None,
            )
        )
    return ScenarioPool(pool_id, tuple(memories))


def train_pools() -> Tuple[ScenarioPool, ...]:
    """Training split -- real, disjoint dev-corpus content only."""
    return (
        dev_corpus.dev_near_duplicate_pool(),
        dev_corpus.dev_admission_pool(),
    )


def dev_pools() -> Tuple[ScenarioPool, ...]:
    """Dev split -- real, disjoint dev-corpus content, used for model
    selection / early-stopping only, never for the final reported number."""
    return (
        dev_corpus.dev_paraphrased_pool(),
        dev_corpus.dev_sleeper_pool(),
        _propagation_pool_from_dev_tuples("POOL-PHASE11-DEV-PROPAGATION"),
    )


def held_out_pools() -> Tuple[ScenarioPool, ...]:
    """Held-out evaluation split -- the SAME reported corpus B0-B9 already
    report real numbers against (`corpus.py`). Touched only for the final,
    disclosed evaluation run -- never for training or threshold selection."""
    return reported_corpus.all_pools()


def all_splits():
    return {"train": train_pools(), "dev": dev_pools(), "held_out": held_out_pools()}


def all_dev_pools() -> Tuple[ScenarioPool, ...]:
    """Follow-on (2026-09-17, Plan Section 5's own named next step): the
    UNION of `train_pools()` and `dev_pools()` -- every real, disjoint
    dev-corpus pool this project has, combined. Still automatically disjoint
    from `held_out_pools()` (a union of two already-disjoint-from-held-out
    sets is itself disjoint from held-out; `test_gnn_gln_corpus_is_disjoint.py`
    is untouched and still holds). Exists because the original fixed
    train/dev split sacrificed roughly half of this project's already-tiny
    real calibration data to a dev role used only for threshold selection --
    a real, avoidable cost at this data scale. `dev_corpus_folds()` below
    provides the SAME 5 pools individually, for leave-one-pool-out
    cross-validation, so no real content is silently withheld from training
    AND threshold selection can still be done without ever peeking at
    held-out data."""
    return train_pools() + dev_pools()


def dev_corpus_folds() -> Tuple[ScenarioPool, ...]:
    """The 5 real, individually-named dev-corpus pools, for leave-one-pool-out
    cross-validation over `all_dev_pools()` -- never a fold boundary that
    splits a single pool's own memories across folds, since a pool's members
    share real structural edges (RETRIEVED_WITH) with each other that a
    naive per-memory fold split would sever."""
    return all_dev_pools()
