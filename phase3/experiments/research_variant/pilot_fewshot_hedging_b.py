"""Phase 3.3-RESEARCH Round 9 -- few-shot hedging-reduction, Condition B (gold evidence),
n=15 pilot before any larger run, per the project's own established discipline (small
controlled pilot before scaling).

WHY FEW-SHOT, NOT ANOTHER INSTRUCTION-WORDING ATTEMPT
--------------------------------------------------------------------------------
Round 1's V_FORMAT prompt (an INSTRUCTED "don't hedge, and if you must refuse, say
exactly X" rule) was net-negative/mixed: the model took the easy fixed-refusal escape
hatch MORE often, not less. The read-only 120-task failure classification
(PHASE3_RESEARCH_IMPROVEMENT_PLAN.md) found a real, non-temporal, non-evaluator-artifact
hedging bucket of 19/120 (15.8%) -- e.g. gold "purple", answer "The question cannot be
answered based on the provided information," despite the evidence plainly stating the
color. This round tests a DEMONSTRATED-behavior fix instead of an instructed one:
few-shot example turns (synthetic, unrelated to the real LoCoMo eval content, to avoid
any contamination) showing both correct extraction AND correct honest refusal, so the
model learns the discrimination rather than either always hedging or always answering.

Same 15 real task_ids as every prior round, Condition B only (no retrieval concept).
No timestamp injection here (isolates the few-shot variable alone; a later round can
combine it with Round 8's timestamp result if this one shows a real effect). Same
model, same generation config (DEFAULT max_tokens=64, n_ctx=4096), same three metrics
(exact, normalized, content-recall) reported side by side.
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
N_TASKS = 15
GEN_MAX_TOKENS = 64

# Synthetic, generic examples -- deliberately unrelated to any real LoCoMo conversation
# content or question, to avoid contaminating the real eval with hints. Demonstrates
# BOTH correct extraction (don't hedge when the fact is present) and correct honest
# refusal (don't fabricate when it truly isn't) -- the discrimination Round 1's
# instructed-only prompt failed to teach.
FEWSHOT_TURNS: List[Mapping[str, str]] = [
    {"role": "user", "content": (
        "Relevant retrieved memories (cite the [id] you use, if any):\n"
        "[m1] Priya: My new car is a bright red convertible, I love it.\n\n"
        "Question: What color is Priya's car?"
    )},
    {"role": "assistant", "content": "red"},
    {"role": "user", "content": (
        "Relevant retrieved memories (cite the [id] you use, if any):\n"
        "[m2] Marcus: The meeting got moved to 3pm on Thursday.\n"
        "[m3] Marcus: Also don't forget to bring the quarterly reports.\n\n"
        "Question: What time is the meeting?"
    )},
    {"role": "assistant", "content": "3pm on Thursday"},
    {"role": "user", "content": (
        "Relevant retrieved memories (cite the [id] you use, if any):\n"
        "[m4] Lena: I'm heading to the gym after work today.\n\n"
        "Question: What did Lena order for lunch?"
    )},
    {"role": "assistant", "content": "Not stated in the provided memories."},
]


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
        tasks.append({"task_id": tid, "question": t["question"], "answer": t["answer"], "evidence_memory_ids": t["evidence_memory_ids"]})
    return tasks


def _run_variant(task, memory_rows_by_id, llm_provider, use_fewshot: bool, results, log, variant_name: str):
    evidence_items = [
        {"memory_id": f"evidence-slot-{i+1}", "content": f"{memory_rows_by_id[eid]['source_role']}: {memory_rows_by_id[eid]['content']}"}
        for i, eid in enumerate(task["evidence_memory_ids"]) if eid in memory_rows_by_id
    ]
    context = build_agent_visible_context(
        condition=CONDITION_GOLD_EVIDENCE, task_id=task["task_id"], prompt=task["question"],
        memory_items=evidence_items,
    )
    base_messages = render_messages(context, DEFAULT_SYSTEM_PROMPT)
    if use_fewshot:
        # splice the few-shot demonstration turns between the system message and the
        # real task's user turn -- system message first, then examples, then the real
        # question, matching standard few-shot chat-formatting convention.
        messages = [base_messages[0]] + FEWSHOT_TURNS + [base_messages[1]]
    else:
        messages = base_messages

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

    results.setdefault(task["task_id"], {})[variant_name] = {
        "answer": answer, "latency_sec": latency,
        "exact_status": exact.status, "normalized_status": norm.status, "content_recall_status": recall.status,
    }
    log(f"  [{variant_name}] exact={exact.status} norm={norm.status} recall={recall.status} ans={str(answer)[:70]!r}")


def main():
    def log(msg):
        print(msg, flush=True)

    task_ids = _select_task_ids(N_TASKS)
    tasks = _build_task_records(task_ids)
    memory_rows_by_id = {row["memory_id"]: row for row in _load_jsonl(_DATA_ROOT / "locomo" / "memory_records.jsonl")}
    log(f"Selected {len(tasks)} real task_ids (same as Rounds 1-6): {task_ids}")

    endpoint = LlamaServerEndpoint()
    llm_provider = LlamaServerProvider(endpoint)
    identity_check = llm_provider.verify_server_identity()
    log(f"Server identity verified: {identity_check}")

    results: Mapping[str, Mapping[str, Any]] = {}
    for i, task in enumerate(tasks):
        log(f"\n=== Task {i+1}/{len(tasks)}: {task['task_id']} — {task['question']!r} (gold={task['answer']!r}) ===")
        _run_variant(task, memory_rows_by_id, llm_provider, use_fewshot=False, results=results, log=log, variant_name="B_NO_FEWSHOT")
        _run_variant(task, memory_rows_by_id, llm_provider, use_fewshot=True, results=results, log=log, variant_name="B_FEWSHOT")

    out_path = _OUT_DIR / "pilot_fewshot_hedging_b_n15.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump({"task_ids": task_ids, "tasks": tasks, "results": results, "fewshot_turns": FEWSHOT_TURNS}, f, indent=2, ensure_ascii=False)
    log(f"\nWrote {out_path}")

    log("\n=== SUMMARY ===")
    for variant_name in ("B_NO_FEWSHOT", "B_FEWSHOT"):
        n_exact = sum(1 for t in results.values() if t.get(variant_name, {}).get("exact_status") == "ANSWER_CORRECT")
        n_norm = sum(1 for t in results.values() if t.get(variant_name, {}).get("normalized_status") == "ANSWER_CORRECT")
        n_recall = sum(1 for t in results.values() if t.get(variant_name, {}).get("content_recall_status") == "ANSWER_CORRECT")
        n = sum(1 for t in results.values() if variant_name in t)
        log(f"  {variant_name}: exact={n_exact}/{n} normalized={n_norm}/{n} content_recall={n_recall}/{n}")


if __name__ == "__main__":
    main()
