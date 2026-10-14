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


def test_ctc_lineage_arms_never_act_on_unflagged_roots():
    from phase17.defence_v3.ctc import _block

    rows = [{"kind": "atk", "flagged": True, "carry": [True] * 4, "sem": [0.9] * 4, "s1": [0.9] * 4, "fg": ["ALLOW"] * 4},
            {"kind": "ben_unflagged", "flagged": False, "sem": [0.9] * 4, "s1": [0.9] * 4, "fg": ["ALLOW"] * 4}]
    b = _block(rows, {"score": "S1", "tau": 0.01})
    assert all(x["k"] == 0 for x in b["RCL"]["collateral_unflagged"])
    assert all(x["k"] == 0 for x in b["CTC"]["collateral_unflagged"])
    assert b["CTC"]["withheld_carrying"][3]["k"] == 1


def test_nli_entail_never_writes_another_programmes_cache(tmp_path, monkeypatch):
    """Regression: v5 RAC once overwrote defence_v3/ctc_nli_cache.json via nli_entail's implicit default path."""
    from phase17.defence_v3 import ctc

    target = tmp_path / "v3.json"
    target.write_text("{}")
    monkeypatch.setattr(ctc, "NLI_CACHE", target)

    class _M:
        def predict(self, pairs):
            import numpy as np
            return np.zeros((len(pairs), 3))
    monkeypatch.setattr("phase17.b13_live._nli", lambda: (_M(), 0))
    other = {}
    ctc.nli_entail([("a premise.", "a hypothesis")], other)              # no path -> must not touch v3's file
    assert target.read_text() == "{}"
    mine = tmp_path / "mine.json"
    ctc.nli_entail([("b premise.", "b hypothesis")], other, mine)
    assert mine.exists() and target.read_text() == "{}"
