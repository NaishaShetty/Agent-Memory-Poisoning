"""Phase 2.1-R: trusted clean-memory baseline selection.

Operationalizes "not part of the trusted clean-memory baseline" as an
actual, testable predicate rather than only a documentation claim. Phase
3's memory-lifecycle work is expected to call `is_trusted_clean_memory`
(or extend it) whenever it needs to decide whether a processed memory
record may enter the clean baseline used for benign-behavior experiments.

This module does not modify any Phase 1 artifact. It reads
`data/metadata/longmemeval_provenance_exceptions.json` -- an additive,
Phase 2.1-R record of specific memory_ids with unresolved source-integrity
issues -- and excludes those IDs regardless of their `quality_status`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from preprocessing.config import PipelineConfig
from preprocessing.io_utils import read_json

_TRUSTED_QUALITY_STATUSES = {"valid", "repaired"}


def provenance_exceptions_path(cfg: PipelineConfig) -> Path:
    return cfg.metadata_dir / "longmemeval_provenance_exceptions.json"


def load_provenance_exceptions(cfg: PipelineConfig) -> dict:
    path = provenance_exceptions_path(cfg)
    if not path.exists():
        return {"records": []}
    return read_json(path)


def excluded_memory_ids(cfg: PipelineConfig) -> set[str]:
    """memory_ids that must never enter the trusted clean-memory baseline,
    regardless of their Phase 1 quality_status, because their source
    integrity is provenance_status != VERIFIED (see the case study doc)."""
    exceptions = load_provenance_exceptions(cfg)
    return {r["memory_id"] for r in exceptions.get("records", [])}


def is_trusted_clean_memory(record: dict, excluded_ids: Optional[set[str]] = None) -> bool:
    """True only for records that are both Phase-1 quality-clean
    (valid/repaired) AND not flagged by a provenance case study exception.

    A record with quality_status in {valid_flagged, irrecoverably_invalid}
    is never trusted-clean. A record in `excluded_ids` is never
    trusted-clean even if its quality_status is valid/repaired -- the
    provenance exception is a stronger, more specific signal than the
    generic quality classification.
    """
    if excluded_ids and record.get("memory_id") in excluded_ids:
        return False
    return record.get("quality_status") in _TRUSTED_QUALITY_STATUSES
