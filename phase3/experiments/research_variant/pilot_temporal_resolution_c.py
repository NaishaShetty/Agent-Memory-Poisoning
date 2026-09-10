"""Phase 3.3-V3 Round 3 -- deterministic temporal resolution applied to Condition C
(retrieved memory), tested on the full 24-task question_type=2 (temporal)
subpopulation -- the same real tasks Round 2 validated for Condition B.

DIFFERENT MECHANISM FROM ROUND 11's ALREADY-NEGATIVE FINDING
--------------------------------------------------------------------------------
Round 11 (`scaleup_retrieval_hybrid_no_timestamp_120.py`) found that BLANKET
timestamp-prefixing every retrieved memory item hurt Condition C. This round tests a
materially different mechanism: `temporal_resolution.py` only ever adds an
annotation when a CLOSED-SET relative-time PATTERN is actually detected in that
specific item's content -- most retrieved items get no annotation at all, unlike
blanket prefixing. Testing this is a genuinely new question, not a re-run of
Round 11's negative result.

CONFIGURATION
--------------------------------------------------------------------------------
Both variants use V2's validated Condition-C mechanism (pool=20 retrieval, hybrid
top-8 selection, fixed weights 0.5/0.3/0.2) -- unmodified. The ONLY difference is
whether `temporal_resolution.render_content_with_temporal_annotations()` is applied
to each SELECTED item's content before rendering (V3 arm) or not (V2 baseline arm,
re-run fresh here for a same-wall-clock-conditions comparison).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, List, Mapping, Tuple

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from phase3.evaluation.agent.conditions import CONDITION_RETRIEVED_MEMORY, build_agent_visible_context
from phase3.evaluation.agent.content_recall_correctness import evaluate_answer_correctness_content_recall
from phase3.evaluation.agent.llm_judge_correctness import evaluate_answer_correctness_llm_judge
from phase3.evaluation.agent.normalized_correctness import evaluate_answer_correctness_normalized
from phase3.evaluation.agent.outcomes import (
    EXECUTION_STATUS_ERROR,
    EXECUTION_STATUS_SUCCESS,
    AgentExecutionResult,
    evaluate_answer_correctness,
)
from phase3.evaluation.agent_runtime.messages import DEFAULT_SYSTEM_PROMPT, render_messages
from phase3.evaluation.agent_runtime.runner import RunConfiguration, _extract_content_text, _extract_memory_id, generate_with_retries
from phase3.evaluation.foundations.adapter import FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL
from phase3.evaluation.foundations.hybrid_selection import DEFAULT_TOP_K, RETRIEVAL_POOL_SIZE_N, select_by_hybrid_score
from phase3.evaluation.foundations.temporal_resolution import render_content_with_temporal_annotations
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


def _select_category2_task_ids():
    with FROZEN_DATASET_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    mem0_task_ids = sorted({r["task_id"] for r in data if r["foundation"] == "MEM0"})
    task_records = {t["task_id"]: t for t in _load_jsonl(_DATA_ROOT / "locomo" / "task_records.jsonl")}
    return [tid for tid in mem0_task_ids if task_records[tid].get("question_type") == "2"]


def _build_task_records(task_ids):
    task_records_by_id = {t["task_id"]: t for t in _load_jsonl(_DATA_ROOT / "locomo" / "task_records.jsonl")}
    memory_session = {}
    for row in _load_jsonl(_DATA_ROOT / "locomo" / "memory_records.jsonl"):
        memory_session[row["memory_id"]] = (row["conversation_id"], row["session_id"])
    tasks = []
    for tid in task_ids:
        t = task_records_by_id[tid]
        sessions = {memory_session[eid] for eid in t["evidence_memory_ids"]}
        (conv_id, session_id) = next(iter(sessions))
        tasks.append({"task_id": tid, "question": t["question"], "answer": str(t["answer"]),
                       "evidence_memory_ids": t["evidence_memory_ids"], "conversation_id": conv_id, "session_id": session_id})
    return tasks


def _ingest_pool(conv_id, session_id):
    for row in _load_jsonl(_DATA_ROOT / "locomo" / "memory_records.jsonl"):
        if row["conversation_id"] == conv_id and row["session_id"] == session_id:
            yield row


def _run_variant_c(task, pool_rows, llm_provider, foundation, apply_temporal_resolution, results, log, variant_name):
    retrieve_field = foundation.retrieve({"text": task["question"], "user_id": f"rv3c-{task['task_id']}"}, top_k=RETRIEVAL_POOL_SIZE_N)
    memory_items: List[Mapping[str, Any]] = []
    if retrieve_field.availability in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
        raw_items = retrieve_field.value or []
        retrieved_ids = tuple(mid for mid in (_extract_memory_id(i) for i in raw_items) if mid is not None)

        candidates: List[Tuple[str, str]] = []
        source_id_by_foundation_id: Mapping[str, str] = {}
        for mid in retrieved_ids:
            inspect_field = foundation.inspect_memory(mid)
            if inspect_field.availability in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
                native = inspect_field.value or {}
                candidates.append((mid, _extract_content_text(native)))
                metadata = native.get("metadata") if isinstance(native, Mapping) else None
                source_id = metadata.get("source_memory_id") if isinstance(metadata, Mapping) else None
                if source_id is not None:
                    source_id_by_foundation_id[mid] = str(source_id)

        selection_result = select_by_hybrid_score(task["question"], candidates, top_k=DEFAULT_TOP_K)
        content_by_id = dict(candidates)
        for c in selection_result.selected:
            content = content_by_id[c.memory_id]
            if apply_temporal_resolution:
                source_id = source_id_by_foundation_id.get(c.memory_id)
                source_ts = pool_rows.get(source_id, {}).get("source_timestamp") if source_id else None
                content = render_content_with_temporal_annotations(content, source_ts)
            memory_items.append({"memory_id": c.memory_id, "content": content})

    context = build_agent_visible_context(condition=CONDITION_RETRIEVED_MEMORY, task_id=task["task_id"], prompt=task["question"], memory_items=memory_items)
    messages = render_messages(context, DEFAULT_SYSTEM_PROMPT)
    gen_config = clean_baseline_generation_config(n_ctx=4096, max_tokens=GEN_MAX_TOKENS)
    run_config = RunConfiguration(llm_provider=llm_provider, generation_config=gen_config, system_prompt=DEFAULT_SYSTEM_PROMPT)
    t0 = time.time()
    answer, attempts = generate_with_retries(messages, run_config)
    latency = time.time() - t0

    exec_result = AgentExecutionResult(
        task_id=task["task_id"], condition=CONDITION_RETRIEVED_MEMORY, answer=answer,
        execution_status=EXECUTION_STATUS_SUCCESS if answer is not None else EXECUTION_STATUS_ERROR,
        selected_memory_ids=tuple(item["memory_id"] for item in memory_items), used_memory_ids=None,
        execution_metadata={"attempts": len(attempts)},
    )
    gold = task["answer"]
    exact = evaluate_answer_correctness(exec_result, gold)
    norm = evaluate_answer_correctness_normalized(exec_result, gold)
    recall = evaluate_answer_correctness_content_recall(exec_result, gold)
    judge = evaluate_answer_correctness_llm_judge(exec_result, gold, task["question"], llm_provider)

    results.setdefault(task["task_id"], {})[variant_name] = {
        "answer": answer, "latency_sec": latency,
        "exact_status": exact.status, "normalized_status": norm.status,
        "content_recall_status": recall.status, "llm_judge_status": judge.status,
        "llm_judge_raw": judge.detail.get("raw_judge_output"),
    }
    log(f"  [{variant_name}] norm={norm.status} recall={recall.status} judge={judge.status} ans={str(answer)[:80]!r}")


def main():
    def log(msg):
        print(msg, flush=True)

    task_ids = _select_category2_task_ids()
    tasks = _build_task_records(task_ids)
    log(f"Selected ALL {len(tasks)} real question_type=2 (temporal) MEM0 tasks (Condition C): {task_ids}")

    endpoint = LlamaServerEndpoint()
    llm_provider = LlamaServerProvider(endpoint)
    identity = llm_provider.verify_server_identity()
    log(f"Server identity verified: {identity}")

    from phase3.evaluation.foundations_real.mem0_real_adapter import RealMem0Adapter

    results: Mapping[str, Mapping[str, Any]] = {}
    for i, task in enumerate(tasks):
        log(f"\n=== Task {i+1}/{len(tasks)}: {task['task_id']} — {task['question']!r} (gold={task['answer']!r}) ===")
        pool_rows_list = list(_ingest_pool(task["conversation_id"], task["session_id"]))
        pool_rows_by_id = {row["memory_id"]: row for row in pool_rows_list}

        foundation = RealMem0Adapter()
        init_field = foundation.initialize({"embedding_model": "sentence-transformers/all-MiniLM-L6-v2", "collection_name": f"research_variant_r3c_{task['task_id']}_mem0"})
        if init_field.availability != FOUNDATION_AVAILABLE:
            log(f"  init failed: {init_field.note}")
            continue
        foundation.reset()
        for row in pool_rows_list:
            foundation.add_memory(memory_id=row["memory_id"], content={"text": f"{row['source_role']}: {row['content']}"},
                                   metadata={"user_id": f"rv3c-{task['task_id']}", "source_memory_id": row["memory_id"]})

        _run_variant_c(task, pool_rows_by_id, llm_provider, foundation, False, results, log, "V2_BASELINE")
        _run_variant_c(task, pool_rows_by_id, llm_provider, foundation, True, results, log, "V2_PLUS_TEMPORAL_RESOLUTION")
        foundation.shutdown()

    out_path = _OUT_DIR / "pilot_temporal_resolution_c_category2_n24.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump({"task_ids": task_ids, "tasks": tasks, "results": results}, f, indent=2, ensure_ascii=False)
    log(f"\nWrote {out_path}")

    log("\n=== SUMMARY (n=24, question_type=2, Condition C) ===")
    for variant_name in ("V2_BASELINE", "V2_PLUS_TEMPORAL_RESOLUTION"):
        n_exact = sum(1 for t in results.values() if t.get(variant_name, {}).get("exact_status") == "ANSWER_CORRECT")
        n_norm = sum(1 for t in results.values() if t.get(variant_name, {}).get("normalized_status") == "ANSWER_CORRECT")
        n_recall = sum(1 for t in results.values() if t.get(variant_name, {}).get("content_recall_status") == "ANSWER_CORRECT")
        n_judge = sum(1 for t in results.values() if t.get(variant_name, {}).get("llm_judge_status") == "ANSWER_CORRECT")
        n = len(results)
        log(f"  {variant_name}: exact={n_exact}/{n} normalized={n_norm}/{n} content_recall={n_recall}/{n} llm_judge={n_judge}/{n}")


if __name__ == "__main__":
    main()
