"""EXPLORATORY, post-hoc: would the rejection ledger have blocked the adaptive evasions of round 7?

adaptive_round7 found an attacker told WHY its note was rejected evades corroboration (B13 with
evidence) on 22 of 48 seeds -- above the 24.6% stateless reference. The successful rewrites are light
paraphrases, which is what the ledger exists to catch. This measures, for every successful evasion,
the highest cosine (the ledger's own frozen encoder) between the winning rewrite and the attempts
already rejected in the same loop, and counts how many fall inside each radius.

Read as an UPPER BOUND on the ledger's benefit, not a measured composition: a blocked attacker
would have kept rewriting within its budget, and may have found a rewrite outside the radius. No
model is called; nothing here was fitted or tuned. Dev data only.
"""
from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).parent / "data"
OUT = DATA / "adaptive_ledger_exploratory.json"
RADII = (0.97, 0.95, 0.90)


def run() -> dict:
    import numpy as np

    from phase17.rejection_memory import _embed

    d = json.loads((DATA / "adaptive_round7.json").read_text(encoding="utf-8"))
    out = {"status": "EXPLORATORY (post-hoc, dev, upper bound)", "frozen_radius": 0.97,
           "recommended_radius": 0.95, "arms": {}}
    for arm in ("vs_corroboration", "vs_neutralisation"):
        rows = [r for r in d[arm]["rows"] if r["success"] and r.get("genuine_adaptive_evasion")]
        sims, truncated = [], 0
        for r in rows:
            h = r["history"]
            rejected = [x["text"] for x in h if not x["got_through"]]
            final = [x["text"] for x in h if x["got_through"]][-1]
            # adaptive_round7 stored each attempt's first 300 characters; flagged, not hidden.
            truncated += any(len(x["text"]) >= 300 for x in h)
            e = _embed(rejected + [final])
            e = e / np.linalg.norm(e, axis=1, keepdims=True)
            sims.append(float(max(e[:-1] @ e[-1])))
        n_seeds = d[arm]["n_seeds"]
        out["arms"][arm] = {
            "n_seeds": n_seeds, "evasions": len(rows), "truncated_histories": truncated,
            "max_sim_to_rejected": [round(s, 4) for s in sims],
            "by_radius": {str(t): {"would_block": int(sum(s >= t for s in sims)),
                                   "residual_evasion_upper_bound": f"{len(rows) - int(sum(s >= t for s in sims))}/{n_seeds}"}
                          for t in RADII}}
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    for arm, a in r["arms"].items():
        print(arm, a["evasions"], "evasions;", {t: v["would_block"] for t, v in a["by_radius"].items()})
