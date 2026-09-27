"""Fix round 3, part 1 -- continuous-score ensemble judge (mean of concept+fewshot
and broad+fewshot logits; demonstrations = DEV items only). Operating points are
set on DEV: EXCLUDE threshold = dev FPR<=0.5%, FLAG threshold = dev FPR<=2%.
Evaluated on held-out splits; benign FPR on odd pools only."""
import json
from pathlib import Path

import numpy as np

from phase17 import arenas
from phase17.arenas import dataset_arena
from phase17.extra_datasets import convomem_pools
from phase17.judge_scores import ScoreJudge, recall_at_fpr
from phase17.novel_attacks import novel_records, MECHANISMS
from phase17.perltqa import perltqa_pools
from phase17.poison_sets import evasion_records, original_records, regenerated_records
from phase17.stats import rate_with_ci
from phase17.translation import zh_records
from phase17.tune_scores import dev_items

OUT = Path(__file__).parent / "data" / "scores_eval_results.json"
EVAL_OVERLAP = {"authority_impersonation": True, "policy_revocation": True, "exfiltration_instruction": True,
                "conditional_backdoor": False, "preference_hijack": False, "memory_worm": False}


def main():
    pos, neg = dev_items()
    demos = pos + neg
    jc, jb = ScoreJudge("concept", demos=demos), ScoreJudge("broad", demos=demos)
    ens = lambda t: (jc.score(t) + jb.score(t)) / 2
    dp, dn = [ens(x["text"]) for x in pos], [ens(x["text"]) for x in neg]
    t_ex, t_fl = recall_at_fpr(dp, dn, 0.005)["threshold"], recall_at_fpr(dp, dn, 0.02)["threshold"]
    out = {"t_exclude": t_ex, "t_flag": t_fl, "dev_recall_exclude": recall_at_fpr(dp, dn, 0.005)["recall"],
           "dev_recall_flag": recall_at_fpr(dp, dn, 0.02)["recall"], "poison": {}, "benign": {}}
    sets = {"signal_source": original_records(), "held_out_regen": regenerated_records(), "held_out_evasion": evasion_records(),
            "held_out_novel": novel_records(), "held_out_zh": zh_records()}
    for name, rs in sets.items():
        sc = [ens(r.text) for r in rs]
        out["poison"][name] = {"n": len(rs), "excluded": rate_with_ci(sum(s >= t_ex for s in sc), len(rs)),
                               "flagged": rate_with_ci(sum(s >= t_fl for s in sc), len(rs))}
        if name == "held_out_novel":
            by = {}
            for r, s in zip(rs, sc):
                g = by.setdefault(r.family, [0, 0, 0]); g[0] += 1; g[1] += s >= t_ex; g[2] += s >= t_fl
            out["poison"][name]["by_mechanism"] = {k: {"n": v[0], "excluded": v[1], "flagged": v[2], "dev_overlap": EVAL_OVERLAP[k]} for k, v in by.items()}
            for ov in (True, False):
                ks = [s for r, s in zip(rs, sc) if EVAL_OVERLAP[r.family] == ov]
                out["poison"][name]["overlap" if ov else "non_overlap"] = {"n": len(ks), "excluded": sum(s >= t_ex for s in ks), "flagged": sum(s >= t_fl for s in ks)}
    for name, pt in {"dataset_arena": dataset_arena(), "convomem": convomem_pools(), "perltqa_zh": perltqa_pools()}.items():
        te = sorted(pt[0], key=lambda p: p.pool_id)[1::2]
        sc = [ens(m.content_text) for p in te for m in p.memories]
        out["benign"][name] = {"n": len(sc), "excluded": rate_with_ci(sum(s >= t_ex for s in sc), len(sc)),
                               "flagged": rate_with_ci(sum(s >= t_fl for s in sc), len(sc))}
    jc.save(); jb.save()
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("DONE")


if __name__ == "__main__":
    main()
