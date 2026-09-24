"""Phase 15 follow-on (2026-09-23, explicitly authorized) -- real tests for
`defended_retrieval.py`'s new B2-B7 support. Fast (no LLM calls -- these
test the real per-memory DECISION layer, not a live agent answer).

WHY THE DEGENERACY CHECK MATTERS
--------------------------------------------------------------------------------
`pipeline.py::evaluate_pool()` only calls `evaluate_propagation_containment()`
when a memory has real `ancestors` (`m.ancestors` truthy). None of Phase 14's
real live task memories (LoCoMo/LongMemEval QA pairs, poison scenarios) carry
real ancestors, so propagation can never fire for them -- this means B3, B5,
B6, B7 are PROVABLY identical to B0, B2, B1, B4 respectively in this live
setting, not merely similar. This is checked directly here, on real Phase 14
pool data (both Track A and Track B real items), rather than only argued from
reading the source -- exactly the "confirmed directly, not assumed" standard
this project applies everywhere else."""

from __future__ import annotations

from phase14.defended_retrieval import (
    CONFIG_B0_NO_DEFENSE,
    CONFIG_B1_ADMISSION_ONLY,
    CONFIG_B2_RETRIEVAL_ONLY,
    CONFIG_B3_PROPAGATION_ONLY,
    CONFIG_B4_ADMISSION_RETRIEVAL,
    CONFIG_B5_RETRIEVAL_PROPAGATION,
    CONFIG_B6_ADMISSION_PROPAGATION,
    CONFIG_B7_ALL_THREE,
    CONFIG_B8_ALL_FOUR,
    apply_defense,
)
from phase14.track_a_benign import build_track_a_cases
from phase14.track_b_poison import build_track_b_cases


def _real_pools():
    """Real (memory_id, content_text) pools from both Track A (real LoCoMo
    QA pairs) and Track B (real DSRM/FARMA/MPBench poison scenarios) --
    covers both benign and adversarial real content, not just one shape."""
    pools = []
    for case in build_track_a_cases(5):
        pools.append(case.pool_items)
    for case in build_track_b_cases():
        pools.append(case.pool_items)
    return pools


def test_b2_through_b7_run_without_error_on_real_pools():
    for pool_items in _real_pools():
        for config in (
            CONFIG_B2_RETRIEVAL_ONLY, CONFIG_B3_PROPAGATION_ONLY, CONFIG_B4_ADMISSION_RETRIEVAL,
            CONFIG_B5_RETRIEVAL_PROPAGATION, CONFIG_B6_ADMISSION_PROPAGATION, CONFIG_B7_ALL_THREE,
        ):
            kept, decisions = apply_defense(config, pool_items)
            assert len(decisions) == len(pool_items)
            assert set(mid for mid, _ in kept) <= {mid for mid, _ in pool_items}


def _actions_for(config, pool_items):
    _, decisions = apply_defense(config, pool_items)
    return {d.memory_id: d.action for d in decisions}


def test_b3_degenerates_to_b0_on_real_data_no_ancestors():
    """Real, direct confirmation: B3 (propagation-only) never excludes
    anything in Phase 14's live setting, matching B0 exactly, because no
    real live task memory carries real ancestors."""
    for pool_items in _real_pools():
        b0 = _actions_for(CONFIG_B0_NO_DEFENSE, pool_items)
        b3 = _actions_for(CONFIG_B3_PROPAGATION_ONLY, pool_items)
        assert b3 == b0


def test_b5_degenerates_to_b2_on_real_data_no_ancestors():
    for pool_items in _real_pools():
        b2 = _actions_for(CONFIG_B2_RETRIEVAL_ONLY, pool_items)
        b5 = _actions_for(CONFIG_B5_RETRIEVAL_PROPAGATION, pool_items)
        assert b5 == b2


def test_b6_degenerates_to_b1_on_real_data_no_ancestors():
    for pool_items in _real_pools():
        b1 = _actions_for(CONFIG_B1_ADMISSION_ONLY, pool_items)
        b6 = _actions_for(CONFIG_B6_ADMISSION_PROPAGATION, pool_items)
        assert b6 == b1


def test_b7_degenerates_to_b4_on_real_data_no_ancestors():
    for pool_items in _real_pools():
        b4 = _actions_for(CONFIG_B4_ADMISSION_RETRIEVAL, pool_items)
        b7 = _actions_for(CONFIG_B7_ALL_THREE, pool_items)
        assert b7 == b4


def test_b1_bespoke_path_matches_the_new_generic_evaluate_pool_path():
    """B1's own bespoke `_b1_action()` (calling `evaluate_admission()`
    directly, predating this session's `evaluate_pool()` reuse) must agree
    exactly with what the new, generic `_pipeline_actions()` path would
    compute for B1 via `evaluate_pool()` -- checked directly rather than
    assumed identical, since B1 is kept on its original bespoke path (no
    reason to touch already-correct, already-tested code) while B2-B7 are
    new and use the generic path."""
    from phase6.defense.orchestration.pipeline import B1_ADMISSION_ONLY
    from phase14.defended_retrieval import _pipeline_actions

    for pool_items in _real_pools():
        bespoke = _actions_for(CONFIG_B1_ADMISSION_ONLY, pool_items)
        generic = _pipeline_actions(pool_items, B1_ADMISSION_ONLY)
        assert bespoke == generic


def test_b2_never_excludes_real_benign_locomo_content():
    """B2 (retrieval-consensus only) real, direct sanity check: the 5 real
    LoCoMo Track A pools (target + 4 real distractors, no coordinated poison
    cluster) should never see a real benign target excluded -- retrieval
    consensus flags divergence FROM the pool's own consensus, and a single
    genuine QA pair among unrelated real distractors is not expected to
    cluster as a false consensus violator (matches this project's own
    already-disclosed retrieval-guard behavior elsewhere)."""
    for case in build_track_a_cases(5):
        kept, decisions = apply_defense(CONFIG_B2_RETRIEVAL_ONLY, case.pool_items)
        target_decision = next(d for d in decisions if d.memory_id == case.target_memory_id)
        assert not target_decision.excluded
