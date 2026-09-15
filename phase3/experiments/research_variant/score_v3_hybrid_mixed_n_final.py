"""Scores the completed V3-hybrid full-campaign dataset (240 records = 120 tasks x
2 foundations) across all EIGHT correctness metrics (adding nli_entailment and
multi_reference as of this pass), mirroring score_v5_full_campaign.py, for direct
comparison against V3's own frozen numbers and V5_VERIFIED's numbers already
gathered this session.

Part M regression-search fix (2026-09-15): `_DATASET` now points at
`..._locomo_120x2_P2FIX.json`, the corrected assembly (regenerated Condition
B + unchanged Conditions A/C-mem0/C-amem, per the resource-reconciliation
pass's own §4/§14) -- this script was found still pointing at the
pre-regeneration file, a real stale-pathway bug: Condition A/C-mem0/C-amem
scores are identical either way (those conditions were never regenerated),
but Condition B scores from the old file would have been stale relative to
the P2 fix. The pre-fix file remains on disk
(`..._locomo_120x2_OLD.json`, under `checkpoints/pre_p2_fix_backup_2026-09-15/`)
for historical comparison, not deleted.
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
from phase3.evaluation.agent.multi_reference_correctness import evaluate_answer_correctness_multi_reference, load_verified_aliases
from phase3.evaluation.agent.nli_entailment_correctness import evaluate_answer_correctness_nli_entailment
from phase3.evaluation.agent.normalized_correctness import evaluate_answer_correctness_normalized
from phase3.evaluation.agent.number_word_normalized_correctness import evaluate_answer_correctness_number_word_normalized
from phase3.evaluation.agent.outcomes import EXECUTION_STATUS_SUCCESS, AgentExecutionResult
from phase3.evaluation.llm.provider import LlamaServerEndpoint, LlamaServerProvider

_DATA_ROOT = _REPO_ROOT / "data" / "processed"
_DATASET = _REPO_ROOT / "phase3" / "experiments" / "results" / "canonical_store" / "v3_hybrid_candidate" / "dataset_full" / "clean_agent_dataset_v3_hybrid_locomo_mixed_n_500_120_FINAL.json"
_OUT_DIR = Path(__file__).resolve().parent / "results"


def _score(answer, gold, question, llm_provider, tid=None, aliases_by_tid=None):
    if answer is None:
        return None
    exec_result = AgentExecutionResult(
        task_id=tid or "x", condition="x", answer=answer,
        execution_status=EXECUTION_STATUS_SUCCESS, selected_memory_ids=(), used_memory_ids=None, execution_metadata={},
    )
    date_result = evaluate_answer_correctness_date_normalized(exec_result, gold)
    aliases = (aliases_by_tid or {}).get(tid)
    return {
        "normalized": evaluate_answer_correctness_normalized(exec_result, gold).status,
        "content_recall": evaluate_answer_correctness_content_recall(exec_result, gold).status,
        "date_normalized": date_result.status,
        "number_word": evaluate_answer_correctness_number_word_normalized(exec_result, gold).status,
        "nli_entailment": evaluate_answer_correctness_nli_entailment(exec_result, gold, question).status,
        "multi_reference": evaluate_answer_correctness_multi_reference(exec_result, gold, aliases).status,
        "llm_judge": evaluate_answer_correctness_llm_judge(exec_result, gold, question, llm_provider).status,
    }


def main():
    def log(msg):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

    with _DATASET.open(encoding="utf-8") as f:
        hybrid = json.load(f)
    log(f"Loaded {len(hybrid)} V3-hybrid records.")

    task_records = {}
    with open(_DATA_ROOT / "locomo" / "task_records.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            task_records[r["task_id"]] = r

    endpoint = LlamaServerEndpoint()
    llm_provider = LlamaServerProvider(endpoint)
    identity = llm_provider.verify_server_identity()
    log(f"Server identity verified: {identity}")

    aliases_path = _OUT_DIR / "multiref_gold_aliases_VERIFIED_110.json"
    aliases_by_tid = load_verified_aliases(str(aliases_path)) if aliases_path.exists() else {}
    log(f"Loaded verified aliases for {len(aliases_by_tid)} tasks (of 120) from {aliases_path.name}.")

    by_task = {}
    for rec in hybrid:
        by_task.setdefault(rec["task_id"], {})[rec["foundation"]] = rec

    def _new_bucket():
        return {"n": 0, "normalized": 0, "content_recall": 0, "date_normalized": 0, "date_applicable": 0, "number_word": 0, "nli_entailment": 0, "multi_reference": 0, "llm_judge": 0}

    tallies = {"A": _new_bucket(), "B": _new_bucket(), "C_MEM0": _new_bucket(), "C_AMEM": _new_bucket()}

    def _accumulate(bucket, scores):
        if scores is None:
            return
        bucket["n"] += 1
        if scores["normalized"] == "ANSWER_CORRECT":
            bucket["normalized"] += 1
        if scores["content_recall"] == "ANSWER_CORRECT":
            bucket["content_recall"] += 1
        if scores["date_normalized"] != "EVALUATION_UNDEFINED":
            bucket["date_applicable"] += 1
            if scores["date_normalized"] == "ANSWER_CORRECT":
                bucket["date_normalized"] += 1
        if scores["number_word"] == "ANSWER_CORRECT":
            bucket["number_word"] += 1
        if scores["nli_entailment"] == "ANSWER_CORRECT":
            bucket["nli_entailment"] += 1
        if scores["multi_reference"] == "ANSWER_CORRECT":
            bucket["multi_reference"] += 1
        if scores["llm_judge"] == "ANSWER_CORRECT":
            bucket["llm_judge"] += 1

    n_tasks = len(by_task)
    for i, (tid, foundations) in enumerate(by_task.items()):
        t = task_records.get(tid)
        if t is None:
            continue
        gold = str(t["answer"])
        question = t["question"]
        any_rec = foundations.get("MEM0") or foundations.get("AMEM")

        a_block = any_rec["conditions"]["A_no_memory"]
        b_block = any_rec["conditions"]["B_gold_evidence"]
        a_answer = a_block.get("answer") if a_block.get("status") == "SUCCESSFUL_EVALUATION" else None
        b_answer = b_block.get("answer") if b_block.get("status") == "SUCCESSFUL_EVALUATION" else None
        _accumulate(tallies["A"], _score(a_answer, gold, question, llm_provider, tid, aliases_by_tid))
        _accumulate(tallies["B"], _score(b_answer, gold, question, llm_provider, tid, aliases_by_tid))

        for fname, key in (("MEM0", "C_MEM0"), ("AMEM", "C_AMEM")):
            rec = foundations.get(fname)
            if rec is None:
                continue
            c_block = rec["conditions"]["C_retrieved_memory"]
            c_answer = c_block.get("answer") if c_block.get("status") == "SUCCESSFUL_EVALUATION" else None
            _accumulate(tallies[key], _score(c_answer, gold, question, llm_provider, tid, aliases_by_tid))

        if (i + 1) % 20 == 0:
            log(f"  scored {i+1}/{n_tasks} tasks")

    out_path = _OUT_DIR / "score_v3_hybrid_mixed_n_FINAL_results.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(tallies, f, indent=2, ensure_ascii=False)
    log(f"Wrote {out_path}")

    log("\n=== SUMMARY (V3-hybrid, n=120 tasks) ===")
    for label in ("A", "B", "C_MEM0", "C_AMEM"):
        b = tallies[label]
        n = b["n"]
        log(f"  {label}: n={n} normalized={b['normalized']}/{n} ({b['normalized']/n*100:.1f}%) multi_reference={b['multi_reference']}/{n} ({b['multi_reference']/n*100:.1f}%) "
            f"content_recall={b['content_recall']}/{n} ({b['content_recall']/n*100:.1f}%) "
            f"date_normalized={b['date_normalized']}/{b['date_applicable']} number_word={b['number_word']}/{n} nli_entailment={b['nli_entailment']}/{n} ({b['nli_entailment']/n*100:.1f}%) "
            f"llm_judge={b['llm_judge']}/{n} ({b['llm_judge']/n*100:.1f}%)")


if __name__ == "__main__":
    main()
