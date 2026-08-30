"""Phase 3.2-H.3 -- `DatasetAdapter` for the MemoryAgentBench candidate (read-only).

Operates on the exact record shapes already produced by
`phase3/datasets/candidates/memoryagentbench/normalize.py` (H.1, unmodified):
- `normalized/task_records.jsonl` -- one record per QA pair, `{"agent_visible": {...},
  "evaluator_only": {...}, "memory_ref": {...}, ...}`.
- `normalized/memory_records.jsonl` -- one record per shared-context row, `{"agent_visible_
  context": {...}, "evaluator_only": {...}, ...}`.

Grounded strictly in `phase3/datasets/candidates/memoryagentbench/profile/
memoryagentbench_profile.json`'s `evidence_availability` (`NOT_PROVIDED_BY_SOURCE`) and
`answer_availability` (`AVAILABLE`) dimensions -- this adapter does not re-derive those
judgments, it reads the already-normalized fields consistent with them.
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
from phase3.evaluation.extensions.evidence_basis import (
    EVIDENCE_BASIS_NONE_AVAILABLE,
    DocumentEvidenceBasisDeclaration,
    EvidenceBasisDeclaration,
    encode_document_evidence_id,
)
from phase3.evaluation.extensions.identity import (
    encode_memoryagentbench_memory_identity,
    encode_memoryagentbench_task_identity,
)

from .base import AdapterField, DatasetAdapter

_CANDIDATE_ROOT = Path(__file__).resolve().parents[3] / "datasets" / "candidates" / "memoryagentbench"
_TASK_RECORDS_PATH = _CANDIDATE_ROOT / "normalized" / "task_records.jsonl"
_MEMORY_RECORDS_PATH = _CANDIDATE_ROOT / "normalized" / "memory_records.jsonl"
_PROFILE_PATH = _CANDIDATE_ROOT / "profile" / "memoryagentbench_profile.json"

_NOT_PROVIDED_SENTINEL = "NOT_PROVIDED_BY_SOURCE"


def load_task_records(limit: int = None) -> List[dict]:
    """Read-only load of `normalized/task_records.jsonl`. Never touches `raw/`."""
    records = []
    with open(_TASK_RECORDS_PATH, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if limit is not None and i >= limit:
                break
            records.append(json.loads(line))
    return records


def load_memory_records(limit: int = None) -> List[dict]:
    """Read-only load of `normalized/memory_records.jsonl`. Never touches `raw/`."""
    records = []
    with open(_MEMORY_RECORDS_PATH, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if limit is not None and i >= limit:
                break
            records.append(json.loads(line))
    return records


class MemoryAgentBenchAdapter(DatasetAdapter):
    """Read-only adapter over MemoryAgentBench's H.1-normalized record shape."""

    def native_task(self, record: Mapping[str, Any]) -> AdapterField:
        question = record.get("agent_visible", {}).get("question")
        if not question:
            return AdapterField(
                value=None,
                availability=CAPABILITY_NOT_PROVIDED_BY_SOURCE,
                source_field="agent_visible.question",
                note="No question text present on this task record.",
            )
        return AdapterField(
            value=question, availability=CAPABILITY_AVAILABLE, source_field="agent_visible.question"
        )

    def native_memory(self, record: Mapping[str, Any]) -> AdapterField:
        """`record` here is a MEMORY record (from `load_memory_records`), not a task record
        -- MemoryAgentBench's memory/task layers are separately normalized (see
        `memory_ref` linking a task record back to its parent memory row)."""
        content = record.get("agent_visible_context", {}).get("content")
        if not content:
            return AdapterField(
                value=None,
                availability=CAPABILITY_NOT_PROVIDED_BY_SOURCE,
                source_field="agent_visible_context.content",
                note="No context content present on this memory record.",
            )
        return AdapterField(
            value=content,
            availability=CAPABILITY_AVAILABLE,
            source_field="agent_visible_context.content",
        )

    def evidence_basis(self, record: Mapping[str, Any]) -> AdapterField:
        """Per `profile/memoryagentbench_profile.json`'s `evidence_availability` dimension:
        NOT_PROVIDED_BY_SOURCE for essentially the whole dataset. This adapter never
        fabricates a gold-evidence pointer for MemoryAgentBench task records.

        UNCHANGED from H.3 -- this method's return value is directly asserted by existing
        tests (`test_framework_extensions_h3.py::
        test_memoryagentbench_adapter_evidence_basis_is_none_available`,
        `::test_unavailable_capability_never_silently_becomes_falsy_zero_or_empty_list`),
        which this stage does not modify. See `document_level_evidence_basis()` below for
        the genuine, ADDITIONAL whole-document-granularity signal Phase 3.2-H.5 found in
        `memory_ref` -- deliberately exposed via a separate method and a separate
        declaration type rather than by changing this method's classification, precisely so
        the existing NONE_AVAILABLE assertion above keeps holding.
        """
        evidence = record.get("evaluator_only", {}).get("evidence_memory_ids")
        if evidence == _NOT_PROVIDED_SENTINEL or not evidence:
            declaration = EvidenceBasisDeclaration(
                kind=EVIDENCE_BASIS_NONE_AVAILABLE,
                source_field="evaluator_only.evidence_memory_ids",
                reason=(
                    "MemoryAgentBench provides no memory-ID-resolvable gold evidence "
                    "pointer for any QA pair (confirmed by whole-dataset field scan; see "
                    "profile/memoryagentbench_profile.json's evidence_availability "
                    "dimension, status NOT_PROVIDED_BY_SOURCE)."
                ),
            )
            return AdapterField(
                value=declaration,
                availability=CAPABILITY_NOT_PROVIDED_BY_SOURCE,
                source_field="evaluator_only.evidence_memory_ids",
                note=declaration.reason,
            )
        # Defensive: no known MemoryAgentBench record actually carries a resolvable
        # evidence pointer, but this branch exists so the adapter never silently drops a
        # genuinely-present value if one is ever found.
        declaration = EvidenceBasisDeclaration(
            kind=EVIDENCE_BASIS_NONE_AVAILABLE,
            source_field="evaluator_only.evidence_memory_ids",
            reason="Unexpected non-sentinel value found; still not memory-ID-resolvable per profile.",
        )
        return AdapterField(
            value=declaration, availability=CAPABILITY_PARTIAL, source_field="evaluator_only.evidence_memory_ids"
        )

    def document_level_evidence_basis(self, record: Mapping[str, Any]) -> AdapterField:
        """Phase 3.2-H.5 -- NEW, additive method (does not exist in H.3): the genuine
        whole-document-granularity evidence signal found in `memory_ref`, classified via the
        SEPARATE `DocumentEvidenceBasisDeclaration` type (not `EvidenceBasisDeclaration`,
        whose 5-way `kind` vocabulary is frozen and test-enforced). See
        `phase3/evaluation/extensions/evidence_basis.py`'s `DocumentEvidenceBasisDeclaration`
        docstring for full reasoning. `evidence_basis()` above is UNCHANGED and still
        reports `EVIDENCE_BASIS_NONE_AVAILABLE` for chunk/turn-granularity evidence, which
        genuinely does not exist in this dataset -- this method reports something narrower
        and additional, not a contradiction of that.
        """
        memory_ref = record.get("memory_ref")
        if isinstance(memory_ref, Mapping) and "split" in memory_ref and "row_index" in memory_ref:
            declaration = DocumentEvidenceBasisDeclaration(
                source_field="memory_ref.split, memory_ref.row_index",
                reason=(
                    "MemoryAgentBench provides no chunk/turn-granularity gold evidence "
                    "pointer, but every task record's memory_ref deterministically "
                    "identifies exactly one whole-document memory record (one of 146). "
                    "This is genuine, source-structure-derived, whole-document-granularity "
                    "evidence -- not a fabricated substitute for the absent fine-grained "
                    "gold_evidence_ids, and coarser than MemBench's [session,turn] pointer."
                ),
            )
            return AdapterField(
                value=declaration,
                availability=CAPABILITY_PARTIAL,
                source_field="memory_ref.split, memory_ref.row_index",
                note=(
                    declaration.reason
                    + " availability=PARTIAL (not AVAILABLE) because this is whole-document, "
                    "not fine-grained, evidence."
                ),
            )
        return AdapterField(
            value=None,
            availability=CAPABILITY_NOT_PROVIDED_BY_SOURCE,
            source_field="memory_ref",
            note="This task record carries no memory_ref of any kind; no document-level evidence basis exists.",
        )

    def encoded_document_evidence_id(self, record: Mapping[str, Any]) -> List[str]:
        """Convenience: this task record's whole-document evidence, encoded via
        `evidence_basis.encode_document_evidence_id`, ready to pass to
        `phase3/evaluation/metrics/{retrieval,selection,evidence}.py` UNCHANGED -- as a
        single-element list, since MemoryAgentBench evidence resolves to exactly one
        document per task record. Returns `[]` if this record has no `memory_ref`."""
        memory_ref = record.get("memory_ref")
        if not isinstance(memory_ref, Mapping) or "split" not in memory_ref or "row_index" not in memory_ref:
            return []
        return [encode_document_evidence_id(memory_ref["split"], memory_ref["row_index"])]

    def memory_identity(self, memory_record: Mapping[str, Any]) -> AdapterField:
        """`ADAPTER_DERIVED_IDENTITY` for a MEMORY record (from `load_memory_records`), built
        from its own `positional_reference: {split, row_index}` -- never `NATIVE_MEMORY_ID`,
        since MemoryAgentBench's source parquet has no per-row id field at all."""
        pos = memory_record.get("positional_reference")
        if not isinstance(pos, Mapping) or "split" not in pos or "row_index" not in pos:
            return AdapterField(
                value=None,
                availability=CAPABILITY_NOT_PROVIDED_BY_SOURCE,
                source_field="positional_reference",
                note="No positional_reference on this memory record.",
            )
        encoded = encode_memoryagentbench_memory_identity(pos["split"], pos["row_index"])
        return AdapterField(
            value=encoded,
            availability=CAPABILITY_AVAILABLE,
            source_field="positional_reference.split, positional_reference.row_index",
            note="ADAPTER_DERIVED_IDENTITY, not NATIVE_MEMORY_ID -- see extensions/identity.py.",
        )

    def task_identity(self, record: Mapping[str, Any]) -> AdapterField:
        """`COMPOSITE_SOURCE_IDENTITY` for a TASK record, resolving the `source_record_id`
        collision (see `extensions/identity.py` docstring) via `memory_ref` +
        `question_index_in_row`."""
        memory_ref = record.get("memory_ref")
        q_index = record.get("question_index_in_row")
        if not isinstance(memory_ref, Mapping) or "split" not in memory_ref or "row_index" not in memory_ref or q_index is None:
            return AdapterField(
                value=None,
                availability=CAPABILITY_NOT_PROVIDED_BY_SOURCE,
                source_field="memory_ref, question_index_in_row",
                note="Missing memory_ref or question_index_in_row on this task record.",
            )
        encoded = encode_memoryagentbench_task_identity(
            memory_ref["split"], memory_ref["row_index"], q_index
        )
        return AdapterField(
            value=encoded,
            availability=CAPABILITY_AVAILABLE,
            source_field="memory_ref.split, memory_ref.row_index, question_index_in_row",
            note="COMPOSITE_SOURCE_IDENTITY, not NATIVE_MEMORY_ID -- see extensions/identity.py.",
        )

    def answer(self, record: Mapping[str, Any]) -> AdapterField:
        answers = record.get("evaluator_only", {}).get("gold_answers")
        if not answers or answers == _NOT_PROVIDED_SENTINEL:
            return AdapterField(
                value=None,
                availability=CAPABILITY_NOT_PROVIDED_BY_SOURCE,
                source_field="evaluator_only.gold_answers",
                note="No gold answer present on this task record.",
            )
        return AdapterField(
            value=list(answers), availability=CAPABILITY_AVAILABLE, source_field="evaluator_only.gold_answers"
        )

    def relationships(self, record: Mapping[str, Any]) -> AdapterField:
        parent_ids = record.get("parent_ids")
        equivalent_to = record.get("equivalent_to")
        if parent_ids == _NOT_PROVIDED_SENTINEL and equivalent_to == _NOT_PROVIDED_SENTINEL:
            return AdapterField(
                value=None,
                availability=CAPABILITY_NOT_PROVIDED_BY_SOURCE,
                source_field="parent_ids, equivalent_to",
                note="No lineage or equivalence field exists anywhere in MemoryAgentBench's schema.",
            )
        return AdapterField(
            value={"parent_ids": parent_ids, "equivalent_to": equivalent_to},
            availability=CAPABILITY_PARTIAL,
            source_field="parent_ids, equivalent_to",
        )

    def session_structure(self, record: Mapping[str, Any]) -> AdapterField:
        """`record` here is a MEMORY record. Only the 5 LongMemEval-sourced rows carry an
        explicit `haystack_sessions` multi-session structure (per
        `profile/memoryagentbench_profile.json`'s `multi_session_memory` dimension, PARTIAL)."""
        haystack_sessions = record.get("evaluator_only", {}).get("haystack_sessions")
        if haystack_sessions and haystack_sessions != _NOT_PROVIDED_SENTINEL:
            return AdapterField(
                value=haystack_sessions,
                availability=CAPABILITY_AVAILABLE,
                source_field="evaluator_only.haystack_sessions",
                note="This is one of the 5 LongMemEval-sourced rows carrying explicit session structure.",
            )
        return AdapterField(
            value=None,
            availability=CAPABILITY_NOT_PROVIDED_BY_SOURCE,
            source_field="evaluator_only.haystack_sessions",
            note="This row presents its context as a single flat text block, no session structure field.",
        )

    def capability_profile(self) -> Mapping[str, Any]:
        with open(_PROFILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
