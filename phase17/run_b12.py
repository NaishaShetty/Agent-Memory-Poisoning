"""Fix round 4 -- B12 (G1 rule + stacked detector + steer flag) per-record on all held-out splits, plus the
ordered conflict check unioned on the 13 gold-bearing parents. Benign FPR on odd pools."""
import json
from pathlib import Path

from phase17 import arenas, conflict_check as cc
from phase17.arenas import dataset_arena
from phase17.b11_live import APPEAL_THRESHOLD, CONFLICT_THRESHOLD, SUPERSEDE_THRESHOLD, _judge
from phase17.b12_live import _detector
from phase17.engine import EXCLUDING_ACTIONS, build_signal_table, rule_actions
from phase17.extra_datasets import convomem_pools
from phase17.gold_registry import gold_memories
from phase17.novel_attacks import novel_records
from phase17.perltqa import perltqa_pools
from phase17.poison_sets import evasion_records, original_records, regenerated_records
from phase17.stats import cluster_bootstrap, paired_delta, rate_with_ci
from phase17.translation import zh_records
from phase6.defense.policy.states import ALLOW
from phase6.defense.risk.risk_score import GROUPED_GATED_ADMISSION_AND_RETRIEVAL_CORROBORATED as G1

OUT = Path(__file__).parent / "data" / "b12_results.json"
KEYS = ("g1_f", "g1_x", "stack_x", "stack_f", "steer", "B12_flag", "B12_excl")


def rows_for(pools, ids):
    det, steer = _detector(), _judge("steer")
    table = build_signal_table(pools)
    g1 = rule_actions(table, rule=G1)
    text = {m.scenario_id: m.content_text for p in pools for m in p.memories}
    order = [i for i in table if i in ids]
    xs, fs = det.decide([text[i] for i in order], 0.005), det.decide([text[i] for i in order], 0.02)
    rows = {}
    for i, x, f in zip(order, xs, fs):
        st = steer.flag(text[i]); gf, gx = g1[i] != ALLOW, g1[i] in EXCLUDING_ACTIONS
        rows[i] = {"g1_f": gf, "g1_x": gx, "stack_x": x, "stack_f": f, "steer": st, "B12_flag": gf or f or x or st, "B12_excl": gx or x}
    steer.save()
    return rows


def main():
    out = {"poison": {}, "benign": {}}
    recs = {"signal_source": original_records(), "held_out_regen": regenerated_records(), "held_out_evasion": evasion_records(),
            "held_out_novel": novel_records(), "held_out_zh": zh_records()}
    got = {}
    for name, rs in recs.items():
        pools, _ = arenas.isolated_arena(rs)
        rows = rows_for(pools, {r.scenario_id for r in rs}); got[name] = rows
        grp = {}
        for r in rs:
            g = grp.setdefault(r.variant if name == "held_out_evasion" else r.family, {"n": 0, **{k: 0 for k in KEYS}})
            g["n"] += 1
            for k in KEYS:
                g[k] += rows[r.scenario_id][k]
        out["poison"][name] = {"n": len(rs), **{k: rate_with_ci(sum(rows[r.scenario_id][k] for r in rs), len(rs)) for k in KEYS}, "by_group": grp}
    ev = evasion_records()
    out["evasion_cluster_aware"] = {k: cluster_bootstrap([got["held_out_evasion"][r.scenario_id][k] for r in ev], [r.parent_id for r in ev])
                                    for k in ("B12_flag", "B12_excl")}
    # union with the ordered conflict check on gold-bearing parents
    gold, evr = gold_memories(), {(r.parent_id, r.variant): r for r in ev}
    from phase14.track_b_poison import build_track_b_cases
    dist = [(f"D{i}", t) for i, (_, t) in enumerate(build_track_b_cases()[0].pool_items[1:])]
    tab = {}
    for parent, (gtext, ptext) in gold.items():
        variants = {"original": ptext, **{v: evr[(parent, v)].text for v in ("plain", "embedded") if (parent, v) in evr}}
        for v, text in variants.items():
            confl = cc.exclusions([("GOLD", gtext)] + dist + [("POISON", text)], CONFLICT_THRESHOLD, SUPERSEDE_THRESHOLD, APPEAL_THRESHOLD)["POISON"]
            det_x = _detector().decide([text], 0.005)[0]
            t = tab.setdefault(v, {"n": 0, "B12_excl": 0, "conflict": 0, "union": 0})
            t["n"] += 1; t["B12_excl"] += det_x; t["conflict"] += confl; t["union"] += (det_x or confl)
    out["gold_parents_union"] = tab
    cc.save_cache()
    zh = zh_records()
    for name, pt in {"dataset_arena": dataset_arena(), "convomem": convomem_pools(), "perltqa_zh": perltqa_pools()}.items():
        te = sorted(pt[0], key=lambda p: p.pool_id)[1::2]
        rows = rows_for(te, {m.scenario_id for p in te for m in p.memories})
        out["benign"][name] = {"n": len(rows), **{k: rate_with_ci(sum(r[k] for r in rows.values()), len(rows)) for k in KEYS}}
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("DONE")


if __name__ == "__main__":
    main()
