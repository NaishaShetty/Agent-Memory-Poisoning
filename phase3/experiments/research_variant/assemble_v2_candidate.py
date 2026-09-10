"""Phase 3.3-RESEARCH -- assembles the "V2" clean-agent candidate from the three
already-independently-validated components, WITHOUT any new agent generation:

- Condition A (no-memory): UNTOUCHED. Nothing in this investigation changes anything
  about the no-memory control -- reused verbatim from the frozen 120x2 dataset's own
  recorded V1 answers.
- Condition B (gold evidence): Round 8's real, already-generated WITH_TIMESTAMP
  answers (`scaleup_timestamp_condition_b_n120.json`) -- timestamp-injected evidence
  text, otherwise identical generation config to V1.
- Condition C (retrieved memory): Round 7's real, already-generated stacked-candidate
  answers (`scaleup_stacked_candidate_n120_mem0.json`) -- pool=20 retrieval + hybrid
  top-8 selection + timestamp injection.

Both B and C were independently validated at full 120-task scale BEFORE this assembly
-- this script performs no new inference, no new agent execution, and does not modify
anything under `canonical_store/`. It only merges three already-real result sets into
one coherent per-task record structure (mirroring the frozen dataset's own shape) and
computes the final V1-vs-V2 comparison across all three conditions and all available
metrics.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from phase3.evaluation.agent.content_recall_correctness import evaluate_answer_correctness_content_recall
from phase3.evaluation.agent.normalized_correctness import evaluate_answer_correctness_normalized
from phase3.evaluation.agent.outcomes import EXECUTION_STATUS_SUCCESS, AgentExecutionResult, evaluate_answer_correctness

_RESULTS_DIR = Path(__file__).resolve().parent / "results"
_DATA_ROOT = _REPO_ROOT / "data" / "processed"

FROZEN_DATASET_PATH = (
    _REPO_ROOT / "phase3" / "experiments" / "results" / "canonical_store" / "dataset_full"
    / "clean_agent_dataset_locomo_120x2.json"
)


def _load_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def _score(answer, gold):
    exec_result = AgentExecutionResult(
        task_id="", condition="", answer=answer, execution_status=EXECUTION_STATUS_SUCCESS,
        selected_memory_ids=(), used_memory_ids=None, execution_metadata={},
    )
    exact = evaluate_answer_correctness(exec_result, gold)
    norm = evaluate_answer_correctness_normalized(exec_result, gold)
    recall = evaluate_answer_correctness_content_recall(exec_result, gold)
    return exact.status, norm.status, recall.status


def main():
    with FROZEN_DATASET_PATH.open("r", encoding="utf-8") as f:
        frozen_data = json.load(f)
    mem0_records = {r["task_id"]: r for r in frozen_data if r["foundation"] == "MEM0"}

    task_records_by_id = {t["task_id"]: t for t in _load_jsonl(_DATA_ROOT / "locomo" / "task_records.jsonl")}

    with (_RESULTS_DIR / "scaleup_timestamp_condition_b_n120.json").open("r", encoding="utf-8") as f:
        round8 = json.load(f)["results_B_with_timestamp"]

    with (_RESULTS_DIR / "scaleup_stacked_candidate_n120_mem0.json").open("r", encoding="utf-8") as f:
        round7 = json.load(f)["results_C_stacked"]

    assert set(mem0_records) == set(round8) == set(round7), "task_id sets must match exactly across all three sources"

    v2_records = {}
    tally = {
        "A": {"v1_exact": 0, "v1_norm": 0, "v1_recall": 0, "v2_exact": 0, "v2_norm": 0, "v2_recall": 0},
        "B": {"v1_exact": 0, "v1_norm": 0, "v1_recall": 0, "v2_exact": 0, "v2_norm": 0, "v2_recall": 0},
        "C": {"v1_exact": 0, "v1_norm": 0, "v1_recall": 0, "v2_exact": 0, "v2_norm": 0, "v2_recall": 0},
    }

    for tid, rec in mem0_records.items():
        gold = str(task_records_by_id[tid]["answer"])

        # Condition A -- untouched, V1 == V2
        a_answer = rec["conditions"]["A_no_memory"]["answer"]
        a_exact, a_norm, a_recall = _score(a_answer, gold)
        tally["A"]["v1_exact"] += a_exact == "ANSWER_CORRECT"; tally["A"]["v2_exact"] += a_exact == "ANSWER_CORRECT"
        tally["A"]["v1_norm"] += a_norm == "ANSWER_CORRECT"; tally["A"]["v2_norm"] += a_norm == "ANSWER_CORRECT"
        tally["A"]["v1_recall"] += a_recall == "ANSWER_CORRECT"; tally["A"]["v2_recall"] += a_recall == "ANSWER_CORRECT"

        # Condition B -- V1 (frozen) vs Round 8 (V2)
        b_v1_answer = rec["conditions"]["B_gold_evidence"]["answer"]
        b_v1_exact, b_v1_norm, b_v1_recall = _score(b_v1_answer, gold)
        b_v2_answer = round8[tid]["answer"]
        b_v2_exact, b_v2_norm, b_v2_recall = round8[tid]["exact_status"], round8[tid]["normalized_status"], round8[tid]["content_recall_status"]
        tally["B"]["v1_exact"] += b_v1_exact == "ANSWER_CORRECT"; tally["B"]["v2_exact"] += b_v2_exact == "ANSWER_CORRECT"
        tally["B"]["v1_norm"] += b_v1_norm == "ANSWER_CORRECT"; tally["B"]["v2_norm"] += b_v2_norm == "ANSWER_CORRECT"
        tally["B"]["v1_recall"] += b_v1_recall == "ANSWER_CORRECT"; tally["B"]["v2_recall"] += b_v2_recall == "ANSWER_CORRECT"

        # Condition C -- V1 (frozen) vs Round 7 (V2)
        c_v1_answer = rec["conditions"]["C_retrieved_memory"]["answer"]
        c_v1_exact, c_v1_norm, c_v1_recall = _score(c_v1_answer, gold)
        c_v2_answer = round7[tid]["answer"]
        c_v2_exact, c_v2_norm, c_v2_recall = round7[tid]["exact_status"], round7[tid]["normalized_status"], _score(c_v2_answer, gold)[2]
        tally["C"]["v1_exact"] += c_v1_exact == "ANSWER_CORRECT"; tally["C"]["v2_exact"] += c_v2_exact == "ANSWER_CORRECT"
        tally["C"]["v1_norm"] += c_v1_norm == "ANSWER_CORRECT"; tally["C"]["v2_norm"] += c_v2_norm == "ANSWER_CORRECT"
        tally["C"]["v1_recall"] += c_v1_recall == "ANSWER_CORRECT"; tally["C"]["v2_recall"] += c_v2_recall == "ANSWER_CORRECT"

        v2_records[tid] = {
            "gold": gold,
            "A_no_memory": {"v1_answer": a_answer, "v2_answer": a_answer, "note": "untouched"},
            "B_gold_evidence": {"v1_answer": b_v1_answer, "v2_answer": b_v2_answer,
                                 "v1_normalized": b_v1_norm, "v2_normalized": b_v2_norm},
            "C_retrieved_memory": {"v1_answer": c_v1_answer, "v2_answer": c_v2_answer,
                                    "v1_normalized": c_v1_norm, "v2_normalized": c_v2_norm},
        }

    out_path = _RESULTS_DIR / "v2_candidate_assembled_n120.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump({"n": 120, "tally": tally, "records": v2_records}, f, indent=2, ensure_ascii=False)

    print(f"Wrote {out_path}\n")
    print(f"{'Condition':<25}{'V1 exact':<12}{'V2 exact':<12}{'V1 norm':<12}{'V2 norm':<12}{'V1 recall':<12}{'V2 recall':<12}")
    for cond, label in (("A", "A (no-memory)"), ("B", "B (gold evidence)"), ("C", "C (retrieved memory)")):
        t = tally[cond]
        print(f"{label:<25}{t['v1_exact']:<12}{t['v2_exact']:<12}{t['v1_norm']:<12}{t['v2_norm']:<12}{t['v1_recall']:<12}{t['v2_recall']:<12}")


if __name__ == "__main__":
    main()
