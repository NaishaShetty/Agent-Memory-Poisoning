"""Targeted phase, statistical validity audit: re-derive every reported p-value of the gap-closure / remediation
families from the counts or vectors stored in the artifacts, with an independent implementation (scipy), and
check the Holm adjustment. No model calls. Output: data/remediation/stats_audit.json.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

DATA = Path(__file__).resolve().parents[1] / "data"
OUT = DATA / "remediation" / "stats_audit.json"


def _mcnemar(b: int, c: int) -> float:
    from scipy.stats import binomtest

    return 1.0 if b + c == 0 else float(binomtest(min(b, c), b + c, 0.5, alternative="two-sided").pvalue)


def _fisher(k1: int, n1: int, k2: int, n2: int, alternative: str = "two-sided") -> float:
    from scipy.stats import fisher_exact

    return float(fisher_exact([[k1, n1 - k1], [k2, n2 - k2]], alternative=alternative)[1])


def _holm(ps: List[float]) -> List[float]:
    m = len(ps)
    order = sorted(range(m), key=lambda i: ps[i])
    adj, run = [0.0] * m, 0.0
    for r, i in enumerate(order):
        run = max(run, min(1.0, (m - r) * ps[i]))
        adj[i] = run
    return adj


def _close(a: float, b: float) -> bool:
    return a == b or abs(a - b) / max(abs(a), abs(b)) < 0.02


def run() -> Dict:
    mem = json.loads((DATA / "remediation" / "mem0_pipeline_eval.json").read_text(encoding="utf-8"))
    sa2 = json.loads((DATA / "remediation" / "sa2_eval.json").read_text(encoding="utf-8"))
    checks = []

    def add(name, test, reported, recomputed, unit, note="", two_sided=None):
        checks.append({"claim": name, "test": test, "reported_p": reported, "recomputed_p": recomputed,
                       "match": _close(reported, recomputed), "unit_of_inference": unit, "note": note,
                       "two_sided_p": two_sided})

    for p in mem["predictions"]:
        if p["p"] is None:
            continue
        ev = p["evidence"]
        if ev.startswith("+"):
            b, c = ev.split(" ")[0][1:].split("/-")
            add(p["id"], "exact McNemar (paired, same items)", p["p"], _mcnemar(int(b), int(c)),
                "items of one owner's corpus (HO4 owner 7 / SA-1 owner 3)")
        elif " vs " in ev:
            a, b = ev.split(" vs ")
            k1, n1 = map(int, a.split("/"))
            k2, n2 = map(int, b.split("/"))
            add(p["id"], "Fisher exact, ONE-SIDED (greater), two independent groups", p["p"],
                _fisher(k1, n1, k2, n2, "greater"), "notes of one owner's corpus",
                "directional prediction; the paper printed it as 'Fisher p' without the sidedness",
                _fisher(k1, n1, k2, n2))
    for p in sa2.get("predictions", []):
        if p.get("p") is None:
            continue
        ev = str(p["evidence"])
        if ev.startswith("+") and "/-" in ev:
            b, c = ev.split(" ")[0][1:].split("/-")
            add(p["id"], "exact McNemar", p["p"], _mcnemar(int(b), int(c)), "notes of one owner (owner 9)")
        elif " vs " in ev:
            a, b = ev.split(" vs ")[:2]
            k1, n1 = map(int, a.split()[-1].split("/"))
            k2, n2 = map(int, b.split()[0].split("/"))
            add(p["id"], "Fisher exact, ONE-SIDED (greater)", p["p"], _fisher(k1, n1, k2, n2, "greater"),
                "notes of one owner (owner 9)", "directional prediction; printed without the sidedness",
                _fisher(k1, n1, k2, n2))
    # Holm over the gap-closure family as reported (\GapHolm)
    fam = {c["claim"]: c["recomputed_p"] for c in checks if c["claim"] in ("M1-2", "M1-6", "M2-2", "M2-4", "S2-3", "S2-4b")}
    holm = dict(zip(fam, _holm(list(fam.values()))))
    out = {"checks": checks, "all_match": all(c["match"] for c in checks), "holm_gapclosure_recomputed": holm,
           "family_size": len(fam)}
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    for c in r["checks"]:
        print(f"{c['claim']:6s} {c['test'][:34]:34s} reported {c['reported_p']:.3g} recomputed {c['recomputed_p']:.3g} match={c['match']}")
    print("holm", {k: f"{v:.2g}" for k, v in r["holm_gapclosure_recomputed"].items()})
