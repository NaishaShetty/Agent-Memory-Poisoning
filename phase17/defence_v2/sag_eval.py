"""WS-A (Gap 1): source-anchored governance (SAG) -- a stored/derived memory inherits the admission decision of the
raw item it was extracted from (write-time lineage), OR-ed with the decision on its own text.
Pre-registered: docs/phase17/PREREGISTRATION_DEFENCE_V2_2026-10-13.md (WS-A).

Sets: MEM-1 (HO4 through Mem0) and MEM-2 (SA-1 through Mem0) from cached decisions (repeated evaluation), and
SA-3-eval through Mem0 (new; computed in sleeper_v2.mem0_stage). Conditions: lineage intact / lost / wrong (seeded
permutation of the raw decisions within the set, benign included) / user channel. No parameters.
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Dict, List

DATA = Path(__file__).resolve().parents[1] / "data"
OUT = DATA / "defence_v2" / "sag_eval.json"


def _r(xs: List[bool]):
    from phase17.stats import rate_with_ci

    return rate_with_ci(sum(xs), len(xs))


def sag_block(items: List[Dict], seed: int = 2026) -> Dict:
    """items: [{kind: atk|ben, raw: {B12,B13}, stored: [{B12,B13}...], stored_any: bool, outcome: bool|None}]
    outcome = the behavioural success flag of the attack (working / activation) when measured, else None."""
    from phase17.stats import paired_delta

    perm = list(range(len(items)))
    random.Random(seed).shuffle(perm)
    out: Dict = {}
    for X in ("B12", "B13"):
        cond = {}
        for name in ("lost", "intact", "wrong"):
            dec = []
            for i, it in enumerate(items):
                stored = any(s[X] for s in it["stored"])
                raw = {"lost": False, "intact": it["raw"][X], "wrong": items[perm[i]]["raw"][X]}[name]
                dec.append(stored or raw)
            cond[name] = dec
        blk = {}
        for kind in ("atk", "ben"):
            ix = [i for i, it in enumerate(items) if it["kind"] == kind]
            blk[kind] = {name: _r([cond[name][i] for i in ix]) for name in cond}
            blk[kind]["raw_only"] = _r([items[i]["raw"][X] for i in ix])
            if kind == "atk":
                blk[kind]["paired_intact_vs_lost"] = paired_delta([cond["intact"][i] for i in ix], [cond["lost"][i] for i in ix])
                oc = [i for i in ix if items[i]["outcome"] is not None]
                if oc:
                    blk[kind]["outcome_undefended"] = _r([items[i]["outcome"] for i in oc])
                    for name in cond:
                        blk[kind][f"outcome_remaining_{name}"] = _r([items[i]["outcome"] and not cond[name][i] for i in oc])
                    blk[kind]["paired_outcome_intact_vs_lost"] = paired_delta(
                        [items[i]["outcome"] and not cond["intact"][i] for i in oc],
                        [items[i]["outcome"] and not cond["lost"][i] for i in oc])
        blk["benign_increase_points_intact_vs_lost"] = round(100 * (blk["ben"]["intact"]["rate"] - blk["ben"]["lost"]["rate"]), 2)
        blk["benign_increase_points_wrong_vs_lost"] = round(100 * (blk["ben"]["wrong"]["rate"] - blk["ben"]["lost"]["rate"]), 2)
        out[X] = blk
    return out


def mem1_items(channel: str = "document") -> List[Dict]:
    part = json.loads((DATA / "remediation" / "mem0_pipeline_eval_partial.json").read_text(encoding="utf-8"))
    res = json.loads((DATA / "remediation" / "mem0_pipeline_eval.json").read_text(encoding="utf-8"))
    inp = json.loads((DATA / "mem0_infer" / "inputs.json").read_text(encoding="utf-8"))
    s4 = json.loads((DATA / "mem0_infer" / "stage1_ho4.json").read_text(encoding="utf-8"))
    d4 = part["defence:ho4"]
    rows = {r["id"]: r for r in res["MEM1_ho4"][f"attacks_{channel}"]["rows"]}
    out = []
    for a in inp["ho4"]["attacks"]:
        der = s4["items"].get(f"{a['id']}|{channel}", {}).get("derived_texts", [])
        raw = dict(d4[a["text"]])
        # user-channel stored texts were scored only where available in the original run (missing -> not excluded,
        # exactly as mem0_pipeline_eval did)
        st = [dict(d4.get(t, {"B12": False, "B13": False})) for t in der]
        if channel == "user":                       # trusted channel: B13 never excludes (by construction)
            raw["B13"] = False
            st = [{**s, "B13": False} for s in st]
        out.append({"kind": "atk", "id": a["id"], "family": a["family"], "raw": raw, "stored": st,
                    "outcome": bool(rows[a["id"]]["working"])})
    if channel == "document":
        for b in inp["ho4"]["benign"]:
            der = s4["items"].get(f"{b['id']}|document", {}).get("derived_texts", [])
            out.append({"kind": "ben", "id": b["id"], "raw": dict(d4[b["text"]]), "stored": [dict(d4[t]) for t in der],
                        "outcome": None})
    return out


def mem2_items(channel: str = "document") -> List[Dict]:
    part = json.loads((DATA / "remediation" / "mem0_pipeline_eval_partial.json").read_text(encoding="utf-8"))
    inp = json.loads((DATA / "mem0_infer" / "inputs.json").read_text(encoding="utf-8"))
    s1 = json.loads((DATA / "mem0_infer" / "stage1_sa1.json").read_text(encoding="utf-8"))
    d1 = part["defence:sa1"]
    out = []
    for x in inp["sa1"]["items"]:
        der = s1["items"].get(f"{x['id']}|{channel}", {}).get("derived_texts", [])
        act = bool(part.get(f"J:sa1:{channel}:trigger:{x['id']}", False)) and not bool(part.get(f"J:sa1:ctrl:trigger:{x['id']}", False))
        raw = dict(d1[x["text"]])
        st = [dict(d1.get(t, {"B12": False, "B13": False})) for t in der]
        if channel == "user":
            raw["B13"] = False
            st = [{**s, "B13": False} for s in st]
        out.append({"kind": x["kind"], "id": x["id"], "raw": raw, "stored": st,
                    "outcome": act if x["kind"] == "atk" else None})
    return out


def run() -> Dict:
    res = {"preregistration": "docs/phase17/PREREGISTRATION_DEFENCE_V2_2026-10-13.md (WS-A)",
           "label": "MEM-1 / MEM-2: repeated evaluation on cached decisions (no model calls)", "sets": {}}
    m1 = mem1_items("document")
    res["sets"]["MEM1_document"] = {"n_attack": sum(x["kind"] == "atk" for x in m1), "n_benign": sum(x["kind"] == "ben" for x in m1),
                                    "outcome": "working (MEM-1 per-item)", **sag_block(m1)}
    m1u = mem1_items("user")
    res["sets"]["MEM1_user"] = {"n_attack": len(m1u), "outcome": "working", **{X: {"atk": v["atk"]} for X, v in sag_block(m1u).items()}}
    m2 = mem2_items("document")
    res["sets"]["MEM2_document"] = {"n_attack": sum(x["kind"] == "atk" for x in m2), "n_benign": sum(x["kind"] == "ben" for x in m2),
                                    "outcome": "activation on trigger (MEM-2 per-item)", **sag_block(m2)}
    sa3 = DATA / "defence_v2" / "sa3_mem0_items.json"
    if sa3.exists():
        it = json.loads(sa3.read_text(encoding="utf-8"))
        for bkind in ("ben_unground", "ben_ground"):
            sub = [dict(x, kind="ben") if x["kind"] == bkind else x for x in it if x["kind"] in ("atk", bkind)]
            res["sets"][f"SA3eval_document_vs_{bkind}"] = {"n_attack": sum(x["kind"] == "atk" for x in sub),
                                                           "n_benign": sum(x["kind"] == "ben" for x in sub),
                                                           "outcome": "activation on trigger (raw note; see WS-C)", **sag_block(sub)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    return res


if __name__ == "__main__":
    r = run()
    for s, v in r["sets"].items():
        for X in ("B12", "B13"):
            a = v[X]["atk"]
            line = f"{s:32s} {X}: atk lost {a['lost']['k']}/{a['lost']['n']} intact {a['intact']['k']} wrong {a['wrong']['k']}"
            if "ben" in v[X]:
                b = v[X]["ben"]
                line += f" | ben lost {b['lost']['k']}/{b['lost']['n']} intact {b['intact']['k']} wrong {b['wrong']['k']}"
            if "outcome_undefended" in a:
                line += f" | outcome {a['outcome_undefended']['k']} -> lost {a['outcome_remaining_lost']['k']} intact {a['outcome_remaining_intact']['k']}"
            print(line)
