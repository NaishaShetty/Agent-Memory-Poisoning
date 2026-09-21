"""Phase 11.z Section 3 -- truthful-declarative counterfactuals at real
scale, the explicitly-authorized follow-on the Y-report named but did not
build: "the much larger controlled counterfactual set that would be needed
to test [the format confound] properly ... explicitly flagged as future
work, not undertaken here."

WHAT THIS IS
--------------------------------------------------------------------------------
`PHASE11_Y_RELATIONAL_SIGNAL_REPORT.md` Section 7-10 (Family A) showed that
neighborhood-agreement AUROC (0.938) collapses to near-chance (truthful mean
0.293 vs poison mean 0.215, both far below genuine benign 0.413) once 7
hand-built truthful counterfactuals -- the SAME real LoCoMo questions,
rendered in the SAME `"{question} {gold_answer}"` declarative template the
QA-pair-based attacks (DSRM/FARMA/MPBench/Sleeper) use, but with the REAL
correct answer instead of a forged one -- are compared. 7 examples is too
few to know whether the small residual gap (0.293 vs 0.215) is real or
noise. This module builds that comparison set at the scale LoCoMo's own real
`qa` field actually supports.

REAL DATA, NOT FABRICATED
--------------------------------------------------------------------------------
Every question and every answer below is real LoCoMo text, read directly
from `data/raw/locomo/locomo10.json`'s own `qa` field (1,986 real
question/answer pairs across the 10 real tasks -- confirmed present, never
previously read by any Phase 11 module; every existing caller
(`load_db_locomo`) only ever reads the `conversation` field). Only the
template rendering (`f"{question} {answer}"`) is new construction, and it is
not new invention -- it is the exact same rendering the Y-report's own 7
hand-built counterfactuals already used, applied at scale instead of by
hand.

TASK RANGE -- MATCHES real_corpus.py's OWN DISJOINTNESS DISCIPLINE
--------------------------------------------------------------------------------
Tasks 1-9 only (task 0 excluded), the same range `real_benign_scenarios()`
already uses and for the same reason: the original 15 hand-authored poison
seeds (DSRM/FARMA/MPBench/MemoryGraft/Sleeper) target task 0, so task-0 QA
pairs are held back from this benign-side construction to avoid overlap
with poison-targeted content.

WHAT THIS DOES NOT DO
--------------------------------------------------------------------------------
Does not touch `held_out_pools()`. Does not add these counterfactuals to
any training pool consumed by the GNN/GLN (`dev_pools()`/`training_pools()`
are unmodified). This module produces a read-only text pool for signal
DISCOVERY only, mirroring `semantic_relations.py`'s own task-0 diagnostic
precedent (real data, read-only, never persisted as a ScenarioPool that
feeds the graph builder).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

LOCOMO_PATH = Path("data/raw/locomo/locomo10.json")

# Same task range real_benign_scenarios() uses; task 0 held back for the
# same overlap-avoidance reason.
COUNTERFACTUAL_TASK_RANGE = tuple(range(1, 10))

# Per-task cap: real_benign_scenarios() itself uses 15 real turns per task
# (its own natural per-conversation session boundary, per the Option 2
# pool-restructuring follow-on) -- matched here so the truthful-declarative
# comparison set is the same real order of magnitude as the benign
# reference it is being compared against, not an arbitrary larger number
# chosen to make a result look more scaled-up than it is.
PER_TASK_CAP = 15


@dataclass(frozen=True)
class QACounterfactual:
    task_id: int
    question: str
    answer: str

    @property
    def declarative_text(self) -> str:
        return f"{self.question} {self.answer}"


_CACHE: Dict[int, List[QACounterfactual]] = {}


def _load_raw_qa() -> List[dict]:
    with LOCOMO_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def truthful_declarative_counterfactuals(
    task_ids: tuple = COUNTERFACTUAL_TASK_RANGE, per_task_cap: int = PER_TASK_CAP,
) -> Dict[int, List[QACounterfactual]]:
    """Real LoCoMo QA pairs for `task_ids`, capped at `per_task_cap` per
    task (first N in the real file's own order -- not randomly cherry-picked,
    not filtered by any property of the answer), rendered as
    `"{question} {answer}"`. Returns {task_id: [QACounterfactual, ...]}."""
    if not _CACHE:
        raw = _load_raw_qa()
        for task_id, task in enumerate(raw):
            qa_pairs = task.get("qa", [])
            items = [
                QACounterfactual(task_id=task_id, question=qa["question"], answer=qa["answer"])
                for qa in qa_pairs
                if qa.get("question") and qa.get("answer")
            ]
            _CACHE[task_id] = items
    return {
        task_id: _CACHE.get(task_id, [])[:per_task_cap]
        for task_id in task_ids
    }


def flat_counterfactual_pool(task_ids: tuple = COUNTERFACTUAL_TASK_RANGE, per_task_cap: int = PER_TASK_CAP) -> List[QACounterfactual]:
    by_task = truthful_declarative_counterfactuals(task_ids, per_task_cap)
    return [c for items in by_task.values() for c in items]


__all__ = [
    "QACounterfactual",
    "COUNTERFACTUAL_TASK_RANGE",
    "PER_TASK_CAP",
    "truthful_declarative_counterfactuals",
    "flat_counterfactual_pool",
]
