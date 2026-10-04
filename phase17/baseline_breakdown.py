"""Per-population comparison against the published baselines (round 6, the #3 item).

THE CLAIM THIS ANSWERS. Aggregated over everything, an off-the-shelf
`deberta-v3-base-prompt-injection-v2` forward pass lands close to this project's configs, and
the honest reading of that was: if a single public classifier nearly matches a bespoke stacked
defense, the bespoke defense is not earning its complexity.

But the aggregate is dominated by the two external prompt-injection corpora (1,258 + 266
items vs 340 own attacks), and those are the home turf of a prompt-injection classifier --
deberta was trained on exactly that distribution. The aggregate therefore mostly measures
"does a prompt-injection detector detect prompt injections", which is not the question this
benchmark asks. Memory poisoning that looks like an ordinary personal note -- a fabricated
preference, an invented standing policy, an additive false claim -- carries none of the
injection surface deberta keys on.

So: per population, both at deberta's dev-calibrated threshold and at its oracle threshold
matched to B12's FPR, never aggregated. Where the two disagree, the comparison is a
composition effect, not a capability one -- and the direction of that disagreement is the
finding, whichever way it points.

This module only re-reads `eval_round5.json`; it runs no models and invents no numbers.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

SRC = Path(__file__).parent / "data" / "eval_round5.json"
OUT = Path(__file__).parent / "data" / "baseline_breakdown.json"
OWN = "own_"
EXTERNAL = ("extdev_", "exttest_")


def _rate(cell) -> Dict:
    v = cell["excluded"] if isinstance(cell, dict) and "excluded" in cell else cell
    return {"k": v["k"], "n": v["n"], "rate": v["rate"]}


def run(ours: str = "B13", baseline: str = "deberta_pi_v2") -> dict:
    d = json.loads(SRC.read_text(encoding="utf-8"))
    ap = d["attack_populations"]
    rows: List[dict] = []
    for pop, cfgs in ap.items():
        if ours not in cfgs or f"{baseline}@dev" not in cfgs:
            continue
        o, b_dev = _rate(cfgs[ours]), _rate(cfgs[f"{baseline}@dev"])
        b_or = _rate(cfgs.get(f"{baseline}@oracle", cfgs[f"{baseline}@dev"]))
        rows.append({"population": pop, "n": o["n"],
                     "group": "own" if pop.startswith(OWN) else "external",
                     ours: o["rate"], f"{baseline}@dev": b_dev["rate"],
                     f"{baseline}@oracle": b_or["rate"],
                     "delta_vs_dev": round(o["rate"] - b_dev["rate"], 4),
                     "delta_vs_oracle": round(o["rate"] - b_or["rate"], 4)})

    def agg(group=None):
        rs = [r for r in rows if group is None or r["group"] == group]
        n = sum(r["n"] for r in rs)
        if not n:
            return None
        w = lambda key: round(sum(r[key] * r["n"] for r in rs) / n, 4)
        return {"n": n, "n_populations": len(rs), ours: w(ours),
                f"{baseline}@dev": w(f"{baseline}@dev"), f"{baseline}@oracle": w(f"{baseline}@oracle"),
                "delta_vs_dev": round(w(ours) - w(f"{baseline}@dev"), 4),
                "delta_vs_oracle": round(w(ours) - w(f"{baseline}@oracle"), 4)}

    out = {"source": SRC.name, "ours": ours, "baseline": baseline,
           "by_population": sorted(rows, key=lambda r: (r["group"], -r["n"])),
           "aggregate_all": agg(), "aggregate_own_attacks": agg("own"),
           "aggregate_external": agg("external"),
           "why_not_to_cite_the_aggregate": (
               "The all-populations aggregate is dominated by the external prompt-injection "
               "corpora, which are the baseline's training distribution. Memory poisoning that "
               "reads as an ordinary personal note carries no injection surface, so the split "
               "below is the comparison that answers this benchmark's question."),
           "note": "re-read from eval_round5.json; no models run here"}
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    import sys

    ours = sys.argv[1] if len(sys.argv) > 1 else "B13"
    base = sys.argv[2] if len(sys.argv) > 2 else "deberta_pi_v2"
    r = run(ours, base)
    hdr = f"{'population':34s} {'n':>5s} {ours:>7s} {'deb@dev':>8s} {'deb@orc':>8s} {'delta':>7s}"
    for grp in ("own", "external"):
        print(f"\n### {grp} attacks\n{hdr}")
        for row in r["by_population"]:
            if row["group"] != grp:
                continue
            print(f"  {row['population']:32s} {row['n']:5d} {row[ours]:6.1%} "
                  f"{row[f'{base}@dev']:7.1%} {row[f'{base}@oracle']:7.1%} "
                  f"{row['delta_vs_dev']:+6.1%}")
    for k in ("aggregate_own_attacks", "aggregate_external", "aggregate_all"):
        a = r[k]
        if a:
            print(f"\n{k:24s} n={a['n']:5d}  {ours} {a[ours]:.1%}  "
                  f"deberta@dev {a[f'{base}@dev']:.1%}  delta {a['delta_vs_dev']:+.1%}")
    print("DONE")
