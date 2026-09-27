"""Phase 17 (generalization fix) -- utility cost of the judge-based exclusion:
the fraction of REAL Track-A QA target memories (the memory a benign question
needs) that the judge would exclude, plus the whole distractor pool. This is the
retrieval-support loss upper bound (an excluded target cannot be retrieved)."""

from __future__ import annotations

import json
from pathlib import Path

from phase17.semantic_detector import LLMJudge
from phase17.stats import rate_with_ci
from phase17.workloads import lme_cases_with_type, locomo_cases_with_category

OUT = Path(__file__).parent / "data" / "gstack_utility.json"


def run() -> dict:
    judge = LLMJudge("broad")
    out = {}
    for name, cases in (("locomo", [c for c, _ in locomo_cases_with_category()]), ("longmemeval", [c for c, _ in lme_cases_with_type()])):
        t_hit = 0
        for c in cases:
            ids = set(getattr(c, "target_memory_ids", None) or (c.target_memory_id,))
            t_hit += any(judge.flag(t) for i, t in c.pool_items if i in ids)  # any target lost = case loses support
        judge.save()
        out[name] = {"target_memories_excluded": rate_with_ci(t_hit, len(cases))}
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(run())
    print("DONE")
