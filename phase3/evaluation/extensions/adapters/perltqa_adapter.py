"""Phase 3.2-J.3 -- `DatasetAdapter` for PerLTQA (zh release only), read-only.

Operates on the exact record shapes produced by
`phase3/datasets/candidates/perltqa/normalize.py` (J.1, unmodified):
- `normalized/task_records.jsonl` -- one record per QA pair (all 4 sections: profile,
  social_relationship, events, dialogues), `{"agent_visible": {...}, "evaluator_only":
  {...}, "character", "section", ...}`.
- `normalized/memory_records.jsonl` -- one record per memory unit, `{"agent_visible_
  context": {...}, "character", "native_memory_unit_id", "memory_kind", ...}`.

Grounded in `phase3/datasets/candidates/perltqa/profile/perltqa_profile.json`'s
`evidence_availability_memory_id_resolvable` (AVAILABLE, 100% for non-profile sections,
full scan) and `language` (MULTILINGUAL, zh fully usable) findings -- this adapter reads
zh records only and does not re-derive those judgments.

Chinese text is never translated, transliterated, or altered anywhere in this module.
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
    EVIDENCE_BASIS_EXPLICIT_ID,
    EVIDENCE_BASIS_NONE_AVAILABLE,
    EvidenceBasisDeclaration,
)
from phase3.evaluation.extensions.identity import encode_perltqa_memory_identity

from .base import AdapterField, DatasetAdapter

_CANDIDATE_ROOT = Path(__file__).resolve().parents[3] / "datasets" / "candidates" / "perltqa"
_TASK_RECORDS_PATH = _CANDIDATE_ROOT / "normalized" / "task_records.jsonl"
_MEMORY_RECORDS_PATH = _CANDIDATE_ROOT / "normalized" / "memory_records.jsonl"
_PROFILE_PATH = _CANDIDATE_ROOT / "profile" / "perltqa_profile.json"

_NOT_RESOLVABLE = "NOT_RESOLVABLE_FROM_SOURCE"
_NOT_PROVIDED = "NOT_PROVIDED_BY_SOURCE"


def load_task_records(limit: int = None) -> List[dict]:
    """Read-only load of the zh `normalized/task_records.jsonl`. Never touches `raw/`."""
    records = []
    with open(_TASK_RECORDS_PATH, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if limit is not None and i >= limit:
                break
            records.append(json.loads(line))
    return records


def load_memory_records(limit: int = None) -> List[dict]:
    """Read-only load of the zh `normalized/memory_records.jsonl`. Never touches `raw/`."""
    records = []
    with open(_MEMORY_RECORDS_PATH, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if limit is not None and i >= limit:
                break
            records.append(json.loads(line))
    return records


class PerLTQAAdapter(DatasetAdapter):
    """Read-only adapter over PerLTQA's (zh) J.1-normalized record shape."""

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
        """`record` here is a MEMORY record (from `load_memory_records`). PerLTQA's memory
        content is a structured dict (profile fields, or a social_relationship/events/
        dialogues unit's own fields), preserved AS-IS -- never flattened to a text blob,
        per this stage's explicit instruction not to collapse source-native structure."""
        content = record.get("agent_visible_context")
        if not content:
            return AdapterField(
                value=None,
                availability=CAPABILITY_NOT_PROVIDED_BY_SOURCE,
                source_field="agent_visible_context",
                note="No context content present on this memory record.",
            )
        return AdapterField(
            value=content, availability=CAPABILITY_AVAILABLE, source_field="agent_visible_context"
        )

    def evidence_basis(self, record: Mapping[str, Any]) -> AdapterField:
        """EXPLICIT_ID for non-profile sections (native `Reference Memory` ID-lists,
        100% internally consistent per J.1's full scan); NONE_AVAILABLE for profile
        sections, whose `Reference Memory` field is a classification label, not an
        evidence pointer (see `classification_label()` below for that separate signal)."""
        eids = record.get("evaluator_only", {}).get("evidence_memory_ids")
        if eids == _NOT_RESOLVABLE or not eids:
            declaration = EvidenceBasisDeclaration(
                kind=EVIDENCE_BASIS_NONE_AVAILABLE,
                source_field="evaluator_only.evidence_memory_ids",
                reason=(
                    "This task record's section carries no memory-unit-ID evidence "
                    "(profile-section question, or a non-profile question whose "
                    "Reference Memory ID did not resolve)."
                ),
            )
            return AdapterField(
                value=declaration,
                availability=CAPABILITY_NOT_PROVIDED_BY_SOURCE,
                source_field="evaluator_only.evidence_memory_ids",
                note=declaration.reason,
            )
        declaration = EvidenceBasisDeclaration(
            kind=EVIDENCE_BASIS_EXPLICIT_ID,
            source_field="evaluator_only.evidence_memory_ids",
            reason=(
                "Native `Reference Memory` ID-list, verified to resolve against the "
                "correct character's social_relationship/events/dialogues dict "
                "(100% valid, full scan, J.1)."
            ),
        )
        return AdapterField(
            value=declaration, availability=CAPABILITY_AVAILABLE, source_field="evaluator_only.evidence_memory_ids"
        )

    def encoded_evidence_ids(self, record: Mapping[str, Any]) -> List[str]:
        """This task record's native evidence IDs, composite-encoded (character-scoped,
        `NATIVE_MEMORY_ID`) via `identity.encode_perltqa_memory_identity`, ready to pass
        to `phase3/evaluation/metrics/*.py` unchanged. `[]` for profile-section records
        or unresolved evidence."""
        eids = record.get("evaluator_only", {}).get("evidence_memory_ids")
        character = record.get("character")
        if eids == _NOT_RESOLVABLE or not eids or not character:
            return []
        return [encode_perltqa_memory_identity(character, uid) for uid in eids]

    def classification_label(self, record: Mapping[str, Any]) -> AdapterField:
        """Additive, PerLTQA-specific signal (not part of the base `DatasetAdapter`
        interface, mirroring `memoryagentbench_adapter.document_level_evidence_basis`'s
        precedent of exposing a genuine dataset-specific capability via an extra method
        rather than overloading `evidence_basis`): the profile-section's native
        classification label (e.g. "Gender", "Occupation") preserved EXACTLY as the
        source wrote it -- never invented, never remapped."""
        label = record.get("evaluator_only", {}).get("reference_memory_classification_label")
        if record.get("section") != "PROFILE" or not label:
            return AdapterField(
                value=None,
                availability=CAPABILITY_NOT_PROVIDED_BY_SOURCE,
                source_field="evaluator_only.reference_memory_classification_label",
                note="Only profile-section records carry a classification label.",
            )
        return AdapterField(
            value=label,
            availability=CAPABILITY_AVAILABLE,
            source_field="evaluator_only.reference_memory_classification_label",
        )

    def memory_identity(self, memory_record: Mapping[str, Any]) -> AdapterField:
        """`NATIVE_MEMORY_ID` (character-scope-resolved) -- see `identity.py`'s module
        docstring for why this is NATIVE, not ADAPTER_DERIVED: the underlying ID string
        is copied verbatim from the source, only namespaced by its owning character."""
        character = memory_record.get("character")
        unit_id = memory_record.get("native_memory_unit_id", "profile")
        if not character:
            return AdapterField(
                value=None,
                availability=CAPABILITY_NOT_PROVIDED_BY_SOURCE,
                source_field="character",
                note="No character field on this memory record.",
            )
        encoded = encode_perltqa_memory_identity(character, unit_id)
        return AdapterField(
            value=encoded,
            availability=CAPABILITY_AVAILABLE,
            source_field="character, native_memory_unit_id",
            note="NATIVE_MEMORY_ID (character-scope-resolved) -- see extensions/identity.py.",
        )

    def answer(self, record: Mapping[str, Any]) -> AdapterField:
        answer = record.get("evaluator_only", {}).get("gold_answer")
        if answer is None:
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
        """PerLTQA's `events[i].Characters` field is a real relational link (event ->
        social_relationship IDs); exposed here as PARTIAL structural relationship data,
        never as a fabricated lineage/equivalence edge -- `parent_ids`/`equivalent_to`
        themselves remain NOT_PROVIDED_BY_SOURCE (J.1, full scan, unchanged)."""
        parent_ids = record.get("parent_ids")
        equivalent_to = record.get("equivalent_to")
        if parent_ids == _NOT_PROVIDED and equivalent_to == _NOT_PROVIDED:
            return AdapterField(
                value=None,
                availability=CAPABILITY_NOT_PROVIDED_BY_SOURCE,
                source_field="parent_ids, equivalent_to",
                note="No lineage or equivalence field exists anywhere in PerLTQA's schema.",
            )
        return AdapterField(
            value={"parent_ids": parent_ids, "equivalent_to": equivalent_to},
            availability=CAPABILITY_PARTIAL,
            source_field="parent_ids, equivalent_to",
        )

    def session_structure(self, record: Mapping[str, Any]) -> AdapterField:
        """`record` here is a MEMORY record. `events`/`dialogues` units carry a
        session/thread-like structure via their id suffix ("4_0_0#0" groups under event
        "4_0_0"); `profile`/`social_relationship` units do not."""
        kind = record.get("memory_kind")
        unit_id = record.get("native_memory_unit_id", "")
        if kind in ("EVENTS", "DIALOGUES"):
            return AdapterField(
                value={"memory_kind": kind, "native_memory_unit_id": unit_id},
                availability=CAPABILITY_AVAILABLE,
                source_field="memory_kind, native_memory_unit_id",
                note="Event/dialogue ID structure implies grouping (dialogues '#N' suffix references its parent event id).",
            )
        return AdapterField(
            value=None,
            availability=CAPABILITY_NOT_PROVIDED_BY_SOURCE,
            source_field="memory_kind",
            note="Profile/social_relationship units carry no session/thread structure.",
        )

    def capability_profile(self) -> Mapping[str, Any]:
        with open(_PROFILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
