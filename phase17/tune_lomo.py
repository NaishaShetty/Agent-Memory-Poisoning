"""Fix round 4 -- LEAVE-MECHANISM-OUT estimate of unseen-mechanism generalization on the
enlarged, diverse dev pool (6 + 7 classes + 24 = 37 groups). A few-shot judge never sees a
demonstration from the mechanism it is scoring (or from the same benign kind/pool), so the
recall it reports is an estimate for UNSEEN mechanisms -- the honest quantity."""
import json
from pathlib import Path

import numpy as np

from phase17 import dev_family_sets, dev_sets, dev_sets2
from phase17.arenas import dataset_arena
from phase17.extra_datasets import convomem_pools
from phase17.judge_scores import ScoreJudge, recall_at_fpr, roc_auc

OUT = Path(__file__).parent / "data" / "lomo_results.json"


def dev_pool():
    d1, d2 = dev_sets.load(), dev_sets2.load()
    pos = [{"text": a["text"], "label": 1, "group": a["mechanism"]} for a in d1["attacks"]]
    pos += [{"text": i["text"], "label": 1, "group": "class:" + i["cls"]} for i in dev_family_sets.load()]
    pos += [{"text": a["text"], "label": 1, "group": a["mechanism"]} for a in d2["attacks"]]
    neg = [{"text": b["text"], "label": 0, "group": "ben:" + b["kind"]} for b in d1["benign"]]
    neg += [{"text": b["text"], "label": 0, "group": "ben2:" + b["kind"]} for b in d2["benign"]]
    for name, pt in (("da", dataset_arena()), ("cm", convomem_pools())):
        for p in sorted(pt[0], key=lambda p: p.pool_id)[0::2]:
            neg += [{"text": m.content_text, "label": 0, "group": f"real:{name}:{p.pool_id}"} for m in p.memories]
    return pos, neg


def main():
    pos, neg = dev_pool()
    allx = pos + neg
    res = {"n_pos": len(pos), "n_neg": len(neg), "n_mechanisms": len({p["group"] for p in pos}), "variants": {}}
    for name, judge, lomo in (("concept_zero_shot", ScoreJudge("concept"), False),
                              ("concept_fewshot_k6_LOMO", ScoreJudge("concept", demos=allx, k=6), True),
                              ("concept_fewshot_k12_LOMO", ScoreJudge("concept", demos=allx, k=12), True)):
        sc = lambda x: judge.score(x["text"], x["group"] if lomo else None)
        p = [sc(x) for x in pos]; n = [sc(x) for x in neg]; judge.save()
        r05, r1 = recall_at_fpr(p, n, 0.005), recall_at_fpr(p, n, 0.01)
        by = {}
        for x, s in zip(pos, p):
            by.setdefault(x["group"], []).append(s >= r05["threshold"])
        res["variants"][name] = {"auc": roc_auc(p, n), "recall@0.5%fpr": r05, "recall@1%fpr": r1,
                                 "macro_recall_over_mechanisms@0.5%": float(np.mean([np.mean(v) for v in by.values()])),
                                 "mechanisms_with_zero_recall@0.5%": sorted(k for k, v in by.items() if not any(v))}
        print(name, {k: v for k, v in res["variants"][name].items() if k != "mechanisms_with_zero_recall@0.5%"}, flush=True)
    OUT.write_text(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
