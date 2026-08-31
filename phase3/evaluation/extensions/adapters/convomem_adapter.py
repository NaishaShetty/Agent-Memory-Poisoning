"""Phase 3.2-J.3 -- `DatasetAdapter` for ConvoMem, read-only.

Operates on the exact record shapes produced by
`phase3/datasets/candidates/convomem/normalize.py` (J.2, unmodified):
- `normalized/task_records.jsonl` -- one record per evidence_item (QA pair), with
  `evaluator_only.evidence_resolution` carrying the J.2 waterfall's per-span status
  (EXACT_RAW/EXACT_NORMALIZED/TRUNCATED_UNIQUE/MULTIMESSAGE_UNIQUE/*_AMBIGUOUS/
  UNRESOLVED/TOO_SHORT) and `locations`.
- `normalized/memory_records.jsonl` -- one record per evidence_item's bundled
  `conversations` list (verbatim).

Grounded in `phase3/datasets/candidates/convomem/profile/convomem_profile.json`'s
`evidence_availability_memory_id_resolvable` (PARTIALLY_SUPPORTED, 97.0%, J.2 full scan)
finding. This adapter never converts an UNRESOLVED/AMBIGUOUS/TOO_SHORT span into a
fabricated evidence id or a `0`/empty-as-failure outcome -- it reports
`EVIDENCE_BASIS_NONE_AVAILABLE` for those, exactly mirroring J.2's own discipline.
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
    EVIDENCE_BASIS_STRUCTURAL_POSITIONAL,
    EvidenceBasisDeclaration,
)
from phase3.evaluation.extensions.identity import (
    encode_convomem_memory_identity,
    encode_convomem_multimessage_identity,
)

from .base import AdapterField, DatasetAdapter

_CANDIDATE_ROOT = Path(__file__).resolve().parents[3] / "datasets" / "candidates" / "convomem"
_TASK_RECORDS_PATH = _CANDIDATE_ROOT / "normalized" / "task_records.jsonl"
_MEMORY_RECORDS_PATH = _CANDIDATE_ROOT / "normalized" / "memory_records.jsonl"
_PROFILE_PATH = _CANDIDATE_ROOT / "profile" / "convomem_profile.json"

_RESOLVABLE_STATUSES = frozenset({"EXACT_RAW", "EXACT_NORMALIZED", "TRUNCATED_UNIQUE", "MULTIMESSAGE_UNIQUE"})
_AMBIGUOUS_STATUSES = frozenset({"TRUNCATED_AMBIGUOUS", "MULTIMESSAGE_AMBIGUOUS"})
_NOT_RESOLVABLE = "NOT_RESOLVABLE_FROM_SOURCE"


def load_task_records(limit: int = None) -> List[dict]:
    """Read-only load of `normalized/task_records.jsonl` (the committed 18-file sample's
    output). Never touches `raw/`."""
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


class ConvoMemAdapter(DatasetAdapter):
    """Read-only adapter over ConvoMem's J.2-normalized record shape."""

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
        """`record` here is a MEMORY record (from `load_memory_records`) -- the bundled
        `conversations` list, preserved verbatim, never flattened."""
        content = record.get("agent_visible_context", {}).get("conversations")
        if not content:
            return AdapterField(
                value=None,
                availability=CAPABILITY_NOT_PROVIDED_BY_SOURCE,
                source_field="agent_visible_context.conversations",
                note="No conversations present on this memory record.",
            )
        return AdapterField(
            value=content, availability=CAPABILITY_AVAILABLE, source_field="agent_visible_context.conversations"
        )

    def evidence_basis(self, record: Mapping[str, Any]) -> AdapterField:
        """STRUCTURAL_POSITIONAL for any resolvable span (EXACT_* or *_UNIQUE); NONE_
        AVAILABLE if every span is UNRESOLVED/TOO_SHORT/*_AMBIGUOUS. This is a per-TASK
        classification (a record may have some resolved and some unresolved spans --
        see `encoded_evidence_ids()` below for the exact per-span breakdown)."""
        resolution = record.get("evaluator_only", {}).get("evidence_resolution")
        if resolution == _NOT_RESOLVABLE or not resolution:
            declaration = EvidenceBasisDeclaration(
                kind=EVIDENCE_BASIS_NONE_AVAILABLE,
                source_field="evaluator_only.evidence_resolution",
                reason="No message_evidences on this record, or none resolvable.",
            )
            return AdapterField(
                value=declaration,
                availability=CAPABILITY_NOT_PROVIDED_BY_SOURCE,
                source_field="evaluator_only.evidence_resolution",
                note=declaration.reason,
            )
        statuses = {r.get("status") for r in resolution}
        if statuses & _RESOLVABLE_STATUSES:
            declaration = EvidenceBasisDeclaration(
                kind=EVIDENCE_BASIS_STRUCTURAL_POSITIONAL,
                source_field="evaluator_only.evidence_resolution",
                reason=(
                    "At least one message_evidences span resolved via J.2's deterministic "
                    "exact/structural-substring waterfall, anchored to the source's native "
                    "conversation `id` field plus a resolved message position."
                ),
            )
            avail = CAPABILITY_AVAILABLE if statuses <= _RESOLVABLE_STATUSES else CAPABILITY_PARTIAL
            return AdapterField(value=declaration, availability=avail, source_field="evaluator_only.evidence_resolution")
        declaration = EvidenceBasisDeclaration(
            kind=EVIDENCE_BASIS_NONE_AVAILABLE,
            source_field="evaluator_only.evidence_resolution",
            reason="All spans on this record are UNRESOLVED/TOO_SHORT/AMBIGUOUS (J.2 waterfall).",
        )
        return AdapterField(
            value=declaration,
            availability=CAPABILITY_NOT_PROVIDED_BY_SOURCE,
            source_field="evaluator_only.evidence_resolution",
            note=declaration.reason,
        )

    def encoded_evidence_ids(self, record: Mapping[str, Any]) -> List[str]:
        """This task record's resolvable evidence spans, `ADAPTER_DERIVED_IDENTITY`-
        encoded via `identity.encode_convomem_memory_identity`/
        `encode_convomem_multimessage_identity`. Spans classified UNRESOLVED/TOO_SHORT/
        *_AMBIGUOUS contribute NOTHING to this list -- never a guessed id, never a
        fabricated 'nearest' location for an ambiguous match (multiple distinct
        candidate locations are reported by `ambiguous_locations()` below, not
        collapsed into one here)."""
        resolution = record.get("evaluator_only", {}).get("evidence_resolution")
        if resolution == _NOT_RESOLVABLE or not resolution:
            return []
        ids = []
        for r in resolution:
            if r.get("status") not in _RESOLVABLE_STATUSES:
                continue
            locs = r.get("locations") or []
            if len(locs) != 1:
                continue  # resolvable statuses always carry exactly one location; defensive
            loc = locs[0]
            if "message_index" in loc:
                ids.append(encode_convomem_memory_identity(loc["conversation_id"], loc["message_index"]))
            elif "message_index_start" in loc:
                ids.append(encode_convomem_multimessage_identity(
                    loc["conversation_id"], loc["message_index_start"], loc["message_index_end"]
                ))
        return ids

    def ambiguous_locations(self, record: Mapping[str, Any]) -> List[Mapping[str, Any]]:
        """Additive, ConvoMem-specific: every span this record has that is genuinely
        AMBIGUOUS_SOURCE_MAPPING, with ALL of its candidate locations preserved (never
        collapsed to one) -- lets a caller see exactly why a span was not resolved,
        per Part 7/Part 20's explicit requirement."""
        resolution = record.get("evaluator_only", {}).get("evidence_resolution")
        if resolution == _NOT_RESOLVABLE or not resolution:
            return []
        return [r for r in resolution if r.get("status") in _AMBIGUOUS_STATUSES]

    def memory_identity(self, memory_record: Mapping[str, Any]) -> AdapterField:
        """A ConvoMem MEMORY record (from `load_memory_records`) bundles a whole
        `conversations` list per evidence_item -- there is no single per-record identity
        finer than `source_record_id` (already assigned by normalize.py); per-message
        identity is only meaningful in the context of a specific resolved evidence span
        (see `encoded_evidence_ids` above), not at the memory-record level."""
        source_record_id = memory_record.get("source_record_id")
        if not source_record_id:
            return AdapterField(
                value=None,
                availability=CAPABILITY_NOT_PROVIDED_BY_SOURCE,
                source_field="source_record_id",
                note="No source_record_id on this memory record.",
            )
        return AdapterField(
            value=source_record_id,
            availability=CAPABILITY_AVAILABLE,
            source_field="source_record_id",
            note="ADAPTER_DERIVED_IDENTITY (evidence_item-scoped) -- see normalize.py.",
        )

    def answer(self, record: Mapping[str, Any]) -> AdapterField:
        answer = record.get("evaluator_only", {}).get("gold_answer")
        if not answer:
            return AdapterField(
                value=None,
                availability=CAPABILITY_NOT_PROVIDED_BY_SOURCE,
                source_field="evaluator_only.gold_answer",
                note="No gold answer present on this task record.",
            )
        return AdapterField(
            value=answer, availability=CAPABILITY_AVAILABLE, source_field="evaluator_only.gold_answer"
        )

    def relationships(self, record: Mapping[str, Any]) -> AdapterField:
        parent_ids = record.get("parent_ids")
        equivalent_to = record.get("equivalent_to")
        if parent_ids == "NOT_PROVIDED_BY_SOURCE" and equivalent_to == "NOT_PROVIDED_BY_SOURCE":
            return AdapterField(
                value=None,
                availability=CAPABILITY_NOT_PROVIDED_BY_SOURCE,
                source_field="parent_ids, equivalent_to",
                note="No lineage or equivalence field exists anywhere in ConvoMem's schema.",
            )
        return AdapterField(
            value={"parent_ids": parent_ids, "equivalent_to": equivalent_to},
            availability=CAPABILITY_PARTIAL,
            source_field="parent_ids, equivalent_to",
        )

    def session_structure(self, record: Mapping[str, Any]) -> AdapterField:
        """`record` here is a MEMORY record. `agent_visible_context.conversations` is
        itself a list of independent transcripts -- a real, if coarse, session-like
        structure (one "conversation" = one session)."""
        conversations = record.get("agent_visible_context", {}).get("conversations")
        if not conversations:
            return AdapterField(
                value=None,
                availability=CAPABILITY_NOT_PROVIDED_BY_SOURCE,
                source_field="agent_visible_context.conversations",
                note="No conversations on this memory record.",
            )
        return AdapterField(
            value={"conversation_count": len(conversations)},
            availability=CAPABILITY_PARTIAL,
            source_field="agent_visible_context.conversations",
            note="Each conversation is a session-like unit; no explicit session_id field beyond conversations[i].id.",
        )

    def capability_profile(self) -> Mapping[str, Any]:
        with open(_PROFILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
