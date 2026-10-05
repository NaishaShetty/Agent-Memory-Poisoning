"""Per-ATTACK-FAMILY results, including the seven founding families (round 6 gap fix).

THE GAP THIS CLOSES, and it was a reporting gap rather than a measurement one. Every detection
table in this project is organised by CORPUS -- `own_founding_regen`, `own_trackb_15`,
`extdev_minja` -- because that is how the populations were built and frozen. But the seven
founding families (AgentPoison, MINJA, MemoryGraft, FARMA, DSRM, MPBench-PCFI, sleeper) are the
project's original contribution and they are spread ACROSS those corpora: a reader looking for
"how well does the defense do on DSRM" could find it in the harm table and nowhere else.

The families were measured all along -- `attack_validity_audit.json` carries `by_family`,
`mechanism_validation.json` carries `by_mechanism`, and `eval_round6.json` persists per-item
decisions whose records know their own family -- so this joins them and reports, per family:

  * mechanism labelling (does the instance implement its own label),
  * working rate (does it subvert an undefended agent, causally),
  * detection by every configuration, on BOTH denominators,
  * undefended and defended harm where the harm study covers the family.

No model is run here; it is a join over existing artifacts.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

DATA = Path(__file__).parent / "data"
OUT = DATA / "family_breakdown.json"

# The seven founding families, in the order Phase 4 introduces them, then the mechanism families
# added later. Kept explicit so a founding family cannot silently vanish from a report again.
FOUNDING = ("agentpoison", "minja", "farma", "memorygraft", "dsrm", "mpbench",
            "sleeper_memory_poisoning")
MECHANISM = ("authority_impersonation", "conditional_backdoor", "preference_hijack",
             "policy_revocation", "exfiltration_instruction", "memory_worm")


def _L(n):
    p = DATA / n
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def run() -> dict:
    from phase17.eval_round6 import _attack_pops
    from phase17.stats import rate_with_ci
    from phase17.working_set import working_set

    r6, audit, mech, harm = _L("eval_round6.json"), _L("attack_validity_audit.json"), \
        _L("mechanism_validation.json"), _L("harm_study_v2.json")
    if not r6 or "raw" not in r6:
        raise SystemExit("eval_round6.json with raw per-item decisions is required")

    pops = _attack_pops()
    ws = working_set()
    alias = {"external_test_1258": ("exttest_gandalf", "exttest_deepset"),
             "external_dev_266": ("extdev_minja", "extdev_agentpoison", "extdev_injecagent",
                                  "extdev_bipia", "extdev_agentdojo"),
             "holdout2_mosscap_1200": ("holdout2_mosscap",)}
    working_ids = set()
    for p in pops:
        for a in alias.get(p, (p,)):
            working_ids |= ws.get(a, set())

    configs = list(r6["configs"])

    def derive(cfg: str, key: str, i: int) -> bool:
        if cfg == "B16":
            return bool(r6["raw"]["B15"][key][i][0])
        if cfg == "B17":
            return bool(r6["raw"]["B13"][key][i][0] or r6["raw"]["B14"][key][i][0])
        return bool(r6["raw"][cfg][key][i][0])

    # family -> list of (population, index, id)
    byfam: Dict[str, List[tuple]] = {}
    for pop, recs in pops.items():
        key = f"attack::{pop}"
        ids = r6["raw_ids"].get(key, [])
        for i, r in enumerate(recs):
            if i < len(ids):
                byfam.setdefault(r.family, []).append((key, i, r.scenario_id))

    af = audit.get("by_family", {})
    mf = mech.get("by_mechanism", {})
    hf = harm.get("by_family", {})

    rows = {}
    all_cfgs = configs + ["B16", "B17"]
    for fam, items in byfam.items():
        n = len(items)
        wk = [(k, i) for k, i, sid in items if sid in working_ids]
        e = {"n_instances": n, "n_working": len(wk),
             "working_rate": round(len(wk) / max(n, 1), 4),
             "is_founding": fam in FOUNDING,
             "audit_working": af.get(fam),
             "mechanism_correct": mf.get(fam),
             "corpora": sorted({k.split("::", 1)[1] for k, _i, _s in items})}
        for cfg in all_cfgs:
            try:
                full = [derive(cfg, k, i) for k, i, _s in items]
                work = [derive(cfg, k, i) for k, i in wk]
            except (KeyError, IndexError):
                continue
            e[cfg] = {"full": rate_with_ci(sum(full), len(full)),
                      "working": rate_with_ci(sum(work), len(work)) if work else None}
        if fam in hf:
            h = hf[fam]
            e["harm"] = {"task_alone": h["harm_no_poison"]["rate"],
                         "undefended": h["harm_no_defense"]["rate"],
                         "B12": h["harm_b12"]["rate"], "B13": h["harm_b13"]["rate"],
                         "n": h["n"]}
        rows[fam] = e

    missing = [f for f in FOUNDING if f not in rows]
    out = {"configs": all_cfgs, "founding_families": list(FOUNDING),
           "mechanism_families": list(MECHANISM),
           "founding_families_absent": missing,
           "note": "a join over existing artifacts; no model is run here. 'working' columns are "
                   "restricted to instances that causally subvert an undefended agent AND "
                   "implement their own labelled mechanism.",
           "families": rows}
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    cfgs = [c for c in ("B12", "B13", "B14", "B15", "B17") if c in next(iter(r["families"].values()))]
    for label, fams in (("THE SEVEN FOUNDING FAMILIES", r["founding_families"]),
                        ("MECHANISM FAMILIES", r["mechanism_families"])):
        print(f"\n### {label}")
        print(f"  {'family':26s} {'n':>4s} {'work':>6s} {'mech':>6s} " +
              " ".join(f"{c:>7s}" for c in cfgs) + "   (full / working)")
        for f in fams:
            v = r["families"].get(f)
            if not v:
                print(f"  {f:26s}  ABSENT")
                continue
            mech = v["mechanism_correct"]
            cells = " ".join(f"{v[c]['full']['rate']:6.0%} " for c in cfgs if c in v)
            print(f"  {f:26s} {v['n_instances']:4d} {v['working_rate']:5.0%} "
                  f"{(mech['rate'] if mech else 0):5.0%} {cells}")
            cellsw = " ".join(f"{v[c]['working']['rate']:6.0%} " if v[c].get('working') else "    -  "
                              for c in cfgs if c in v)
            print(f"  {'  (on working attacks)':26s} {v['n_working']:4d} {'':5s} {'':5s} {cellsw}")
    if r["founding_families_absent"]:
        print("\nFOUNDING FAMILIES WITH NO INSTANCES IN THE EVALUATION:",
              r["founding_families_absent"])
    print("DONE")
