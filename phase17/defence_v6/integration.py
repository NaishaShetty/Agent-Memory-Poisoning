"""v6 Phase 5: integration and ablation (pre-registered §5). Computed from the per-item decisions saved by g1_eval
(g1_items.json) and g3_eval (g3_items.json) on SA-6 eval single notes, and from g2_eval on HO9. No new model calls.

Arms (memory policy -> behaviour on the trigger message):
  BASE      exclude if B12 or B13 on the stored text, else the undefended stored answer
  PCL       exclude if PCL (Gap-1 candidate), else stored
  TS        two-stage sleeper defence (no exclusion)
  COMBINED  exclude if PCL, else TS
Ablations of COMBINED: native metadata instead of the ledger (after the forced UPDATE); item-level instead of claim-level;
B13 instead of PAB13 (= VPL_v3); stored-text frame (F2s) instead of the Stage-2 restore.
An excluded memory's behaviour is the clean-store answer. Propagation (HO9) is a separate substrate and is reported
from g2_eval at the policy level.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

DATA = Path(__file__).resolve().parents[1] / "data" / "defence_v6"
OUT = DATA / "integration_eval.json"
UNG = ("ben_unground", "ben_future", "ben_unusual")


def _policy(excl, frame_slot):
    def f(g1, g3):
        if excl(g1):
            return {"excluded": True, **g3["clean"], "unconfirmed": False}
        return {"excluded": False, **g3[frame_slot]}
    return f


def evaluate() -> Dict:
    from phase17.stats import paired_delta, rate_with_ci

    g1 = json.loads((DATA / "g1_items.json").read_text(encoding="utf-8"))
    g3 = json.loads((DATA / "g3_items.json").read_text(encoding="utf-8"))
    ids = [i for i in g3 if i in g1]
    arms = {
        "BASE": _policy(lambda a: a["B12s"] or a["B13s"], "stored"),
        "PCL": _policy(lambda a: a["PCL"], "stored"),
        "TS": _policy(lambda a: False, "TS"),
        "COMBINED": _policy(lambda a: a["PCL"], "TS"),
        "ABL_native_metadata": None,
        "ABL_item_level": _policy(lambda a: a["ITEM"], "TS"),
        "ABL_B13_not_PAB13": _policy(lambda a: a["VPL_v3"], "TS"),
        "ABL_frame_on_stored": _policy(lambda a: a["PCL"], "F2s"),
    }

    def native(a, b):
        # after the forced UPDATE, Mem0's native metadata says 'user' for attack memories: no exclusion by provenance,
        # and Stage 2 does not apply (no recorded document source)
        relabelled = bool(a["forced_native_src_after"]) and all(s == "user" for s in a["forced_native_src_after"])
        if a["PCL_if_native_metadata"]:
            return {"excluded": True, **b["clean"], "unconfirmed": False}
        return {"excluded": False, **(b["stored"] if relabelled else b["TS"])}
    arms["ABL_native_metadata"] = lambda a, b: native(a, b)
    res = {}
    per = {name: {i: f(g1[i], g3[i]) for i in ids} for name, f in arms.items()}
    for name in arms:
        r = {}
        for grp, sel in (("atk_implicit", lambda k: k == "atk_implicit"), ("atk_explicit", lambda k: k == "atk_explicit"),
                         ("ungrounded_legit", lambda k: k in UNG), ("grounded_legit", lambda k: k == "ben_ground")):
            xs = [i for i in ids if sel(g3[i]["kind"])]
            r[grp] = {"unconfirmed_activation": rate_with_ci(sum(per[name][i]["unconfirmed"] for i in xs), len(xs)),
                      "excluded": rate_with_ci(sum(per[name][i]["excluded"] for i in xs), len(xs)),
                      "surfaced": rate_with_ci(sum(per[name][i]["surfaced"] for i in xs), len(xs)),
                      "asked(deferral)": rate_with_ci(sum(per[name][i]["ask"] for i in xs), len(xs))}
        leg = [i for i in ids if g3[i]["kind"].startswith("ben")]
        r["memory_availability_legit"] = rate_with_ci(sum(not per[name][i]["excluded"] for i in leg), len(leg))
        r["legit_by_channel_surfaced"] = {ch: rate_with_ci(sum(per[name][i]["surfaced"] for i in leg if g3[i]["channel"] == ch),
                                                           sum(g3[i]["channel"] == ch for i in leg))
                                          for ch in ("user", "document", "missing")}
        res[name] = r
    tests = {}
    for grp in ("atk_implicit", "atk_explicit"):
        xs = [i for i in ids if g3[i]["kind"] == grp]
        for a, b in (("COMBINED", "BASE"), ("COMBINED", "PCL"), ("COMBINED", "TS"), ("ABL_native_metadata", "COMBINED"),
                     ("ABL_frame_on_stored", "COMBINED"), ("ABL_item_level", "COMBINED"), ("ABL_B13_not_PAB13", "COMBINED")):
            tests[f"{grp}: {a} vs {b} (unconfirmed activation)"] = paired_delta([per[a][i]["unconfirmed"] for i in xs],
                                                                                [per[b][i]["unconfirmed"] for i in xs])
    leg = [i for i in ids if g3[i]["kind"].startswith("ben")]
    for a, b in (("COMBINED", "BASE"), ("ABL_B13_not_PAB13", "COMBINED")):
        tests[f"legit: {a} vs {b} (excluded)"] = paired_delta([per[a][i]["excluded"] for i in leg], [per[b][i]["excluded"] for i in leg])
        tests[f"legit: {a} vs {b} (surfaced)"] = paired_delta([per[a][i]["surfaced"] for i in leg], [per[b][i]["surfaced"] for i in leg])
    # latency / overhead (Mem0 stage timings)
    from phase17.defence_v6.mem0_sa6 import STAGE
    st = json.loads(STAGE.read_text(encoding="utf-8"))["items"]
    ing = [v["ingest_seconds"] for v in st.values() if "ingest_seconds" in v]
    led = [v["ledger_seconds"] for v in st.values() if "ledger_seconds" in v]
    lat = {"mem0_ingest_seconds_median": sorted(ing)[len(ing) // 2] if ing else None,
           "ledger_bookkeeping_seconds_median": sorted(led)[len(led) // 2] if led else None,
           "ledger_overhead_pct_of_ingest": round(100 * sum(led) / sum(ing), 3) if ing else None}
    g2p = DATA / "g2_eval.json"
    prop = None
    if g2p.exists():
        g2 = json.loads(g2p.read_text(encoding="utf-8"))
        prop = {pay: {a: b[a]["withheld_carrying"][3] for a in ("FG", "ND", "RCL", "CTC", "PRC", "RAR", "RAR-B")}
                for pay, b in g2["by_payload"].items()}
    out = {"n_items": len(ids), "arms": res, "paired_tests": tests, "latency": lat, "propagation_gen4_withheld_carrying": prop}
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = evaluate()
    for a, v in r["arms"].items():
        print(a, {g: v[g]["unconfirmed_activation"]["k"] for g in ("atk_implicit", "atk_explicit")},
              "legit excluded", v["ungrounded_legit"]["excluded"]["k"], "avail", v["memory_availability_legit"]["rate"])
