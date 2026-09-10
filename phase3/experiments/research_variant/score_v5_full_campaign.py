"""Scores the completed V5_VERIFIED full-campaign dataset (240 records = 120 tasks
x 2 foundations) across all four correctness metrics (exact, normalized, content-
recall, date-normalized) plus LLM-judge, for direct comparison against V3's
existing full-scale (n=120) rescoring report. Condition A/B are foundation-
independent (duplicated verbatim across the two foundation records per
dataset_record_assembler.py's own docstring), so each is judged ONCE per task_id,
not twice -- Condition C differs per foundation and is judged separately for each.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from phase3.evaluation.agent.content_recall_correctness import evaluate_answer_correctness_content_recall
from phase3.evaluation.agent.date_normalized_correctness import evaluate_answer_correctness_date_normalized
from phase3.evaluation.agent.llm_judge_correctness import evaluate_answer_correctness_llm_judge
from phase3.evaluation.agent.nli_entailment_correctness import evaluate_answer_correctness_nli_entailment
from phase3.evaluation.agent.normalized_correctness import evaluate_answer_correctness_normalized
from phase3.evaluation.agent.outcomes import EXECUTION_STATUS_SUCCESS, AgentExecutionResult
from phase3.evaluation.llm.provider import LlamaServerEndpoint, LlamaServerProvider

_DATA_ROOT = _REPO_ROOT / "data" / "processed"
_V5_DATASET = _REPO_ROOT / "phase3" / "experiments" / "results" / "canonical_store" / "v5_candidate" / "dataset_full" / "clean_agent_dataset_v5_verified_locomo_120x2.json"
_OUT_DIR = Path(__file__).resolve().parent / "results"


def _score_one(answer, gold, question, llm_provider, condition_label):
    exec_result = AgentExecutionResult(
        task_id="scoring", condition=condition_label, answer=answer,
        execution_status=EXECUTION_STATUS_SUCCESS, selected_memory_ids=(), used_memory_ids=None, execution_metadata={},
    )
    return {
        "normalized": None,  # already present in the assembled dataset's evaluation_result.success_status
        "content_recall": evaluate_answer_correctness_content_recall(exec_result, gold).status,
        "date_normalized": evaluate_answer_correctness_date_normalized(exec_result, gold).status,
        "nli_entailment": evaluate_answer_correctness_nli_entailment(exec_result, gold, question).status,
        "llm_judge": evaluate_answer_correctness_llm_judge(exec_result, gold, question, llm_provider).status,
    }


def main():
    def log(msg):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

    with _V5_DATASET.open(encoding="utf-8") as f:
        v5 = json.load(f)
    log(f"Loaded {len(v5)} V5 records.")

    task_records = {}
    with open(_DATA_ROOT / "locomo" / "task_records.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            task_records[r["task_id"]] = r

    endpoint = LlamaServerEndpoint()
    llm_provider = LlamaServerProvider(endpoint)
    identity = llm_provider.verify_server_identity()
    log(f"Server identity verified: {identity}")

    by_task = {}
    for rec in v5:
        by_task.setdefault(rec["task_id"], {})[rec["foundation"]] = rec

    results = {}
    n_tasks = len(by_task)
    for i, (tid, foundations) in enumerate(by_task.items()):
        t = task_records.get(tid)
        if t is None:
            continue
        gold = str(t["answer"])
        question = t["question"]
        any_rec = foundations.get("MEM0") or foundations.get("AMEM")

        row = {"gold": gold}

        a_block = any_rec["conditions"]["A_no_memory"]
        b_block = any_rec["conditions"]["B_gold_evidence"]
        a_answer = a_block.get("answer") if a_block.get("status") == "SUCCESSFUL_EVALUATION" else None
        b_answer = b_block.get("answer") if b_block.get("status") == "SUCCESSFUL_EVALUATION" else None
        row["A_answer"] = a_answer
        row["A_normalized"] = a_block.get("evaluation_result", {}).get("success_status")
        row["A_scores"] = _score_one(a_answer, gold, question, llm_provider, "A_NO_MEMORY") if a_answer is not None else None
        row["B_answer"] = b_answer
        row["B_normalized"] = b_block.get("evaluation_result", {}).get("success_status")
        row["B_scores"] = _score_one(b_answer, gold, question, llm_provider, "B_GOLD_EVIDENCE") if b_answer is not None else None

        for fname in ("MEM0", "AMEM"):
            rec = foundations.get(fname)
            if rec is None:
                continue
            c_block = rec["conditions"]["C_retrieved_memory"]
            c_answer = c_block.get("answer") if c_block.get("status") == "SUCCESSFUL_EVALUATION" else None
            row[f"C_{fname}_answer"] = c_answer
            row[f"C_{fname}_normalized"] = c_block.get("evaluation_result", {}).get("success_status")
            row[f"C_{fname}_scores"] = _score_one(c_answer, gold, question, llm_provider, "C_RETRIEVED_MEMORY") if c_answer is not None else None

        results[tid] = row
        if (i + 1) % 20 == 0:
            log(f"  scored {i+1}/{n_tasks} tasks")

    out_path = _OUT_DIR / "score_v5_full_campaign_results.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    log(f"Wrote {out_path}")

    def _tally(key_prefix, normalized_key, scores_key):
        n = n_norm = n_recall = n_date = n_judge = n_date_applicable = n_nli = 0
        for row in results.values():
            if row.get(f"{key_prefix}_answer") is None and row.get(scores_key) is None:
                continue
            n += 1
            if row.get(normalized_key) == "ANSWER_CORRECT":
                n_norm += 1
            sc = row.get(scores_key)
            if sc:
                if sc["content_recall"] == "ANSWER_CORRECT":
                    n_recall += 1
                if sc["date_normalized"] == "ANSWER_CORRECT":
                    n_date += 1
                if sc["date_normalized"] != "EVALUATION_UNDEFINED":
                    n_date_applicable += 1
                if sc["nli_entailment"] == "ANSWER_CORRECT":
                    n_nli += 1
                if sc["llm_judge"] == "ANSWER_CORRECT":
                    n_judge += 1
        return n, n_norm, n_recall, n_date, n_date_applicable, n_nli, n_judge

    log("\n=== SUMMARY (V5_VERIFIED, n=120 tasks) ===")
    for label, prefix, norm_key, scores_key in (
        ("A (no memory)", "A", "A_normalized", "A_scores"),
        ("B (gold evidence)", "B", "B_normalized", "B_scores"),
        ("C (Mem0)", "C_MEM0", "C_MEM0_normalized", "C_MEM0_scores"),
        ("C (A-MEM)", "C_AMEM", "C_AMEM_normalized", "C_AMEM_scores"),
    ):
        n, n_norm, n_recall, n_date, n_date_app, n_nli, n_judge = _tally(prefix, norm_key, scores_key)
        log(f"  {label}: n={n} normalized={n_norm}/{n} content_recall={n_recall}/{n} date_normalized={n_date}/{n_date_app} nli_entailment={n_nli}/{n} llm_judge={n_judge}/{n}")


if __name__ == "__main__":
    main()
