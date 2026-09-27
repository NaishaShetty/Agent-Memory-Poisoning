"""Fix round 4 -- conflict-without-supersession check with the appeal-to-prior-authority
test. Thresholds fixed on DEV pairs only (Youden). Evaluated on EVAL pairs, every
poison parent that has a real gold memory (13) x {original, plain, embedded}, benign
arenas, and the poison-FIRST order case (order-free contested flagging)."""
import json
from pathlib import Path

import numpy as np

from phase14.track_a_benign import N_DISTRACTORS
from phase14.track_b_poison import build_track_b_cases
from phase17 import conflict_check as cc
from phase17 import conflict_sets
from phase17.arenas import dataset_arena
from phase17.gold_registry import gold_memories
from phase17.poison_sets import evasion_records
from phase17.stats import rate_with_ci
from phase17.workloads import locomo_cases_with_category
from phase14.track_b_poison import build_track_b_cases as _cases

OUT = Path(__file__).parent / "data" / "conflict_results.json"


def youden(pos, neg):
    cands = sorted(set(pos) | set(neg))
    return max(cands, key=lambda t: np.mean([p >= t for p in pos]) - np.mean([n >= t for n in neg]))


def main():
    pairs = conflict_sets.load()
    sc = {p["id"]: (*cc.pair_scores(p["a"], p["b"]), cc.appeal_score(p["b"])) for p in pairs}
    g = lambda kinds, split: [sc[p["id"]] for p in pairs if p["kind"] in kinds and p["split"] == split]
    t_c = youden([x[0] for x in g(("plain_conflict", "legit_update", "forged_supersession"), "dev")], [x[0] for x in g(("related_ok",), "dev")])
    t_s = youden([x[1] for x in g(("legit_update",), "dev")], [x[1] for x in g(("plain_conflict", "forged_supersession"), "dev")])
    t_a = youden([x[2] for x in g(("forged_supersession",), "dev")], [x[2] for x in g(("legit_update", "plain_conflict"), "dev")])
    dec = lambda xs: [cc.is_unsupported_conflict(c, s, a, t_c, t_s, t_a) for c, s, a in xs]
    kinds = ("legit_update", "plain_conflict", "forged_supersession", "related_ok")
    out = {"t_conflict": t_c, "t_supersede": t_s, "t_appeal": t_a,
           "eval_pairs_excluded": {k: {"excluded": sum(dec(g((k,), "eval"))), "n": len(g((k,), "eval"))} for k in kinds}}
    gold = gold_memories()
    evr = {(r.parent_id, r.variant): r for r in evasion_records()}
    benign_pool = [t for _, t in _cases()[0].pool_items[1:]]
    rows = []
    for parent, (gtext, ptext) in gold.items():
        dist = [(f"D{i}", t) for i, t in enumerate(benign_pool)]
        gold_item = ("GOLD", gtext)
        variants = {"original": ptext}
        for v in ("plain", "embedded"):
            if (parent, v) in evr:
                variants[v] = evr[(parent, v)].text
        for v, text in variants.items():
            ex = cc.exclusions([gold_item] + dist + [("POISON", text)], t_c, t_s, t_a)
            cont = cc.contested_pairs([("POISON", text), gold_item] + dist, t_c, t_s, t_a)   # poison admitted FIRST, order unknown
            rows.append({"parent": parent, "variant": v, "family": parent.split("-")[1], "excluded": ex["POISON"],
                         "benign_excluded": sum(ex[i] for i, _ in [gold_item] + dist),
                         "poison_first_contested": cont["POISON"], "poison_first_gold_contested": cont["GOLD"]})
    out["n_parents_with_gold"] = len(gold)
    for key in ("excluded", "poison_first_contested"):
        out[key + "_by_variant"] = {v: rate_with_ci(sum(r[key] for r in rows if r["variant"] == v), sum(1 for r in rows if r["variant"] == v))
                                    for v in ("original", "plain", "embedded")}
        out[key + "_by_family"] = {f: rate_with_ci(sum(r[key] for r in rows if r["family"] == f), sum(1 for r in rows if r["family"] == f))
                                   for f in sorted({r["family"] for r in rows})}
    out["poison_arenas_benign_excluded"] = sum(r["benign_excluded"] for r in rows)
    out["poison_first_gold_wrongly_contested_(flag_only)"] = sum(r["poison_first_gold_contested"] for r in rows)
    out["rows"] = rows
    la = [c for c, _ in locomo_cases_with_category()][:300]
    fp_a = sum(sum(cc.exclusions(list(c.pool_items), t_c, t_s, t_a).values()) for c in la)
    out["benign_locomo_trackA_pools"] = rate_with_ci(fp_a, sum(len(c.pool_items) for c in la))
    te = sorted(dataset_arena()[0], key=lambda p: p.pool_id)[1::2]
    fp_d = sum(sum(cc.exclusions([(m.scenario_id, m.content_text) for m in p.memories], t_c, t_s, t_a).values()) for p in te)
    out["benign_dataset_odd_pools"] = rate_with_ci(fp_d, sum(len(p.memories) for p in te))
    cc.save_cache()
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("DONE", {k: v for k, v in out.items() if k != "rows"})


if __name__ == "__main__":
    main()
