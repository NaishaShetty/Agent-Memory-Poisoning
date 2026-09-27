"""Phase 17 -- tests. Fast, no LLM. The load-bearing ones check that the
ablation engine reproduces the FROZEN decision code exactly when nothing is
ablated (every ablation number depends on that), and that the poison
populations / statistics behave as documented."""

from __future__ import annotations

import json

from phase14.defended_retrieval import apply_defense
from phase14.track_b_poison import build_track_b_cases
from phase17 import arenas
from phase17.engine import (
    ADMISSION_KEYS, admission_actions, build_signal_table, guard_actions, rule_actions,
)
from phase17.generalization import SIGNALS_FROM_FAMILY
from phase17.poison_sets import (
    EVASION_CACHE, SPLIT_EVASION, SPLIT_REGEN, SPLIT_SOURCE, all_records, by_split, evasion_records,
    original_records, regenerated_records,
)
from phase17.stats import exact_mcnemar_p, paired_delta, rate_with_ci, wilson_interval
from phase6.defense.orchestration.pipeline import B8_ALL_FOUR, MemoryScenario, ScenarioPool
from phase6.defense.risk.risk_score import GROUPED_GATED_ADMISSION_CORROBORATED


# ---- statistics ----
def test_wilson_interval_brackets_the_rate_and_widens_for_small_n():
    lo, hi = wilson_interval(4, 9)
    assert lo < 4 / 9 < hi
    assert (hi - lo) > (wilson_interval(40, 90)[1] - wilson_interval(40, 90)[0])
    assert wilson_interval(0, 0) == (0.0, 1.0)


def test_exact_mcnemar_known_values():
    assert exact_mcnemar_p(0, 0) == 1.0
    assert exact_mcnemar_p(1, 0) == 1.0          # a single discordant pair proves nothing
    assert abs(exact_mcnemar_p(6, 0) - 2 / 64) < 1e-12
    assert exact_mcnemar_p(3, 3) == 1.0


def test_paired_delta_counts():
    d = paired_delta([True, True, False, False], [True, False, False, True])
    assert (d["only_a"], d["only_b"], d["detected_a"], d["detected_b"]) == (1, 1, 2, 2)


# ---- poison populations ----
def test_populations_have_documented_sizes_and_disjoint_provenance():
    assert len(original_records()) == 15
    assert len(regenerated_records()) == 9
    ids = [r.scenario_id for r in all_records()]
    assert len(ids) == len(set(ids))
    splits = by_split(all_records())
    assert set(splits) == {SPLIT_SOURCE, SPLIT_REGEN, SPLIT_EVASION}


def test_evasion_cache_is_recorded_with_full_provenance_and_mostly_valid():
    data = json.loads(EVASION_CACHE.read_text(encoding="utf-8"))
    assert len(data["variants"]) == 48
    for v in data["variants"]:
        assert {"prompt", "seed", "model", "text", "parent_similarity", "valid", "parent_id"} <= set(v)
    assert len(evasion_records()) >= 40            # invalid ones are kept in the cache, not silently dropped
    parents = {r.scenario_id for r in original_records() + regenerated_records()}
    assert all(r.parent_id in parents for r in evasion_records())


# ---- engine reproduces frozen decisions when nothing is ablated ----
def test_admission_only_engine_matches_the_frozen_b1_decision_exactly():
    recs = all_records(include_evasion=False)
    pools, _ = arenas.isolated_arena(recs[:12])
    table = build_signal_table(pools)
    mine = admission_actions(table)
    for pool in pools:
        for m in pool.memories:
            _, decisions = apply_defense("B1", [(m.scenario_id, m.content_text)])
            assert mine[m.scenario_id] == decisions[0].action


def test_rule_engine_matches_phase14_live_b9_decision_exactly():
    case = build_track_b_cases()[0]
    pool = ScenarioPool("t", tuple(MemoryScenario(i, t) for i, t in case.pool_items))
    mine = rule_actions(build_signal_table([pool]), rule=GROUPED_GATED_ADMISSION_CORROBORATED)
    _, decisions = apply_defense("B9", case.pool_items)
    assert mine == {d.memory_id: d.action for d in decisions}


def test_guard_engine_matches_apply_defense_for_b8():
    case = build_track_b_cases()[1]
    pool = ScenarioPool("t", tuple(MemoryScenario(i, t) for i, t in case.pool_items))
    mine = guard_actions([pool], B8_ALL_FOUR)
    _, decisions = apply_defense("B8", case.pool_items)
    assert mine == {d.memory_id: d.action for d in decisions}


def test_dropping_a_signal_can_only_lower_or_keep_the_admission_score():
    pools, _ = arenas.isolated_arena(all_records(include_evasion=False)[:8])
    table = build_signal_table(pools)
    order = {"ALLOW": 0, "ALLOW_WITH_RESTRICTION": 1, "QUARANTINE": 2, "BLOCK": 3}
    full = admission_actions(table)
    for key in ADMISSION_KEYS:
        ablated = admission_actions(table, frozenset({key}))
        assert all(order[ablated[m]] <= order[full[m]] for m in full)


# ---- arenas / maps ----
def test_isolated_arena_shape_and_truth():
    recs = all_records(include_evasion=False)[:5]
    pools, truth = arenas.isolated_arena(recs)
    assert len(pools) == 5 and all(len(p.memories) == 1 + arenas.N_DISTRACTORS for p in pools)
    assert sum(t.is_poison for t in truth.values()) == 5


def test_family_signal_map_only_names_real_admission_or_sleeper_keys():
    valid = set(ADMISSION_KEYS) | {"imperative_write_directive_score", "activation_shape_score"}
    for fam, sigs in SIGNALS_FROM_FAMILY.items():
        assert sigs <= valid, fam
