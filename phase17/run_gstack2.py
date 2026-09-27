"""Phase 17 generalization fix 2 -- B11 (two-tier judge + language-safe rule)
on every held-out split; benign FPR on ODD (held-out) pools only. Judge variants
chosen on DEV (`tune_judge.py`, `judge_tuning.json`); nothing tuned on eval."""
import json
from pathlib import Path

from phase17 import arenas
from phase17.arenas import dataset_arena
from phase17.engine import EXCLUDING_ACTIONS, build_signal_table, rule_actions
from phase17.extra_datasets import convomem_pools
from phase17.novel_attacks import novel_records
from phase17.perltqa import perltqa_pools
from phase17.poison_sets import evasion_records, original_records, regenerated_records
from phase17.semantic_detector import LLMJudge
from phase17.stats import cluster_bootstrap, paired_delta, rate_with_ci
from phase17.translation import zh_records
from phase6.defense.policy.states import ALLOW
from phase6.defense.risk.risk_score import (
    GROUPED_GATED_ADMISSION_AND_RETRIEVAL_CORROBORATED as G1, GROUPED_GATED_ADMISSION_CORROBORATED as LIVE,
)

OUT = Path(__file__).parent / "data" / "gstack2_results.json"
KEYS = ("base_f", "base_x", "g1_f", "g1_x", "concept", "broad", "steer", "B11_flag", "B11_excl")


def rows_for(pools, ids, jc, jb, js=None):
    js = js or LLMJudge("steer")
    table = build_signal_table(pools)
    base, g1 = rule_actions(table, rule=LIVE), rule_actions(table, rule=G1)
    text = {m.scenario_id: m.content_text for p in pools for m in p.memories}
    rows = {}
    for i in (x for x in table if x in ids):
        c, b, st = jc.flag(text[i]), jb.flag(text[i]), js.flag(text[i])
        gf, gx = g1[i] != ALLOW, g1[i] in EXCLUDING_ACTIONS
        rows[i] = {"base_f": base[i] != ALLOW, "base_x": base[i] in EXCLUDING_ACTIONS, "g1_f": gf, "g1_x": gx,
                   "concept": c, "broad": b, "steer": st, "B11_flag": gf or c or b or st, "B11_excl": gx or c}
    jc.save(); jb.save(); js.save()
    return rows


def run():
    jc, jb = LLMJudge("concept"), LLMJudge("broad")
    out = {"poison": {}, "benign": {}}
    recs = {"signal_source": original_records(), "held_out_regen": regenerated_records(), "held_out_evasion": evasion_records(),
            "held_out_novel": novel_records(), "held_out_zh": zh_records()}
    got = {}
    for name, rs in recs.items():
        pools, _ = arenas.isolated_arena(rs)
        rows = rows_for(pools, {r.scenario_id for r in rs}, jc, jb)
        got[name] = rows
        grp = {}
        for r in rs:
            g = grp.setdefault(r.variant if name == "held_out_evasion" else r.family, {"n": 0, **{k: 0 for k in KEYS}})
            g["n"] += 1
            for k in KEYS:
                g[k] += rows[r.scenario_id][k]
        out["poison"][name] = {"n": len(rs), **{k: rate_with_ci(sum(rows[r.scenario_id][k] for r in rs), len(rs)) for k in KEYS}, "by_group": grp}
    ev = evasion_records()
    out["evasion_cluster_aware"] = {k: cluster_bootstrap([got["held_out_evasion"][r.scenario_id][k] for r in ev], [r.parent_id for r in ev])
                                    for k in ("base_f", "B11_flag", "B11_excl")}
    zh = zh_records()
    par = {r.scenario_id: r for r in original_records() + regenerated_records() + novel_records()}
    prs = [par[z.parent_id] for z in zh]
    pp, _ = arenas.isolated_arena(prs)
    er = rows_for(pp, {r.scenario_id for r in prs}, jc, jb)
    out["language_paired"] = {k: paired_delta([er[r.scenario_id][k] for r in prs], [got["held_out_zh"][z.scenario_id][k] for z in zh])
                              for k in ("B11_flag", "B11_excl")}
    for name, pt in {"dataset_arena": dataset_arena(), "convomem": convomem_pools(), "perltqa_zh": perltqa_pools()}.items():
        te = sorted(pt[0], key=lambda p: p.pool_id)[1::2]
        ids = {m.scenario_id for p in te for m in p.memories}
        rows = rows_for(te, ids, jc, jb)
        out["benign"][name] = {"n": len(rows), **{k: rate_with_ci(sum(r[k] for r in rows.values()), len(rows)) for k in KEYS}}
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    run(); print("DONE")
