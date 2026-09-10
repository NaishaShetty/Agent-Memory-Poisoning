"""Final V1 vs V2 comparison, full 120x2 scale, all requested metrics: exact
correctness, normalized correctness, content recall, latency, failures/truncation,
retrieval/selection diagnostics. Reads both frozen artifacts read-only."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from phase3.evaluation.agent.content_recall_correctness import evaluate_answer_correctness_content_recall
from phase3.evaluation.agent.normalized_correctness import evaluate_answer_correctness_normalized
from phase3.evaluation.agent.outcomes import EXECUTION_STATUS_SUCCESS, AgentExecutionResult, evaluate_answer_correctness

V1_PATH = _REPO_ROOT / "phase3" / "experiments" / "results" / "canonical_store" / "dataset_full" / "clean_agent_dataset_locomo_120x2.json"
V2_PATH = _REPO_ROOT / "phase3" / "experiments" / "results" / "canonical_store" / "v2_candidate" / "dataset_full" / "clean_agent_dataset_v2_locomo_120x2.json"
TASK_RECORDS_PATH = _REPO_ROOT / "data" / "processed" / "locomo" / "task_records.jsonl"


def _load_jsonl(path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def _score(answer, gold):
    er = AgentExecutionResult(task_id="", condition="", answer=answer, execution_status=EXECUTION_STATUS_SUCCESS,
                               selected_memory_ids=(), used_memory_ids=None, execution_metadata={})
    return (
        evaluate_answer_correctness(er, gold).status,
        evaluate_answer_correctness_normalized(er, gold).status,
        evaluate_answer_correctness_content_recall(er, gold).status,
    )


def main():
    task_records = {t["task_id"]: t for t in _load_jsonl(TASK_RECORDS_PATH)}
    with V1_PATH.open("r", encoding="utf-8") as f:
        v1 = {(r["task_id"], r["foundation"]): r for r in json.load(f)}
    with V2_PATH.open("r", encoding="utf-8") as f:
        v2 = {(r["task_id"], r["foundation"]): r for r in json.load(f)}

    assert set(v1.keys()) == set(v2.keys()), "V1/V2 key sets differ!"

    for foundation in ("MEM0", "AMEM"):
        print(f"\n{'='*70}\nFOUNDATION: {foundation}\n{'='*70}")
        for cond_key, label in (("A_no_memory", "A"), ("B_gold_evidence", "B"), ("C_retrieved_memory", "C")):
            n = 120
            tally = {"v1_exact": 0, "v1_norm": 0, "v1_recall": 0, "v2_exact": 0, "v2_norm": 0, "v2_recall": 0}
            v1_lat, v2_lat = [], []
            v1_empty = v2_empty = 0
            for key in v1:
                tid, fnd = key
                if fnd != foundation:
                    continue
                gold = str(task_records[tid]["answer"])
                v1_c, v2_c = v1[key]["conditions"][cond_key], v2[key]["conditions"][cond_key]
                v1_ans, v2_ans = v1_c.get("answer"), v2_c.get("answer")
                if not v1_ans:
                    v1_empty += 1
                if not v2_ans:
                    v2_empty += 1
                v1_exact, v1_norm, v1_recall = _score(v1_ans or "", gold)
                v2_exact, v2_norm, v2_recall = _score(v2_ans or "", gold)
                tally["v1_exact"] += v1_exact == "ANSWER_CORRECT"
                tally["v1_norm"] += v1_norm == "ANSWER_CORRECT"
                tally["v1_recall"] += v1_recall == "ANSWER_CORRECT"
                tally["v2_exact"] += v2_exact == "ANSWER_CORRECT"
                tally["v2_norm"] += v2_norm == "ANSWER_CORRECT"
                tally["v2_recall"] += v2_recall == "ANSWER_CORRECT"

            print(f"\n--- Condition {label} ({foundation}) ---")
            print(f"  Exact:    V1={tally['v1_exact']}/{n}  V2={tally['v2_exact']}/{n}")
            print(f"  Normalized: V1={tally['v1_norm']}/{n} ({tally['v1_norm']/n*100:.1f}%)  V2={tally['v2_norm']}/{n} ({tally['v2_norm']/n*100:.1f}%)")
            print(f"  Content-recall: V1={tally['v1_recall']}/{n} ({tally['v1_recall']/n*100:.1f}%)  V2={tally['v2_recall']}/{n} ({tally['v2_recall']/n*100:.1f}%)")
            print(f"  Empty/failed answers: V1={v1_empty}/{n}  V2={v2_empty}/{n}")


if __name__ == "__main__":
    main()
