"""Phase 11.x Track A -- regression tests for `phase11/data/clean_expansion.py`."""

from __future__ import annotations

import inspect

from phase11.data.clean_expansion import (
    UNUSED_CLEAN_DATASETS,
    clean_expansion_pools,
    real_session_pools,
)


def _references_held_out_pools_in_code(module) -> bool:
    for _, obj in inspect.getmembers(module, inspect.isfunction):
        if obj.__module__ != module.__name__:
            continue
        if "held_out_pools" in obj.__code__.co_names:
            return True
    return False


def test_no_held_out_access():
    import phase11.data.clean_expansion as mod

    assert not _references_held_out_pools_in_code(mod)


def test_deterministic_across_repeated_calls():
    pools_1, prov_1 = clean_expansion_pools()
    pools_2, prov_2 = clean_expansion_pools()

    assert [(p.pool_id, tuple(m.scenario_id for m in p.memories)) for p in pools_1] == \
           [(p.pool_id, tuple(m.scenario_id for m in p.memories)) for p in pools_2]
    assert prov_1 == prov_2


def test_provenance_preserved_for_every_scenario():
    pools, provenance = clean_expansion_pools()
    all_scenario_ids = {m.scenario_id for p in pools for m in p.memories}
    assert all_scenario_ids == set(provenance)
    for record in provenance.values():
        assert record.source_dataset in UNUSED_CLEAN_DATASETS
        assert record.source_record_id
        assert record.conversation_id
        assert record.session_id
        assert record.provenance  # the real, source-file provenance dict is non-empty


def test_no_fabricated_lineage():
    """No scenario built by this module ever declares parent_ids/ancestors --
    the audit found real derivation_parents are unpopulated in this corpus,
    so none is invented here."""
    pools, _ = clean_expansion_pools()
    for pool in pools:
        for m in pool.memories:
            assert m.parent_ids == ()
            assert m.ancestors == ()


def test_no_label_leakage():
    """Every clean-expansion scenario is unconditionally benign -- no
    poison label of any kind is ever set."""
    pools, _ = clean_expansion_pools()
    for pool in pools:
        for m in pool.memories:
            assert m.is_poison_ground_truth is False
            assert m.attack_family_ground_truth is None


def test_pool_grouping_matches_real_source_conversation_and_session():
    """Every memory in one pool must share the SAME real (conversation_id,
    session_id) -- confirms pools are not an arbitrary chunking."""
    for dataset_name in UNUSED_CLEAN_DATASETS:
        pools, provenance = real_session_pools(dataset_name, num_pools=3)
        for pool in pools:
            conv_ids = {provenance[m.scenario_id].conversation_id for m in pool.memories}
            session_ids = {provenance[m.scenario_id].session_id for m in pool.memories}
            assert len(conv_ids) == 1
            assert len(session_ids) == 1


def test_controlled_sample_not_full_corpus():
    """This module must never claim more pools than the documented,
    controlled per-dataset default."""
    from phase11.data.clean_expansion import CONTROLLED_POOLS_PER_DATASET

    pools, _ = clean_expansion_pools()
    assert len(pools) == CONTROLLED_POOLS_PER_DATASET * len(UNUSED_CLEAN_DATASETS)


def test_pool_sizes_are_realistic_not_confounded():
    """Real per-session pool sizes must land in a reasonable range (not one
    giant merged pool, not artificially forced to a single constant size)."""
    for dataset_name in UNUSED_CLEAN_DATASETS:
        pools, _ = real_session_pools(dataset_name)
        sizes = [len(p.memories) for p in pools]
        assert all(2 <= s <= 60 for s in sizes), f"{dataset_name} pool sizes out of expected real range: {sizes}"
