"""Phase 3.3-RESEARCH Round 2 -- retrieval pool widening + calibrated threshold
selection, vs. V1's fixed top-5 slice. See PHASE3_RESEARCH_IMPROVEMENT_PLAN.md for the
full hypothesis and root-cause justification (149/240 = 62% of Condition C's frozen
shortfall is RETRIEVAL_FAILURE).

Reuses, unmodified: `foundations/selection_policy.py::select_by_threshold` +
`CALIBRATED_THRESHOLD_LOCOMO` + `RETRIEVAL_POOL_SIZE_N` (the real, already-calibrated
mechanism), `RealMem0Adapter`, `generate_with_retries`, `render_messages`,
`build_agent_visible_context`. Uses the WINNING (i.e. least-bad -- BASELINE, since Round
1 was net-negative/neutral) prompt configuration from Round 1: DEFAULT_SYSTEM_PROMPT,
max_tokens=64 -- so this round isolates the retrieval-mechanism variable alone, not
conflated with the Round 1 prompt variable.

Same 15 real task_ids as Round 1, for direct comparability.
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
from phase3.evaluation.foundations.selection_policy import (
    CALIBRATED_THRESHOLD_LOCOMO,
    RETRIEVAL_POOL_SIZE_N,
    select_by_threshold,
)
from phase3.evaluation.foundations.similarity import score_candidates
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
GEN_MAX_TOKENS = 64  # Round-1 baseline, held fixed to isolate the retrieval variable


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


def _run_variant_c(task, llm_provider, pool_size: int, use_threshold: bool, results, log, variant_name: str, top_k_by_score: int = 0):
    from phase3.evaluation.foundations_real.mem0_real_adapter import RealMem0Adapter

    foundation = RealMem0Adapter()
    init_field = foundation.initialize(
        {"embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
         "collection_name": f"research_variant_r2_{variant_name}_{task['task_id']}_mem0"}
    )
    if init_field.availability != FOUNDATION_AVAILABLE:
        log(f"  [{variant_name}] init failed: {init_field.note}")
        return
    foundation.reset()

    pool_rows = list(_ingest_pool(task["conversation_id"], task["session_id"]))
    for row in pool_rows:
        foundation.add_memory(
            memory_id=row["memory_id"], content={"text": f"{row['source_role']}: {row['content']}"},
            metadata={"user_id": f"rv2-{task['task_id']}", "source_memory_id": row["memory_id"]},
        )

    retrieve_field = foundation.retrieve({"text": task["question"], "user_id": f"rv2-{task['task_id']}"}, top_k=pool_size)
    retrieved_ids: Tuple[str, ...] = ()
    memory_items: List[Mapping[str, Any]] = []
    gold_in_pool = False
    gold_selected = False

    if retrieve_field.availability in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
        raw_items = retrieve_field.value or []
        retrieved_ids = tuple(mid for mid in (_extract_memory_id(i) for i in raw_items) if mid is not None)

        # Mem0 assigns its OWN internal id per memory point -- gold-evidence
        # comparison must resolve through metadata["source_memory_id"] (the same
        # identity bridge `identity.py::resolve_source_identity` and
        # `trace.py::evaluate_and_trace_with_identity` use for the frozen dataset's
        # own RETRIEVAL_FAILURE classification), never compare raw foundation ids
        # directly against source-space evidence_memory_ids.
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

        if use_threshold:
            sel_result = select_by_threshold(task["question"], candidates, threshold=CALIBRATED_THRESHOLD_LOCOMO)
            selected_ids = tuple(c.memory_id for c in sel_result.selected)
        elif top_k_by_score:
            scored = score_candidates(task["question"], candidates)
            scored_sorted = sorted(scored, key=lambda c: c.score, reverse=True)
            selected_ids = tuple(c.memory_id for c in scored_sorted[:top_k_by_score])
        else:
            selected_ids = select_from_retrieved(retrieved_ids, top_k=5)

        selected_source_ids = tuple(source_id_by_foundation_id.get(mid) for mid in selected_ids)
        gold_selected = any(eid in selected_source_ids for eid in task["evidence_memory_ids"])
        content_by_id = dict(candidates)
        for mid in selected_ids:
            if mid in content_by_id:
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

    results.setdefault(task["task_id"], {})[variant_name] = {
        "answer": answer, "latency_sec": latency,
        "exact_status": exact.status, "normalized_status": norm.status,
        "pool_size": pool_size, "retrieved_count": len(retrieved_ids), "selected_count": len(memory_items),
        "gold_in_pool": gold_in_pool, "gold_selected": gold_selected,
        "pool_actual_size": len(pool_rows),
    }
    log(f"  [{variant_name}] norm={norm.status} exact={exact.status} gold_in_pool={gold_in_pool} "
        f"gold_selected={gold_selected} selected={len(memory_items)} ans={str(answer)[:70]!r}")

    foundation.shutdown()


def main():
    def log(msg):
        print(msg, flush=True)

    task_ids = _select_task_ids(N_TASKS)
    tasks = _build_task_records(task_ids)
    log(f"Selected {len(tasks)} real task_ids (same as Round 1): {task_ids}")

    endpoint = LlamaServerEndpoint()
    llm_provider = LlamaServerProvider(endpoint)
    identity_check = llm_provider.verify_server_identity()
    log(f"Server identity verified: {identity_check}")

    results: Mapping[str, Mapping[str, Any]] = {}
    for i, task in enumerate(tasks):
        log(f"\n=== Task {i+1}/{len(tasks)}: {task['task_id']} — {task['question']!r} (gold={task['answer']!r}) ===")
        # V1 baseline: pool=5 (== retrieve top-5 directly), no threshold (order-preserving slice)
        _run_variant_c(task, llm_provider, pool_size=5, use_threshold=False, results=results, log=log, variant_name="C_POOL5_BASELINE")
        # Round 2: pool=20 (RETRIEVAL_POOL_SIZE_N), calibrated threshold selection
        _run_variant_c(task, llm_provider, pool_size=RETRIEVAL_POOL_SIZE_N, use_threshold=True, results=results, log=log, variant_name="C_POOL20_THRESHOLD")
        # Isolate pool-width alone: pool=20, but still V1-style top-5 slice (no threshold)
        _run_variant_c(task, llm_provider, pool_size=RETRIEVAL_POOL_SIZE_N, use_threshold=False, results=results, log=log, variant_name="C_POOL20_TOP5")
        # Round 2b: pool=20, take top-8 by benchmark-owned cosine score, uncapped by the
        # hard 0.263 threshold -- isolates whether the THRESHOLD VALUE (too strict) or the
        # THRESHOLD MECHANISM (hard cutoff vs. ranked top-k) explains why Round 2's
        # threshold variant failed to convert extra recall into extra selection.
        _run_variant_c(task, llm_provider, pool_size=RETRIEVAL_POOL_SIZE_N, use_threshold=False, top_k_by_score=8, results=results, log=log, variant_name="C_POOL20_TOP8_BY_SCORE")

    out_path = _OUT_DIR / "pilot_retrieval_pool_widening_n15_mem0.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump({"task_ids": task_ids, "tasks": tasks, "results": results}, f, indent=2, ensure_ascii=False)
    log(f"\nWrote {out_path}")

    log("\n=== SUMMARY ===")
    for variant_name in ("C_POOL5_BASELINE", "C_POOL20_THRESHOLD", "C_POOL20_TOP5", "C_POOL20_TOP8_BY_SCORE"):
        n_norm = sum(1 for t in results.values() if t.get(variant_name, {}).get("normalized_status") == "ANSWER_CORRECT")
        n_exact = sum(1 for t in results.values() if t.get(variant_name, {}).get("exact_status") == "ANSWER_CORRECT")
        n_gold_in_pool = sum(1 for t in results.values() if t.get(variant_name, {}).get("gold_in_pool"))
        n_gold_selected = sum(1 for t in results.values() if t.get(variant_name, {}).get("gold_selected"))
        n = sum(1 for t in results.values() if variant_name in t)
        log(f"  {variant_name}: normalized={n_norm}/{n} exact={n_exact}/{n} gold_in_retrieved_pool={n_gold_in_pool}/{n} gold_in_selected={n_gold_selected}/{n}")


if __name__ == "__main__":
    main()
