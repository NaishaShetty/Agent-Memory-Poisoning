"""WS-D: integration and ablation, composed from the workstream outputs (no new model calls except timing).
Pre-registered: docs/phase17/PREREGISTRATION_DEFENCE_V2_2026-10-13.md (WS-D).

D0 baseline (B13 on the text in front of it; frozen guard FG; no sleeper signal); D1 +SAG; D2 +RCL; D3 +WS-C signal
(the dev-selected B13&INTENT_v2, applied to stored text and through SAG); D4 all. Admission sets: MEM-1, MEM-2,
SA-3-eval (vs ungrounded and grounded benign). Propagation: HO4 chains (RCL vs FG). Overhead: wall-clock per memory.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict

DATA = Path(__file__).resolve().parents[1] / "data" / "defence_v2"
OUT = DATA / "integration.json"


def _f(d):
    return f"{d['k']}/{d['n']}"


def admission() -> Dict:
    sag = json.loads((DATA / "sag_eval.json").read_text(encoding="utf-8"))["sets"]
    sl = json.loads((DATA / "sleeper_v2_eval.json").read_text(encoding="utf-8"))
    ch = sl["chosen"]
    out = {}
    for name, key in (("MEM-1 (HO4)", "MEM1_document"), ("MEM-2 (SA-1)", "MEM2_document"),
                      ("SA-3 eval vs ungrounded benign", "SA3eval_document_vs_ben_unground"),
                      ("SA-3 eval vs grounded benign", "SA3eval_document_vs_ben_ground")):
        s = sag[key]["B13"]
        row = {"D0 B13 stored": {"atk": _f(s["atk"]["lost"]), "ben": _f(s["ben"]["lost"])},
               "D1 +SAG": {"atk": _f(s["atk"]["intact"]), "ben": _f(s["ben"]["intact"])},
               "D1 +SAG, wrong lineage": {"atk": _f(s["atk"]["wrong"]), "ben": _f(s["ben"]["wrong"])}}
        if "outcome_undefended" in s["atk"]:
            row["outcome_undefended"] = _f(s["atk"]["outcome_undefended"])
            row["outcome_remaining_D0"] = _f(s["atk"]["outcome_remaining_lost"])
            row["outcome_remaining_D1"] = _f(s["atk"]["outcome_remaining_intact"])
        if key.startswith("SA3"):
            bk = "ben_unground" if key.endswith("unground") else "ben_ground"
            tr = sl["eval_transformed"]
            row["D3 +WS-C signal (stored)"] = {"atk": tr["stored_any"][ch]["atk"], "ben": tr["stored_any"][ch][bk]}
            row["D4 SAG + WS-C signal"] = {"atk": tr["SAG"][ch]["atk"], "ben": tr["SAG"][ch][bk]}
            row["note"] = ("D3/D4 replace B13 by the selected WS-C policy (a conjunction with B13), so they are subsets "
                           "of D0/D1, not additions")
        out[name] = row
    return out


def propagation() -> Dict:
    p = json.loads((DATA / "prop_eval.json").read_text(encoding="utf-8"))
    d = json.loads((DATA / "prop_dev.json").read_text(encoding="utf-8"))["summary"]
    g = lambda arm, blk="withheld_carrying_flagged", src=p: [_f(x) for x in src[blk][arm]]  # noqa: E731
    return {"HO4 held-out": {"D0 FG": g("FG"), "D2 RCL": g("RCL"), "RECHECK": g("RECHECK"), "RCL|RECHECK": g("RCL|RECHECK"),
                             "influence_remaining": {a: g(a, "influence_remaining") for a in ("A0", "FG", "RCL")},
                             "collateral_unflagged": {a: g(a, "collateral_unflagged_benign") for a in ("FG", "RCL", "RECHECK")},
                             "collateral_flagged_benign": {a: g(a, "collateral_flagged_benign") for a in ("FG", "RCL")}},
            "dev (diagnostic)": {"D0 FG": g("FG", src=d), "D2 RCL": g("RCL", src=d),
                                 "benign_collateral_flagged_roots": {a: [_f(x) for x in d["benign_collateral_flagged_roots"][a]]
                                                                     for a in ("FG", "RCL")}}}


def overhead(n: int = 20) -> Dict:
    """Wall-clock per memory (warm models, this machine; Ollama judges on GPU, Python on CPU)."""
    from phase17 import harm_study_v2 as H
    from phase17.b13_live import support_scores
    from phase17.defence_v2 import sa3_corpus as C
    from phase17.defence_v2.propagation_multigen import _sem
    from phase17.defence_v2.sleeper_v2 import _intent
    from phase17.provenance_sets import owner_turns

    xs = [x["note"] + " (timing)" for x in C.items(split="eval")[:n]]
    ev = [t["text"] for t in owner_turns(5)]
    support_scores(xs[:2], ev)
    t0 = time.time()
    support_scores(xs, ev)
    t_corr = (time.time() - t0) / n
    cache: Dict = {}
    _intent(xs[:1], cache)
    t0 = time.time()
    _intent(xs[1:], cache)
    t_int = (time.time() - t0) / (n - 1) / 2            # two prompt variants per text
    ret = _sem(H._retriever())
    ret(xs[0], xs[1])
    t0 = time.time()
    for i in range(n - 1):
        ret(xs[i], xs[i + 1] + " root")
    t_rcl = (time.time() - t0) / (n - 1)
    return {"corroboration_NLI_seconds_per_memory": round(t_corr, 3), "INTENT_judge_seconds_per_memory": round(t_int, 3),
            "RCL_seconds_per_descendant_per_root": round(t_rcl, 4), "SAG": "one lineage lookup (O(1)); no model call",
            "n_timed": n, "note": "single machine, warm caches excluded by appending '(timing)'; indicative only"}


def run() -> Dict:
    out = {"preregistration": "docs/phase17/PREREGISTRATION_DEFENCE_V2_2026-10-13.md (WS-D)",
           "admission": admission(), "propagation": propagation(), "overhead": overhead()}
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(json.dumps(run(), indent=1))
