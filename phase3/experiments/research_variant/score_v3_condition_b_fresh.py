"""Rescoring V3's CURRENT frozen Condition B dataset from scratch (normalized,
content-recall, date-normalized, number-word-normalized, LLM-judge) -- built after
discovering the pre-existing `llm_judge_rescoring_report_n120.json` was scored
against a DIFFERENT, older snapshot of V3 Condition B answers than what's actually
in `clean_agent_dataset_v3_locomo_120x2.json` right now (same gold, different
answer text in 112/120 cases -- V3's B must have been re-run at some point after
that report was generated). This script is the single, self-consistent source of
truth for V3's CURRENT B numbers, scored the exact same way V5's were.
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
from phase3.evaluation.agent.normalized_correctness import evaluate_answer_correctness_normalized
from phase3.evaluation.agent.number_word_normalized_correctness import evaluate_answer_correctness_number_word_normalized
from phase3.evaluation.agent.outcomes import EXECUTION_STATUS_SUCCESS, AgentExecutionResult
from phase3.evaluation.llm.provider import LlamaServerEndpoint, LlamaServerProvider

_DATA_ROOT = _REPO_ROOT / "data" / "processed"
_V3_DATASET = _REPO_ROOT / "phase3" / "experiments" / "results" / "canonical_store" / "v3_candidate" / "dataset_full" / "clean_agent_dataset_v3_locomo_120x2.json"
_OUT_DIR = Path(__file__).resolve().parent / "results"


def main():
    def log(msg):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

    with _V3_DATASET.open(encoding="utf-8") as f:
        v3 = json.load(f)
    task_records = {}
    with open(_DATA_ROOT / "locomo" / "task_records.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            task_records[r["task_id"]] = r

    endpoint = LlamaServerEndpoint()
    llm_provider = LlamaServerProvider(endpoint)
    identity = llm_provider.verify_server_identity()
    log(f"Server identity verified: {identity}")

    mem0 = [r for r in v3 if r["foundation"] == "MEM0"]
    log(f"Scoring V3 Condition B (foundation-independent, {len(mem0)} MEM0 records used as the single source) ...")

    n = n_norm = n_recall = n_date = n_date_app = n_numw = n_judge = 0
    rows = {}
    for i, r in enumerate(mem0):
        tid = r["task_id"]
        t = task_records.get(tid)
        if t is None:
            continue
        gold = str(t["answer"])
        b = r["conditions"]["B_gold_evidence"]
        answer = b.get("answer") if b.get("status") == "SUCCESSFUL_EVALUATION" else None
        if answer is None:
            continue
        n += 1
        exec_result = AgentExecutionResult(
            task_id=tid, condition="B_GOLD_EVIDENCE", answer=answer,
            execution_status=EXECUTION_STATUS_SUCCESS, selected_memory_ids=(), used_memory_ids=None, execution_metadata={},
        )
        norm_status = evaluate_answer_correctness_normalized(exec_result, gold).status
        recall_status = evaluate_answer_correctness_content_recall(exec_result, gold).status
        date_result = evaluate_answer_correctness_date_normalized(exec_result, gold)
        numw_status = evaluate_answer_correctness_number_word_normalized(exec_result, gold).status
        judge_status = evaluate_answer_correctness_llm_judge(exec_result, gold, t["question"], llm_provider).status

        if norm_status == "ANSWER_CORRECT":
            n_norm += 1
        if recall_status == "ANSWER_CORRECT":
            n_recall += 1
        if date_result.status != "EVALUATION_UNDEFINED":
            n_date_app += 1
            if date_result.status == "ANSWER_CORRECT":
                n_date += 1
        if numw_status == "ANSWER_CORRECT":
            n_numw += 1
        if judge_status == "ANSWER_CORRECT":
            n_judge += 1

        rows[tid] = {"gold": gold, "answer": answer, "normalized": norm_status, "content_recall": recall_status, "date_normalized": date_result.status, "number_word_normalized": numw_status, "llm_judge": judge_status}
        if (i + 1) % 20 == 0:
            log(f"  scored {i+1}/{len(mem0)}")

    log(f"V3 B (fresh, current frozen dataset): n={n} normalized={n_norm}/{n} content_recall={n_recall}/{n} date_normalized={n_date}/{n_date_app} number_word={n_numw}/{n} llm_judge={n_judge}/{n}")

    out_path = _OUT_DIR / "score_v3_condition_b_fresh_results.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump({"n": n, "n_normalized": n_norm, "n_content_recall": n_recall, "n_date_normalized": n_date, "n_date_applicable": n_date_app, "n_number_word": n_numw, "n_llm_judge": n_judge, "rows": rows}, f, indent=2, ensure_ascii=False)
    log(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
