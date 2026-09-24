"""Phase 15 -- tests for the live per-task B10 decision (no LLM calls)."""

from __future__ import annotations

from phase14.defended_retrieval import CONFIG_B10_LEARNED_HYBRID, REAL_CONFIGS, apply_defense
from phase14.track_a_benign import build_track_a_cases
from phase14.track_b_poison import build_track_b_cases
from phase15.b10_live import live_threshold


def test_b10_is_a_registered_live_config():
    assert CONFIG_B10_LEARNED_HYBRID in REAL_CONFIGS


def test_live_threshold_is_calibrated_once_and_is_minus_inf_because_no_benign_is_corroborated():
    """Disclosed real fact: no Phase 12 benign record is corroborated, so
    there is nothing to calibrate a score boundary on -- the threshold is -inf
    and the corroboration gate alone decides."""
    t = live_threshold()
    assert t == live_threshold()
    assert t == float("-inf")


def test_apply_defense_b10_returns_a_decision_per_candidate_and_only_quarantines():
    for case in build_track_a_cases(3) + build_track_b_cases()[:3]:
        kept, decisions = apply_defense(CONFIG_B10_LEARNED_HYBRID, case.pool_items)
        assert len(decisions) == len(case.pool_items)
        assert {d.action for d in decisions} <= {"ALLOW", "QUARANTINE"}
        assert len(kept) == sum(1 for d in decisions if not d.excluded)


def test_corroborated_live_b10_protects_isolated_track_b_poison():
    """Real, measured: the corroboration-gated live B10 excludes all 9
    isolated Track B poison cases (the FIRST, ungated version excluded 0/9 and
    also excluded ~5% of benign Track A candidates -- retrieval-only evidence,
    the B9/LongMemEval root cause -- which is why the gate exists)."""
    excluded = 0
    for case in build_track_b_cases():
        _, decisions = apply_defense(CONFIG_B10_LEARNED_HYBRID, case.pool_items)
        excluded += any(d.excluded and d.memory_id == case.target_scenario_id for d in decisions)
    assert excluded == 9


def test_corroborated_live_b10_excludes_no_benign_locomo_candidates():
    for case in build_track_a_cases(20):
        _, decisions = apply_defense(CONFIG_B10_LEARNED_HYBRID, case.pool_items)
        assert not any(d.excluded for d in decisions)
