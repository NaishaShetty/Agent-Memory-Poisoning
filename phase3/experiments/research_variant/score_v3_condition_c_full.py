"""Scores V3's frozen Condition C (both Mem0 and A-MEM) answers, at full n=120,
across content-recall and LLM-judge -- the two metrics that were previously only
computed for V3 Condition B (llm_judge_rescoring_report_n120.json), never for
Condition C. Built to give a real, same-metric baseline to compare V5_VERIFIED's
full-campaign Condition C results against, rather than only having V3's normalized
number to compare (see this conversation's V5-vs-V3 report). Reads ONLY from V3's
existing frozen dataset file -- never writes back to it, never modifies it.
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
from phase3.evaluation.agent.llm_judge_correctness import evaluate_answer_correctness_llm_judge
from phase3.evaluation.agent.normalized_correctness import evaluate_answer_correctness_normalized
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

    results = {}
    for fname in ("MEM0", "AMEM"):
        recs = [r for r in v3 if r["foundation"] == fname]
        log(f"=== V3 Condition C, {fname} ({len(recs)} records) ===")
        n = n_norm = n_recall = n_judge = 0
        rows = {}
        for i, r in enumerate(recs):
            tid = r["task_id"]
            t = task_records.get(tid)
            if t is None:
                continue
            gold = str(t["answer"])
            c = r["conditions"]["C_retrieved_memory"]
            answer = c.get("answer") if c.get("status") == "SUCCESSFUL_EVALUATION" else None
            if answer is None:
                continue
            n += 1
            exec_result = AgentExecutionResult(
                task_id=tid, condition="C_RETRIEVED_MEMORY", answer=answer,
                execution_status=EXECUTION_STATUS_SUCCESS, selected_memory_ids=(), used_memory_ids=None, execution_metadata={},
            )
            norm_status = evaluate_answer_correctness_normalized(exec_result, gold).status
            recall_status = evaluate_answer_correctness_content_recall(exec_result, gold).status
            judge_status = evaluate_answer_correctness_llm_judge(exec_result, gold, t["question"], llm_provider).status
            if norm_status == "ANSWER_CORRECT":
                n_norm += 1
            if recall_status == "ANSWER_CORRECT":
                n_recall += 1
            if judge_status == "ANSWER_CORRECT":
                n_judge += 1
            rows[tid] = {"gold": gold, "answer": answer, "normalized": norm_status, "content_recall": recall_status, "llm_judge": judge_status}
            if (i + 1) % 20 == 0:
                log(f"  scored {i+1}/{len(recs)}")

        log(f"  {fname}: n={n} normalized={n_norm}/{n} content_recall={n_recall}/{n} llm_judge={n_judge}/{n}")
        results[fname] = {"n": n, "n_normalized": n_norm, "n_content_recall": n_recall, "n_llm_judge": n_judge, "rows": rows}

    out_path = _OUT_DIR / "score_v3_condition_c_full_results.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    log(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
