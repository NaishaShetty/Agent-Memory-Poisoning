"""Structural tests for phase17/arenas.py (no LLM calls -- pool shape only)."""
from phase17.arenas import BENIGN_REALISTIC, REALISTIC_N_DISTRACTORS, isolated_arena, realistic_arena
from phase17.novel_attacks import novel_records


def test_realistic_arena_default_distractor_count():
    recs = novel_records()[:3]
    pools, truth = realistic_arena(recs)
    assert len(pools) == 3
    for pool, r in zip(pools, recs):
        assert len(pool.memories) == 1 + REALISTIC_N_DISTRACTORS
        assert pool.memories[0].scenario_id == r.scenario_id
        assert pool.memories[0].is_poison_ground_truth is True
        assert all(not m.is_poison_ground_truth for m in pool.memories[1:])
    distractor_ids = [m.scenario_id for pool in pools for m in pool.memories[1:]]
    assert len(distractor_ids) == len(set(distractor_ids)), "distractor scenario_ids must be unique across pools"
    assert all(truth[m.scenario_id].split == BENIGN_REALISTIC for pool in pools for m in pool.memories[1:])


def test_realistic_arena_respects_custom_distractor_count():
    recs = novel_records()[:2]
    pools, _ = realistic_arena(recs, n_distractors=10)
    assert all(len(pool.memories) == 11 for pool in pools)


def test_realistic_arena_vs_isolated_arena_same_poison_records():
    """Both arenas must agree on which record is the poison and its ground-truth family
    -- only the distractor count and source should differ."""
    recs = novel_records()[:5]
    iso_pools, iso_truth = isolated_arena(recs)
    real_pools, real_truth = realistic_arena(recs, n_distractors=5)
    for iso_pool, real_pool, r in zip(iso_pools, real_pools, recs):
        assert iso_pool.memories[0].scenario_id == real_pool.memories[0].scenario_id == r.scenario_id
        assert iso_truth[r.scenario_id].family == real_truth[r.scenario_id].family == r.family
