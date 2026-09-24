"""Phase 14 -- real ledger storage/record-count overhead, defended vs
undefended (2026-09-23, explicitly authorized).

WHY THIS EXISTS
--------------------------------------------------------------------------------
Every real defended task run, unlike an undefended one, produces real
per-candidate defense decisions (Phase 14's own `DefenseDecision`s) that a
real deployment would want to persist for audit -- exactly the same real
`CanonicalMemoryRecord`/`CanonicalEvent` infrastructure Phases 3/5/12/13
already use. No report has directly measured what that costs in real bytes
on disk. This module measures it directly: for a real, small batch of tasks,
persist a real `created` event per real candidate memory PLUS a real
`admission`-shaped decision record when a defense config is active, using
the SAME real, unmodified ledger machinery Phase 13's own modules already
use, and reports real bytes-on-disk and real record-count growth, defended
vs undefended (`CONFIG_B0_NO_DEFENSE`), on the SAME real candidate set.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence, Tuple

from phase3.evaluation.foundations.canonical import (
    CanonicalMemoryRecord,
    LIFECYCLE_CREATED,
    MEMORY_TYPE_FOUNDATION,
    SOURCE_TYPE_PHASE2_UMR,
)
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase5.identity.run_identity import EventRunMembershipLedger, ExperimentRunLedger, ExperimentRunRecord
from phase5.wiring.memory_lifecycle import record_memory_creation
from phase14.defended_retrieval import DefenseDecision, apply_defense

TS = "2026-09-23T00:00:00Z"
RUN_ID = "phase14-storage-overhead"


@dataclass(frozen=True)
class StorageOverheadResult:
    config_name: str
    n_tasks: int
    n_candidates: int
    total_bytes: int
    n_records: int
    bytes_per_task: float


def _dir_size_and_count(path: Path) -> Tuple[int, int]:
    total_bytes = 0
    n_records = 0
    for f in path.rglob("*"):
        if f.is_file():
            total_bytes += f.stat().st_size
            if f.suffix == ".jsonl":
                with f.open(encoding="utf-8") as fh:
                    n_records += sum(1 for line in fh if line.strip())
    return total_bytes, n_records


def measure_storage_overhead(
    config_name: str, tasks: Sequence[Tuple[str, Sequence[Tuple[str, str]]]],
) -> StorageOverheadResult:
    """`tasks`: `[(task_id, [(memory_id, content_text), ...]), ...]` -- the
    SAME real candidate pools Track A/B build. Persists a real `created`
    event for every real candidate (undefended baseline already does this
    much -- retrieval always requires the candidate to exist as a real
    memory record), and, when `config_name` is a real defended
    configuration, ALSO records each real `DefenseDecision` as a structured
    note on that same real record's `source` field (the smallest real,
    disclosed way to persist an audit trail without inventing a new event
    type Phase 5/12/13 do not already support)."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="phase14_storage_"))
    try:
        memory_ledger = CanonicalMemoryLedger(tmp_dir / "memory")
        event_ledger = CanonicalEventLedger(tmp_dir / "events", memory_ledger)
        run_ledger = ExperimentRunLedger(tmp_dir / "runs")
        membership_ledger = EventRunMembershipLedger(tmp_dir / "membership", run_ledger)
        run_ledger.register(ExperimentRunRecord(
            experiment_id="phase14-utility", run_id=RUN_ID, dataset="phase14_pilot", scope={},
            started_at=TS, actor="phase14-storage-overhead", reason="real storage overhead measurement",
        ))

        n_candidates = 0
        for task_id, items in tasks:
            _, decisions = apply_defense(config_name, items)
            decisions_by_id = {d.memory_id: d for d in decisions}
            for memory_id, content_text in items:
                n_candidates += 1
                decision: DefenseDecision = decisions_by_id.get(memory_id)
                source = {"source_type": SOURCE_TYPE_PHASE2_UMR}
                if decision is not None and config_name != "B0":
                    source["phase14_defense_decision"] = json.dumps({
                        "config": config_name, "action": decision.action, "excluded": decision.excluded,
                    })
                record = CanonicalMemoryRecord(
                    memory_id=f"{task_id}::{memory_id}", memory_type=MEMORY_TYPE_FOUNDATION,
                    content={"text": content_text}, source=source, parent_ids=(),
                    creation_event=f"creation-of-{task_id}::{memory_id}", creation_timestamp=TS,
                    lifecycle_state=LIFECYCLE_CREATED,
                )
                record_memory_creation(
                    memory_ledger=memory_ledger, event_ledger=event_ledger, membership_ledger=membership_ledger,
                    run_id=RUN_ID, record=record, actor="phase14-storage-overhead",
                    reason="real Phase 14 pilot candidate memory", timestamp=TS,
                )

        total_bytes, n_records = _dir_size_and_count(tmp_dir)
        return StorageOverheadResult(
            config_name=config_name, n_tasks=len(tasks), n_candidates=n_candidates,
            total_bytes=total_bytes, n_records=n_records,
            bytes_per_task=total_bytes / len(tasks) if tasks else 0.0,
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


__all__ = ["StorageOverheadResult", "measure_storage_overhead"]
