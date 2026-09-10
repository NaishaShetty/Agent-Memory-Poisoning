"""Phase 3.3-RESEARCH Round 11 -- SCALE-UP: retrieval+hybrid WITHOUT timestamp
injection, Condition C, full 120-task scale. Isolates how much of Round 7's stacked
candidate (pool=20 + hybrid top-8 + timestamp, 45.8% normalized) is actually
attributable to retrieval+hybrid alone vs. the marginal contribution of timestamp
injection.

WHY THIS, NOT A LITERAL "RE-RUN ROUND 7" (Round 7 already includes timestamp)
--------------------------------------------------------------------------------
At n=15 (Rounds 4/5/6), retrieval+hybrid alone and retrieval+hybrid+timestamp reached
the EXACT SAME 7/15 ceiling -- fully redundant at that scale. But Round 8 (Condition B,
n=120) found timestamp's real effect is roughly 2x what the n=15 pilots could reliably
detect (a ~13-18% population effect is hard to sample at n=15). This round tests
whether that same undersampling explains Round 7's apparent redundancy, or whether
timestamp genuinely adds nothing beyond retrieval+hybrid once evidence is actually
being selected correctly. Reuses `pilot_stacked_three_candidate.py`'s exact
retrieval/hybrid-selection logic unmodified -- only the content-text function is
swapped to omit the timestamp prefix.

V1 baseline NOT re-run (frozen dataset already has it for all 120 tasks). Round 7's
own already-computed stacked-with-timestamp result is reused for the three-way
comparison, not re-run either.
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
sys.path.insert(0, str(Path(__file__).resolve().parent))

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

import pilot_stacked_three_candidate as base  # reuse task selection/build helpers

_OUT_DIR = Path(__file__).resolve().parent / "results"
_OUT_DIR.mkdir(parents=True, exist_ok=True)

GEN_MAX_TOKENS = 64
TOP_K_BY_SCORE = 8
HYBRID_WEIGHT_COSINE = 0.5
HYBRID_WEIGHT_TOKEN_OVERLAP = 0.3
HYBRID_WEIGHT_ENTITY_OVERLAP = 0.2


def _content_text_no_timestamp(row: Mapping[str, Any]) -> str:
    return f"{row['source_role']}: {row['content']}"


def _run_no_timestamp_c(task, llm_provider, results, log):
    from phase3.evaluation.foundations_real.mem0_real_adapter import RealMem0Adapter

    foundation = RealMem0Adapter()
    init_field = foundation.initialize(
        {"embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
         "collection_name": f"research_variant_r11_{task['task_id']}_mem0"}
    )
    if init_field.availability != FOUNDATION_AVAILABLE:
        log(f"  [NO_TIMESTAMP] init failed: {init_field.note}")
        return
    foundation.reset()

    pool_rows = list(base._ingest_pool(task["conversation_id"], task["session_id"]))
    for row in pool_rows:
        metadata = {"user_id": f"rv11-{task['task_id']}", "source_memory_id": row["memory_id"]}
        foundation.add_memory(memory_id=row["memory_id"], content={"text": _content_text_no_timestamp(row)}, metadata=metadata)

    retrieve_field = foundation.retrieve({"text": task["question"], "user_id": f"rv11-{task['task_id']}"}, top_k=RETRIEVAL_POOL_SIZE_N)
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
            tok = base._token_overlap_recall(task["question"], content)
            ent = base._entity_overlap_recall(task["question"], content)
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
    log(f"  [NO_TIMESTAMP] norm={norm.status} exact={exact.status} gold_in_pool={gold_in_pool} "
        f"gold_selected={gold_selected} ans={str(answer)[:70]!r}")

    foundation.shutdown()


def main():
    def log(msg):
        print(msg, flush=True)

    task_ids = sorted({r["task_id"] for r in json.load(open(base.FROZEN_DATASET_PATH, encoding="utf-8")) if r["foundation"] == "MEM0"})
    tasks = base._build_task_records(task_ids)
    log(f"Selected ALL {len(tasks)} real MEM0 task_ids (Round 11: retrieval+hybrid, NO timestamp).")

    endpoint = LlamaServerEndpoint()
    llm_provider = LlamaServerProvider(endpoint)
    identity_check = llm_provider.verify_server_identity()
    log(f"Server identity verified: {identity_check}")

    out_path = _OUT_DIR / "scaleup_retrieval_hybrid_no_timestamp_n120.json"
    results = {}
    if out_path.exists():
        with out_path.open("r", encoding="utf-8") as f:
            prior = json.load(f)
        results = prior.get("results_C_no_timestamp", {})
        log(f"Resuming from existing checkpoint: {len(results)}/{len(tasks)} tasks already completed.")

    def _checkpoint():
        with out_path.open("w", encoding="utf-8") as f:
            json.dump({"task_ids": task_ids, "tasks": tasks, "results_C_no_timestamp": results}, f, indent=2, ensure_ascii=False)

    t_start = time.time()
    for i, task in enumerate(tasks):
        if task["task_id"] in results:
            continue
        log(f"\n=== Task {i+1}/{len(tasks)}: {task['task_id']} — {task['question']!r} (gold={task['answer']!r}) ===")
        _run_no_timestamp_c(task, llm_provider, results, log)
        _checkpoint()
        if len(results) % 10 == 0:
            elapsed = time.time() - t_start
            log(f"--- progress: {len(results)}/{len(tasks)} total completed, elapsed this run={elapsed/60:.1f}min ---")

    log(f"\nFinal write complete: {out_path}")
    n_norm = sum(1 for t in results.values() if t.get("normalized_status") == "ANSWER_CORRECT")
    n_exact = sum(1 for t in results.values() if t.get("exact_status") == "ANSWER_CORRECT")
    n_gold_pool = sum(1 for t in results.values() if t.get("gold_in_pool"))
    n_gold_sel = sum(1 for t in results.values() if t.get("gold_selected"))
    n = len(results)
    log(f"\n=== SUMMARY: RETRIEVAL+HYBRID, NO TIMESTAMP (n={n}), Condition C ===")
    log(f"  normalized={n_norm}/{n} exact={n_exact}/{n} gold_in_pool={n_gold_pool}/{n} gold_selected={n_gold_sel}/{n}")


if __name__ == "__main__":
    main()
