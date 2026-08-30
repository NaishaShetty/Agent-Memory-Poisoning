"""Phase 3.2-H.3 -- `DatasetAdapter` for the MemBench candidate (read-only).

Operates on the exact record shape already produced by
`phase3/datasets/candidates/membench/` H.1 normalization:
`normalized/membench_normalized.jsonl`, one record per QA-annotated conversation sample,
`{"agent_visible_context": {"sessions": [...], "question": ..., "choices": ...},
"evaluator_reference": {"answer": [...], "ground_truth_choice": ..., "gold_evidence_step_ids":
[[session_index, turn_index], ...]}, ...}`.

This is the adapter that exercises Extension 1 (`evidence_basis.py`): MemBench's
`gold_evidence_step_ids` is a `[session_index, turn_index]` STRUCTURAL POSITIONAL pointer
(confirmed by direct inspection of the normalized JSONL, and independently corroborated by
`phase3/datasets/candidates/membench/profile/mambench_compatibility.json`'s
`phase_3_2_D_evidence_equivalence_provenance_lineage.evidence` entry, which flags the exact
same `[session_index, turn_index]` -> string-id encoding need). `evidence_basis()` below
classifies this correctly as `EVIDENCE_BASIS_STRUCTURAL_POSITIONAL`, not
`EVIDENCE_BASIS_EXPLICIT_ID` -- and provides the encoded ids via
`evidence_basis.encode_positional_evidence_ids`, ready to feed unmodified to
`phase3/evaluation/metrics/evidence.py`/`retrieval.py`/`selection.py`.
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
    encode_positional_evidence_ids,
    normalize_membench_evidence_positions,
)

from .base import AdapterField, DatasetAdapter

_CANDIDATE_ROOT = Path(__file__).resolve().parents[3] / "datasets" / "candidates" / "membench"
_NORMALIZED_PATH = _CANDIDATE_ROOT / "normalized" / "membench_normalized.jsonl"
_PROFILE_PATH = _CANDIDATE_ROOT / "profile" / "membench_profile.json"

_NOT_PROVIDED_SENTINEL = "NOT_PROVIDED_BY_SOURCE"


def load_normalized_records(limit: int = None) -> List[dict]:
    """Read-only load of `normalized/membench_normalized.jsonl`. Never touches `raw/`."""
    records = []
    with open(_NORMALIZED_PATH, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if limit is not None and i >= limit:
                break
            records.append(json.loads(line))
    return records


class MemBenchAdapter(DatasetAdapter):
    """Read-only adapter over MemBench's H.1-normalized record shape."""

    def native_task(self, record: Mapping[str, Any]) -> AdapterField:
        avc = record.get("agent_visible_context", {})
        question = avc.get("question")
        if not question:
            return AdapterField(
                value=None,
                availability=CAPABILITY_NOT_PROVIDED_BY_SOURCE,
                source_field="agent_visible_context.question",
                note="No question present on this record.",
            )
        return AdapterField(
            value=question, availability=CAPABILITY_AVAILABLE, source_field="agent_visible_context.question"
        )

    def native_memory(self, record: Mapping[str, Any]) -> AdapterField:
        sessions = record.get("agent_visible_context", {}).get("sessions")
        if not sessions:
            return AdapterField(
                value=None,
                availability=CAPABILITY_NOT_PROVIDED_BY_SOURCE,
                source_field="agent_visible_context.sessions",
                note="No session/turn transcript present on this record.",
            )
        return AdapterField(
            value=sessions, availability=CAPABILITY_AVAILABLE, source_field="agent_visible_context.sessions"
        )

    def evidence_basis(self, record: Mapping[str, Any]) -> AdapterField:
        step_ids = record.get("evaluator_reference", {}).get("gold_evidence_step_ids")
        if not step_ids or step_ids == _NOT_PROVIDED_SENTINEL:
            declaration = EvidenceBasisDeclaration(
                kind=EVIDENCE_BASIS_NONE_AVAILABLE,
                source_field="evaluator_reference.gold_evidence_step_ids",
                reason=(
                    "This is one of the 4 (of 26,637) MemBench records missing "
                    "gold_evidence_step_ids (all in FirstAgent/highlevel_rec/movie, per "
                    "the H.1 profile's evidence_availability note); not malformed, "
                    "genuinely absent for this record."
                ),
            )
            return AdapterField(
                value=declaration,
                availability=CAPABILITY_NOT_PROVIDED_BY_SOURCE,
                source_field="evaluator_reference.gold_evidence_step_ids",
                note=declaration.reason,
            )
        declaration = EvidenceBasisDeclaration(
            kind=EVIDENCE_BASIS_STRUCTURAL_POSITIONAL,
            source_field="evaluator_reference.gold_evidence_step_ids",
            reason=(
                "MemBench's gold_evidence_step_ids is a structural pointer into the "
                "record's own transcript -- a deterministic, source-derived position, not "
                "a standalone source-native memory-id string. Phase 3.2-H.5 finding: this "
                "field occurs in the source in TWO shapes -- explicit [session_index, "
                "turn_index] pairs, and (for every single-session record, confirmed by "
                "full scan of the 275-record sample) a flat list of bare turn-index "
                "integers with the session index (always 0, the record's only session) "
                "implicit. See normalize_membench_evidence_positions() in "
                "phase3/evaluation/extensions/evidence_basis.py, which normalizes both "
                "shapes losslessly and without fabrication before encoding."
            ),
        )
        return AdapterField(
            value=declaration,
            availability=CAPABILITY_AVAILABLE,
            source_field="evaluator_reference.gold_evidence_step_ids",
            note=(
                "Encode via this adapter's encoded_gold_evidence_ids(record) (which calls "
                "normalize_membench_evidence_positions then encode_positional_evidence_ids) "
                "to feed the existing Sequence[str]-based metrics unmodified."
            ),
        )

    def encoded_gold_evidence_ids(self, record: Mapping[str, Any]) -> List[str]:
        """Convenience: the record's `gold_evidence_step_ids`, deterministically encoded as
        plain strings, ready to pass to
        `phase3/evaluation/metrics/{retrieval,selection,evidence}.py` UNCHANGED. Returns an
        empty list if this record has no evidence basis at all (never fabricates ids).

        Phase 3.2-H.5 fix: `gold_evidence_step_ids` occurs in the source in two shapes (see
        `evidence_basis()`'s docstring above) -- this method now normalizes BOTH shapes via
        `evidence_basis.normalize_membench_evidence_positions` before encoding. Previously
        (H.3), this method called `encode_positional_evidence_ids` directly on the raw
        field, which raised `TypeError` for every record using the flat-int-list shape
        (140/275 in the sample, confirmed by direct execution before this fix) -- a genuine,
        previously-undiscovered adapter bug, not a dataset limitation.
        """
        step_ids = record.get("evaluator_reference", {}).get("gold_evidence_step_ids")
        if not step_ids or step_ids == _NOT_PROVIDED_SENTINEL:
            return []
        sessions = record.get("agent_visible_context", {}).get("sessions") or []
        normalized_pairs = normalize_membench_evidence_positions(step_ids, len(sessions))
        return encode_positional_evidence_ids(normalized_pairs)

    def answer(self, record: Mapping[str, Any]) -> AdapterField:
        er = record.get("evaluator_reference", {})
        answer = er.get("answer")
        ground_truth = er.get("ground_truth_choice")
        if not answer and not ground_truth:
            return AdapterField(
                value=None,
                availability=CAPABILITY_NOT_PROVIDED_BY_SOURCE,
                source_field="evaluator_reference.answer, evaluator_reference.ground_truth_choice",
                note="No gold answer/ground truth present on this record.",
            )
        return AdapterField(
            value={"answer": answer, "ground_truth_choice": ground_truth},
            availability=CAPABILITY_AVAILABLE,
            source_field="evaluator_reference.answer, evaluator_reference.ground_truth_choice",
        )

    def relationships(self, record: Mapping[str, Any]) -> AdapterField:
        parent_ids = record.get("parent_ids")
        equivalent_to = record.get("equivalent_to")
        if parent_ids == _NOT_PROVIDED_SENTINEL and equivalent_to == _NOT_PROVIDED_SENTINEL:
            return AdapterField(
                value=None,
                availability=CAPABILITY_NOT_PROVIDED_BY_SOURCE,
                source_field="parent_ids, equivalent_to",
                note="No lineage or equivalence relationship exists anywhere in MemBench's schema.",
            )
        return AdapterField(
            value={"parent_ids": parent_ids, "equivalent_to": equivalent_to},
            availability=CAPABILITY_PARTIAL,
            source_field="parent_ids, equivalent_to",
        )

    def session_structure(self, record: Mapping[str, Any]) -> AdapterField:
        sessions = record.get("agent_visible_context", {}).get("sessions")
        if not sessions:
            return AdapterField(
                value=None,
                availability=CAPABILITY_NOT_PROVIDED_BY_SOURCE,
                source_field="agent_visible_context.sessions",
            )
        multi_session = len(sessions) > 1
        return AdapterField(
            value={"session_count": len(sessions), "multi_session": multi_session},
            availability=CAPABILITY_AVAILABLE,
            source_field="agent_visible_context.sessions",
        )

    def capability_profile(self) -> Mapping[str, Any]:
        with open(_PROFILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
