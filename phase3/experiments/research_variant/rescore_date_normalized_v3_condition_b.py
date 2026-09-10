"""Phase 3.3-V4 -- Sec 15.1 pilot: pure rescoring of all 120 already-generated,
FROZEN V3 Condition-B (gold evidence, foundation-independent) answers under the new
`evaluate_answer_correctness_date_normalized()` metric. Zero new LLM generation.
Reads only from the frozen V3 dataset file -- never writes back to it, never
modifies canonical V1/V2/V3 artifacts.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from phase3.evaluation.agent.date_normalized_correctness import evaluate_answer_correctness_date_normalized
from phase3.evaluation.agent.outcomes import EXECUTION_STATUS_SUCCESS, AgentExecutionResult

V3_DATASET = _REPO_ROOT / "phase3" / "experiments" / "results" / "canonical_store" / "v3_candidate" / "dataset_full" / "clean_agent_dataset_v3_locomo_120x2.json"
TASK_RECORDS = _REPO_ROOT / "data" / "processed" / "locomo" / "task_records.jsonl"
OUT_DIR = Path(__file__).resolve().parent / "results"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    with V3_DATASET.open(encoding="utf-8") as f:
        v3 = json.load(f)
    mem0 = {r["task_id"]: r for r in v3 if r["foundation"] == "MEM0"}

    task_records = {}
    with TASK_RECORDS.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            task_records[r["task_id"]] = r

    applicable = 0
    already_correct_normalized = 0
    newly_credited = []
    still_incorrect_examples = []

    for tid, rec in mem0.items():
        gold = str(task_records[tid]["answer"])
        b = rec["conditions"]["B_gold_evidence"]
        if b.get("status") != "SUCCESSFUL_EVALUATION":
            continue
        answer = b.get("answer") or ""
        exec_result = AgentExecutionResult(
            task_id=tid, condition="B_GOLD_EVIDENCE", answer=answer,
            execution_status=EXECUTION_STATUS_SUCCESS, selected_memory_ids=(), used_memory_ids=None,
            execution_metadata={},
        )
        date_result = evaluate_answer_correctness_date_normalized(exec_result, gold)
        if date_result.status == "EVALUATION_UNDEFINED":
            continue  # not date-shaped gold -- this metric declines to opine

        applicable += 1
        was_normalized_correct = b.get("evaluation_result", {}).get("success_status") == "ANSWER_CORRECT"
        if was_normalized_correct:
            already_correct_normalized += 1

        if date_result.status == "ANSWER_CORRECT" and not was_normalized_correct:
            newly_credited.append({
                "task_id": tid, "question": task_records[tid]["question"], "gold": gold,
                "answer": answer, "date_detail": date_result.detail,
            })
        elif date_result.status == "ANSWER_INCORRECT":
            still_incorrect_examples.append({
                "task_id": tid, "question": task_records[tid]["question"], "gold": gold,
                "answer": answer, "date_detail": date_result.detail,
            })

    print(f"Applicable (date-shaped gold) tasks: {applicable}/120")
    print(f"Already normalized-correct among those: {already_correct_normalized}")
    print(f"Newly credited by date-normalization: {len(newly_credited)}")
    print(f"Still incorrect under date-normalization too: {len(still_incorrect_examples)}")
    print()
    print("=== ALL NEWLY-CREDITED CASES (for mandatory hand spot-check) ===")
    for c in newly_credited:
        print(f"- Q: {c['question']!r}")
        print(f"  GOLD: {c['gold']!r}")
        print(f"  ANSWER: {c['answer']!r}")
        print(f"  date_detail: {c['date_detail']}")
        print()

    print("=== Sample of still-incorrect-under-date-normalization (first 5, sanity check) ===")
    for c in still_incorrect_examples[:5]:
        print(f"- Q: {c['question']!r} | GOLD: {c['gold']!r} | ANSWER: {c['answer'][:100]!r}")

    out = {
        "applicable": applicable,
        "already_correct_normalized": already_correct_normalized,
        "newly_credited": newly_credited,
        "still_incorrect_examples": still_incorrect_examples,
    }
    out_path = OUT_DIR / "rescore_date_normalized_v3_condition_b.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
