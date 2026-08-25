"""Common normalized representation for Phase 1.

Two record types are produced, because the source datasets contain two
genuinely different kinds of information (see research plan Step 11 and the
"IMPORTANT DATASET PRINCIPLE" section): conversational turns that form the
long-term memory substrate (MemoryRecord), and, where a dataset provides
them, question-answering evaluation instances that reference that substrate
(TaskRecord). Forcing QA instances into MemoryRecord rows (or dropping them)
would destroy information LoCoMo and LongMemEval both provide natively.

Every field is explicitly one of:
  - SOURCE-PROVIDED   : copied verbatim from the raw dataset
  - DERIVED           : deterministically computed from source data
  - RESERVED          : always null in Phase 1; populated by later phases

Fields never fabricated: source_timestamp, provenance identifiers, license,
trust. Missing information is represented as None, never guessed.
"""
from __future__ import annotations

import dataclasses
from typing import Any, Optional


@dataclasses.dataclass
class Provenance:
    source_dataset: str          # SOURCE-PROVIDED (dataset identity)
    source_file: str             # SOURCE-PROVIDED (path relative to data/raw)
    source_record_id: str        # SOURCE-PROVIDED (dataset's own top-level record id)
    conversation_id: str         # DERIVED (see field docstring on MemoryRecord)
    session_id: Optional[str]    # SOURCE-PROVIDED where the dataset has sessions, else None
    turn_id: Optional[str]       # SOURCE-PROVIDED where the dataset has turn ids, else None
    extraction_pipeline_version: str  # DERIVED (preprocessing.PIPELINE_VERSION)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class MemoryRecord:
    """One conversational turn / utterance, normalized across datasets."""

    memory_id: str                      # DERIVED: deterministic hash of provenance chain
    content: str                        # SOURCE-PROVIDED: the utterance text
    source_dataset: str                 # SOURCE-PROVIDED
    source_file: str                    # SOURCE-PROVIDED
    source_record_id: str               # SOURCE-PROVIDED
    conversation_id: str                # DERIVED (dataset-specific composite key; documented per-dataset)
    session_id: Optional[str]           # SOURCE-PROVIDED or None
    turn_id: Optional[str]              # SOURCE-PROVIDED or DERIVED (positional) — see data_quality flags
    source_role: Optional[str]          # SOURCE-PROVIDED speaker/role label, or None
    event_order: int                    # DERIVED: 0-based turn position within conversation_id
    source_timestamp: Optional[str]     # SOURCE-PROVIDED raw timestamp string, or None
    timestamp_type: str                 # DERIVED: "absolute" | "relative" | "unavailable"
    benchmark_timestamp: Optional[str]  # RESERVED: always None in Phase 1
    provenance: dict                    # DERIVED (see Provenance)
    data_quality: list                  # DERIVED: list of quality-flag strings, [] if none
    metadata: dict                      # SOURCE-PROVIDED dataset-specific extras (persona, dia_id, etc.)
    quality_status: str = "valid"       # DERIVED: one of preprocessing.quality's four statuses.
                                         # Records with quality_status != "valid" are still natural
                                         # data-quality findings, NEVER an indication of poisoning
                                         # (see preprocessing/quality.py docstring).

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class TaskRecord:
    """A QA / evaluation instance that references the memory substrate.

    Only produced for datasets that natively contain such instances
    (LoCoMo `qa`, LongMemEval top-level entries). Not fabricated for MSC or
    Conversation Chronicles, which contain no such structure.
    """

    task_id: str                        # DERIVED
    source_dataset: str                 # SOURCE-PROVIDED
    source_file: str                    # SOURCE-PROVIDED
    source_record_id: str               # SOURCE-PROVIDED
    conversation_id: str                # DERIVED, links to MemoryRecord.conversation_id
    question: str                       # SOURCE-PROVIDED
    answer: Any                         # SOURCE-PROVIDED (kept in native type: str/int/list)
    question_type: Optional[str]        # SOURCE-PROVIDED (dataset's own category label), or None
    evidence_refs_raw: list             # SOURCE-PROVIDED: evidence identifiers as given by the dataset
    evidence_memory_ids: list           # DERIVED: evidence_refs_raw resolved to memory_id where possible
    metadata: dict                      # SOURCE-PROVIDED dataset-specific extras

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)
