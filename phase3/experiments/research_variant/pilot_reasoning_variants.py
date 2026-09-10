"""Phase 3.3-RESEARCH Round 3 -- attacking the reasoning/answer-formulation bottleneck
directly (56.7-point headroom below the Gold-Evidence ceiling, vs. only 3.7 points lost
to retrieval -- see PHASE3_RESEARCH_IMPROVEMENT_PLAN.md). Two specific, diagnosed fixes,
tested independently and combined:

1. TIMESTAMP INJECTION -- real, previously-undiscovered gap confirmed directly in
   `campaign_runner.py::_run_condition_mem0()`: ingestion metadata never includes a
   timestamp, so the model has no way to resolve relative-time evidence ("last week")
   into the absolute-date answers LoCoMo's gold answers frequently require. LoCoMo's own
   UMR records carry a real `source_timestamp` field (human-readable absolute time,
   `timestamp_type: "absolute"` for every LoCoMo record -- confirmed by direct read of
   data/processed/locomo/memory_records.jsonl) that is simply never surfaced. This round
   injects it into both the Condition-B evidence text and the Condition-C ingested
   metadata + rendered context.

2. REFINED PROMPT (V_PROMPT2) -- Round 1's V_FORMAT prompt was a genuine but flawed
   attempt: it helped when it reduced verbose hedging, but its RIGID forced-refusal
   phrase ("reply exactly: 'Not stated...'") gave the model an easy escape hatch that
   caused new failures. V_PROMPT2 keeps the "no hedging preamble" instruction (the part
   that worked) and removes the rigid forced-refusal line, replacing it with a softer,
   own-words instruction. Also explicitly tells the model to use any given date to
   compute relative-date answers, since that only makes sense once timestamps are
   actually present in context.

Retrieval mechanism held FIXED at V1's plain top-5 (not the Round 2b top-8-by-score
winner) so this round isolates the reasoning/prompt/content variable cleanly. A final
combined round should stack the retrieval winner with whatever wins here.

Same 15 real task_ids as Rounds 1-2, for direct comparability.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, List, Mapping, Optional, Tuple

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from phase3.evaluation.agent.conditions import CONDITION_GOLD_EVIDENCE, CONDITION_RETRIEVED_MEMORY, build_agent_visible_context
from phase3.evaluation.agent.normalized_correctness import evaluate_answer_correctness_normalized
from phase3.evaluation.agent.outcomes import (
    EXECUTION_STATUS_ERROR,
    EXECUTION_STATUS_SUCCESS,
    AgentExecutionResult,
    evaluate_answer_correctness,
)
from phase3.evaluation.agent_runtime.messages import DEFAULT_SYSTEM_PROMPT, render_messages
from phase3.evaluation.agent_runtime.runner import (
    RunConfiguration,
    _extract_content_text,
    _extract_memory_id,
    generate_with_retries,
    select_from_retrieved,
)
from phase3.evaluation.foundations.adapter import FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL
from phase3.evaluation.llm.provider import (
    LlamaServerEndpoint,
    LlamaServerProvider,
    clean_baseline_generation_config,
)

_DATA_ROOT = _REPO_ROOT / "data" / "processed"
_OUT_DIR = Path(__file__).resolve().parent / "results"
_OUT_DIR.mkdir(parents=True, exist_ok=True)

FROZEN_DATASET_PATH = (
    _REPO_ROOT / "phase3" / "experiments" / "results" / "canonical_store" / "dataset_full"
    / "clean_agent_dataset_locomo_120x2.json"
)
N_TASKS = 15
GEN_MAX_TOKENS = 64  # Round-1 finding: budget alone doesn't matter; hold fixed at V1's value

VARIANT_PROMPT2_SYSTEM_PROMPT = (
    "You are answering a factual question using ONLY the retrieved/provided memory "
    "content. Give the direct factual answer as a short phrase or sentence -- no "
    "preamble, no meta-commentary about what the memories do or do not contain. If a "
    "date or time is given alongside a memory, use it to compute a relative date "
    "(e.g. 'last week', 'next month') into an absolute date if the question asks for "
    "one. If the memories truly contain nothing relevant to the question, say so "
    "briefly, in your own words."
)

PROMPT_VARIANTS: Mapping[str, str] = {
    "BASELINE": DEFAULT_SYSTEM_PROMPT,
    "V_PROMPT2": VARIANT_PROMPT2_SYSTEM_PROMPT,
}
CONTENT_VARIANTS = ("NO_TIMESTAMP", "WITH_TIMESTAMP")


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
    memory_session = {}
    for row in _load_jsonl(_DATA_ROOT / "locomo" / "memory_records.jsonl"):
        memory_session[row["memory_id"]] = (row["conversation_id"], row["session_id"])

    tasks = []
    for tid in task_ids:
        t = task_records_by_id[tid]
        sessions = {memory_session[eid] for eid in t["evidence_memory_ids"]}
        (conv_id, session_id) = next(iter(sessions))
        tasks.append({
            "task_id": tid, "question": t["question"], "answer": t["answer"],
            "evidence_memory_ids": t["evidence_memory_ids"],
            "conversation_id": conv_id, "session_id": session_id,
        })
    return tasks


def _ingest_pool(conv_id: str, session_id: str):
    for row in _load_jsonl(_DATA_ROOT / "locomo" / "memory_records.jsonl"):
        if row["conversation_id"] == conv_id and row["session_id"] == session_id:
            yield row


def _content_text(row: Mapping[str, Any], with_timestamp: bool) -> str:
    if with_timestamp and row.get("source_timestamp"):
        return f"[{row['source_timestamp']}] {row['source_role']}: {row['content']}"
    return f"{row['source_role']}: {row['content']}"


def _score(task, exec_result):
    exact = evaluate_answer_correctness(exec_result, task["answer"])
    norm = evaluate_answer_correctness_normalized(exec_result, task["answer"])
    return exact, norm


def _run_condition_b(task, llm_provider, memory_rows_by_id, results, log):
    for content_variant in CONTENT_VARIANTS:
        with_ts = content_variant == "WITH_TIMESTAMP"
        evidence_items = [
            {"memory_id": f"evidence-slot-{i+1}", "content": _content_text(memory_rows_by_id[eid], with_ts)}
            for i, eid in enumerate(task["evidence_memory_ids"]) if eid in memory_rows_by_id
        ]
        for prompt_variant, system_prompt in PROMPT_VARIANTS.items():
            variant_name = f"B_{content_variant}_{prompt_variant}"
            context = build_agent_visible_context(
                condition=CONDITION_GOLD_EVIDENCE, task_id=task["task_id"], prompt=task["question"],
                memory_items=evidence_items,
            )
            messages = render_messages(context, system_prompt)
            gen_config = clean_baseline_generation_config(n_ctx=4096, max_tokens=GEN_MAX_TOKENS)
            run_config = RunConfiguration(llm_provider=llm_provider, generation_config=gen_config, system_prompt=system_prompt)
            t0 = time.time()
            answer, attempts = generate_with_retries(messages, run_config)
            latency = time.time() - t0
            exec_result = AgentExecutionResult(
                task_id=task["task_id"], condition=CONDITION_GOLD_EVIDENCE, answer=answer,
                execution_status=EXECUTION_STATUS_SUCCESS if answer is not None else EXECUTION_STATUS_ERROR,
                selected_memory_ids=(), used_memory_ids=None, execution_metadata={"attempts": len(attempts)},
            )
            exact, norm = _score(task, exec_result)
            results.setdefault(task["task_id"], {})[variant_name] = {
                "answer": answer, "latency_sec": latency,
                "exact_status": exact.status, "normalized_status": norm.status,
            }
            log(f"  [{variant_name}] norm={norm.status} exact={exact.status} ans={str(answer)[:70]!r}")


def _run_condition_c(task, llm_provider, results, log):
    from phase3.evaluation.foundations_real.mem0_real_adapter import RealMem0Adapter

    for content_variant in CONTENT_VARIANTS:
        with_ts = content_variant == "WITH_TIMESTAMP"
        foundation = RealMem0Adapter()
        init_field = foundation.initialize(
            {"embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
             "collection_name": f"research_variant_r3_{content_variant}_{task['task_id']}_mem0"}
        )
        if init_field.availability != FOUNDATION_AVAILABLE:
            log(f"  [C/{content_variant}] init failed: {init_field.note}")
            continue
        foundation.reset()

        for row in _ingest_pool(task["conversation_id"], task["session_id"]):
            metadata = {"user_id": f"rv3-{task['task_id']}", "source_memory_id": row["memory_id"]}
            if with_ts and row.get("source_timestamp"):
                metadata["source_timestamp"] = row["source_timestamp"]
            foundation.add_memory(
                memory_id=row["memory_id"],
                content={"text": _content_text(row, with_ts)},
                metadata=metadata,
            )

        retrieve_field = foundation.retrieve({"text": task["question"], "user_id": f"rv3-{task['task_id']}"}, top_k=5)
        memory_items: List[Mapping[str, Any]] = []
        if retrieve_field.availability in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
            raw_items = retrieve_field.value or []
            retrieved_ids = tuple(mid for mid in (_extract_memory_id(i) for i in raw_items) if mid is not None)
            selected_ids = select_from_retrieved(retrieved_ids, top_k=5)
            for mid in selected_ids:
                inspect_field = foundation.inspect_memory(mid)
                if inspect_field.availability in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
                    memory_items.append({"memory_id": mid, "content": _extract_content_text(inspect_field.value or {})})

        for prompt_variant, system_prompt in PROMPT_VARIANTS.items():
            variant_name = f"C_{content_variant}_{prompt_variant}"
            context = build_agent_visible_context(
                condition=CONDITION_RETRIEVED_MEMORY, task_id=task["task_id"], prompt=task["question"],
                memory_items=memory_items,
            )
            messages = render_messages(context, system_prompt)
            gen_config = clean_baseline_generation_config(n_ctx=4096, max_tokens=GEN_MAX_TOKENS)
            run_config = RunConfiguration(llm_provider=llm_provider, generation_config=gen_config, system_prompt=system_prompt)
            t0 = time.time()
            answer, attempts = generate_with_retries(messages, run_config)
            latency = time.time() - t0
            exec_result = AgentExecutionResult(
                task_id=task["task_id"], condition=CONDITION_RETRIEVED_MEMORY, answer=answer,
                execution_status=EXECUTION_STATUS_SUCCESS if answer is not None else EXECUTION_STATUS_ERROR,
                selected_memory_ids=tuple(item["memory_id"] for item in memory_items), used_memory_ids=None,
                execution_metadata={"attempts": len(attempts)},
            )
            exact, norm = _score(task, exec_result)
            results.setdefault(task["task_id"], {})[variant_name] = {
                "answer": answer, "latency_sec": latency,
                "exact_status": exact.status, "normalized_status": norm.status,
            }
            log(f"  [{variant_name}] norm={norm.status} exact={exact.status} ans={str(answer)[:70]!r}")

        foundation.shutdown()


def main():
    def log(msg):
        print(msg, flush=True)

    task_ids = _select_task_ids(N_TASKS)
    tasks = _build_task_records(task_ids)
    memory_rows_by_id = {row["memory_id"]: row for row in _load_jsonl(_DATA_ROOT / "locomo" / "memory_records.jsonl")}
    log(f"Selected {len(tasks)} real task_ids (same as Rounds 1-2): {task_ids}")

    endpoint = LlamaServerEndpoint()
    llm_provider = LlamaServerProvider(endpoint)
    identity_check = llm_provider.verify_server_identity()
    log(f"Server identity verified: {identity_check}")

    results: Mapping[str, Mapping[str, Any]] = {}
    for i, task in enumerate(tasks):
        log(f"\n=== Task {i+1}/{len(tasks)}: {task['task_id']} — {task['question']!r} (gold={task['answer']!r}) ===")
        _run_condition_b(task, llm_provider, memory_rows_by_id, results, log)
        _run_condition_c(task, llm_provider, results, log)

    out_path = _OUT_DIR / "pilot_reasoning_variants_n15_mem0.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump({"task_ids": task_ids, "tasks": tasks, "results": results}, f, indent=2, ensure_ascii=False)
    log(f"\nWrote {out_path}")

    log("\n=== SUMMARY (normalized / exact) ===")
    for cond in ("B", "C"):
        for content_variant in CONTENT_VARIANTS:
            for prompt_variant in PROMPT_VARIANTS:
                key = f"{cond}_{content_variant}_{prompt_variant}"
                n_norm = sum(1 for t in results.values() if t.get(key, {}).get("normalized_status") == "ANSWER_CORRECT")
                n_exact = sum(1 for t in results.values() if t.get(key, {}).get("exact_status") == "ANSWER_CORRECT")
                n = sum(1 for t in results.values() if key in t)
                log(f"  {key}: normalized={n_norm}/{n} exact={n_exact}/{n}")


if __name__ == "__main__":
    main()
