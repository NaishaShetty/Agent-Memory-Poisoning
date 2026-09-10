"""Phase 3.3-RESEARCH Round 12 -- model-capability pilot: Qwen3-4B-Thinking-2507
(Q4_K_M GGUF) as a candidate replacement reasoning engine for MAMBench V2, tested
against the exact same 15 real LoCoMo/Mem0 tasks used throughout this investigation,
under the SAME V2 memory-foundation configuration (per-condition winning configs
already validated at full 120-task scale):

- Condition A (no-memory): no retrieval, no evidence -- same structural shape as V1/V2.
- Condition B (gold evidence): timestamp-injected evidence text (Round 8's validated
  winning config).
- Condition C (retrieved memory): pool=20 retrieval + hybrid top-8 selection, NO
  timestamp injection (Round 11's finding: this outperforms the timestamp-injected
  variant for Condition C specifically -- the corrected, better V2 config for C).

ONLY THE MODEL AND THE MINIMUM SERVING/GENERATION CHANGES NEEDED FOR IT ARE CHANGED
--------------------------------------------------------------------------------
Model: Qwen3-4B-Thinking-2507-Q4_K_M.gguf (verified real GGUF, sha-checked by the
downloading tool, confirmed loadable on the exact pinned llama-server build
b10717/a32af33de -- same binary V1/V2 already used, zero compatibility risk).
Server: `-ngl 99 --ctx-size 16384 --parallel 4` -- IDENTICAL to the flags the frozen
120x2 production campaign used for Qwen3-8B (not a new, untested serving
configuration). Real measured VRAM: 4851 MiB used / 1070 MiB free at this config,
vs. Qwen3-8B's ~5844/297 MiB under the identical flags -- confirmed real headroom,
not estimated.
Generation config: `max_tokens=1024` (up from V1/V2's 64), `enable_thinking=True` (this
model "supports only thinking mode" per its own model card, and a live test at
max_tokens=300 showed `finish_reason: "length"` -- thinking alone consumed the entire
budget for even a trivial one-fact question, confirming 64 or 300 tokens is
structurally insufficient for this model). 1024 was chosen from the technical budget
analysis (per-slot ctx=4096, typical real prompt length ~50-120 tokens per the actual
server logs, leaving ample room for both a reasoning trace and a final answer) BEFORE
running this pilot -- not tuned on any pilot result. Same n_ctx=4096, same
temperature=0, same seed=42 as V1/V2's `clean_baseline_generation_config`.
`provider.py`'s existing `text=message.get("content") or ""` parsing already correctly
discards `reasoning_content` and keeps only the final answer -- zero code changes
needed; verified directly against a live raw HTTP response before this pilot ran.

Retrieval/selection/memory-architecture code is completely unmodified -- only the
`llm_provider`/`generation_config` passed into the existing, unmodified
`run_agent_task`/`gold_evidence_runner` primitives differs.

Records VRAM, latency, finish_reason (to catch truncation), and throughput for every
single generation, not just aggregate correctness -- per explicit instruction.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, List, Mapping, Tuple

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from phase3.evaluation.agent.conditions import (
    CONDITION_GOLD_EVIDENCE,
    CONDITION_NO_MEMORY,
    CONDITION_RETRIEVED_MEMORY,
    build_agent_visible_context,
)
from phase3.evaluation.agent.content_recall_correctness import evaluate_answer_correctness_content_recall
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
from phase3.evaluation.foundations.selection_policy import RETRIEVAL_POOL_SIZE_N
from phase3.evaluation.foundations.similarity import score_candidates
from phase3.evaluation.llm.provider import GenerationConfig, LlamaServerEndpoint, LlamaServerProvider

_DATA_ROOT = _REPO_ROOT / "data" / "processed"
_OUT_DIR = Path(__file__).resolve().parent / "results"
_OUT_DIR.mkdir(parents=True, exist_ok=True)

FROZEN_DATASET_PATH = (
    _REPO_ROOT / "phase3" / "experiments" / "results" / "canonical_store" / "dataset_full"
    / "clean_agent_dataset_locomo_120x2.json"
)
N_TASKS = 15
GEN_MAX_TOKENS = 1024
HYBRID_WEIGHT_COSINE = 0.5
HYBRID_WEIGHT_TOKEN_OVERLAP = 0.3
HYBRID_WEIGHT_ENTITY_OVERLAP = 0.2

MODEL_IDENTITY = {
    "model_file": "Qwen3-4B-Thinking-2507-Q4_K_M.gguf",
    "source": "https://huggingface.co/unsloth/Qwen3-4B-Thinking-2507-GGUF",
    "quantization": "Q4_K_M",
    "llama_cpp_build": "b10717",
    "llama_cpp_commit": "a32af33de",
    "server_flags": "-ngl 99 --ctx-size 16384 --parallel 4",
    "generation_config": {"max_tokens": GEN_MAX_TOKENS, "enable_thinking": True, "n_ctx": 4096, "temperature": 0.0, "seed": 42},
}


def _gpu_vram_mib():
    try:
        out = subprocess.check_output(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], text=True)
        return int(out.strip().splitlines()[0])
    except Exception as exc:
        return f"UNAVAILABLE: {exc}"


def _load_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def _token_overlap_recall(query: str, content: str) -> float:
    import re
    q = set(re.findall(r"[a-z0-9']+", query.lower()))
    if not q:
        return 0.0
    c = set(re.findall(r"[a-z0-9']+", content.lower()))
    return len(q & c) / len(q)


def _entity_overlap_recall(query: str, content: str) -> float:
    import re
    q_ent = set(re.findall(r"\b[A-Z][a-zA-Z]+\b", query)) | set(re.findall(r"\b\d+\b", query))
    if not q_ent:
        return 0.0
    c_ent = set(re.findall(r"\b[A-Z][a-zA-Z]+\b", content)) | set(re.findall(r"\b\d+\b", content))
    return len(q_ent & c_ent) / len(q_ent)


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
        tasks.append({"task_id": tid, "question": t["question"], "answer": str(t["answer"]),
                       "evidence_memory_ids": t["evidence_memory_ids"], "conversation_id": conv_id, "session_id": session_id})
    return tasks


def _ingest_pool(conv_id: str, session_id: str):
    for row in _load_jsonl(_DATA_ROOT / "locomo" / "memory_records.jsonl"):
        if row["conversation_id"] == conv_id and row["session_id"] == session_id:
            yield row


def _generate_and_score(messages, task, run_config, condition, selected_ids, log, tag):
    t0 = time.time()
    vram_before = _gpu_vram_mib()
    answer, attempts = generate_with_retries(messages, run_config)
    latency = time.time() - t0
    vram_after = _gpu_vram_mib()
    finish_reason = attempts[-1].error if (attempts and not attempts[-1].succeeded) else None

    exec_result = AgentExecutionResult(
        task_id=task["task_id"], condition=condition, answer=answer,
        execution_status=EXECUTION_STATUS_SUCCESS if answer is not None else EXECUTION_STATUS_ERROR,
        selected_memory_ids=selected_ids, used_memory_ids=None, execution_metadata={"attempts": len(attempts)},
    )
    exact = evaluate_answer_correctness(exec_result, task["answer"])
    norm = evaluate_answer_correctness_normalized(exec_result, task["answer"])
    recall = evaluate_answer_correctness_content_recall(exec_result, task["answer"])

    row = {
        "answer": answer, "latency_sec": latency, "vram_before_mib": vram_before, "vram_after_mib": vram_after,
        "exact_status": exact.status, "normalized_status": norm.status, "content_recall_status": recall.status,
        "attempts": len(attempts), "answer_is_empty_or_none": not answer,
    }
    log(f"  [{tag}] norm={norm.status} exact={exact.status} recall={recall.status} lat={latency:.2f}s ans={str(answer)[:80]!r}")
    return row


def _run_condition_a(task, llm_provider, run_config, results, log):
    context = build_agent_visible_context(condition=CONDITION_NO_MEMORY, task_id=task["task_id"], prompt=task["question"], memory_items=[])
    messages = render_messages(context, DEFAULT_SYSTEM_PROMPT)
    results.setdefault(task["task_id"], {})["A"] = _generate_and_score(messages, task, run_config, CONDITION_NO_MEMORY, (), log, "A")


def _run_condition_b(task, memory_rows_by_id, llm_provider, run_config, results, log):
    evidence_items = [
        {"memory_id": f"evidence-slot-{i+1}", "content": (
            f"[{memory_rows_by_id[eid]['source_timestamp']}] {memory_rows_by_id[eid]['source_role']}: {memory_rows_by_id[eid]['content']}"
            if memory_rows_by_id[eid].get("source_timestamp") else f"{memory_rows_by_id[eid]['source_role']}: {memory_rows_by_id[eid]['content']}"
        )}
        for i, eid in enumerate(task["evidence_memory_ids"]) if eid in memory_rows_by_id
    ]
    context = build_agent_visible_context(condition=CONDITION_GOLD_EVIDENCE, task_id=task["task_id"], prompt=task["question"], memory_items=evidence_items)
    messages = render_messages(context, DEFAULT_SYSTEM_PROMPT)
    results.setdefault(task["task_id"], {})["B"] = _generate_and_score(messages, task, run_config, CONDITION_GOLD_EVIDENCE, (), log, "B")


def _run_condition_c(task, llm_provider, run_config, results, log):
    from phase3.evaluation.foundations_real.mem0_real_adapter import RealMem0Adapter

    foundation = RealMem0Adapter()
    init_field = foundation.initialize({"embedding_model": "sentence-transformers/all-MiniLM-L6-v2", "collection_name": f"research_variant_r12_{task['task_id']}_mem0"})
    if init_field.availability != FOUNDATION_AVAILABLE:
        log(f"  [C] init failed: {init_field.note}")
        return
    foundation.reset()

    for row in _ingest_pool(task["conversation_id"], task["session_id"]):
        foundation.add_memory(memory_id=row["memory_id"], content={"text": f"{row['source_role']}: {row['content']}"},
                               metadata={"user_id": f"rv12-{task['task_id']}", "source_memory_id": row["memory_id"]})

    retrieve_field = foundation.retrieve({"text": task["question"], "user_id": f"rv12-{task['task_id']}"}, top_k=RETRIEVAL_POOL_SIZE_N)
    memory_items: List[Mapping[str, Any]] = []
    if retrieve_field.availability in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
        raw_items = retrieve_field.value or []
        retrieved_ids = tuple(mid for mid in (_extract_memory_id(i) for i in raw_items) if mid is not None)
        candidates: List[Tuple[str, str]] = []
        for mid in retrieved_ids:
            inspect_field = foundation.inspect_memory(mid)
            if inspect_field.availability in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
                candidates.append((mid, _extract_content_text(inspect_field.value or {})))
        cosine_scored = {c.memory_id: c.score for c in score_candidates(task["question"], candidates)}
        final_scores = []
        for mid, content in candidates:
            cosine = cosine_scored.get(mid, 0.0)
            tok = _token_overlap_recall(task["question"], content)
            ent = _entity_overlap_recall(task["question"], content)
            score = HYBRID_WEIGHT_COSINE * cosine + HYBRID_WEIGHT_TOKEN_OVERLAP * tok + HYBRID_WEIGHT_ENTITY_OVERLAP * ent
            final_scores.append((mid, score))
        final_scores.sort(key=lambda x: x[1], reverse=True)
        selected_ids = tuple(mid for mid, _ in final_scores[:8])
        content_by_id = dict(candidates)
        for mid in selected_ids:
            memory_items.append({"memory_id": mid, "content": content_by_id[mid]})

    context = build_agent_visible_context(condition=CONDITION_RETRIEVED_MEMORY, task_id=task["task_id"], prompt=task["question"], memory_items=memory_items)
    messages = render_messages(context, DEFAULT_SYSTEM_PROMPT)
    results.setdefault(task["task_id"], {})["C"] = _generate_and_score(
        messages, task, run_config, CONDITION_RETRIEVED_MEMORY, tuple(item["memory_id"] for item in memory_items), log, "C"
    )
    foundation.shutdown()


def main():
    def log(msg):
        print(msg, flush=True)

    task_ids = _select_task_ids(N_TASKS)
    tasks = _build_task_records(task_ids)
    memory_rows_by_id = {row["memory_id"]: row for row in _load_jsonl(_DATA_ROOT / "locomo" / "memory_records.jsonl")}
    log(f"Selected {len(tasks)} real task_ids (SAME as every prior round): {task_ids}")
    log(f"Model identity: {json.dumps(MODEL_IDENTITY, indent=2)}")

    endpoint = LlamaServerEndpoint()
    llm_provider = LlamaServerProvider(endpoint)
    log(f"VRAM at pilot start: {_gpu_vram_mib()} MiB used")

    gen_config = GenerationConfig(temperature=0.0, seed=42, max_tokens=GEN_MAX_TOKENS, enable_thinking=True, n_ctx=4096)
    run_config = RunConfiguration(llm_provider=llm_provider, generation_config=gen_config, system_prompt=DEFAULT_SYSTEM_PROMPT)

    results: Mapping[str, Mapping[str, Any]] = {}
    t_start = time.time()
    for i, task in enumerate(tasks):
        log(f"\n=== Task {i+1}/{len(tasks)}: {task['task_id']} — {task['question']!r} (gold={task['answer']!r}) ===")
        _run_condition_a(task, llm_provider, run_config, results, log)
        _run_condition_b(task, memory_rows_by_id, llm_provider, run_config, results, log)
        _run_condition_c(task, llm_provider, run_config, results, log)
    total_wall_clock = time.time() - t_start

    out_path = _OUT_DIR / "pilot_qwen3_4b_thinking_v2_n15.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump({"task_ids": task_ids, "tasks": tasks, "model_identity": MODEL_IDENTITY,
                    "total_wall_clock_sec": total_wall_clock, "results": results}, f, indent=2, ensure_ascii=False)
    log(f"\nWrote {out_path}")
    log(f"Total wall clock: {total_wall_clock/60:.2f} min for {len(tasks)} tasks x 3 conditions = {len(tasks)*3} generations "
        f"({total_wall_clock/(len(tasks)*3):.2f} sec/generation average)")

    log("\n=== SUMMARY (Qwen3-4B-Thinking-2507) ===")
    for cond in ("A", "B", "C"):
        n_norm = sum(1 for t in results.values() if t.get(cond, {}).get("normalized_status") == "ANSWER_CORRECT")
        n_exact = sum(1 for t in results.values() if t.get(cond, {}).get("exact_status") == "ANSWER_CORRECT")
        n_recall = sum(1 for t in results.values() if t.get(cond, {}).get("content_recall_status") == "ANSWER_CORRECT")
        n_empty = sum(1 for t in results.values() if t.get(cond, {}).get("answer_is_empty_or_none"))
        n = sum(1 for t in results.values() if cond in t)
        avg_lat = sum(t[cond]["latency_sec"] for t in results.values() if cond in t) / max(1, n)
        log(f"  Condition {cond}: normalized={n_norm}/{n} exact={n_exact}/{n} content_recall={n_recall}/{n} "
            f"empty_answers={n_empty}/{n} avg_latency={avg_lat:.2f}s")


if __name__ == "__main__":
    main()
