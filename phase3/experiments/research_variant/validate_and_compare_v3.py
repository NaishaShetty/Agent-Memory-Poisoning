"""V3 validation + V1/V2/V3 comparison, full 120x2 scale, all metrics."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import jsonschema

from phase3.evaluation.agent.content_recall_correctness import evaluate_answer_correctness_content_recall
from phase3.evaluation.agent.normalized_correctness import evaluate_answer_correctness_normalized
from phase3.evaluation.agent.outcomes import EXECUTION_STATUS_SUCCESS, AgentExecutionResult, evaluate_answer_correctness

V1_PATH = _REPO_ROOT / "phase3" / "experiments" / "results" / "canonical_store" / "dataset_full" / "clean_agent_dataset_locomo_120x2.json"
V2_PATH = _REPO_ROOT / "phase3" / "experiments" / "results" / "canonical_store" / "v2_candidate" / "dataset_full" / "clean_agent_dataset_v2_locomo_120x2.json"
V3_PATH = _REPO_ROOT / "phase3" / "experiments" / "results" / "canonical_store" / "v3_candidate" / "dataset_full" / "clean_agent_dataset_v3_locomo_120x2.json"
SCHEMA_PATH = _REPO_ROOT / "phase3" / "schemas" / "clean_agent_dataset_record_schema.json"
TASK_RECORDS_PATH = _REPO_ROOT / "data" / "processed" / "locomo" / "task_records.jsonl"

V1_HASH_BEFORE = "a7c4ca592bfe1e350ce7cb394a4e653f1cc553e74ce2a06bbff6d83c4764b863"
V2_HASH_BEFORE = "db45a18f2c15ce1bd6f59d297049c5f7810e05cf3a39f4f5eb1d8f55002f5e52"


def _sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_jsonl(path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def _score(answer, gold):
    er = AgentExecutionResult(task_id="", condition="", answer=answer, execution_status=EXECUTION_STATUS_SUCCESS,
                               selected_memory_ids=(), used_memory_ids=None, execution_metadata={})
    return (evaluate_answer_correctness(er, gold).status, evaluate_answer_correctness_normalized(er, gold).status,
            evaluate_answer_correctness_content_recall(er, gold).status)


def main():
    def log(m): print(m, flush=True)

    log("=== VALIDATION ===")
    v1_now, v2_now = _sha256(V1_PATH), _sha256(V2_PATH)
    log(f"V1 unchanged: {v1_now == V1_HASH_BEFORE}")
    log(f"V2 unchanged: {v2_now == V2_HASH_BEFORE}")
    issues = []
    if v1_now != V1_HASH_BEFORE: issues.append("V1 file changed!")
    if v2_now != V2_HASH_BEFORE: issues.append("V2 file changed!")

    with V3_PATH.open("r", encoding="utf-8") as f:
        v3_records = json.load(f)
    log(f"V3 record count: {len(v3_records)} (expect 240)")
    if len(v3_records) != 240: issues.append(f"Expected 240 V3 records, got {len(v3_records)}")

    keys = [(r["task_id"], r["foundation"]) for r in v3_records]
    if len(keys) != len(set(keys)): issues.append("Duplicate records found")

    non_success = [(r["task_id"], r["foundation"], c, r["conditions"][c]["status"])
                    for r in v3_records for c in ("A_no_memory", "B_gold_evidence", "C_retrieved_memory")
                    if r["conditions"][c]["status"] != "SUCCESSFUL_EVALUATION"]
    log(f"Non-successful condition records: {len(non_success)} (expect 0)")
    if non_success: issues.append(f"{len(non_success)} non-successful records")

    with SCHEMA_PATH.open("r", encoding="utf-8") as f:
        schema = json.load(f)
    schema_errors = 0
    for r in v3_records:
        try:
            jsonschema.validate(instance=r, schema=schema)
        except jsonschema.ValidationError:
            schema_errors += 1
    log(f"Schema validation failures: {schema_errors}/240")
    if schema_errors: issues.append(f"{schema_errors} schema failures")

    log(f"\nTotal validation issues: {len(issues)}")
    for i in issues: log(f"  ISSUE: {i}")

    log("\n=== V1 vs V2 vs V3 COMPARISON ===")
    task_records = {t["task_id"]: t for t in _load_jsonl(TASK_RECORDS_PATH)}
    with V1_PATH.open("r", encoding="utf-8") as f:
        v1 = {(r["task_id"], r["foundation"]): r for r in json.load(f)}
    with V2_PATH.open("r", encoding="utf-8") as f:
        v2 = {(r["task_id"], r["foundation"]): r for r in json.load(f)}
    v3 = {(r["task_id"], r["foundation"]): r for r in v3_records}

    assert set(v1.keys()) == set(v2.keys()) == set(v3.keys()), "key sets differ!"

    for foundation in ("MEM0", "AMEM"):
        log(f"\n{'='*70}\nFOUNDATION: {foundation}\n{'='*70}")
        for cond_key, label in (("A_no_memory", "A"), ("B_gold_evidence", "B"), ("C_retrieved_memory", "C")):
            tally = {f"{v}_{m}": 0 for v in ("v1", "v2", "v3") for m in ("exact", "norm", "recall")}
            for key in v1:
                tid, fnd = key
                if fnd != foundation:
                    continue
                gold = str(task_records[tid]["answer"])
                for vname, vdata in (("v1", v1), ("v2", v2), ("v3", v3)):
                    ans = vdata[key]["conditions"][cond_key].get("answer")
                    ex, no, re = _score(ans or "", gold)
                    tally[f"{vname}_exact"] += ex == "ANSWER_CORRECT"
                    tally[f"{vname}_norm"] += no == "ANSWER_CORRECT"
                    tally[f"{vname}_recall"] += re == "ANSWER_CORRECT"
            n = 120
            log(f"\n--- Condition {label} ({foundation}) ---")
            log(f"  Exact:      V1={tally['v1_exact']}/{n}  V2={tally['v2_exact']}/{n}  V3={tally['v3_exact']}/{n}")
            log(f"  Normalized: V1={tally['v1_norm']}/{n} ({tally['v1_norm']/n*100:.1f}%)  V2={tally['v2_norm']}/{n} ({tally['v2_norm']/n*100:.1f}%)  V3={tally['v3_norm']}/{n} ({tally['v3_norm']/n*100:.1f}%)")
            log(f"  Recall:     V1={tally['v1_recall']}/{n} ({tally['v1_recall']/n*100:.1f}%)  V2={tally['v2_recall']}/{n} ({tally['v2_recall']/n*100:.1f}%)  V3={tally['v3_recall']}/{n} ({tally['v3_recall']/n*100:.1f}%)")


if __name__ == "__main__":
    main()
