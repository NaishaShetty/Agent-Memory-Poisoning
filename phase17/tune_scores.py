"""DEV-only comparison of score-based judges (zero-shot vs dev-demo few-shot,
ensembles). Leave-one-out demos (a dev item never sees itself). Writes
`score_tuning.json`."""
import json
from pathlib import Path

import numpy as np

from phase17 import dev_family_sets, dev_sets
from phase17.arenas import dataset_arena
from phase17.extra_datasets import convomem_pools
from phase17.judge_scores import ScoreJudge, recall_at_fpr, roc_auc

OUT = Path(__file__).parent / "data" / "score_tuning.json"


def dev_items():
    d = dev_sets.load()
    pos = [{"text": a["text"], "label": 1, "overlaps": a["overlaps"]} for a in d["attacks"]]
    pos += [{"text": i["text"], "label": 1, "overlaps": "family"} for i in dev_family_sets.load()]
    neg = [{"text": b["text"], "label": 0} for b in d["benign"]]
    for pt in (dataset_arena(), convomem_pools()):
        ordered = sorted(pt[0], key=lambda p: p.pool_id)
        neg += [{"text": m.content_text, "label": 0} for p in ordered[0::2] for m in p.memories]
    return pos, neg


def main():
    pos, neg = dev_items()
    allx = pos + neg
    res = {"n_pos": len(pos), "n_neg": len(neg), "variants": {}}
    scores = {}
    for name, judge in (("concept", ScoreJudge("concept")), ("broad", ScoreJudge("broad")),
                        ("concept+fewshot", ScoreJudge("concept", demos=allx)), ("broad+fewshot", ScoreJudge("broad", demos=allx))):
        p = [judge.score(x["text"]) for x in pos]
        n = [judge.score(x["text"]) for x in neg]
        judge.save()
        scores[name] = (p, n)
        res["variants"][name] = {"auc": roc_auc(p, n), **{f"recall@fpr{f}": recall_at_fpr(p, n, f) for f in (0.005, 0.01, 0.02)}}
        print(name, res["variants"][name], flush=True)
    for a, b in (("concept", "broad"), ("concept+fewshot", "broad+fewshot")):
        p = list(np.add(scores[a][0], scores[b][0]) / 2)
        n = list(np.add(scores[a][1], scores[b][1]) / 2)
        res["variants"][f"mean({a},{b})"] = {"auc": roc_auc(p, n), **{f"recall@fpr{f}": recall_at_fpr(p, n, f) for f in (0.005, 0.01, 0.02)}}
        print(f"mean({a},{b})", res["variants"][f"mean({a},{b})"], flush=True)
    OUT.write_text(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
