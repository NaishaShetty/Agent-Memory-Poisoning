"""v7 Gap 2 DEVELOPMENT exploration on HO9 (spent in v6; designated v7 development substrate before any v7 held-out
set exists). Nothing here is confirmatory. Output: data/defence_v7/g2_dev_explore.json.

Candidates explored (HFP-B thresholds tau_n = 0.2, tau_r = 0.9 are carried from v6 unchanged, not re-tuned):
  RAR-S   sentence-level claim fingerprint: the descendant carries the root if ANY (descendant sentence, root sentence)
          pair with sem >= 0.30 has NLI(d_s -> r_s) >= tau_n or NLI(r_s -> d_s) >= tau_r (or exact match)
  ND, PRC, RCL, CTC, FG   v6 arms (frozen)
  unions and payload routing of the above
"""
from __future__ import annotations

from phase17.defence_v7 import atomic  # noqa: F401  (crash-safe checkpoints: atomic file writes)

import json
import re
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "defence_v7"
NLI7 = DATA / "v7_nli_cache.json"
OUT = DATA / "g2_dev_explore.json"
_SENT = re.compile(r"(?<=[.!?])\s+")
TAU_N, TAU_R, FLOOR = 0.2, 0.9, 0.30


def sents(t: str):
    return [s.strip() for s in _SENT.split(t or "") if len(s.strip()) > 3] or [t]


def sentence_pairs(rs):
    return [(d, r) for x in rs for g in x["gens"] for d in sents(g) for r in sents(x["root"])]


def rar_s_factory(F, nli):
    def carry(desc: str, root: str) -> bool:
        from phase17.defence_v6.fpb import exact
        if exact(desc, root):
            return True
        for d in sents(desc):
            for r in sents(root):
                if F.sem(d, r) < FLOOR:
                    continue
                if nli[f"{d}||{r}"] >= TAU_N or nli[f"{r}||{d}"] >= TAU_R:
                    return True
        return False
    return carry


def main():
    from phase17.defence_v3.ctc import nli_entail, _withhold
    from phase17.defence_v6 import g2_eval as G
    from phase17.stats import rate_with_ci

    tau_ctc = json.loads((Path(__file__).resolve().parents[1] / "data" / "defence_v3" / "ctc_selection.json")
                         .read_text(encoding="utf-8"))["chosen"]["tau"]
    F = G.Feat()
    rs = G.rows(F)                      # HO9 rows; v6 NLI cache is READ only (F.save() is never called here)
    nli = json.loads(NLI7.read_text(encoding="utf-8")) if NLI7.exists() else {}
    pairs = []
    for x in rs:
        for g in x["gens"]:
            for d in sents(g):
                for r in sents(x["root"]):
                    pairs += [(d, r), (r, d)]
    F.embed([p for ab in pairs for p in ab])
    pairs = [(a, b) for a, b in pairs if F.sem(a, b) >= FLOOR]
    nli_entail(pairs, nli, path=NLI7)
    carry_s = rar_s_factory(F, nli)
    for x in rs:
        x["rs"] = [carry_s(g, x["root"]) for g in x["gens"]]
    rcl = lambda r, k: r["flagged"] and r["sem"][k] >= 0.5  # noqa: E731
    ctc = lambda r, k: r["flagged"] and _withhold("S1", r["sem"][k], r["s1"][k], tau_ctc)  # noqa: E731
    nd = lambda r, k: r["nd"][k] in G.WITHHOLD  # noqa: E731
    rars = lambda r, k: r["flagged"] and r["rs"][k]  # noqa: E731
    arms = {
        "FG": lambda r, k: r["fg"][k] in G.WITHHOLD, "ND": nd, "RCL": rcl, "CTC": ctc,
        "PRC": lambda r, k: ctc(r, k) if r["route_instr"] else rcl(r, k),
        "RAR-B": lambda r, k: r["flagged"] and G._hfp_row(r, k, ("B", TAU_N, TAU_R)),
        "RAR-S": rars,
        "ND|RAR-S": lambda r, k: nd(r, k) or rars(r, k),
        "RCL|RAR-S": lambda r, k: rcl(r, k) or rars(r, k),
        "ND|RCL": lambda r, k: nd(r, k) or rcl(r, k),
        "PRC-S (instr: ND|RAR-S; fact: RCL)": lambda r, k: (nd(r, k) or rars(r, k)) if r["route_instr"] else rcl(r, k),
        "PRC|RAR-S": lambda r, k: (ctc(r, k) if r["route_instr"] else rcl(r, k)) or rars(r, k),
    }
    out = {"substrate": "HO9 (v6 held-out, spent) as v7 DEVELOPMENT", "tau_n": TAU_N, "tau_r": TAU_R, "by_payload": {}}
    for pay in ("instruction", "factual"):
        A = [r for r in rs if r["kind"] == "atk" and r["flagged"] and r["payload"] == pay]
        BU = [r for r in rs if r["kind"] == "ben_unflagged"]
        res = {}
        for a, f in arms.items():
            res[a] = {"gen4_withheld_carrying": rate_with_ci(sum(f(r, 3) for r in A if r["carry"][3]), sum(r["carry"][3] for r in A)),
                      "noncarrying_withheld_pooled": rate_with_ci(sum(f(r, k) for r in A for k in range(4) if not r["carry"][k]),
                                                                  sum(not r["carry"][k] for r in A for k in range(4))),
                      "unflagged_collateral_max": max((sum(f(r, k) for r in BU) / len(BU)) for k in range(4)),
                      "gen4_influence_left": sum(r["influence"][3] and not f(r, 3) for r in A),
                      "claim_detect_on_judge_carrying_g4": sum(r["rs"][3] for r in A if r["carry"][3]) if a == "RAR-S" else None}
        out["by_payload"][pay] = res
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    for pay, res in out["by_payload"].items():
        for a, v in res.items():
            g = v["gen4_withheld_carrying"]
            n = v["noncarrying_withheld_pooled"]
            print(f"{pay:11s} {a:36s} g4 {g['k']}/{g['n']} ({100*(g['rate'] or 0):.1f}%)  noncarry {100*(n['rate'] or 0):.1f}%  "
                  f"coll {100*v['unflagged_collateral_max']:.1f}%  infl_left {v['gen4_influence_left']}")


if __name__ == "__main__":
    main()
