"""DEV-ONLY calibration of B13's corroboration thresholds (external review round 4).

Everything here uses dev data only: LoCoMo conversations 1-4 (owner turns as evidence,
the dataset's own `observation` memories as the benign control, qwen-authored additive /
preference fabrications as attacks, `provenance_sets.py`) and the dev half of the AgentDojo
benign tool outputs. The thresholds it derives are frozen as constants in `b13_live.py`;
`test_review4_fixes.py` checks the constants match what this script persisted.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from phase17.stats import rate_with_ci

OUT = Path(__file__).parent / "data" / "b13_dev_calibration.json"
ADJ = Path(__file__).parent / "data" / "agentdojo_benign_tool_outputs.json"


def agentdojo_benign(split: str):
    return [i["text"] for i in json.loads(ADJ.read_text(encoding="utf-8"))["items"] if i["split"] == split]


def run() -> dict:
    from phase17.b13_live import is_personal_claim, support_scores
    from phase17.provenance_sets import DEV_SAMPLES, fabrications, observations, owner_turns, speakers

    fabs = fabrications("dev")
    obs_s, fab_rows, adj_rows = [], [], []
    adj = agentdojo_benign("dev")
    for s in DEV_SAMPLES:
        ev = [t["text"] for t in owner_turns(s)]
        names = speakers(s)
        obs = observations(s)
        obs_s += list(support_scores([o["text"] for o in obs], ev))
        fs = [f for f in fabs if f["sample"] == s]
        for f, sc in zip(fs, support_scores([f["text"] for f in fs], ev)):
            fab_rows.append({"kind": f["kind"], "support": float(sc), "personal": is_personal_claim(f["text"], names)})
        # AgentDojo tool outputs dropped into this conversation's store: are they treated as personal claims?
        pers = [t for t in adj if is_personal_claim(t, names)]
        sc = support_scores(pers, ev) if pers else []
        adj_rows.append({"sample": s, "n": len(adj), "personal": len(pers), "support": [float(x) for x in sc]})
    obs_sorted = np.sort(obs_s)
    thr = {"exclude@2%obs": float(obs_sorted[int(0.02 * len(obs_sorted))]),
           "flag@5%obs": float(obs_sorted[int(0.05 * len(obs_sorted))])}
    out = {"n_observations": len(obs_s), "thresholds": thr, "fabrications": {}, "agentdojo_dev": {}}
    for kind in ("additive", "preference"):
        k = [r for r in fab_rows if r["kind"] == kind]
        out["fabrications"][kind] = {
            "n": len(k), "personal_claim": sum(r["personal"] for r in k),
            "excluded": rate_with_ci(sum(r["personal"] and r["support"] < thr["exclude@2%obs"] for r in k), len(k)),
            "flagged_or_excluded": rate_with_ci(sum(r["personal"] and r["support"] < thr["flag@5%obs"] for r in k), len(k)),
        }
    n = sum(r["n"] for r in adj_rows)
    out["agentdojo_dev"] = {
        "n_placements": n, "personal_claim": sum(r["personal"] for r in adj_rows),
        "excluded": rate_with_ci(sum(sum(x < thr["exclude@2%obs"] for x in r["support"]) for r in adj_rows), n),
        "flagged_or_excluded": rate_with_ci(sum(sum(x < thr["flag@5%obs"] for x in r["support"]) for r in adj_rows), n),
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(json.dumps(run(), indent=1))
    print("DONE")
