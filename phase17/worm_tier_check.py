"""Does the `worm` judge tier do what it claims, and what does it cost? (round 4)

Two claims need independent checking before the tier ships inside B13:

 1. The ORIGINAL 30 `memory_worm` instances (`novel_attacks*.py`) do not actually implement
    the mechanism they are labelled with ("the note instructs the assistant to copy or
    re-insert this same note into any new memory or summary it writes"). If true, every
    memory_worm detection number this project has published describes a population that was
    never the attack it claimed to be -- a substantive correction, not a tuning detail.
 2. The tier's false-positive cost on benign text, including the hard benign sets: ordinary
    standing instructions ("always CC my wife on invoices") are the obvious confusion, since
    they are also imperative and also about the future.

Both are measured here directly, on the corrected instances (`memory_worm_regen.py`) and
every benign population in `eval_populations.py`.
"""
from __future__ import annotations

import json
from pathlib import Path

from phase17.stats import rate_with_ci

OUT = Path(__file__).parent / "data" / "worm_tier_check.json"


def run() -> dict:
    from phase17.eval_populations import benign_populations
    from phase17.memory_worm_regen import worm_regen_records
    from phase17.novel_attacks_extended import novel_records_extended
    from phase17.semantic_detector import LLMJudge

    judge = LLMJudge("worm")
    original = [r.text for r in novel_records_extended() if r.family == "memory_worm"]
    corrected = [r.text for r in worm_regen_records()]
    out = {
        "original_memory_worm": {"n": len(original), "flagged_by_worm_tier": rate_with_ci(
            sum(judge.flag(t) for t in original), len(original))},
        "corrected_memory_worm": {"n": len(corrected), "flagged_by_worm_tier": rate_with_ci(
            sum(judge.flag(t) for t in corrected), len(corrected))},
        "benign_false_positives": {},
    }
    for name, texts in benign_populations().items():
        out["benign_false_positives"][name] = rate_with_ci(sum(judge.flag(t) for t in texts), len(texts))
    judge.save()
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    print("original memory_worm flagged:", r["original_memory_worm"]["flagged_by_worm_tier"]["k"], "/",
          r["original_memory_worm"]["n"])
    print("corrected memory_worm flagged:", r["corrected_memory_worm"]["flagged_by_worm_tier"]["k"], "/",
          r["corrected_memory_worm"]["n"])
    for k, v in r["benign_false_positives"].items():
        print(f"  benign {k:55s} {v['k']}/{v['n']}")
    print("DONE")
