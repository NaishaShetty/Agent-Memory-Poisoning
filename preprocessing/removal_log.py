"""Append-only, machine-readable log of every record removed or materially
transformed during cleaning. Nothing is ever silently dropped (Step 7).
"""
from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Optional

from preprocessing import PIPELINE_VERSION
from preprocessing.io_utils import append_jsonl


@dataclasses.dataclass
class RemovalEvent:
    dataset: str
    source_record_id: str
    source_file: str
    operation: str          # "removed" | "transformed" | "flagged"
    reason: str
    run_timestamp: str
    pipeline_version: str = PIPELINE_VERSION
    detail: Optional[str] = None

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


class RemovalLog:
    """Buffers events in memory and flushes them to logs/removal_log.jsonl."""

    def __init__(self, dataset: str, run_timestamp: str):
        self.dataset = dataset
        self.run_timestamp = run_timestamp
        self._events: list[RemovalEvent] = []

    def record(
        self,
        source_record_id: str,
        source_file: str,
        operation: str,
        reason: str,
        detail: Optional[str] = None,
    ) -> None:
        self._events.append(
            RemovalEvent(
                dataset=self.dataset,
                source_record_id=source_record_id,
                source_file=source_file,
                operation=operation,
                reason=reason,
                run_timestamp=self.run_timestamp,
                detail=detail,
            )
        )

    def __len__(self) -> int:
        return len(self._events)

    def count_by_operation(self, operation: str) -> int:
        return sum(1 for e in self._events if e.operation == operation)

    def flush(self, logs_dir: Path) -> int:
        path = logs_dir / "removal_log.jsonl"
        return append_jsonl(path, (e.to_dict() for e in self._events))
