"""Phase 17 (generalization fix) -- evaluate the new detectors on every held-out
split and every benign population. Dev-only choices (see `semantic_detector.py`):
EmbeddingDetector trained on dev; judge variant = highest dev recall subject to
dev-benign FP <= 2% (chosen on DEV, recorded below). Nothing here is tuned on eval."""

from __future__ import annotations

import json
from pathlib import Path

from phase17 import dev_sets
from phase17.arenas import dataset_arena
from phase17.extra_datasets import convomem_pools
from phase17.novel_attacks import novel_records
from phase17.perltqa import perltqa_pools
from phase17.poison_sets import evasion_records, original_records, regenerated_records
from phase17.semantic_detector import EmbeddingDetector, LLMJudge
from phase17.stats import paired_delta, rate_with_ci
from phase17.translation import zh_records

OUT = Path(__file__).parent / "data" / "generalized_results.json"


def _texts(pools_truth):
    pools, _ = pools_truth
    return [m.content_text for p in pools for m in p.memories]


def run(judge_variant: str = "broad") -> dict:
    d = dev_sets.load()
    emb = EmbeddingDetector()
    fit = emb.fit([a["text"] for a in d["attacks"]], [b["text"] for b in d["benign"]])
    judge = LLMJudge(judge_variant)
    sets = {"signal_source": original_records(), "held_out_regen": regenerated_records(), "held_out_evasion": evasion_records(),
            "held_out_novel": novel_records(), "held_out_zh": zh_records()}
    out = {"dev_fit": fit, "judge_variant": judge_variant, "poison": {}, "benign": {}}
    vecs = {}
    for name, recs in sets.items():
        texts = [r.text for r in recs]
        e, j = emb.flags(texts), [judge.flag(t) for t in texts]
        judge.save()
        vecs[name] = {"embedding": e, "judge": j, "either": [a or b for a, b in zip(e, j)]}
        out["poison"][name] = {k: rate_with_ci(sum(v), len(v)) for k, v in vecs[name].items()}
        if name in ("held_out_novel", "held_out_evasion"):
            by = {}
            for r, a, b in zip(recs, e, j):
                g = by.setdefault(r.family if name == "held_out_novel" else r.variant, [0, 0, 0])
                g[0] += 1; g[1] += a; g[2] += b
            out["poison"][name + "_by_group"] = {k: {"n": v[0], "embedding": v[1], "judge": v[2]} for k, v in by.items()}
    novel = novel_records()
    zh = zh_records()
    parents = {r.scenario_id: r for r in original_records() + regenerated_records() + novel}
    en = [judge.flag(parents[z.parent_id].text) for z in zh]
    out["language_judge_paired"] = paired_delta(en, vecs["held_out_zh"]["judge"])
    for name, pt in {"dataset_arena(locomo/lme/msc...)": dataset_arena(), "convomem": convomem_pools(), "perltqa_zh": perltqa_pools()}.items():
        texts = _texts(pt)
        e, j = emb.flags(texts), [judge.flag(t) for t in texts]
        judge.save()
        out["benign"][name] = {"n": len(texts), "embedding": rate_with_ci(sum(e), len(texts)), "judge": rate_with_ci(sum(j), len(texts)),
                               "either": rate_with_ci(sum(a or b for a, b in zip(e, j)), len(texts))}
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    run()
    print("DONE")
