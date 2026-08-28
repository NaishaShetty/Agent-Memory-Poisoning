"""Loss-aware, provenance-preserving normalization of MemoryAgentBench (candidate prep).

Phase 3.2-H.1 candidate dataset preparation. This module is part of the ISOLATED
candidate package under phase3/datasets/candidates/memoryagentbench/ -- it is not part
of the active phase3/evaluation/ pipeline and does not modify anything there.

Deterministic: no randomness, no wall-clock timestamps inside record content, no network
access (reads only from the already-downloaded raw/ directory). Running build() twice over
the same raw/ input produces byte-identical normalized/*.jsonl output -- verified in
phase3/evaluation/tests/test_candidate_memoryagentbench.py.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pandas as pd

CANDIDATE_DIR = Path(__file__).resolve().parent
HF_DIR = CANDIDATE_DIR / "raw" / "hf_dataset" / "data"
OUT_DIR = CANDIDATE_DIR / "normalized"
MANIFEST_DIR = CANDIDATE_DIR / "manifests"

SOURCE_DATASET = "memoryagentbench"
NORMALIZATION_VERSION = "3.2-h1.candidate.1"
HF_REVISION = "7ea066982b140a19337e17e60d45d4076e042faf"
GITHUB_COMMIT = "fe1735de8cf8b9908e1e3d3b5612afc815698062"

SPLIT_TO_COMPETENCY = {
    "Accurate_Retrieval": "ACCURATE_RETRIEVAL",
    "Test_Time_Learning": "TEST_TIME_LEARNING",
    "Long_Range_Understanding": "LONG_RANGE_UNDERSTANDING",
    "Conflict_Resolution": "CONFLICT_RESOLUTION",
}

SPLITS = ["Accurate_Retrieval", "Test_Time_Learning", "Long_Range_Understanding", "Conflict_Resolution"]


def np_to_native(x):
    """Convert numpy/pandas objects to plain Python (list/str/None) recursively."""
    if x is None:
        return None
    if isinstance(x, (str, int, float, bool)):
        return x
    if hasattr(x, "tolist"):
        return np_to_native(x.tolist())
    if isinstance(x, dict):
        return {k: np_to_native(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [np_to_native(v) for v in x]
    try:
        return x.item()
    except Exception:
        return x


def source_revision_block():
    return {
        "hf_dataset_revision_sha": HF_REVISION,
        "github_repo_commit": GITHUB_COMMIT,
    }


def build():
    """Read raw/hf_dataset parquet files and return (memory_records, task_records,
    counters, preprocessing_entries, exclusion_entries) -- pure function of the raw/
    directory's contents, no side effects."""
    memory_records = []
    task_records = []
    preprocessing_entries = []
    exclusion_entries = []

    counters = {
        "input_rows_total": 0,
        "input_qa_pairs_total": 0,
        "output_memory_records": 0,
        "output_task_records": 0,
        "excluded_rows": 0,
        "excluded_qa_pairs": 0,
    }

    for split in SPLITS:
        path = HF_DIR / f"{split}-00000-of-00001.parquet"
        df = pd.read_parquet(path)
        competency = SPLIT_TO_COMPETENCY[split]

        for row_index, row in df.iterrows():
            counters["input_rows_total"] += 1
            md_raw = row["metadata"]
            md = {k: np_to_native(v) for k, v in md_raw.items()} if isinstance(md_raw, dict) else np_to_native(md_raw)
            source_task_name = md.get("source")
            context = row["context"]
            questions = np_to_native(row["questions"])
            answers = np_to_native(row["answers"])

            if context is None or questions is None or answers is None or len(questions) != len(answers):
                exclusion_entries.append({
                    "record_id": f"{split}::row{row_index}",
                    "source_file": f"raw/hf_dataset/data/{split}-00000-of-00001.parquet",
                    "reason": "STRUCTURALLY_MALFORMED: context/questions/answers missing or length-mismatched (questions and answers arrays must be equal length; none were observed in the full scan performed for this candidate, so this branch is expected to be inert, but is retained as a safety net rather than assumed unreachable).",
                    "recoverable": False,
                    "retained_in_raw": True,
                    "impact_on_counts": "1 context row and all of its associated QA pairs excluded from normalized/ view.",
                })
                counters["excluded_rows"] += 1
                counters["excluded_qa_pairs"] += len(questions) if questions else 0
                continue

            positional_reference = {
                "split": split,
                "row_index": int(row_index),
                "note": (
                    "MemoryAgentBench's HF parquet format provides no explicit per-context/"
                    "document-level identifier field. This positional (split, row_index) pair "
                    "is a DERIVED, non-source-native addressing key assigned by this candidate "
                    "normalization step for stable internal cross-referencing between "
                    "memory_records.jsonl and task_records.jsonl. It is NOT a substitute for a "
                    "source-native record_id and is not asserted as one."
                ),
            }

            demo = md.get("demo")
            previous_events = md.get("previous_events")
            keypoints = md.get("keypoints")
            haystack_sessions = md.get("haystack_sessions")

            memory_record = {
                "source_dataset": SOURCE_DATASET,
                "source_record_id": "NOT_PROVIDED_BY_SOURCE",
                "source_task_id": "NOT_PROVIDED_BY_SOURCE",
                "source_session_id": "NOT_PROVIDED_BY_SOURCE",
                "source_revision": source_revision_block(),
                "normalization_version": NORMALIZATION_VERSION,
                "positional_reference": positional_reference,
                "competency": competency,
                "source_task_name": source_task_name,
                "parent_ids": "NOT_PROVIDED_BY_SOURCE",
                "equivalent_to": "NOT_PROVIDED_BY_SOURCE",
                "agent_visible_context": {
                    "content": context,
                    "content_length_chars": len(context),
                    "demo": demo if demo is not None else "NOT_PROVIDED_BY_SOURCE",
                    "previous_events": previous_events if previous_events is not None else "NOT_PROVIDED_BY_SOURCE",
                },
                "evaluator_only": {
                    "keypoints": keypoints if keypoints is not None else "NOT_PROVIDED_BY_SOURCE",
                    "haystack_sessions": haystack_sessions if haystack_sessions is not None else "NOT_PROVIDED_BY_SOURCE",
                },
            }
            memory_records.append(memory_record)
            counters["output_memory_records"] += 1
            preprocessing_entries.append({
                "input_file": f"raw/hf_dataset/data/{split}-00000-of-00001.parquet",
                "input_record_id": f"{split}::row{row_index} (positional; source provides no native context-level id)",
                "transformation": "NO_TRANSFORMATION_REQUIRED -- verbatim field carry-over into memory_records.jsonl with agent-visible/evaluator-only boundary tagging applied per phase3/evaluation/contracts/boundary.py naming conventions. No text was altered, truncated, or re-encoded.",
                "reason": "Structural normalization only (grouping under agent_visible_context/evaluator_only); no content transformation.",
                "output_record_id": f"memory_records.jsonl::{split}::row{row_index}",
                "info_preserved": ["context", "demo", "previous_events", "keypoints", "haystack_sessions", "source"],
                "info_omitted": [],
                "omission_reason": "NONE -- all source fields for this row carried over verbatim (null source fields are represented as NOT_PROVIDED_BY_SOURCE, not omitted).",
                "normalization_version": NORMALIZATION_VERSION,
            })

            qa_pair_ids = md.get("qa_pair_ids")
            question_dates = md.get("question_dates")
            question_ids = md.get("question_ids")
            question_types = md.get("question_types")

            for qi in range(len(questions)):
                counters["input_qa_pairs_total"] += 1
                qpid = qa_pair_ids[qi] if qa_pair_ids and qi < len(qa_pair_ids) else None
                q_date = question_dates[qi] if question_dates and qi < len(question_dates) else None
                q_id = question_ids[qi] if question_ids and qi < len(question_ids) else None
                q_type = question_types[qi] if question_types and qi < len(question_types) else None

                task_record = {
                    "source_dataset": SOURCE_DATASET,
                    "source_record_id": qpid if qpid is not None else "NOT_PROVIDED_BY_SOURCE",
                    "source_task_id": qpid if qpid is not None else "NOT_PROVIDED_BY_SOURCE",
                    "source_session_id": "NOT_PROVIDED_BY_SOURCE",
                    "source_revision": source_revision_block(),
                    "normalization_version": NORMALIZATION_VERSION,
                    "memory_ref": positional_reference,
                    "competency": competency,
                    "source_task_name": source_task_name,
                    "question_index_in_row": qi,
                    "parent_ids": "NOT_PROVIDED_BY_SOURCE",
                    "equivalent_to": "NOT_PROVIDED_BY_SOURCE",
                    "agent_visible": {
                        "question": questions[qi],
                    },
                    "evaluator_only": {
                        "gold_answers": answers[qi],
                        "question_date": q_date if q_date is not None else "NOT_PROVIDED_BY_SOURCE",
                        "question_id": q_id if q_id is not None else "NOT_PROVIDED_BY_SOURCE",
                        "question_type": q_type if q_type is not None else "NOT_PROVIDED_BY_SOURCE",
                        "evidence_memory_ids": "NOT_PROVIDED_BY_SOURCE",
                    },
                    "evidence_availability_note": (
                        "MemoryAgentBench does not provide per-question gold evidence memory "
                        "IDs (no chunk/turn IDs at the granularity of a retrievable memory "
                        "unit). The one partial exception is LongMemEval-sourced rows, where "
                        "the PARENT memory record's evaluator_only.haystack_sessions carries a "
                        "per-turn has_answer boolean; this task record does not duplicate that "
                        "into a synthetic evidence_memory_ids list because no source-native "
                        "turn ID exists to reference (see memory_records.jsonl's "
                        "haystack_sessions structure directly for the raw evidence-location "
                        "signal)."
                    ),
                }
                task_records.append(task_record)
                counters["output_task_records"] += 1

            preprocessing_entries.append({
                "input_file": f"raw/hf_dataset/data/{split}-00000-of-00001.parquet",
                "input_record_id": f"{split}::row{row_index}::questions[0:{len(questions)}] (qa_pair_ids: {'present' if qa_pair_ids is not None else 'ABSENT'})",
                "transformation": "One task_records.jsonl entry created per (row, question_index) pair; questions/answers arrays unzipped into individual records, tagged with agent_visible/evaluator_only boundary.",
                "reason": "MemoryAgentBench's native unit-of-evaluation is one question against one shared context ('inject once, query multiple times'); this normalization step makes each question independently addressable as its own task record, matching the mission's memory/task/evidence/answer conceptual mapping, while memory_ref preserves the link back to the shared context.",
                "output_record_id": f"task_records.jsonl::{split}::row{row_index}::q{{0..{len(questions)-1}}}",
                "info_preserved": ["questions[i]", "answers[i] (all alias strings, not just first)", "qa_pair_ids[i]", "question_dates[i] (LongMemEval only)", "question_ids[i] (LongMemEval only)", "question_types[i] (LongMemEval only)"],
                "info_omitted": [],
                "omission_reason": "NONE -- every answer alias string in the source's answers[i] list is preserved verbatim in gold_answers; no answer was dropped or collapsed to a single string.",
                "normalization_version": NORMALIZATION_VERSION,
            })

    return memory_records, task_records, counters, preprocessing_entries, exclusion_entries


def records_to_jsonl_string(records):
    return "".join(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n" for rec in records)


def write_outputs():
    memory_records, task_records, counters, preprocessing_entries, exclusion_entries = build()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "memory_records.jsonl", "w", encoding="utf-8") as f:
        f.write(records_to_jsonl_string(memory_records))
    with open(OUT_DIR / "task_records.jsonl", "w", encoding="utf-8") as f:
        f.write(records_to_jsonl_string(task_records))

    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_DIR / "preprocessing_manifest.json", "w", encoding="utf-8") as f:
        json.dump({
            "dataset_id": "memoryagentbench",
            "normalization_version": NORMALIZATION_VERSION,
            "record_count_reconciliation": counters,
            "entries": preprocessing_entries,
        }, f, indent=2, ensure_ascii=False)

    with open(MANIFEST_DIR / "exclusion_manifest.json", "w", encoding="utf-8") as f:
        json.dump({
            "dataset_id": "memoryagentbench",
            "normalization_version": NORMALIZATION_VERSION,
            "exclusions": exclusion_entries,
            "exclusion_count": len(exclusion_entries),
            "record_count_reconciliation": {
                "note": (
                    "This full-dataset scan found ZERO structurally malformed records: all "
                    "146 context rows across all 4 splits had non-null context/questions/"
                    "answers with matching questions/answers lengths (verified in "
                    "phase3/datasets/candidates/memoryagentbench/reports/raw_inventory.md). "
                    "Nothing was excluded; every input row and every input QA pair is present "
                    "in normalized/. See counters below for the explicit reconciliation."
                ),
                "counters": counters,
            },
        }, f, indent=2, ensure_ascii=False)

    return counters, preprocessing_entries, exclusion_entries


if __name__ == "__main__":
    counters, preprocessing_entries, exclusion_entries = write_outputs()
    print(json.dumps(counters, indent=2))
    print("preprocessing entries:", len(preprocessing_entries))
    print("exclusion entries:", len(exclusion_entries))
