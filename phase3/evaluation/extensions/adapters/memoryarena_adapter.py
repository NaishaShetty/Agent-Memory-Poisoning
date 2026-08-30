"""Phase 3.2-H.3 -- `DatasetAdapter` for the MemoryArena candidate (read-only).

Operates on the exact record shapes already produced by
`phase3/datasets/candidates/memoryarena/normalized/normalize.py` (H.1, unmodified):
- `normalized/task_chains.jsonl` -- one record per task chain, `{"chain_length": ...,
  "source_task_id": ..., "source_config": ..., ...}`.
- `normalized/subtasks.jsonl` -- one record per subtask, `{"derived_subtask_key":
  "<config>:<chain_record_id>:<subtask_index>", "chain_length": ..., "question": ...,
  "answer": ..., "evidence_memory_ids": "NOT_PROVIDED_BY_SOURCE", ...}`.

This is the adapter that exercises Extension 3 (`agentic_memory.py`): MemoryArena has no
memory-unit layer and no gold_evidence_ids at all (confirmed by full scan, 701 records,
per `mambench_compatibility.json`), so `evidence_basis()` below always classifies
`EVIDENCE_BASIS_NONE_AVAILABLE` -- this adapter never invents a memory-ID scheme for
MemoryArena. Its actual native strength, chain/subtask structure, is surfaced via
`session_structure()` and `phase3.evaluation.extensions.agentic_memory.ChainSubtask`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List, Mapping

from phase3.evaluation.datasets.capability import (
    CAPABILITY_AVAILABLE,
    CAPABILITY_NOT_PROVIDED_BY_SOURCE,
    CAPABILITY_PARTIAL,
)
from phase3.evaluation.extensions.agentic_memory import (
    ChainSubtask,
    subtask_index_from_derived_key,
)
from phase3.evaluation.extensions.evidence_basis import (
    EVIDENCE_BASIS_NONE_AVAILABLE,
    EvidenceBasisDeclaration,
)

from .base import AdapterField, DatasetAdapter

_CANDIDATE_ROOT = Path(__file__).resolve().parents[3] / "datasets" / "candidates" / "memoryarena"
_TASK_CHAINS_PATH = _CANDIDATE_ROOT / "normalized" / "task_chains.jsonl"
_SUBTASKS_PATH = _CANDIDATE_ROOT / "normalized" / "subtasks.jsonl"
_PROFILE_PATH = _CANDIDATE_ROOT / "profile" / "memoryarena_profile.json"

_NOT_PROVIDED_SENTINEL = "NOT_PROVIDED_BY_SOURCE"


def load_task_chains(limit: int = None) -> List[dict]:
    """Read-only load of `normalized/task_chains.jsonl`. Never touches `raw/`."""
    records = []
    with open(_TASK_CHAINS_PATH, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if limit is not None and i >= limit:
                break
            records.append(json.loads(line))
    return records


def load_subtasks(limit: int = None) -> List[dict]:
    """Read-only load of `normalized/subtasks.jsonl`. Never touches `raw/`."""
    records = []
    with open(_SUBTASKS_PATH, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if limit is not None and i >= limit:
                break
            records.append(json.loads(line))
    return records


def subtask_record_to_chain_subtask(record: Mapping[str, Any]) -> ChainSubtask:
    """Deterministic, lossless conversion of one `subtasks.jsonl` record into the
    `agentic_memory.ChainSubtask` shape the paired memory-availability/usage/contribution
    diagnostics operate on. Raises `ValueError` (propagated from
    `subtask_index_from_derived_key`) if `derived_subtask_key` is malformed -- never
    silently defaults a subtask index.
    """
    derived_key = record["derived_subtask_key"]
    chain_id = ":".join(derived_key.split(":")[:-1])
    return ChainSubtask(
        chain_id=chain_id,
        subtask_index=subtask_index_from_derived_key(derived_key),
        chain_length=record["chain_length"],
        question=record["question"],
        answer=record["answer"],
    )


class MemoryArenaAdapter(DatasetAdapter):
    """Read-only adapter over MemoryArena's H.1-normalized record shape.

    Unlike the MemoryAgentBench/MemBench adapters, `record` here is always a SUBTASK record
    (from `load_subtasks`) -- MemoryArena has no separate memory-record layer at all (per
    `mambench_compatibility.json`: "no memory-unit layer exists at all"), so there is no
    analogous `native_memory`-from-a-different-record-type split to make.
    """

    def native_task(self, record: Mapping[str, Any]) -> AdapterField:
        question = record.get("question")
        if not question:
            return AdapterField(
                value=None,
                availability=CAPABILITY_NOT_PROVIDED_BY_SOURCE,
                source_field="question",
                note="No question text present on this subtask record.",
            )
        return AdapterField(value=question, availability=CAPABILITY_AVAILABLE, source_field="question")

    def native_memory(self, record: Mapping[str, Any]) -> AdapterField:
        """MemoryArena has NO native memory-unit layer at all (confirmed by full scan, 701
        records) -- this always returns NOT_PROVIDED_BY_SOURCE. A chain's PRIOR subtasks can
        be treated as an adapter-DEFINED memory item (see
        `agentic_memory.build_prior_subtask_memory_items`), but that is an explicit,
        documented convention this method does not silently claim is a native memory field.
        """
        return AdapterField(
            value=None,
            availability=CAPABILITY_NOT_PROVIDED_BY_SOURCE,
            source_field="NONE",
            note=(
                "MemoryArena has no memory-unit layer in the source at all. "
                "See phase3.evaluation.extensions.agentic_memory for the adapter-defined "
                "prior-subtask-as-memory convention, which is NOT a source-native field."
            ),
        )

    def evidence_basis(self, record: Mapping[str, Any]) -> AdapterField:
        evidence = record.get("evidence_memory_ids")
        declaration = EvidenceBasisDeclaration(
            kind=EVIDENCE_BASIS_NONE_AVAILABLE,
            source_field="evidence_memory_ids",
            reason=(
                "MemoryArena has no gold_evidence_ids-equivalent field anywhere (confirmed "
                "by full scan of all 701 records / 4850 subtasks). backgrounds/base_person "
                "content is agent-visible context, not an evidence pointer to a separately "
                "identified memory unit -- see registry_entry.json known_limitations."
            ),
        )
        return AdapterField(
            value=declaration,
            availability=CAPABILITY_NOT_PROVIDED_BY_SOURCE,
            source_field="evidence_memory_ids",
            note=declaration.reason,
        )

    def answer(self, record: Mapping[str, Any]) -> AdapterField:
        """Answer element TYPE varies by config (dict/list/str) -- this adapter carries the
        value through FAITHFULLY, never coercing to string, per the mission's absolute rule
        against fabricating a value where the source means something structurally richer.
        Use `extensions.answer_matching.evaluate_structural_answer_correctness` (not the
        canonical str-only function) to score non-str answers.
        """
        answer = record.get("answer")
        if answer is None:
            return AdapterField(
                value=None,
                availability=CAPABILITY_NOT_PROVIDED_BY_SOURCE,
                source_field="answer",
                note="No answer present on this subtask record.",
            )
        return AdapterField(
            value=answer,
            availability=CAPABILITY_AVAILABLE,
            source_field="answer",
            note=f"answer type is {type(answer).__name__}; carried through verbatim, never coerced.",
        )

    def relationships(self, record: Mapping[str, Any]) -> AdapterField:
        parent_ids = record.get("parent_ids")
        equivalent_to = record.get("equivalent_to")
        if parent_ids == _NOT_PROVIDED_SENTINEL and equivalent_to == _NOT_PROVIDED_SENTINEL:
            return AdapterField(
                value=None,
                availability=CAPABILITY_NOT_PROVIDED_BY_SOURCE,
                source_field="parent_ids, equivalent_to",
                note="No lineage or equivalence relationship exists anywhere in MemoryArena's schema.",
            )
        return AdapterField(
            value={"parent_ids": parent_ids, "equivalent_to": equivalent_to},
            availability=CAPABILITY_PARTIAL,
            source_field="parent_ids, equivalent_to",
        )

    def session_structure(self, record: Mapping[str, Any]) -> AdapterField:
        """MemoryArena's genuinely-new structure: chain/subtask dependency, positional-only
        (no explicit session_id/timestamp field, per `memoryarena_profile.json`'s
        `multi_session_memory` dimension, PARTIAL)."""
        derived_key = record.get("derived_subtask_key")
        chain_length = record.get("chain_length")
        if not derived_key or chain_length is None:
            return AdapterField(
                value=None,
                availability=CAPABILITY_NOT_PROVIDED_BY_SOURCE,
                source_field="derived_subtask_key, chain_length",
                note="No chain/subtask structural fields present on this record.",
            )
        chain_subtask = subtask_record_to_chain_subtask(record)
        return AdapterField(
            value={
                "chain_id": chain_subtask.chain_id,
                "subtask_index": chain_subtask.subtask_index,
                "chain_length": chain_subtask.chain_length,
            },
            availability=CAPABILITY_PARTIAL,
            source_field="derived_subtask_key, chain_length",
            note=(
                "Subtask ordering is positional (list index / trailing key integer) only, "
                "not an explicit timestamp or session_index field -- PARTIAL, not AVAILABLE, "
                "per memoryarena_profile.json's multi_session_memory dimension."
            ),
        )

    def capability_profile(self) -> Mapping[str, Any]:
        with open(_PROFILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
