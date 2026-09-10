"""Phase 3.3-RESEARCH Round 6 -- the stacked-three candidate: ALL THREE validated wins
combined, per explicit instruction, nothing else added:

1. Retrieval: pool=20 (RETRIEVAL_POOL_SIZE_N).
2. Selection: hybrid score (cosine + token-overlap + entity-overlap, SAME fixed weights
   as Round 5: 0.5/0.3/0.2, not retuned here), top-8 by that hybrid score.
3. Content: real `source_timestamp` injected into ingested/rendered memory text (same
   as Round 3/4).

Still NO prompt change (DEFAULT_SYSTEM_PROMPT), NO model change, NO budget change
(max_tokens=64, n_ctx=4096) -- isolates whether stacking all three compounds or is
redundant with the pairwise Round 4 (retrieval+timestamp) and Round 5 (hybrid) results,
per explicit instruction not to add a fourth variable.

Same 15 real task_ids as every prior round, Condition C only (Condition B has no
retrieval axis; its already-measured Round 3 timestamp-only result -- 5/15 -- remains
the correct comparison point, not re-run here).
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Any, List, Mapping, Tuple

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from phase3.evaluation.agent.conditions import CONDITION_RETRIEVED_MEMORY, build_agent_visible_context
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
TOP_K_BY_SCORE = 8
HYBRID_WEIGHT_COSINE = 0.5
HYBRID_WEIGHT_TOKEN_OVERLAP = 0.3
HYBRID_WEIGHT_ENTITY_OVERLAP = 0.2

_WORD_RE = re.compile(r"[A-Za-z0-9']+")
_PROPER_RE = re.compile(r"\b[A-Z][a-zA-Z]+\b")
_DIGIT_RE = re.compile(r"\b\d+\b")


def _tokenize(s: str) -> set:
    return set(_WORD_RE.findall(s.lower()))


def _token_overlap_recall(query: str, content: str) -> float:
    q = _tokenize(query)
    if not q:
        return 0.0
    return len(q & _tokenize(content)) / len(q)


def _entity_overlap_recall(query: str, content: str) -> float:
    q_entities = set(_PROPER_RE.findall(query)) | set(_DIGIT_RE.findall(query))
    if not q_entities:
        return 0.0
    c_entities = set(_PROPER_RE.findall(content)) | set(_DIGIT_RE.findall(content))
    return len(q_entities & c_entities) / len(q_entities)


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
            "task_id": tid, "question": t["question"], "answer": str(t["answer"]),
            "evidence_memory_ids": t["evidence_memory_ids"],
            "conversation_id": conv_id, "session_id": session_id,
        })
    return tasks


def _ingest_pool(conv_id: str, session_id: str):
    for row in _load_jsonl(_DATA_ROOT / "locomo" / "memory_records.jsonl"):
        if row["conversation_id"] == conv_id and row["session_id"] == session_id:
            yield row


def _content_text(row: Mapping[str, Any]) -> str:
    if row.get("source_timestamp"):
        return f"[{row['source_timestamp']}] {row['source_role']}: {row['content']}"
    return f"{row['source_role']}: {row['content']}"


def _run_stacked_c(task, llm_provider, results, log):
    from phase3.evaluation.foundations_real.mem0_real_adapter import RealMem0Adapter

    foundation = RealMem0Adapter()
    init_field = foundation.initialize(
        {"embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
         "collection_name": f"research_variant_r6_stacked_{task['task_id']}_mem0"}
    )
    if init_field.availability != FOUNDATION_AVAILABLE:
        log(f"  [STACKED] init failed: {init_field.note}")
        return
    foundation.reset()

    pool_rows = list(_ingest_pool(task["conversation_id"], task["session_id"]))
    for row in pool_rows:
        metadata = {"user_id": f"rv6-{task['task_id']}", "source_memory_id": row["memory_id"]}
        if row.get("source_timestamp"):
            metadata["source_timestamp"] = row["source_timestamp"]
        foundation.add_memory(memory_id=row["memory_id"], content={"text": _content_text(row)}, metadata=metadata)

    retrieve_field = foundation.retrieve({"text": task["question"], "user_id": f"rv6-{task['task_id']}"}, top_k=RETRIEVAL_POOL_SIZE_N)
    retrieved_ids: Tuple[str, ...] = ()
    memory_items: List[Mapping[str, Any]] = []
    gold_in_pool = False
    gold_selected = False

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

        retrieved_source_ids = tuple(source_id_by_foundation_id.get(mid) for mid in retrieved_ids)
        gold_in_pool = any(eid in retrieved_source_ids for eid in task["evidence_memory_ids"])

        cosine_scored = {c.memory_id: c.score for c in score_candidates(task["question"], candidates)}
        final_scores = []
        for mid, content in candidates:
            cosine = cosine_scored.get(mid, 0.0)
            tok = _token_overlap_recall(task["question"], content)
            ent = _entity_overlap_recall(task["question"], content)
            score = HYBRID_WEIGHT_COSINE * cosine + HYBRID_WEIGHT_TOKEN_OVERLAP * tok + HYBRID_WEIGHT_ENTITY_OVERLAP * ent
            final_scores.append((mid, score))
        final_scores.sort(key=lambda x: x[1], reverse=True)
        selected_ids = tuple(mid for mid, _ in final_scores[:TOP_K_BY_SCORE])

        selected_source_ids = tuple(source_id_by_foundation_id.get(mid) for mid in selected_ids)
        gold_selected = any(eid in selected_source_ids for eid in task["evidence_memory_ids"])

        content_by_id = dict(candidates)
        for mid in selected_ids:
            memory_items.append({"memory_id": mid, "content": content_by_id[mid]})

    context = build_agent_visible_context(
        condition=CONDITION_RETRIEVED_MEMORY, task_id=task["task_id"], prompt=task["question"],
        memory_items=memory_items,
    )
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
    exact = evaluate_answer_correctness(exec_result, task["answer"])
    norm = evaluate_answer_correctness_normalized(exec_result, task["answer"])

    results[task["task_id"]] = {
        "answer": answer, "latency_sec": latency,
        "exact_status": exact.status, "normalized_status": norm.status,
        "gold_in_pool": gold_in_pool, "gold_selected": gold_selected,
    }
    log(f"  [STACKED] norm={norm.status} exact={exact.status} gold_in_pool={gold_in_pool} "
        f"gold_selected={gold_selected} latency={latency:.2f}s ans={str(answer)[:70]!r}")

    foundation.shutdown()


def main():
    def log(msg):
        print(msg, flush=True)

    task_ids = _select_task_ids(N_TASKS)
    tasks = _build_task_records(task_ids)
    log(f"Selected {len(tasks)} real task_ids (same as prior rounds): {task_ids}")

    endpoint = LlamaServerEndpoint()
    llm_provider = LlamaServerProvider(endpoint)
    identity_check = llm_provider.verify_server_identity()
    log(f"Server identity verified: {identity_check}")

    results: Mapping[str, Mapping[str, Any]] = {}
    for i, task in enumerate(tasks):
        log(f"\n=== Task {i+1}/{len(tasks)}: {task['task_id']} — {task['question']!r} (gold={task['answer']!r}) ===")
        _run_stacked_c(task, llm_provider, results, log)

    out_path = _OUT_DIR / "pilot_stacked_three_candidate_n15_mem0.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump({"task_ids": task_ids, "tasks": tasks, "results_C_stacked": results}, f, indent=2, ensure_ascii=False)
    log(f"\nWrote {out_path}")

    n_norm = sum(1 for t in results.values() if t.get("normalized_status") == "ANSWER_CORRECT")
    n_exact = sum(1 for t in results.values() if t.get("exact_status") == "ANSWER_CORRECT")
    n_gold_pool = sum(1 for t in results.values() if t.get("gold_in_pool"))
    n_gold_sel = sum(1 for t in results.values() if t.get("gold_selected"))
    log(f"\n=== SUMMARY: STACKED (pool20 + hybrid-top8 + timestamp), Condition C ===")
    log(f"  normalized={n_norm}/15 exact={n_exact}/15 gold_in_pool={n_gold_pool}/15 gold_selected={n_gold_sel}/15")


if __name__ == "__main__":
    main()
