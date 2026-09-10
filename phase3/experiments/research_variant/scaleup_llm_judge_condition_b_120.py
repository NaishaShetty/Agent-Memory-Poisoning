"""Phase 3.3-RESEARCH Round 10 -- LLM-judge rescoring of all 120 real Condition-B
(gold evidence) answers already on record in the frozen dataset. Does NOT generate any
NEW agent answers -- purely re-judges the existing, already-generated real answers with
`evaluate_answer_correctness_llm_judge()`. Reports alongside the other three metrics
(exact, normalized, content-recall), never replacing any of them.

Incrementally checkpointed after every task (same discipline as Rounds 7/8, after an
earlier scale-up was lost mid-run to a session exit).
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
from phase3.evaluation.agent.outcomes import EXECUTION_STATUS_SUCCESS, AgentExecutionResult, evaluate_answer_correctness
from phase3.evaluation.llm.provider import LlamaServerEndpoint, LlamaServerProvider

_DATA_ROOT = _REPO_ROOT / "data" / "processed"
_OUT_DIR = Path(__file__).resolve().parent / "results"
_OUT_DIR.mkdir(parents=True, exist_ok=True)

FROZEN_DATASET_PATH = (
    _REPO_ROOT / "phase3" / "experiments" / "results" / "canonical_store" / "dataset_full"
    / "clean_agent_dataset_locomo_120x2.json"
)


def _load_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def main():
    def log(msg):
        print(msg, flush=True)

    with FROZEN_DATASET_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    mem0_records = [r for r in data if r["foundation"] == "MEM0"]

    task_records_by_id = {t["task_id"]: t for t in _load_jsonl(_DATA_ROOT / "locomo" / "task_records.jsonl")}

    endpoint = LlamaServerEndpoint()
    llm_provider = LlamaServerProvider(endpoint)
    identity_check = llm_provider.verify_server_identity()
    log(f"Server identity verified: {identity_check}")

    out_path = _OUT_DIR / "llm_judge_rescoring_report_n120.json"
    results = {}
    if out_path.exists():
        with out_path.open("r", encoding="utf-8") as f:
            prior = json.load(f)
        results = prior.get("rows_by_task_id", {})
        log(f"Resuming from existing checkpoint: {len(results)}/120 tasks already judged.")

    def _checkpoint():
        n_exact = sum(1 for r in results.values() if r["exact"] == "ANSWER_CORRECT")
        n_norm = sum(1 for r in results.values() if r["normalized"] == "ANSWER_CORRECT")
        n_recall = sum(1 for r in results.values() if r["content_recall"] == "ANSWER_CORRECT")
        n_judge = sum(1 for r in results.values() if r["llm_judge"] == "ANSWER_CORRECT")
        with out_path.open("w", encoding="utf-8") as f:
            json.dump({
                "n": len(results), "n_exact": n_exact, "n_normalized": n_norm,
                "n_content_recall": n_recall, "n_llm_judge": n_judge,
                "rows_by_task_id": results,
            }, f, indent=2, ensure_ascii=False)

    t_start = time.time()
    for i, rec in enumerate(mem0_records):
        tid = rec["task_id"]
        if tid in results:
            continue
        gold = str(task_records_by_id[tid]["answer"])
        question = task_records_by_id[tid]["question"]
        b = rec["conditions"]["B_gold_evidence"]
        answer = b.get("answer")

        exec_result = AgentExecutionResult(
            task_id=tid, condition="B", answer=answer, execution_status=EXECUTION_STATUS_SUCCESS,
            selected_memory_ids=(), used_memory_ids=None, execution_metadata={},
        )
        exact = evaluate_answer_correctness(exec_result, gold)
        norm = evaluate_answer_correctness_normalized(exec_result, gold)
        recall = evaluate_answer_correctness_content_recall(exec_result, gold)
        judge = evaluate_answer_correctness_llm_judge(exec_result, gold, question, llm_provider)

        results[tid] = {
            "gold": gold, "answer": answer,
            "exact": exact.status, "normalized": norm.status, "content_recall": recall.status,
            "llm_judge": judge.status, "llm_judge_raw": judge.detail.get("raw_judge_output"),
        }
        log(f"[{i+1}/120] {tid[:8]} judge={judge.status} ({judge.detail.get('raw_judge_output')!r}) "
            f"recall={recall.status} gold={gold!r} ans={str(answer)[:60]!r}")
        _checkpoint()
        if len(results) % 20 == 0:
            elapsed = time.time() - t_start
            log(f"--- progress: {len(results)}/120, elapsed this run={elapsed/60:.1f}min ---")

    n_exact = sum(1 for r in results.values() if r["exact"] == "ANSWER_CORRECT")
    n_norm = sum(1 for r in results.values() if r["normalized"] == "ANSWER_CORRECT")
    n_recall = sum(1 for r in results.values() if r["content_recall"] == "ANSWER_CORRECT")
    n_judge = sum(1 for r in results.values() if r["llm_judge"] == "ANSWER_CORRECT")
    n_undefined = sum(1 for r in results.values() if r["llm_judge"] not in ("ANSWER_CORRECT", "ANSWER_INCORRECT"))
    log(f"\nFinal write complete: {out_path}")
    log(f"\n=== SUMMARY (n=120, Condition B) ===")
    log(f"  exact={n_exact}/120  normalized={n_norm}/120  content_recall={n_recall}/120  llm_judge={n_judge}/120  (llm_judge undefined/unparsed: {n_undefined})")


if __name__ == "__main__":
    main()
