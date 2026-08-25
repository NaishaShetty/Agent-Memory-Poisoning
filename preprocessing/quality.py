"""Record-level data-quality classification and quarantine (Phase 1
extension, Section 4-6 of the research plan).

Four possible states for any raw record considered for inclusion in the
canonical processed dataset:

    VALID                 -- normal, usable, no issue found
    REPAIRED              -- a deterministic, justifiable repair was applied
                             (e.g. whitespace normalization); original raw
                             text is still recoverable from data/raw, and the
                             exact change is recorded in data_quality flags
    VALID_FLAGGED         -- usable as-is, but carries a known quality
                             concern (e.g. a source-inherited encoding
                             defect) that could not be repaired without
                             guessing -- kept in the canonical dataset,
                             flagged for later robustness analysis
    IRRECOVERABLY_INVALID -- cannot be reliably reconstructed (e.g. no text
                             at all, or no usable conversation identifier);
                             excluded from the canonical dataset and
                             preserved in quarantine instead of deleted

IMPORTANT: this classifies *natural data quality*, never *maliciousness*.
Nothing here labels a record as poisoned -- that determination belongs to
a later phase's attack-injection ground truth, which does not exist yet.
See docstring in each dataset module's `known_limitations` for the
NATURAL-NOISE vs POISONED distinction this file exists to support.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, Optional

from preprocessing import PIPELINE_VERSION
from preprocessing.io_utils import append_jsonl

QUALITY_VALID = "valid"
QUALITY_REPAIRED = "repaired"
QUALITY_VALID_FLAGGED = "valid_flagged"
QUALITY_IRRECOVERABLY_INVALID = "irrecoverably_invalid"

_ALL_STATUSES = {QUALITY_VALID, QUALITY_REPAIRED, QUALITY_VALID_FLAGGED, QUALITY_IRRECOVERABLY_INVALID}


def resolve_quality_status(whitespace_normalized: bool, has_encoding_issue: bool) -> str:
    """Single source of truth for turn-level quality status, shared by all
    dataset adapters so the classification logic is not duplicated four
    times. Priority: an unresolved defect (encoding) outranks a fully
    resolved one (whitespace), which outranks "nothing found"."""
    if has_encoding_issue:
        return QUALITY_VALID_FLAGGED
    if whitespace_normalized:
        return QUALITY_REPAIRED
    return QUALITY_VALID


@dataclasses.dataclass
class QuarantineRecord:
    """A record excluded from the canonical processed dataset, preserved
    with enough context to audit the exclusion decision later. `raw_content`
    holds the original, untouched source record/turn (or the smallest
    self-contained fragment of it) -- nothing is summarized away."""

    dataset: str
    source_file: str
    source_record_id: str
    conversation_id: Optional[str]
    session_id: Optional[str]
    turn_id: Optional[str]
    quality_status: str          # normally IRRECOVERABLY_INVALID, but see `exclusion_reason`
    exclusion_reason: str        # e.g. "empty_content", "missing_conversation_id", "duplicate_session_across_files"
    raw_content: Any             # the original record/turn, verbatim
    run_timestamp: str
    pipeline_version: str = PIPELINE_VERSION

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


class QuarantineLog:
    """Buffers quarantined records and flushes them to two places: the
    dataset's own interim/quarantine.jsonl (the "AUDITED/QUARANTINED" layer
    the research plan asks for, sitting between RAW and CANONICAL PROCESSED)
    and the shared logs/quarantine_log.jsonl (a single cross-dataset index)."""

    def __init__(self, dataset: str, run_timestamp: str):
        self.dataset = dataset
        self.run_timestamp = run_timestamp
        self._records: list[QuarantineRecord] = []

    def add(
        self,
        source_file: str,
        source_record_id: str,
        exclusion_reason: str,
        raw_content: Any,
        conversation_id: Optional[str] = None,
        session_id: Optional[str] = None,
        turn_id: Optional[str] = None,
        quality_status: str = QUALITY_IRRECOVERABLY_INVALID,
    ) -> None:
        assert quality_status in _ALL_STATUSES, f"unknown quality_status {quality_status!r}"
        self._records.append(
            QuarantineRecord(
                dataset=self.dataset,
                source_file=source_file,
                source_record_id=source_record_id,
                conversation_id=conversation_id,
                session_id=session_id,
                turn_id=turn_id,
                quality_status=quality_status,
                exclusion_reason=exclusion_reason,
                raw_content=raw_content,
                run_timestamp=self.run_timestamp,
            )
        )

    def __len__(self) -> int:
        return len(self._records)

    def count_by_reason(self, reason: str) -> int:
        return sum(1 for r in self._records if r.exclusion_reason == reason)

    def flush(self, interim_dataset_dir: Path, logs_dir: Path) -> int:
        n1 = append_jsonl(interim_dataset_dir / "quarantine.jsonl", (r.to_dict() for r in self._records))
        append_jsonl(logs_dir / "quarantine_log.jsonl", (r.to_dict() for r in self._records))
        return n1
