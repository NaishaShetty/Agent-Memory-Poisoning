"""Fix round 4 -- evaluate the stacked detector on every held-out split (benign FPR on odd pools)."""
import json
from pathlib import Path

from phase17.arenas import dataset_arena
from phase17.extra_datasets import convomem_pools
from phase17.novel_attacks import novel_records
from phase17.perltqa import perltqa_pools
from phase17.poison_sets import evasion_records, original_records, regenerated_records
from phase17.stacked_detector import StackedDetector
from phase17.stats import rate_with_ci
from phase17.translation import zh_records
from phase17.tune_lomo import dev_pool
from phase17.run_scores_eval import EVAL_OVERLAP

OUT = Path(__file__).parent / "data" / "stacked_results.json"


def main():
    pos, neg = dev_pool()
    allx = pos + neg
    det = StackedDetector()
    out = {"fit": det.fit([x["text"] for x in allx], [x["label"] for x in allx], [x["group"] for x in allx]), "poison": {}, "benign": {}}
    sets = {"signal_source": original_records(), "held_out_regen": regenerated_records(), "held_out_evasion": evasion_records(),
            "held_out_novel": novel_records(), "held_out_zh": zh_records()}
    for name, rs in sets.items():
        tx = [r.text for r in rs]
        ex, fl = det.decide(tx, 0.005), det.decide(tx, 0.02)
        out["poison"][name] = {"n": len(rs), "excluded": rate_with_ci(sum(ex), len(rs)), "flagged": rate_with_ci(sum(fl), len(rs))}
        if name == "held_out_novel":
            by = {}
            for r, e, f in zip(rs, ex, fl):
                b = by.setdefault(r.family, [0, 0, 0]); b[0] += 1; b[1] += e; b[2] += f
            out["poison"][name]["by_mechanism"] = {k: {"n": v[0], "excluded": v[1], "flagged": v[2], "dev_overlap_old": EVAL_OVERLAP[k]} for k, v in by.items()}
    for name, pt in {"dataset_arena": dataset_arena(), "convomem": convomem_pools(), "perltqa_zh": perltqa_pools()}.items():
        te = sorted(pt[0], key=lambda p: p.pool_id)[1::2]
        tx = [m.content_text for p in te for m in p.memories]
        ex, fl = det.decide(tx, 0.005), det.decide(tx, 0.02)
        out["benign"][name] = {"n": len(tx), "excluded": rate_with_ci(sum(ex), len(tx)), "flagged": rate_with_ci(sum(fl), len(tx))}
    det.save(Path(__file__).parent / "data" / "stacked_model.json")
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("DONE")


if __name__ == "__main__":
    main()
