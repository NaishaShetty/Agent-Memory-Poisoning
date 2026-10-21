"""W3 Gap-2 factual sub-test scoring (docs/phase17/v8/V8_PREREG_ADDENDUM_W3.md). Reuses
phase17.defence_v7.g2_v7's arms()/block()/accept() UNCHANGED (all pure functions of their
arguments, no HO10-specific state) against HO11's factual-only chains, via the same
module-attribute monkeypatch trick v7 itself uses to let the generic
phase17.defence_v6.g2_eval.rows() read a different chain source
(ho9_chains.PARTIAL/chains reassigned to ho11_chains's, exactly as g2_v7.rows() reassigns
them to ho10_chains's).

  python -m phase17.defence_v8.w3_scoring
"""
from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "defence_v8"
NLI8 = DATA / "v8_nli_cache.json"
OUT = DATA / "g2_eval_ho11.json"


def rows():
    from phase17.defence_v3.ctc import nli_entail
    from phase17.defence_v6 import g2_eval as G
    from phase17.defence_v6 import ho9_chains as C9
    from phase17.defence_v7.g2_dev import FLOOR, rar_s_factory, sents
    from phase17.defence_v8 import ho11_chains as C11
    from phase17.defence_v8 import ho11_corpus

    assert ho11_corpus.verify_frozen()
    C9.PARTIAL, C9.chains = C11.PARTIAL, C11.chains   # G.rows reads these at call time
    F = G.Feat()
    F.path = NLI8                                      # whole-root NLI entries go to v8's own cache
    F.nli = json.loads(NLI8.read_text(encoding="utf-8")) if NLI8.exists() else {}
    rs = G.rows(F)
    pairs = []
    for x in rs:
        for g in x["gens"] + x["rw"]:
            for d in sents(g):
                for r in sents(x["root"]):
                    pairs += [(d, r), (r, d)]
    F.embed([p for ab in pairs for p in ab])
    pairs = [(a, b) for a, b in pairs if F.sem(a, b) >= FLOOR]
    nli_entail(pairs, F.nli, path=NLI8)
    carry = rar_s_factory(F, F.nli)
    for x in rs:
        x["rs"] = [carry(g, x["root"]) for g in x["gens"]]
        x["rs_rw"] = [carry(g, x["root"]) for g in x["rw"]]
    NLI8.write_text(json.dumps(F.nli), encoding="utf-8")
    return rs, F


def evaluate() -> dict:
    from phase17.defence_v7.common import ROOT
    from phase17.defence_v7.g2_v7 import accept, arms, block

    tau_ctc = json.loads((ROOT / "phase17/data/defence_v3/ctc_selection.json").read_text(encoding="utf-8"))["chosen"]["tau"]
    rs, F = rows()
    A_arms = arms(tau_ctc)
    bl = block(rs, A_arms)   # every atk item is factual-payload by construction of HO11
    for cand in ("ND|RAR-S", "PRC"):
        bl[f"acceptance_{cand}"] = accept(bl, cand)
    out = {"preregistration": "docs/phase17/v8/V8_PREREG_ADDENDUM_W3.md", "tau_ctc_frozen": tau_ctc,
           "n_flagged_roots": bl["n_flagged_roots"], "factual": bl}
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = evaluate()
    print("n_flagged_roots:", r["n_flagged_roots"])
    for c in ("ND|RAR-S", "PRC"):
        print(c, json.dumps(r["factual"][f"acceptance_{c}"]))
