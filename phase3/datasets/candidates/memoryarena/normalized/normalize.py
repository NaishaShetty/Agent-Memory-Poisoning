"""Loss-aware, provenance-preserving normalization for the MemoryArena candidate dataset.

Phase 3.2-H.1 candidate preparation ONLY. This script is deterministic (no randomness, no
network, no model calls) and, run twice over the same raw input, produces byte-identical
output (verified by phase3/evaluation/tests/test_candidate_memoryarena.py).

Design decision (native structure, not a forced QA collapse): MemoryArena's source data is
organized as "task chains" -- one record per chain, containing an ordered list of
interdependent subtasks. This script preserves that native two-level structure:

  - one `task_chain_record` per source JSONL line (the chain-level object -- carries
    source_dataset/source_record_id/source_task_id and whatever chain-level fields the
    source provides: category, paper_name, base_person, backgrounds), and
  - one `subtask_record` per (chain, subtask-index) pair (questions[i]/answers[i]),
    carrying its own source_record_id (derived from the parent id + index, since the
    source provides no separate subtask-level ID) and an explicit `subtask_index` /
    `chain_length` pair encoding the positional interdependency ordering the source
    conveys implicitly via list position.

No gold answer, evidence, or lineage is invented anywhere. Every field absent from the
source is written as the literal string "NOT_PROVIDED_BY_SOURCE", never omitted silently
and never guessed.
"""

from __future__ import annotations

import json
import os

NORMALIZATION_VERSION = "memoryarena-normalization-1.0.0"
SOURCE_DATASET = "memoryarena"
NOT_PROVIDED = "NOT_PROVIDED_BY_SOURCE"

CONFIGS = [
    "bundled_shopping",
    "progressive_search",
    "group_travel_planner",
    "formal_reasoning_math",
    "formal_reasoning_phys",
]

# Source revision pins recorded in manifests/raw_fingerprint.json; repeated here so the
# normalized output is self-describing without requiring a cross-file join.
SOURCE_REVISION = {
    "github_commit_hash": "6cd9de14b71915e39ac742a20dc33785e14b6aab",
    "huggingface_dataset_sha": "da1a37c8b19280e18627ca01cf368195a5e1d92e",
}


def _load_config(raw_dir: str, config: str) -> list[dict]:
    path = os.path.join(raw_dir, "hf_dataset", config, "data.jsonl")
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def _chain_level_fields(config: str, record: dict) -> dict:
    """Extract whatever chain-level (non-questions/answers) fields the source provides
    for this config, verbatim, with NOT_PROVIDED_BY_SOURCE for absent ones. Never
    invented, never inferred."""
    if config == "bundled_shopping":
        return {"category": record.get("category", NOT_PROVIDED)}
    if config == "formal_reasoning_math" or config == "formal_reasoning_phys":
        return {
            "paper_name": record.get("paper_name", NOT_PROVIDED),
            "backgrounds": record.get("backgrounds", NOT_PROVIDED),
        }
    if config == "group_travel_planner":
        return {"base_person": record.get("base_person", NOT_PROVIDED)}
    if config == "progressive_search":
        return {}
    raise ValueError(f"unknown config: {config}")


def normalize(raw_dir: str) -> dict:
    """Returns {"task_chains": [...], "subtasks": [...]} -- both loss-aware, sorted
    deterministically by (source_config, source_record_id, [subtask_index]) so re-running
    this function is byte-for-byte reproducible."""
    task_chains = []
    subtasks = []

    for config in CONFIGS:
        records = _load_config(raw_dir, config)
        for record in records:
            source_record_id = record["id"]
            questions = record.get("questions", [])
            answers = record.get("answers", [])

            chain_entry = {
                "source_dataset": SOURCE_DATASET,
                "source_config": config,
                "source_record_id": source_record_id,
                "source_task_id": f"{config}:{source_record_id}",
                "source_session_id": NOT_PROVIDED,
                "source_revision": SOURCE_REVISION,
                "normalization_version": NORMALIZATION_VERSION,
                "chain_length": len(questions),
                "parent_ids": NOT_PROVIDED,
                "equivalent_to": NOT_PROVIDED,
                "chain_fields": _chain_level_fields(config, record),
            }
            task_chains.append(chain_entry)

            for idx, (q, a) in enumerate(zip(questions, answers)):
                subtask_entry = {
                    "source_dataset": SOURCE_DATASET,
                    "source_config": config,
                    "source_record_id": source_record_id,
                    "source_task_id": f"{config}:{source_record_id}",
                    "source_session_id": NOT_PROVIDED,
                    # Derived (not source-provided) composite key; this is NOT a
                    # source_record_id, it is documented explicitly as
                    # normalization-derived, never presented as if the source assigned it.
                    "derived_subtask_key": f"{config}:{source_record_id}:{idx}",
                    "subtask_index": idx,
                    "chain_length": len(questions),
                    "source_revision": SOURCE_REVISION,
                    "normalization_version": NORMALIZATION_VERSION,
                    "question": q,
                    "answer": a,
                    "parent_ids": NOT_PROVIDED,
                    "equivalent_to": NOT_PROVIDED,
                    "evidence_memory_ids": NOT_PROVIDED,
                    "timestamp": NOT_PROVIDED,
                }
                subtasks.append(subtask_entry)

    # Deterministic ordering: already inserted in file-then-line-then-index order, which
    # is itself deterministic given a fixed raw_dir; no further sort needed, but an
    # explicit stable sort is applied anyway so the guarantee does not silently depend on
    # dict/list insertion-order behavior of a particular Python version.
    task_chains.sort(key=lambda r: (r["source_config"], r["source_record_id"]))
    subtasks.sort(key=lambda r: (r["source_config"], r["source_record_id"], r["subtask_index"]))

    return {"task_chains": task_chains, "subtasks": subtasks}


def write_normalized(raw_dir: str, out_dir: str) -> None:
    result = normalize(raw_dir)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "task_chains.jsonl"), "w", encoding="utf-8") as f:
        for entry in result["task_chains"]:
            f.write(json.dumps(entry, ensure_ascii=False, sort_keys=True))
            f.write("\n")
    with open(os.path.join(out_dir, "subtasks.jsonl"), "w", encoding="utf-8") as f:
        for entry in result["subtasks"]:
            f.write(json.dumps(entry, ensure_ascii=False, sort_keys=True))
            f.write("\n")


if __name__ == "__main__":
    import sys

    raw_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "raw")
    out_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(__file__)
    write_normalized(raw_dir, out_dir)
    print(f"Normalized output written to {out_dir}")
