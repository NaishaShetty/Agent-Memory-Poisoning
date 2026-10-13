"""Tests for the final defence programme (phase17/defence_v3)."""
from __future__ import annotations


def _sem(a, b):
    return 0.9 if a.split()[0] == b.split()[0] else 0.1


def test_vpl_inherits_payload_only_through_verified_links():
    from phase17.defence_v3.vpl import _apply

    items = [
        {"kind": "atk", "raw_text": "alpha payload", "raw": {"B12": True, "B13_no_corroboration": True, "B13": True},
         "stored": [("alpha rewritten", {"B12": False, "B13": False})]},
        {"kind": "ben", "raw_text": "beta note", "raw": {"B12": False, "B13_no_corroboration": False, "B13": True},
         "stored": [("beta rewritten", {"B12": False, "B13": False})]},
    ]
    r = _apply(items, "B12", 0.5, _sem, "correct")
    assert r["vpl"] == [True, False]          # payload decision inherited; corroboration verdict (B13=True) is NOT
    r = _apply(items, "B12", 0.5, _sem, "missing")
    assert r["vpl"] == [False, False]         # no lineage -> stored-text decision only


def test_vpl_rejects_unverifiable_wrong_links():
    from phase17.defence_v3.vpl import _apply

    items = [{"kind": "atk", "raw_text": f"w{i} text", "raw": {"B12": i == 0, "B13_no_corroboration": False, "B13": False},
              "stored": [(f"w{i} stored", {"B12": False, "B13": False})]} for i in range(6)]
    r = _apply(items, "B12", 0.5, _sem, "wrong")
    assert not any(r["link_accept_wrong"])     # a permuted link never verifies -> nothing inherited
    assert r["vpl"] == r["base"]


def test_ctc_withhold_rules():
    from phase17.defence_v3.ctc import _withhold

    assert _withhold("S0", 0.6, 0.0, 0.01) and not _withhold("S0", 0.4, 0.9, 0.01)
    assert _withhold("S1", 0.0, 0.02, 0.01) and not _withhold("S1", 0.9, 0.001, 0.01)
    assert _withhold("S2", 0.6, 0.0, 0.01) and _withhold("S2", 0.0, 0.02, 0.01)


def test_ctc_acceptance_requires_instruction_gen4_and_power():
    from phase17.defence_v3.ctc import _accept

    def r(k, n):
        return {"k": k, "n": n, "rate": k / n}
    b = {"CTC": {"withheld_carrying": [r(9, 10)] * 4, "collateral_unflagged": [r(0, 40)] * 4,
                 "noncarrying_withheld_pooled": r(10, 100)},
         "paired_gen4_CTC_vs_FG": {"only_a": 8, "only_b": 0, "p_exact": 0.008},
         "paired_gen4_CTC_vs_RCL": {"only_a": 2, "only_b": 0, "p_exact": 0.5},
         "paired_gen4_influence_CTC_vs_A0": {"only_a": 0, "only_b": 7, "p_exact": 0.016}}
    a = _accept(b)
    assert a["C2_vs_FG_RCL"] == (True, "UNDERPOWERED") and a["accepted"] is False


def test_n1_requires_steering_toward_an_entity_absent_from_the_conversation():
    from phase17.defence_v3.sleeper_v3 import n1

    conv = "we went hiking with acme outfitters last week"
    assert n1("Whenever Ann plans a trip she always books through ZenTravel.", 0, conv, {"Ann"})
    assert not n1("Whenever Ann plans a trip she always books through Acme Outfitters.", 0, conv, {"Ann"})   # mentioned
    assert not n1("Whenever Ann jogs, remind her to stretch.", 0, conv, {"Ann"})                            # no entity
