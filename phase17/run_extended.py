"""Phase 17 -- extended evaluation closing the four disclosed caveats:
(1) cluster-aware statistics for the correlated evasion variants,
(2) novel-mechanism attacks (60 independent LLM-authored parents),
(3) [Consolidation ablation -> consolidation_ablation.py],
(4) PerLTQA benign FPR + recorded Chinese translations of the poison sets.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Sequence

from phase17 import arenas
from phase17.b10_ablation import decisions as b10_decisions
from phase17.engine import (
    B8_ALL_FOUR, EXCLUDING_ACTIONS, admission_actions, build_signal_table, guard_actions, rule_actions,
)
from phase17.extra_datasets import convomem_pools
from phase17.novel_attacks import novel_records
from phase17.perltqa import perltqa_pools
from phase17.poison_sets import PoisonRecord, all_records, evasion_records, original_records, regenerated_records
from phase17.stats import cluster_bootstrap, paired_delta, rate_with_ci
from phase17.translation import zh_records
from phase6.defense.risk.risk_score import GROUPED_GATED_ADMISSION_CORROBORATED, GROUPED_GATED_RETRIEVAL_CORROBORATED

OUT = Path(__file__).parent / "data" / "extended_results.json"
SYSTEMS = ("B1", "B9-matrix", "B9-live", "B8", "B10-gated")


def evaluate_records(records: Sequence[PoisonRecord]) -> dict:
    """Per-record {system: {flagged, excluded}} in the isolated arena, plus the
    3 real LoCoMo distractors' false-positive counts per system."""
    pools, truth = arenas.isolated_arena(records)
    table = build_signal_table(pools)
    acts = {
        "B1": admission_actions(table),
        "B9-matrix": rule_actions(table, rule=GROUPED_GATED_RETRIEVAL_CORROBORATED),
        "B9-live": rule_actions(table, rule=GROUPED_GATED_ADMISSION_CORROBORATED),
        "B8": guard_actions(pools, B8_ALL_FOUR),
    }
    b10 = b10_decisions(pools, 0.25, True, float("-inf"))
    rows = {}
    for r in records:
        rows[r.scenario_id] = {
            **{s: {"flagged": acts[s][r.scenario_id] != "ALLOW", "excluded": acts[s][r.scenario_id] in EXCLUDING_ACTIONS}
               for s in ("B1", "B9-matrix", "B9-live", "B8")},
            "B10-gated": {"flagged": bool(b10[r.scenario_id]), "excluded": bool(b10[r.scenario_id])},
        }
    distractor_ids = [m for m, t in truth.items() if not t.is_poison]
    fp = {}
    for s in ("B1", "B9-matrix", "B9-live", "B8"):
        fp[s] = {"flagged": sum(acts[s][m] != "ALLOW" for m in distractor_ids),
                 "excluded": sum(acts[s][m] in EXCLUDING_ACTIONS for m in distractor_ids), "n": len(distractor_ids)}
    fp["B10-gated"] = {"flagged": sum(bool(b10[m]) for m in distractor_ids), "excluded": sum(bool(b10[m]) for m in distractor_ids),
                       "n": len(distractor_ids)}
    return {"rows": rows, "distractor_fp": fp}


def cells(records: Sequence[PoisonRecord], res: dict, group_key=lambda r: r.family) -> dict:
    out = {}
    for g in sorted({group_key(r) for r in records}):
        ids = [r.scenario_id for r in records if group_key(r) == g]
        out[g] = {s: {k: rate_with_ci(sum(res["rows"][i][s][k] for i in ids), len(ids)) for k in ("flagged", "excluded")}
                  for s in SYSTEMS}
    total = {s: {k: rate_with_ci(sum(res["rows"][r.scenario_id][s][k] for r in records), len(records))
                 for k in ("flagged", "excluded")} for s in SYSTEMS}
    return {"by_group": out, "total": total, "n": len(records)}


def benign_fpr(pools_truth, name: str) -> dict:
    pools, truth = pools_truth
    table = build_signal_table(pools)
    acts = {
        "B1": admission_actions(table),
        "B9-matrix": rule_actions(table, rule=GROUPED_GATED_RETRIEVAL_CORROBORATED),
        "B9-live": rule_actions(table, rule=GROUPED_GATED_ADMISSION_CORROBORATED),
        "B8": guard_actions(pools, B8_ALL_FOUR),
    }
    b10 = b10_decisions(pools, 0.25, True, float("-inf"))
    n = len(table)
    out = {s: {"flagged": rate_with_ci(sum(a != "ALLOW" for a in acts[s].values()), n),
               "excluded": rate_with_ci(sum(a in EXCLUDING_ACTIONS for a in acts[s].values()), n)} for s in acts}
    k = sum(bool(v) for i, v in b10.items() if i in truth)
    out["B10-gated"] = {"flagged": rate_with_ci(k, n), "excluded": rate_with_ci(k, n)}
    return {"dataset": name, "n": n, "systems": out}


def run() -> dict:
    orig, regen, eva = original_records(), regenerated_records(), evasion_records()
    novel, zh = novel_records(), zh_records()
    result = {"counts": {"original": len(orig), "regen": len(regen), "evasion": len(eva), "novel": len(novel), "zh": len(zh)}}

    # (1) cluster-aware evasion statistics
    res_eva = evaluate_records(eva)
    result["evasion_cluster_aware"] = {
        s: {k: cluster_bootstrap([res_eva["rows"][r.scenario_id][s][k] for r in eva], [r.parent_id for r in eva])
            for k in ("flagged", "excluded")} for s in SYSTEMS}
    result["evasion_by_strategy"] = cells(eva, res_eva, group_key=lambda r: r.variant)

    # (2) novel mechanisms
    res_novel = evaluate_records(novel)
    result["novel_mechanisms"] = cells(novel, res_novel)
    result["novel_distractor_fp"] = res_novel["distractor_fp"]

    # (4) language axis: paired English-vs-Chinese on the SAME parents, plus Chinese benign FPR
    parents = {r.scenario_id: r for r in orig + regen + novel}
    res_en = evaluate_records([parents[z.parent_id] for z in zh])
    res_zh = evaluate_records(zh)
    paired = {}
    for s in SYSTEMS:
        for k in ("flagged", "excluded"):
            en = [res_en["rows"][z.parent_id][s][k] for z in zh]
            cn = [res_zh["rows"][z.scenario_id][s][k] for z in zh]
            paired[f"{s}|{k}"] = {"english": rate_with_ci(sum(en), len(en)), "chinese": rate_with_ci(sum(cn), len(cn)),
                                  "paired": paired_delta(en, cn)}
    result["language"] = {"n_pairs": len(zh), "paired_english_vs_chinese": paired,
                          "zh_distractor_fp_note": "distractors are English LoCoMo turns (arena shape unchanged)"}
    result["benign"] = {"perltqa(zh)": benign_fpr(perltqa_pools(), "perltqa"), "convomem(en)": benign_fpr(convomem_pools(), "convomem")}

    OUT.write_text(json.dumps(result, indent=2, default=list, ensure_ascii=False), encoding="utf-8")
    return result


if __name__ == "__main__":
    run()
    print("DONE")
