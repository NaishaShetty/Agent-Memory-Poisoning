"""Phase 3.3-E -- post-hoc canonical-metric analysis over `campaign_3_3e_result.json`.

Reuses the EXISTING, UNMODIFIED Phase 3.2 metric functions
(`metrics.retrieval.recall_at_k`/`reciprocal_rank`, `metrics.evidence.evidence_precision`/
`evidence_recall`/`evidence_coverage`, `metrics.selection.strict_tsr`) over the
already-collected campaign traces' resolved-source-space retrieved/selected ids. This is
purely a reporting/aggregation step -- it computes nothing the frozen metrics don't
already define, and it does not touch `phase3/evaluation/metrics/` at all.

For Condition B (Mem0, METADATA_LOOKUP identity strategy), resolved-source-space ids
live under `trace["identity"]["retrieved_memories_source_space"]`/
`"selected_memories_source_space"`. For Condition C (A-MEM, DIRECT_ASSIGNMENT strategy),
the base trace's `retrieved_memories`/`selected_memories` ARE ALREADY source ids (see
`campaign_runner.py`'s own comment on this) -- there is no separate `identity` block for
A-MEM traces in this campaign (they were produced by `evaluate_and_trace()`, not
`evaluate_and_trace_with_identity()`), so this script reads the base fields directly for C.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from phase3.evaluation.agent_runtime.campaign_sampling import build_pilot_sample
from phase3.evaluation.metrics.evidence import evidence_coverage, evidence_precision, evidence_recall
from phase3.evaluation.metrics.retrieval import reciprocal_rank, recall_at_k
from phase3.evaluation.metrics.selection import strict_tsr

RESULTS_PATH = _REPO_ROOT / "phase3" / "experiments" / "results" / "campaign_3_3e_result.json"
ANALYSIS_OUTPUT_PATH = _REPO_ROOT / "phase3" / "experiments" / "results" / "campaign_3_3e_analysis.json"


def _resolved_ids(trace: Mapping[str, Any], condition: str):
    if condition == "B":
        identity = trace.get("identity", {})
        return (
            tuple(identity.get("retrieved_memories_source_space", ())),
            tuple(identity.get("selected_memories_source_space", ())),
        )
    # Condition C (A-MEM): base fields already ARE source-space, per DIRECT_ASSIGNMENT.
    return tuple(trace.get("retrieved_memories", ())), tuple(trace.get("selected_memories", ()))


def analyze() -> Mapping[str, Any]:
    campaign = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    gold_by_task = {t.task_id: tuple(t.evidence_memory_ids) for t in build_pilot_sample()}

    per_task_condition = []
    for task_entry in campaign["tasks"]:
        task_id = task_entry["task_id"]
        gold_ids = gold_by_task.get(task_id, ())
        for condition in ("A", "B", "C"):
            run = task_entry["runs"].get(condition)
            if not run or "trace" not in run:
                per_task_condition.append(
                    {"task_id": task_id, "dataset": task_entry["dataset"], "condition": condition,
                     "status": run.get("status") if run else "NOT_RUN"}
                )
                continue
            trace = run["trace"]

            if condition == "A":
                retrieved, selected = (), ()
            else:
                retrieved, selected = _resolved_ids(trace, condition)

            row = {
                "task_id": task_id, "dataset": task_entry["dataset"], "condition": condition,
                "failure_stage": trace.get("resolved_evaluation", {}).get("failure_stage", trace["failure_stage"]),
                "answer_correctness": trace["evaluation_result"]["success_status"],
                "gold_ids": list(gold_ids),
                "retrieved_source_space": list(retrieved),
                "selected_source_space": list(selected),
            }
            if condition != "A" and gold_ids:
                row["recall_at_5"] = recall_at_k(retrieved, gold_ids, 5).value
                rr = reciprocal_rank(retrieved, gold_ids)
                row["reciprocal_rank"] = rr.value
                row["strict_tsr"] = strict_tsr(selected, gold_ids).value
                ep = evidence_precision(selected, gold_ids)
                row["evidence_precision"] = ep.value
                er = evidence_recall(selected, gold_ids)
                row["evidence_recall"] = er.value
                ec = evidence_coverage(retrieved, gold_ids)
                row["evidence_coverage"] = ec.value
            per_task_condition.append(row)

    # -------------------------------------------------------------------
    # Aggregation by condition (A/B/C) -- means over DEFINED values only, count reported.
    # -------------------------------------------------------------------
    def _agg(condition: str, field: str):
        values = [r[field] for r in per_task_condition if r.get("condition") == condition and r.get(field) is not None]
        return {"mean": (sum(values) / len(values)) if values else None, "n": len(values)}

    def _failure_stage_distribution(condition: str):
        dist: dict = {}
        for r in per_task_condition:
            if r.get("condition") != condition or "failure_stage" not in r:
                continue
            dist[r["failure_stage"]] = dist.get(r["failure_stage"], 0) + 1
        return dist

    summary = {
        "per_task_condition": per_task_condition,
        "aggregate": {
            cond: {
                "answer_correctness_distribution": {
                    status: sum(1 for r in per_task_condition if r.get("condition") == cond and r.get("answer_correctness") == status)
                    for status in {r.get("answer_correctness") for r in per_task_condition if r.get("condition") == cond}
                },
                "failure_stage_distribution": _failure_stage_distribution(cond),
                **({
                    "recall_at_5": _agg(cond, "recall_at_5"),
                    "mrr": _agg(cond, "reciprocal_rank"),
                    "strict_tsr": _agg(cond, "strict_tsr"),
                    "evidence_precision": _agg(cond, "evidence_precision"),
                    "evidence_recall": _agg(cond, "evidence_recall"),
                    "evidence_coverage": _agg(cond, "evidence_coverage"),
                } if cond != "A" else {}),
            }
            for cond in ("A", "B", "C")
        },
    }

    ANALYSIS_OUTPUT_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


if __name__ == "__main__":
    result = analyze()
    print(json.dumps(result["aggregate"], indent=2))
