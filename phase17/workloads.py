"""Phase 17 -- the real workload axis (Phase 12's dropped axis, definition
(b): real task types), `PHASE17_PLAN.md` B3.

WHY OFFLINE FIRST: utility cost in this project arises ONLY when a defense
excludes content (URS=1.0 whenever the defended context equals B0's; Phase 14's
`reuse_if_context_unchanged`). So the decision layer alone determines where a
workload could pay a cost, and it needs no LLM calls -- letting this
stratification use EVERY real QA pair (LoCoMo tasks 1-9: all pairs with an
answer; LongMemEval: all 479 usable items) instead of a 300-task pilot. The
LLM is only run afterwards on the (few) tasks where a target memory WAS
excluded, to measure the actual answer change.

Categories are real fields: LoCoMo `category` 1-5 (names per the LoCoMo paper:
1 multi-hop, 2 temporal, 3 open-domain, 4 single-hop, 5 adversarial -- the
mapping is NOT in the data file, so it is cited, not verified here) and
LongMemEval `question_type`. DISCLOSED: Phase 14's Track A pool only includes
QA pairs that have an `answer` field, which silently excludes LoCoMo category 5
(adversarial pairs carry `adversarial_answer` instead) -- Track A never
measured that workload.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from phase11.relational_signals.locomo_qa_counterfactuals import COUNTERFACTUAL_TASK_RANGE
from phase14.defended_retrieval import apply_defense
from phase14.track_a_benign import N_DISTRACTORS, TrackACase
from phase17.stats import rate_with_ci

LOCOMO_CATEGORY_NAMES = {1: "multi-hop", 2: "temporal", 3: "open-domain", 4: "single-hop", 5: "adversarial"}
LOCOMO = Path("data/raw/locomo/locomo10.json")
LME = Path("data/raw/longmemeval/longmemeval_oracle.json")


def locomo_cases_with_category() -> List[Tuple[TrackACase, int]]:
    raw = json.loads(LOCOMO.read_text(encoding="utf-8"))
    flat = []
    for tid in COUNTERFACTUAL_TASK_RANGE:
        for qa in raw[tid].get("qa", []):
            if qa.get("question") and qa.get("answer"):
                flat.append((tid, qa["question"], str(qa["answer"]), qa["category"]))
    cases = []
    for i, (tid, q, a, cat) in enumerate(flat):
        target_id = f"LOCOMO-T{tid}-{i}"
        pool = [(target_id, f"{q} {a}")]
        off = 1
        while len(pool) < 1 + N_DISTRACTORS:
            j = (i + off) % len(flat)
            off += 1
            if j == i:
                continue
            pool.append((f"LOCOMO-T{flat[j][0]}-{j}", f"{flat[j][1]} {flat[j][2]}"))
        cases.append((TrackACase(f"p17-locomo-{i}", q, a, target_id, tuple(pool)), cat))
    return cases


def lme_cases_with_type() -> List[Tuple[object, str]]:
    from phase14.track_a_longmemeval import build_track_a_longmemeval_cases

    raw = json.loads(LME.read_text(encoding="utf-8"))
    cases = build_track_a_longmemeval_cases(len(raw))
    out = []
    for c in cases:
        idx = int(c.task_id.rsplit("-", 1)[1])
        out.append((c, raw[idx]["question_type"]))
    return out


def stratify(cases_with_cat, configs: Sequence[str], target_ids_of=lambda c: c.target_memory_ids if hasattr(c, "target_memory_ids") else (c.target_memory_id,)):
    """{config: {category: {n, target_excluded k, any_excluded k}}} plus the
    list of (case, config) where a target was excluded (for the LLM step)."""
    agg: Dict[str, Dict[str, dict]] = {c: defaultdict(lambda: {"n": 0, "target": 0, "any": 0}) for c in configs}
    excluded_cases: List[Tuple[object, str, str]] = []
    for case, cat in cases_with_cat:
        tids = set(target_ids_of(case))
        for cfg in configs:
            _, decisions = apply_defense(cfg, case.pool_items)
            cell = agg[cfg][str(cat)]
            cell["n"] += 1
            t_ex = any(d.excluded and d.memory_id in tids for d in decisions)
            cell["target"] += int(t_ex)
            cell["any"] += int(any(d.excluded for d in decisions))
            if t_ex:
                excluded_cases.append((case, cfg, str(cat)))
    return agg, excluded_cases


def to_report(agg) -> dict:
    return {cfg: {cat: {"n": v["n"], "target_excluded": rate_with_ci(v["target"], v["n"]),
                        "any_excluded": rate_with_ci(v["any"], v["n"])} for cat, v in cats.items()}
            for cfg, cats in agg.items()}


__all__ = ["locomo_cases_with_category", "lme_cases_with_type", "stratify", "to_report", "LOCOMO_CATEGORY_NAMES"]
