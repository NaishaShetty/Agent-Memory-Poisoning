"""Phase 3.3-V3 Round 1 -- n=15 pilot for deterministic relative-time resolution
(§5.1 of PHASE3_V3_DIAGNOSIS_AND_ROADMAP.md), Condition B only (isolates the
mechanism from retrieval entirely, per the pilot design in the roadmap).

Compares TWO variants against the same 15 real task_ids used throughout this
investigation:
- V2_BASELINE: exact frozen V2 Condition B config (timestamp-prepended evidence,
  no arithmetic resolution) -- re-run fresh here (not reused from the frozen
  dataset) so this pilot's baseline and treatment arm are generated under
  IDENTICAL wall-clock conditions, removing the reproducibility-non-determinism
  confound documented in PHASE3_V2_VALIDATION_FINALIZATION_REPORT.md section 8.
- V2_PLUS_TEMPORAL_RESOLUTION: V2 Condition B's exact same evidence content, PLUS
  the new `temporal_resolution.render_content_with_temporal_annotations()` applied
  on top -- isolates exactly one new variable.

No prompt change, no model change, no budget change (DEFAULT_SYSTEM_PROMPT,
max_tokens=64, n_ctx=4096 -- identical to V2's own Condition B generation config).
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
from phase3.evaluation.foundations.temporal_resolution import render_content_with_temporal_annotations
from phase3.evaluation.llm.provider import LlamaServerEndpoint, LlamaServerProvider, clean_baseline_generation_config

_DATA_ROOT = _REPO_ROOT / "data" / "processed"
_OUT_DIR = Path(__file__).resolve().parent / "results"
_OUT_DIR.mkdir(parents=True, exist_ok=True)

FROZEN_DATASET_PATH = (
    _REPO_ROOT / "phase3" / "experiments" / "results" / "canonical_store" / "dataset_full"
    / "clean_agent_dataset_locomo_120x2.json"
)
N_TASKS = 15
GEN_MAX_TOKENS = 64


def _load_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def _select_task_ids(n: int) -> List[str]:
    with FROZEN_DATASET_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    mem0_task_ids = sorted({r["task_id"] for r in data if r["foundation"] == "MEM0"})
    return mem0_task_ids[:n]


def _build_task_records(task_ids):
    task_records_by_id = {t["task_id"]: t for t in _load_jsonl(_DATA_ROOT / "locomo" / "task_records.jsonl")}
    tasks = []
    for tid in task_ids:
        t = task_records_by_id[tid]
        tasks.append({"task_id": tid, "question": t["question"], "answer": str(t["answer"]), "evidence_memory_ids": t["evidence_memory_ids"]})
    return tasks


def _v2_content(row: Mapping[str, Any]) -> str:
    if row.get("source_timestamp"):
        return f"[{row['source_timestamp']}] {row['source_role']}: {row['content']}"
    return f"{row['source_role']}: {row['content']}"


def _v3_content(row: Mapping[str, Any]) -> str:
    base = _v2_content(row)
    if row.get("source_timestamp"):
        annotated = render_content_with_temporal_annotations(f"{row['source_role']}: {row['content']}", row["source_timestamp"])
        if annotated != f"{row['source_role']}: {row['content']}":
            # append the resolution annotation onto the V2-style (timestamp-prefixed) content
            resolved_part = annotated[len(f"{row['source_role']}: {row['content']}"):]
            return f"{base}{resolved_part}"
    return base


def _run_variant(task, memory_rows_by_id, llm_provider, content_fn, results, log, variant_name):
    evidence_items = [
        {"memory_id": f"evidence-slot-{i+1}", "content": content_fn(memory_rows_by_id[eid])}
        for i, eid in enumerate(task["evidence_memory_ids"]) if eid in memory_rows_by_id
    ]
    context = build_agent_visible_context(condition=CONDITION_GOLD_EVIDENCE, task_id=task["task_id"], prompt=task["question"], memory_items=evidence_items)
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
    gold = task["answer"]
    exact = evaluate_answer_correctness(exec_result, gold)
    norm = evaluate_answer_correctness_normalized(exec_result, gold)
    recall = evaluate_answer_correctness_content_recall(exec_result, gold)

    results.setdefault(task["task_id"], {})[variant_name] = {
        "answer": answer, "latency_sec": latency,
        "exact_status": exact.status, "normalized_status": norm.status, "content_recall_status": recall.status,
        "evidence_shown": [item["content"] for item in evidence_items],
    }
    log(f"  [{variant_name}] exact={exact.status} norm={norm.status} recall={recall.status} ans={str(answer)[:80]!r}")


def main():
    def log(msg):
        print(msg, flush=True)

    task_ids = _select_task_ids(N_TASKS)
    tasks = _build_task_records(task_ids)
    memory_rows_by_id = {row["memory_id"]: row for row in _load_jsonl(_DATA_ROOT / "locomo" / "memory_records.jsonl")}
    log(f"Selected {len(tasks)} real task_ids (same as every prior round): {task_ids}")

    endpoint = LlamaServerEndpoint()
    llm_provider = LlamaServerProvider(endpoint)
    identity = llm_provider.verify_server_identity()
    log(f"Server identity verified: {identity}")

    results: Mapping[str, Mapping[str, Any]] = {}
    for i, task in enumerate(tasks):
        log(f"\n=== Task {i+1}/{len(tasks)}: {task['task_id']} — {task['question']!r} (gold={task['answer']!r}) ===")
        _run_variant(task, memory_rows_by_id, llm_provider, _v2_content, results, log, "V2_BASELINE")
        _run_variant(task, memory_rows_by_id, llm_provider, _v3_content, results, log, "V2_PLUS_TEMPORAL_RESOLUTION")

    out_path = _OUT_DIR / "pilot_temporal_resolution_b_n15.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump({"task_ids": task_ids, "tasks": tasks, "results": results}, f, indent=2, ensure_ascii=False)
    log(f"\nWrote {out_path}")

    log("\n=== SUMMARY ===")
    for variant_name in ("V2_BASELINE", "V2_PLUS_TEMPORAL_RESOLUTION"):
        n_exact = sum(1 for t in results.values() if t.get(variant_name, {}).get("exact_status") == "ANSWER_CORRECT")
        n_norm = sum(1 for t in results.values() if t.get(variant_name, {}).get("normalized_status") == "ANSWER_CORRECT")
        n_recall = sum(1 for t in results.values() if t.get(variant_name, {}).get("content_recall_status") == "ANSWER_CORRECT")
        n = sum(1 for t in results.values() if variant_name in t)
        log(f"  {variant_name}: exact={n_exact}/{n} normalized={n_norm}/{n} content_recall={n_recall}/{n}")


if __name__ == "__main__":
    main()
