"""Tests for the defence-improvement programme (phase17/defence_v2)."""
from __future__ import annotations

import pytest


def _ret(d, a):
    return 0.8 if ("X" in d and "X" in a) else 0.05


def test_frozen_guard_decays_but_rcl_does_not_at_constant_retention():
    from phase17.defence_v2.propagation_multigen import chain_arms

    arms = chain_arms("X root", "QUARANTINED", ["X1", "X2", "X3", "X4"], [["a"], ["b"], ["c"], ["d"]], _ret)
    assert arms["RCL"] == ["REQUIRE_VALIDATION"] * 4                     # 0.7 * 0.8 = 0.56 every generation
    assert arms["FG"][0] == "REQUIRE_VALIDATION" and arms["FG"][-1] == "ALLOW"   # attenuates hop by hop
    assert arms["A0"] == ["ALLOW"] * 4


def test_lineage_arms_need_a_flagged_root_and_release_recovers():
    from phase17.defence_v2.propagation_multigen import chain_arms

    arms = chain_arms("X root", "UNASSESSED", ["X1", "X2"], [["a"], ["b"]], _ret)
    assert arms["RCL"] == ["ALLOW", "ALLOW"] and arms["FG"] == ["ALLOW", "ALLOW"]
    arms = chain_arms("X root", "QUARANTINED", ["X1", "X2"], [["a"], ["b"]], _ret)
    assert arms["RCL_released"] == ["ALLOW", "ALLOW"]                    # released root -> descendants recover


def test_rcl_ignores_unrelated_descendants():
    from phase17.defence_v2.propagation_multigen import chain_arms

    arms = chain_arms("X root", "QUARANTINED", ["benign summary"], [["a"]], _ret)
    assert arms["RCL"] == ["ALLOW"]                                      # 0.7 * 0.05 below every threshold


def test_sag_block_or_semantics_and_wrong_lineage():
    from phase17.defence_v2.sag_eval import sag_block

    items = [
        {"kind": "atk", "raw": {"B12": True, "B13": True}, "stored": [{"B12": False, "B13": False}], "outcome": True},
        {"kind": "atk", "raw": {"B12": False, "B13": False}, "stored": [{"B12": False, "B13": True}], "outcome": False},
        {"kind": "ben", "raw": {"B12": False, "B13": False}, "stored": [{"B12": False, "B13": False}], "outcome": None},
        {"kind": "ben", "raw": {"B12": False, "B13": True}, "stored": [], "outcome": None},
    ]
    r = sag_block(items)
    assert r["B13"]["atk"]["lost"]["k"] == 1 and r["B13"]["atk"]["intact"]["k"] == 2
    assert r["B13"]["ben"]["lost"]["k"] == 0 and r["B13"]["ben"]["intact"]["k"] == 1
    assert r["B13"]["atk"]["outcome_remaining_lost"]["k"] == 1 and r["B13"]["atk"]["outcome_remaining_intact"]["k"] == 0


def test_rcl_acceptance_requires_every_condition():
    from phase17.defence_v2.propagation_multigen import _accept

    def rate(k, n):
        return {"k": k, "n": n, "rate": k / n if n else None}
    o = {"withheld_carrying_flagged": {"RCL": [rate(8, 10), rate(8, 10), rate(7, 10), rate(7, 10)]},
         "paired": {"gen2_RCL_vs_FG": {"only_a": 9, "only_b": 0, "p_exact": 0.004},
                    "gen4_RCL_vs_FG": {"only_a": 9, "only_b": 0, "p_exact": 0.004},
                    "gen4_influence_RCL_vs_A0": {"only_a": 0, "only_b": 3, "p_exact": 0.25}},
         "collateral_unflagged_benign": {"RCL": [rate(0, 40)] * 4}}
    a = _accept(o)
    assert a["C1_gen4_withheld>=60%_drop<=15"] and a["C2_RCL>FG_gen2_gen4_holm"] and a["C3_unflagged_collateral<=5%"]
    assert a["C4_gen4_influence_RCL<A0"] == "UNDERPOWERED" and a["accepted"] is False


def test_sleeper_selection_rule_respects_benign_constraints(monkeypatch, tmp_path):
    from phase17.defence_v2 import sleeper_v2 as S

    agg = {n: {"atk": (30, 60), "ben_unground": (12, 60), "ben_ground": (0, 60)} for n in S.COMPLEXITY}
    agg["B13&INTENT_v1"] = {"atk": (20, 60), "ben_unground": (3, 60), "ben_ground": (1, 60)}
    monkeypatch.setattr(S, "score", lambda split: {})
    monkeypatch.setattr(S, "_rates", lambda owners, cache: {"aggregate": agg, "per_owner": {}})
    monkeypatch.setattr(S, "SEL", tmp_path / "sel.json")

    class _F:
        FREEZE = tmp_path / "f.json"
    (tmp_path / "f.json").write_text('{"sha256": "x"}')
    import phase17.defence_v2.sa3_corpus as C
    monkeypatch.setattr(C, "FREEZE", _F.FREEZE)
    out = S.select()
    assert out["chosen"] == "B13&INTENT_v1"                              # the only policy within both constraints


@pytest.mark.parametrize("fn", ["INTENT_V1", "INTENT_V2"])
def test_intent_prompts_never_see_labels(fn):
    from phase17.defence_v2 import sleeper_v2 as S

    t = getattr(S, fn)
    assert "{note}" in t and "attack" not in t.lower() and "poison" not in t.lower()
