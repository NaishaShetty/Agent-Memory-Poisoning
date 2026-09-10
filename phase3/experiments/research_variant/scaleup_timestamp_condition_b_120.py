"""Phase 3.3-RESEARCH Round 8 -- SCALE-UP: timestamp injection on Condition B (gold
evidence) at full 120-task scale, purely a REASONING test (Condition B has NO retrieval
step at all -- gold evidence content is handed directly, per
`gold_evidence_runner.py`'s own docstring: "hands evidence content directly, skipping
retrieval and selection entirely"). This isolates whether the model can resolve a
relative-time expression to an absolute date when given an anchor timestamp, with
retrieval quality removed from the picture entirely.

WHY THIS ROUND, PRECISELY
--------------------------------------------------------------------------------
The read-only failure-mode classification of all 120 real Condition-B answers (see
PHASE3_RESEARCH_IMPROVEMENT_PLAN.md) found that in 16/120 (13.3%) of ALL tasks, the
model's own answer already contained a relative-time expression extracted correctly
from evidence (e.g. "last week," "four months ago") but was never resolved to the
absolute date the gold answer requires -- BECAUSE the real per-record `source_timestamp`
field is never surfaced anywhere in the agent's context. This round tests the direct,
targeted fix at the same 120-task scale the diagnosis itself used, not a fresh n=15
sample.

V1 baseline is NOT re-run. The frozen 240-record dataset already contains real,
recorded Condition-B (NO_TIMESTAMP) answers for all 120 MEM0 tasks -- this script only
executes the NEW WITH_TIMESTAMP variant; a separate analysis pass compares against the
existing frozen numbers using all three metrics now available (exact-match, normalized
bidirectional-substring, and the new content-word-recall metric), never conflating the
three.

No prompt change, no model change, no budget change (DEFAULT_SYSTEM_PROMPT,
max_tokens=64, n_ctx=4096 -- identical to V1's own Condition-B generation config).

Incrementally checkpointed after every task (a prior scale-up run for Condition C was
killed mid-run by a session exit and lost all unwritten work -- this script writes its
partial JSON after every single task and resumes from it if re-launched).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, List, Mapping

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from phase3.evaluation.agent.conditions import CONDITION_GOLD_EVIDENCE, build_agent_visible_context
from phase3.evaluation.agent.content_recall_correctness import evaluate_answer_correctness_content_recall
from phase3.evaluation.agent.normalized_correctness import evaluate_answer_correctness_normalized
from phase3.evaluation.agent.outcomes import (
    EXECUTION_STATUS_ERROR,
    EXECUTION_STATUS_SUCCESS,
    AgentExecutionResult,
    evaluate_answer_correctness,
)
from phase3.evaluation.agent_runtime.messages import DEFAULT_SYSTEM_PROMPT, render_messages
from phase3.evaluation.agent_runtime.runner import RunConfiguration, generate_with_retries
from phase3.evaluation.llm.provider import LlamaServerEndpoint, LlamaServerProvider, clean_baseline_generation_config

_DATA_ROOT = _REPO_ROOT / "data" / "processed"
_OUT_DIR = Path(__file__).resolve().parent / "results"
_OUT_DIR.mkdir(parents=True, exist_ok=True)

FROZEN_DATASET_PATH = (
    _REPO_ROOT / "phase3" / "experiments" / "results" / "canonical_store" / "dataset_full"
    / "clean_agent_dataset_locomo_120x2.json"
)
GEN_MAX_TOKENS = 64


def _load_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def _all_mem0_task_ids():
    with FROZEN_DATASET_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return sorted({r["task_id"] for r in data if r["foundation"] == "MEM0"})


def _build_task_records(task_ids):
    task_records_by_id = {t["task_id"]: t for t in _load_jsonl(_DATA_ROOT / "locomo" / "task_records.jsonl")}
    tasks = []
    for tid in task_ids:
        t = task_records_by_id[tid]
        tasks.append({"task_id": tid, "question": t["question"], "answer": t["answer"], "evidence_memory_ids": t["evidence_memory_ids"]})
    return tasks


def _content_text(row: Mapping[str, Any]) -> str:
    if row.get("source_timestamp"):
        return f"[{row['source_timestamp']}] {row['source_role']}: {row['content']}"
    return f"{row['source_role']}: {row['content']}"


def _run_with_timestamp_b(task, memory_rows_by_id, llm_provider, results, log):
    evidence_items = [
        {"memory_id": f"evidence-slot-{i+1}", "content": _content_text(memory_rows_by_id[eid])}
        for i, eid in enumerate(task["evidence_memory_ids"]) if eid in memory_rows_by_id
    ]
    context = build_agent_visible_context(
        condition=CONDITION_GOLD_EVIDENCE, task_id=task["task_id"], prompt=task["question"],
        memory_items=evidence_items,
    )
    messages = render_messages(context, DEFAULT_SYSTEM_PROMPT)
    gen_config = clean_baseline_generation_config(n_ctx=4096, max_tokens=GEN_MAX_TOKENS)
    run_config = RunConfiguration(llm_provider=llm_provider, generation_config=gen_config, system_prompt=DEFAULT_SYSTEM_PROMPT)
    t0 = time.time()
    answer, attempts = generate_with_retries(messages, run_config)
    latency = time.time() - t0

    exec_result = AgentExecutionResult(
        task_id=task["task_id"], condition=CONDITION_GOLD_EVIDENCE, answer=answer,
        execution_status=EXECUTION_STATUS_SUCCESS if answer is not None else EXECUTION_STATUS_ERROR,
        selected_memory_ids=(), used_memory_ids=None, execution_metadata={"attempts": len(attempts)},
    )
    gold = str(task["answer"])
    exact = evaluate_answer_correctness(exec_result, gold)
    norm = evaluate_answer_correctness_normalized(exec_result, gold)
    recall = evaluate_answer_correctness_content_recall(exec_result, gold)

    results[task["task_id"]] = {
        "answer": answer, "latency_sec": latency,
        "exact_status": exact.status, "normalized_status": norm.status, "content_recall_status": recall.status,
    }
    log(f"  [B_WITH_TIMESTAMP] exact={exact.status} norm={norm.status} recall={recall.status} ans={str(answer)[:70]!r}")


def main():
    def log(msg):
        print(msg, flush=True)

    task_ids = _all_mem0_task_ids()
    tasks = _build_task_records(task_ids)
    memory_rows_by_id = {row["memory_id"]: row for row in _load_jsonl(_DATA_ROOT / "locomo" / "memory_records.jsonl")}
    log(f"Selected ALL {len(tasks)} real MEM0 task_ids (Condition B, WITH_TIMESTAMP scale-up).")

    endpoint = LlamaServerEndpoint()
    llm_provider = LlamaServerProvider(endpoint)
    identity_check = llm_provider.verify_server_identity()
    log(f"Server identity verified: {identity_check}")

    out_path = _OUT_DIR / "scaleup_timestamp_condition_b_n120.json"
    results = {}
    if out_path.exists():
        with out_path.open("r", encoding="utf-8") as f:
            prior = json.load(f)
        results = prior.get("results_B_with_timestamp", {})
        log(f"Resuming from existing checkpoint: {len(results)}/{len(tasks)} tasks already completed.")

    def _checkpoint():
        with out_path.open("w", encoding="utf-8") as f:
            json.dump({"task_ids": task_ids, "tasks": tasks, "results_B_with_timestamp": results}, f, indent=2, ensure_ascii=False)

    t_start = time.time()
    for i, task in enumerate(tasks):
        if task["task_id"] in results:
            continue
        log(f"\n=== Task {i+1}/{len(tasks)}: {task['task_id']} — {task['question']!r} (gold={task['answer']!r}) ===")
        _run_with_timestamp_b(task, memory_rows_by_id, llm_provider, results, log)
        _checkpoint()
        if len(results) % 10 == 0:
            elapsed = time.time() - t_start
            log(f"--- progress: {len(results)}/{len(tasks)} total completed, elapsed this run={elapsed/60:.1f}min ---")

    log(f"\nFinal write complete: {out_path}")

    n_exact = sum(1 for t in results.values() if t["exact_status"] == "ANSWER_CORRECT")
    n_norm = sum(1 for t in results.values() if t["normalized_status"] == "ANSWER_CORRECT")
    n_recall = sum(1 for t in results.values() if t["content_recall_status"] == "ANSWER_CORRECT")
    n = len(results)
    log(f"\n=== SUMMARY: Condition B WITH_TIMESTAMP (n={n}) ===")
    log(f"  exact={n_exact}/{n}  normalized={n_norm}/{n}  content_recall={n_recall}/{n}")


if __name__ == "__main__":
    main()
