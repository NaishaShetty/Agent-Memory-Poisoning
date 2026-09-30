"""Phase 17 (external review round 4, 2026-09-29) -- one shared definition of the TEST
populations every defense (B12, B13, and the external baselines in `external_baselines.py`)
is compared on, so no comparison can silently use a different slice.

Nothing here is dev data: every attack population is a held-out split, and every benign
population is either the ODD half of a pooled dataset (the even half is `tune_lomo.dev_pool`,
which calibrated B12's thresholds and calibrates every baseline's here) or a dedicated
held-out benign set.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

DATA = Path(__file__).parent / "data"


def attack_populations() -> Dict[str, List[str]]:
    from phase17.chinese_native_attacks import native_zh_records
    from phase17.external_attacks import external_records
    from phase17.gemini_authored_attacks import gemini_records
    from phase17.novel_attacks import novel_records
    from phase17.novel_attacks_extended import novel_records_extra_only
    from phase17.poison_sets import evasion_records, regenerated_records

    ext = external_records()
    out = {
        "novel_60 (qwen)": [r.text for r in novel_records()],
        "novel_new120 (qwen, disjoint scenarios)": [r.text for r in novel_records_extra_only()],
        "gemini_authored_30": [r.text for r in gemini_records()],
        "evasion_47": [r.text for r in evasion_records()],
        "trackb_regen_9": [r.text for r in regenerated_records()],
        "zh_native_30 (gemini)": [r.text for r in native_zh_records()],
        "external_all_266": [r.text for r in ext],
    }
    for src in sorted({r.family for r in ext}):
        out[f"  {src}"] = [r.text for r in ext if r.family == src]
    return out


def benign_populations() -> Dict[str, List[str]]:
    from phase17.arenas import dataset_arena
    from phase17.confirmed_human_benign_check import CONFIRMED_HUMAN_BENIGN
    from phase17.extra_datasets import convomem_pools
    from phase17.legitimate_imperatives import LEGITIMATE_IMPERATIVES
    from phase17.perltqa import perltqa_pools
    from phase17.steer_holdout_check import HOLDOUT_BENIGN_NAMED_PARTY

    out = {}
    for name, pt in (("dataset_arena_test_half", dataset_arena()), ("convomem_test_half", convomem_pools()),
                     ("perltqa_zh_test_half", perltqa_pools())):
        te = sorted(pt[0], key=lambda p: p.pool_id)[1::2]
        out[name] = [m.content_text for p in te for m in p.memories]
    # These three sets store their items in different shapes upstream (plain strings, and
    # (id, text) pairs); `_text` normalizes them so every population here is a list of str.
    out["legitimate_imperatives_40"] = [_text(x) for x in LEGITIMATE_IMPERATIVES]
    out["confirmed_human_20"] = [_text(x) for x in CONFIRMED_HUMAN_BENIGN]
    out["named_party_preferences_6"] = [_text(x) for x in HOLDOUT_BENIGN_NAMED_PARTY]
    g = json.loads((DATA / "gemini_authored_benign_results.json").read_text(encoding="utf-8"))["samples"]["gemini_fresh"]
    out["gemini_benign_5 (only 5 of 30 texts were persisted)"] = [_text(x) for x in g]
    return out


def _text(x) -> str:
    if isinstance(x, str):
        return x
    if isinstance(x, dict):
        return x.get("text", "")
    return x[-1]  # (id, text) pair


# Benign sets that make up the "ordinary content" FPR used for matched-FPR comparisons.
# The legitimate-imperative / named-party sets are reported separately: they are deliberately
# hard cases, not a sample of ordinary memory content.
# The Gemini benign set is deliberately NOT in this reference pool: only 5 of its 30 texts
# were ever persisted (`gemini_authored_benign_results.json` stored the aggregate and a
# 5-item sample), and an n=5 population would move a matched-FPR reference around for no
# statistical reason. It is still scored and reported on its own.
ORDINARY_BENIGN = ("dataset_arena_test_half", "convomem_test_half", "perltqa_zh_test_half",
                   "confirmed_human_20")
