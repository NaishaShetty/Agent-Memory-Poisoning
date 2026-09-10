"""Phase 3.3-V3 Round 2 -- FULL category-2 (temporal, question_type=2) population,
n=24 -- the entire relevant subpopulation among the 120-task formal sample, not a
further sample. Per PHASE3_V3_ROUND1_TEMPORAL_RESOLUTION_PILOT.md's decision: the
n=15/n=2 pilot showed real, judge-validated positive signal but was underpowered;
this is the real test.

Reuses every function from `pilot_temporal_resolution_b.py` unmodified -- only the
task-selection logic changes (all 24 real question_type=2 MEM0 tasks, not the
first-15-by-sort-order set).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pilot_temporal_resolution_b as base  # noqa: E402
from phase3.evaluation.agent.llm_judge_correctness import evaluate_answer_correctness_llm_judge  # noqa: E402
from phase3.evaluation.agent.outcomes import AgentExecutionResult, EXECUTION_STATUS_SUCCESS  # noqa: E402
from phase3.evaluation.llm.provider import LlamaServerEndpoint, LlamaServerProvider  # noqa: E402

_DATA_ROOT = _REPO_ROOT / "data" / "processed"


def _select_category2_task_ids():
    with base.FROZEN_DATASET_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    mem0_task_ids = sorted({r["task_id"] for r in data if r["foundation"] == "MEM0"})
    task_records = {t["task_id"]: t for t in base._load_jsonl(_DATA_ROOT / "locomo" / "task_records.jsonl")}
    return [tid for tid in mem0_task_ids if task_records[tid].get("question_type") == "2"]


def main():
    def log(msg):
        print(msg, flush=True)

    task_ids = _select_category2_task_ids()
    tasks = base._build_task_records(task_ids)
    memory_rows_by_id = {row["memory_id"]: row for row in base._load_jsonl(_DATA_ROOT / "locomo" / "memory_records.jsonl")}
    log(f"Selected ALL {len(tasks)} real question_type=2 (temporal) MEM0 tasks: {task_ids}")

    endpoint = LlamaServerEndpoint()
    llm_provider = LlamaServerProvider(endpoint)
    identity = llm_provider.verify_server_identity()
    log(f"Server identity verified: {identity}")

    results = {}
    for i, task in enumerate(tasks):
        log(f"\n=== Task {i+1}/{len(tasks)}: {task['task_id']} — {task['question']!r} (gold={task['answer']!r}) ===")
        base._run_variant(task, memory_rows_by_id, llm_provider, base._v2_content, results, log, "V2_BASELINE")
        base._run_variant(task, memory_rows_by_id, llm_provider, base._v3_content, results, log, "V2_PLUS_TEMPORAL_RESOLUTION")

    # LLM-judge pass on every task for both variants -- since content-recall/normalized
    # metrics are word-overlap-based and §_ round-1 found they can't credit a correctly
    # -computed point-date against a range-phrased gold answer, judge every case here.
    log("\n=== LLM-judge pass (both variants, all 24 tasks) ===")
    for task in tasks:
        for variant in ("V2_BASELINE", "V2_PLUS_TEMPORAL_RESOLUTION"):
            row = results[task["task_id"]][variant]
            er = AgentExecutionResult(task_id=task["task_id"], condition="B", answer=row["answer"],
                                       execution_status=EXECUTION_STATUS_SUCCESS, selected_memory_ids=(),
                                       used_memory_ids=None, execution_metadata={})
            judge_result = evaluate_answer_correctness_llm_judge(er, task["answer"], task["question"], llm_provider)
            row["llm_judge_status"] = judge_result.status
            row["llm_judge_raw"] = judge_result.detail.get("raw_judge_output")
        log(f"  {task['task_id'][:8]}: BASELINE_judge={results[task['task_id']]['V2_BASELINE']['llm_judge_status']}  "
            f"RESOLVED_judge={results[task['task_id']]['V2_PLUS_TEMPORAL_RESOLUTION']['llm_judge_status']}")

    out_path = base._OUT_DIR / "pilot_temporal_resolution_b_category2_full_n24.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump({"task_ids": task_ids, "tasks": tasks, "results": results}, f, indent=2, ensure_ascii=False)
    log(f"\nWrote {out_path}")

    log("\n=== SUMMARY (n=24, question_type=2 only) ===")
    for variant_name in ("V2_BASELINE", "V2_PLUS_TEMPORAL_RESOLUTION"):
        n_exact = sum(1 for t in results.values() if t.get(variant_name, {}).get("exact_status") == "ANSWER_CORRECT")
        n_norm = sum(1 for t in results.values() if t.get(variant_name, {}).get("normalized_status") == "ANSWER_CORRECT")
        n_recall = sum(1 for t in results.values() if t.get(variant_name, {}).get("content_recall_status") == "ANSWER_CORRECT")
        n_judge = sum(1 for t in results.values() if t.get(variant_name, {}).get("llm_judge_status") == "ANSWER_CORRECT")
        n = len(results)
        log(f"  {variant_name}: exact={n_exact}/{n} normalized={n_norm}/{n} content_recall={n_recall}/{n} llm_judge={n_judge}/{n}")


if __name__ == "__main__":
    main()
