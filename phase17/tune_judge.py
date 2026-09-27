"""DEV-only tuning of the judge: variants, and a two-tier scheme (flag = first
judge; exclude = first AND `confirm`). Negatives = dev benign + real benign from
EVEN pools (English); eval FPR is later measured only on ODD pools."""
import json
from pathlib import Path
from phase17 import dev_sets, dev_family_sets
from phase17.arenas import dataset_arena
from phase17.extra_datasets import convomem_pools
from phase17.semantic_detector import LLMJudge

OUT = Path(__file__).parent / "data" / "judge_tuning.json"


def main():
    d = dev_sets.load()
    pos = [a["text"] for a in d["attacks"]] + [i["text"] for i in dev_family_sets.load()]
    neg = [b["text"] for b in d["benign"]]
    for pt in (dataset_arena(), convomem_pools()):
        ordered = sorted(pt[0], key=lambda p: p.pool_id)
        neg += [m.content_text for p in ordered[0::2] for m in p.memories]
    res = {"n_pos": len(pos), "n_neg": len(neg), "variants": {}}
    flags = {}
    for v in ("broad", "concept", "confirm"):
        j = LLMJudge(v)
        flags[v] = ([j.flag(t) for t in pos], [j.flag(t) for t in neg])
        j.save()
        res["variants"][v] = {"recall": sum(flags[v][0]), "fp": sum(flags[v][1])}
    for a, b in (("broad", "confirm"), ("concept", "confirm")):
        res["variants"][f"{a}&{b}"] = {"recall": sum(x and y for x, y in zip(flags[a][0], flags[b][0])),
                                       "fp": sum(x and y for x, y in zip(flags[a][1], flags[b][1]))}
    OUT.write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=1))

if __name__ == "__main__":
    main()
