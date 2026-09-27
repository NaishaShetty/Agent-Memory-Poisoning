"""Phase 17 (generalization fix) -- the combined generalized stack ("G-stack") on
every held-out split and benign population.

Training discipline: the EmbeddingDetector's negatives are DEV benign notes PLUS
real benign memories from the EVEN-indexed benign pools of each dataset; every
benign FPR number below is computed on the ODD-indexed (held-out) pools only, so
the detector never scores memories it was trained on. Judge variant chosen on
dev only (`broad`). Poison sets are never used for training (dev attacks only).

Systems per record (all opt-in; frozen B0-B10 untouched):
  base   = live B9 rule (ADMISSION_CORROBORATED)          [Phase 14 shipped]
  g1     = live B9 rule + retrieval-only zeroing (G1)
  judge  = LLM judge (G3)      emb = embedding detector (G2)
  G-flag = g1-flagged OR judge OR emb
  G-excl-A = g1-excluded OR judge          G-excl-B = g1-excluded OR (judge AND emb)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from phase17 import arenas, dev_sets
from phase17.arenas import dataset_arena
from phase17.engine import EXCLUDING_ACTIONS, build_signal_table, rule_actions
from phase17.extra_datasets import convomem_pools
from phase17.novel_attacks import novel_records
from phase17.perltqa import perltqa_pools
from phase17.poison_sets import evasion_records, original_records, regenerated_records
from phase17.semantic_detector import EmbeddingDetector, LLMJudge
from phase17.stats import cluster_bootstrap, paired_delta, rate_with_ci
from phase17.translation import zh_records
from phase6.defense.policy.states import ALLOW
from phase6.defense.risk.risk_score import (
    GROUPED_GATED_ADMISSION_AND_RETRIEVAL_CORROBORATED, GROUPED_GATED_ADMISSION_CORROBORATED,
)

OUT = Path(__file__).parent / "data" / "gstack_results.json"


def _per_record(pools, truth_ids, emb, judge) -> Dict[str, dict]:
    table = build_signal_table(pools)
    base = rule_actions(table, rule=GROUPED_GATED_ADMISSION_CORROBORATED)
    g1 = rule_actions(table, rule=GROUPED_GATED_ADMISSION_AND_RETRIEVAL_CORROBORATED)
    text = {m.scenario_id: m.content_text for p in pools for m in p.memories}
    ids = [i for i in table if i in truth_ids]
    e = dict(zip(ids, emb.flags([text[i] for i in ids])))
    j = {i: judge.flag(text[i]) for i in ids}
    judge.save()
    rows = {}
    for i in ids:
        bf, bx = base[i] != ALLOW, base[i] in EXCLUDING_ACTIONS
        gf, gx = g1[i] != ALLOW, g1[i] in EXCLUDING_ACTIONS
        rows[i] = {"base_f": bf, "base_x": bx, "g1_f": gf, "g1_x": gx, "emb": e[i], "judge": j[i],
                   "G_flag": gf or j[i] or e[i], "G_excl_A": gx or j[i], "G_excl_B": gx or (j[i] and e[i])}
    return rows


def _split_benign(pt):
    pools, truth = pt
    ordered = sorted(pools, key=lambda p: p.pool_id)
    tr, te = ordered[0::2], ordered[1::2]
    ids = lambda ps: {m.scenario_id for p in ps for m in p.memories}
    return tr, te, ids(te)


def run() -> dict:
    d = dev_sets.load()
    benign_sets = {"dataset_arena": dataset_arena(), "convomem": convomem_pools(), "perltqa_zh": perltqa_pools()}
    train_neg = [b["text"] for b in d["benign"]]
    splits = {}
    for name, pt in benign_sets.items():
        tr, te, te_ids = _split_benign(pt)
        splits[name] = (te, te_ids)
        if name != "perltqa_zh":  # English embedding model: Chinese not used for training
            train_neg += [m.content_text for p in tr for m in p.memories]
    emb = EmbeddingDetector()
    fit = emb.fit([a["text"] for a in d["attacks"]], train_neg)
    judge = LLMJudge("broad")
    out = {"dev_fit": fit, "n_train_negatives": len(train_neg), "poison": {}, "benign": {}}
    keys = ("base_f", "base_x", "g1_f", "g1_x", "emb", "judge", "G_flag", "G_excl_A", "G_excl_B")
    recs = {"signal_source": original_records(), "held_out_regen": regenerated_records(), "held_out_evasion": evasion_records(),
            "held_out_novel": novel_records(), "held_out_zh": zh_records()}
    rows_by_split = {}
    for name, rs in recs.items():
        pools, truth = arenas.isolated_arena(rs)
        rows = _per_record(pools, {r.scenario_id for r in rs}, emb, judge)
        rows_by_split[name] = (rs, rows)
        out["poison"][name] = {"n": len(rs), **{k: rate_with_ci(sum(rows[r.scenario_id][k] for r in rs), len(rs)) for k in keys}}
        grp = {}
        for r in rs:
            g = grp.setdefault(r.variant if name == "held_out_evasion" else r.family, {"n": 0, **{k: 0 for k in keys}})
            g["n"] += 1
            for k in keys:
                g[k] += rows[r.scenario_id][k]
        out["poison"][name]["by_group"] = grp
    ev, evrows = rows_by_split["held_out_evasion"]
    out["evasion_cluster_aware"] = {k: cluster_bootstrap([evrows[r.scenario_id][k] for r in ev], [r.parent_id for r in ev])
                                    for k in ("base_f", "G_flag", "G_excl_A", "G_excl_B")}
    zh, zrows = rows_by_split["held_out_zh"]
    par = {r.scenario_id: r for r in original_records() + regenerated_records() + novel_records()}
    for k in ("G_flag", "G_excl_A", "G_excl_B"):
        p_recs = [par[z.parent_id] for z in zh]
        pool_e, _ = arenas.isolated_arena(p_recs)
        erows = _per_record(pool_e, {r.scenario_id for r in p_recs}, emb, judge)
        out.setdefault("language_paired", {})[k] = paired_delta([erows[r.scenario_id][k] for r in p_recs], [zrows[z.scenario_id][k] for z in zh])
    for name, (pools, te_ids) in splits.items():
        rows = _per_record(pools, te_ids, emb, judge)
        n = len(rows)
        out["benign"][name] = {"n_heldout_pool_memories": n, **{k: rate_with_ci(sum(r[k] for r in rows.values()), n) for k in keys}}
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    run()
    print("DONE")
