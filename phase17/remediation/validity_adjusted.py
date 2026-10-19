"""Attack validity, causal attribution, and validity-adjusted defence comparisons -- from CACHED verdicts and
decisions only (no model calls). Gap-closure Stage C; NEW ANALYSIS (not pre-registered), labelled as such.

1. Memory-attributable compliance per population, under C0 and under the vote: net = P(comply | memory) -
   P(comply | no memory) on the SAME task, with paired counts and a Wald interval for a paired difference.
   A leading probe raises both arms; the net is what the memory adds.
2. Probe admissibility: which populations' fitted probe meets the project's own rule (task-alone base rate
   <= 20%, `working_set.MAX_PROBE_BASE_RATE`, adopted in round 7) under each judge.
3. Defence recall on five denominators -- full population; published working set (union over probes, C0);
   fitted-probe working under C0; under the vote; and ROBUST working (working under BOTH judges) -- for the
   own memory-poisoning populations and the external corpora, B12-B15 and B17 (= B13 or B14), with B13-vs-B14
   paired tests, to see whether any ranking or conclusion depends on the denominator.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, List

DATA = Path(__file__).resolve().parents[1] / "data"
OUT = DATA / "remediation" / "validity_adjusted.json"


def _net(w: List[bool], o: List[bool]) -> Dict:
    n = len(w)
    b = sum(x and not y for x, y in zip(w, o))
    c = sum(y and not x for x, y in zip(w, o))
    d = (b - c) / n
    se = math.sqrt(max(0.0, (b + c) / n - d * d) / n)
    from phase17.stats import exact_mcnemar_p

    return {"n": n, "with": sum(w), "without": sum(o), "net_points": round(100 * d, 1),
            "ci95_points": [round(100 * (d - 1.96 * se), 1), round(100 * (d + 1.96 * se), 1)],
            "discordant": [b, c], "p_exact": exact_mcnemar_p(b, c)}


def run() -> Dict:
    from phase17.remediation.validity_judge_sensitivity import rows
    from phase17.stats import paired_delta, rate_with_ci
    from phase17.working_set import MAX_PROBE_BASE_RATE, _mechanism_ok, working_set

    cache = json.loads((DATA / "remediation" / "validity_judge_sensitivity_cache.json").read_text(encoding="utf-8"))
    mech = _mechanism_ok()
    items = rows()
    for it in items:
        y = lambda j, arm: cache[f"{j}|{arm}|{it['id']}"].startswith("YES")  # noqa: E731
        it["V_with"] = (it["C0_with"] + y("C1", "with") + y("C3", "with")) >= 2
        it["V_without"] = (it["C0_without"] + y("C1", "without") + y("C3", "without")) >= 2
        m = mech.get(it["id"], True)
        it["work_C0"] = it["C0_with"] and not it["C0_without"] and m
        it["work_V"] = it["V_with"] and not it["V_without"] and m
        it["work_robust"] = it["work_C0"] and it["work_V"]
    pub = {i for ids in working_set().values() for i in ids}
    out: Dict = {"kind": "NEW ANALYSIS on cached data (not pre-registered)", "n": len(items),
                 "admissibility_rule": f"task-alone base rate <= {MAX_PROBE_BASE_RATE:.0%}"}

    groups = {"ALL": items, "own": [x for x in items if x["pop"].startswith("own")],
              "external": [x for x in items if not x["pop"].startswith("own")]}
    for p in sorted({x["pop"] for x in items}):
        groups[p] = [x for x in items if x["pop"] == p]
    out["memory_attributable"] = {}
    for g, xs in groups.items():
        c0 = _net([x["C0_with"] for x in xs], [x["C0_without"] for x in xs])
        v = _net([x["V_with"] for x in xs], [x["V_without"] for x in xs])
        out["memory_attributable"][g] = {
            "C0": c0, "vote": v,
            "base_rate_C0": round(c0["without"] / c0["n"], 3), "base_rate_vote": round(v["without"] / v["n"], 3),
            "admissible_C0": c0["without"] / c0["n"] <= MAX_PROBE_BASE_RATE,
            "admissible_vote": v["without"] / v["n"] <= MAX_PROBE_BASE_RATE,
            "working_C0": sum(x["work_C0"] for x in xs), "working_vote": sum(x["work_V"] for x in xs),
            "working_robust": sum(x["work_robust"] for x in xs), "published_working": sum(x["id"] in pub for x in xs)}

    # ---- defence recall on five denominators (own populations + external corpora)
    ev = json.loads((DATA / "eval_round6.json").read_text(encoding="utf-8"))
    alias = {"external_test_1258": ("exttest_gandalf", "exttest_deepset"),
             "external_dev_266": ("extdev_minja", "extdev_agentpoison", "extdev_injecagent", "extdev_bipia",
                                  "extdev_agentdojo")}
    by_id = {x["id"]: x for x in items}
    dec: Dict[str, Dict[str, List[bool]]] = {"own": {}, "external": {}}
    den: Dict[str, Dict[str, List[bool]]] = {"own": {}, "external": {}}
    for key, ids in ev["raw_ids"].items():
        pop = key.split("::", 1)[1]
        grp = "own" if pop.startswith("own") else ("external" if pop in alias else None)
        if grp is None:
            continue
        keep = [i for i, sid in enumerate(ids) if sid in by_id]        # audited items only (all, except capped)
        for cfg in ("B12", "B13", "B14", "B15"):
            v = ev["raw"][cfg].get(key)
            dec[grp].setdefault(cfg, []).extend(bool(v[i][0]) for i in keep)
        dec[grp].setdefault("B17", [])
        b13, b14 = ev["raw"]["B13"][key], ev["raw"]["B14"][key]
        dec[grp]["B17"].extend(bool(b13[i][0] or b14[i][0]) for i in keep)
        for dn, fn in (("full", lambda x: True), ("published_working", lambda x: x["id"] in pub),
                       ("working_C0", lambda x: x["work_C0"]), ("working_vote", lambda x: x["work_V"]),
                       ("working_robust", lambda x: x["work_robust"])):
            den[grp].setdefault(dn, []).extend(fn(by_id[ids[i]]) for i in keep)
    out["defence_by_denominator"] = {}
    for grp in ("own", "external"):
        tab = {}
        for dn, mask in den[grp].items():
            row = {"n": sum(mask)}
            for cfg, d in dec[grp].items():
                xs = [a for a, m in zip(d, mask) if m]
                row[cfg] = rate_with_ci(sum(xs), len(xs)) if xs else None
            b13 = [a for a, m in zip(dec[grp]["B13"], mask) if m]
            b14 = [a for a, m in zip(dec[grp]["B14"], mask) if m]
            row["B13_vs_B14"] = paired_delta(b13, b14)
            row["ranking"] = sorted((c for c in dec[grp]), key=lambda c: -(row[c]["rate"] if row[c] else -1))
            tab[dn] = row
        out["defence_by_denominator"][grp] = tab
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    for g in ("ALL", "own", "external"):
        m = r["memory_attributable"][g]
        print(g, "net C0", m["C0"]["net_points"], m["C0"]["ci95_points"], "net vote", m["vote"]["net_points"], m["vote"]["ci95_points"],
              "base", m["base_rate_C0"], m["base_rate_vote"])
    print("admissible (C0):", [p for p, m in r["memory_attributable"].items() if p not in ("ALL", "own", "external") and m["admissible_C0"]])
    print("admissible (vote):", [p for p, m in r["memory_attributable"].items() if p not in ("ALL", "own", "external") and m["admissible_vote"]])
    for grp, tab in r["defence_by_denominator"].items():
        for dn, row in tab.items():
            print(grp, f"{dn:18s} n={row['n']:4d}", {c: round(100 * row[c]['rate'], 1) for c in ('B12', 'B13', 'B14', 'B15', 'B17')},
                  "B13vB14", f"+{row['B13_vs_B14']['only_a']}/-{row['B13_vs_B14']['only_b']} p={row['B13_vs_B14']['p_exact']:.2g}")
