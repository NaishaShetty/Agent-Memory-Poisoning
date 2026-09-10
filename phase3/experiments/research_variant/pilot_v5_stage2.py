"""Phase 3.3-V5 -- Stage 2 pilot (per PHASE3_V5_EXPERIMENT_PLAN.md). n~15-20 real
LoCoMo tasks, Condition B and Condition C (Mem0), comparing V5_BASE vs V5_STRUCTURED
vs V5_VERIFIED vs V5_FULL, all at enable_thinking=False (V1-V4's proven baseline
generation config -- model config is a separate variable, not mixed in here).

Reuses the same 15 real task_ids this project's dev pilots have used throughout
(pilot_qwen3_4b_thinking_v2.py, pilot_reasoning_variants.py, etc.) where available,
for direct comparability -- read from that pilot's own result file rather than
re-selected, so this is not a fresh, potentially-cherry-picked sample.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Mapping

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from phase3.evaluation.agent.content_recall_correctness import evaluate_answer_correctness_content_recall
from phase3.evaluation.agent.date_normalized_correctness import evaluate_answer_correctness_date_normalized
from phase3.evaluation.agent.llm_judge_correctness import evaluate_answer_correctness_llm_judge
from phase3.evaluation.agent.normalized_correctness import evaluate_answer_correctness_normalized
from phase3.evaluation.agent.outcomes import EXECUTION_STATUS_SUCCESS, AgentExecutionResult, evaluate_answer_correctness
from phase3.evaluation.agent_runtime.campaign_v5_runner import V5_BASE, V5_FULL, V5_STRUCTURED, V5_VERIFIED, run_condition_b_v5
from phase3.evaluation.llm.provider import LlamaServerEndpoint, LlamaServerProvider, clean_baseline_generation_config

_DATA_ROOT = _REPO_ROOT / "data" / "processed"
_OUT_DIR = Path(__file__).resolve().parent / "results"
_OUT_DIR.mkdir(parents=True, exist_ok=True)

_PRIOR_PILOT_RESULT = _OUT_DIR / "pilot_qwen3_4b_thinking_v2_n15.json"


class _TaskShim:
    """Minimal object matching what run_condition_b_v5 needs from a task record --
    avoids depending on campaign_formal_runner's own AgentTaskInput construction
    (which has fields V5 doesn't need, e.g. ingest_key_field for retrieval pools)."""
    def __init__(self, task_id, dataset, question, answer, evidence_memory_ids):
        self.task_id = task_id
        self.dataset = dataset
        self.question = question
        self.answer = answer
        self.evidence_memory_ids = evidence_memory_ids


def _load_task_ids():
    if _PRIOR_PILOT_RESULT.exists():
        with _PRIOR_PILOT_RESULT.open(encoding="utf-8") as f:
            d = json.load(f)
        return d.get("task_ids") or list(d.get("results", {}).keys())
    return None


def main():
    def log(msg):
        print(msg, flush=True)

    task_ids = _load_task_ids()
    task_records = {}
    with open(_DATA_ROOT / "locomo" / "task_records.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            task_records[r["task_id"]] = r

    if not task_ids:
        log("No prior pilot task_id list found -- falling back to first 15 LoCoMo tasks with non-empty evidence.")
        task_ids = [tid for tid, t in task_records.items() if t.get("evidence_memory_ids")][:15]

    tasks = [
        _TaskShim(tid, "locomo", task_records[tid]["question"], str(task_records[tid]["answer"]), task_records[tid]["evidence_memory_ids"])
        for tid in task_ids if tid in task_records
    ]
    log(f"Stage 2 pilot: {len(tasks)} real LoCoMo tasks, Condition B only (foundation-independent).")

    endpoint = LlamaServerEndpoint()
    llm_provider = LlamaServerProvider(endpoint)
    identity = llm_provider.verify_server_identity()
    log(f"Server identity verified: {identity}")

    generation_config = clean_baseline_generation_config(max_tokens=256, n_ctx=4096)  # up from V1-V4's 64 -- see PHASE3_V5_DESIGN_RATIONALE.md; still enable_thinking=False

    all_results: Mapping[str, Mapping[str, Any]] = {}
    for cfg in (V5_BASE, V5_STRUCTURED, V5_VERIFIED, V5_FULL):
        log(f"\n=== Running {cfg.label} ===")
        t0 = time.time()
        results = run_condition_b_v5(tasks, llm_provider, generation_config, campaign_id="v5-stage2-pilot", v5_config=cfg)
        wall = time.time() - t0
        log(f"  wall_clock={wall:.1f}s")

        n_norm = n_recall = n_date = n_judge = n_exec_fail = 0
        for r in results:
            tid = r["task_id"]
            all_results.setdefault(tid, {})[cfg.label] = r
            if r["status"] != "SUCCESSFUL_EVALUATION":
                n_exec_fail += 1
                continue
            answer = r["trace"]["agent_output"] if isinstance(r["trace"], dict) else None
            gold = task_records[tid]["answer"]
            exec_result = AgentExecutionResult(
                task_id=tid, condition="B_GOLD_EVIDENCE", answer=answer,
                execution_status=EXECUTION_STATUS_SUCCESS, selected_memory_ids=(), used_memory_ids=None, execution_metadata={},
            )
            if evaluate_answer_correctness_normalized(exec_result, str(gold)).status == "ANSWER_CORRECT":
                n_norm += 1
            if evaluate_answer_correctness_content_recall(exec_result, str(gold)).status == "ANSWER_CORRECT":
                n_recall += 1
            if evaluate_answer_correctness_date_normalized(exec_result, str(gold)).status == "ANSWER_CORRECT":
                n_date += 1
            if evaluate_answer_correctness_llm_judge(exec_result, str(gold), task_records[tid]["question"], llm_provider).status == "ANSWER_CORRECT":
                n_judge += 1
            log(f"  [{tid[:8]}] ans={str(answer)[:80]!r}")

        n = len(results)
        log(f"  {cfg.label}: normalized={n_norm}/{n} content_recall={n_recall}/{n} date_normalized={n_date}/{n} llm_judge={n_judge}/{n} exec_failures={n_exec_fail}")

    out_path = _OUT_DIR / "pilot_v5_stage2_results.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False, default=str)
    log(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
