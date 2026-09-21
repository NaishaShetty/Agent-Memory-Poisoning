"""Phase 11.x Track A -- authorized clean-side expansion using the 3 real,
currently-unused datasets in the Phase 1/2 unified corpus (LongMemEval, MSC,
Conversation Chronicles -- 1,260,312 real records the audit found untouched
by any Phase 11 work). LoCoMo is deliberately excluded here -- it is already
handled by `phase11/data/real_corpus.py`, which this module does not modify.

CONTROLLED, NOT FULL-CORPUS INGESTION
--------------------------------------------------------------------------------
Per the governing instructions ("do NOT immediately ingest all 1.26M
records... start with a scientifically controlled, representative
sample"), this module reads only the first `MAX_RECORDS_SCANNED_PER_DATASET`
real records of each file (file order, deterministic, disclosed -- not a
random sample, not cherry-picked) and keeps only the first
`CONTROLLED_POOLS_PER_DATASET` real, complete (conversation_id, session_id)
groups encountered within that scan.

REAL POOL-GROUPING KEY -- VERIFIED, NOT ASSUMED
--------------------------------------------------------------------------------
Direct inspection (this investigation) found `session_id` ALONE is not
globally unique within any of these 3 files -- it resets per conversation
(e.g. "session_1" is reused by hundreds of unrelated real conversations).
The correct, real, natural grouping boundary is the COMPOSITE
`(conversation_id, session_id)` key, verified against a real sample of each
file: this gives natural real pool sizes of roughly 5-50 records (LongMemEval
mean 11.1, MSC mean 13.3, Conversation Chronicles mean 11.7 -- see
`docs/phase11/PHASE11_X_TRACK_AB_REPORT.md` for the full distribution), a
real, unforced range in the same neighborhood the project's own sanctioned
pools already use -- not tuned to hit that range, discovered to already be
in it.

DERIVED_FROM IS NEVER USED HERE
--------------------------------------------------------------------------------
The prior audit found `derivation_parents` is populated in 0 of 8,000
sampled records across all 4 unified-corpus datasets. This module never
sets `parent_ids`/`ancestors` on any `MemoryScenario` it builds -- doing so
would fabricate lineage this real data does not contain. Only
`RETRIEVED_WITH` edges (implied by real, shared `(conversation_id,
session_id)` pool membership, via the SAME sanctioned mechanism
`phase11/gnn/graph_build.py` already uses) are ever implied by this module's
output.

PROVENANCE IS PRESERVED, NOT DISCARDED
--------------------------------------------------------------------------------
`MemoryScenario` has no generic metadata slot, so full source provenance
(source_dataset, source_record_id, conversation_id, session_id, turn_id,
timestamps, the record's own real `provenance` dict, quality/trust status)
is returned SEPARATELY, keyed by `scenario_id`, in a `CleanRecordProvenance`
map alongside each `ScenarioPool` -- additive, not a modification to
`MemoryScenario` itself.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from phase6.defense.orchestration.pipeline import MemoryScenario, ScenarioPool

UNUSED_CLEAN_DATASETS: Tuple[str, ...] = ("longmemeval", "msc", "conversation_chronicles")
UNIFIED_MEMORY_ROOT = Path("data/processed/unified_memory")

MAX_RECORDS_SCANNED_PER_DATASET = 20_000  # a controlled prefix, not the full file
CONTROLLED_POOLS_PER_DATASET = 10  # matches the scale already used for LoCoMo in real_corpus.py


@dataclass(frozen=True)
class CleanRecordProvenance:
    scenario_id: str
    source_dataset: str
    source_record_id: str
    conversation_id: str
    session_id: str
    turn_id: str
    source_timestamp: str
    normalized_timestamp: str
    provenance: Dict[str, object]
    quality_status: str
    trusted_clean_memory: bool


def _unified_path(dataset_name: str) -> Path:
    return UNIFIED_MEMORY_ROOT / dataset_name / "memory_records.jsonl"


def _scan_first_n_records(dataset_name: str, n: int):
    path = _unified_path(dataset_name)
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= n:
                return
            yield json.loads(line)


def real_session_pools(
    dataset_name: str, *, num_pools: int = CONTROLLED_POOLS_PER_DATASET,
    max_records_scanned: int = MAX_RECORDS_SCANNED_PER_DATASET,
) -> Tuple[Tuple[ScenarioPool, ...], Dict[str, CleanRecordProvenance]]:
    """Real (conversation_id, session_id)-grouped pools from `dataset_name`,
    deterministic (file order), first `num_pools` real groups encountered
    within the first `max_records_scanned` real records. Every scenario's
    `is_poison_ground_truth` is `False`, `parent_ids`/`ancestors` are always
    empty (per module docstring -- no fabricated lineage)."""
    groups: Dict[Tuple[str, str], List[dict]] = {}
    group_order: List[Tuple[str, str]] = []

    for record in _scan_first_n_records(dataset_name, max_records_scanned):
        key = (record["conversation_id"], record["session_id"])
        if key not in groups:
            if len(group_order) >= num_pools:
                continue
            groups[key] = []
            group_order.append(key)
        if key in groups:
            groups[key].append(record)

    pools: List[ScenarioPool] = []
    provenance_map: Dict[str, CleanRecordProvenance] = {}

    for conv_id, session_id in group_order:
        records = groups[(conv_id, session_id)]
        memories = []
        for record in records:
            scenario_id = f"REAL-CLEAN-{dataset_name.upper()}-{record['source_record_id']}-{record['turn_id']}"
            memories.append(
                MemoryScenario(scenario_id, record["content"], is_poison_ground_truth=False)
            )
            provenance_map[scenario_id] = CleanRecordProvenance(
                scenario_id=scenario_id,
                source_dataset=record["source_dataset"],
                source_record_id=record["source_record_id"],
                conversation_id=conv_id,
                session_id=session_id,
                turn_id=record["turn_id"],
                source_timestamp=record.get("source_timestamp") or "",
                normalized_timestamp=record.get("normalized_timestamp") or "",
                provenance=record.get("provenance") or {},
                quality_status=record.get("quality_status") or "",
                trusted_clean_memory=bool(record.get("trusted_clean_memory")),
            )
        pool_id = f"POOL-REAL-CLEAN-{dataset_name.upper()}-{conv_id}-{session_id}"
        pools.append(ScenarioPool(pool_id, tuple(memories)))

    return tuple(pools), provenance_map


def clean_expansion_pools(
    *, num_pools_per_dataset: int = CONTROLLED_POOLS_PER_DATASET,
) -> Tuple[Tuple[ScenarioPool, ...], Dict[str, CleanRecordProvenance]]:
    """All 3 unused real datasets combined -- additive to, never a
    replacement for, `real_corpus.py`'s existing LoCoMo-only expansion."""
    all_pools: List[ScenarioPool] = []
    all_provenance: Dict[str, CleanRecordProvenance] = {}
    for dataset_name in UNUSED_CLEAN_DATASETS:
        pools, provenance = real_session_pools(dataset_name, num_pools=num_pools_per_dataset)
        all_pools.extend(pools)
        all_provenance.update(provenance)
    return tuple(all_pools), all_provenance


@dataclass(frozen=True)
class PoolSizeReport:
    dataset_name: str
    n_pools: int
    sizes: Tuple[int, ...]
    minimum: int
    maximum: int
    mean: float
    median: float
    stdev: float
    p25: float
    p75: float
    p90: float


def pool_size_report(dataset_name: str, pools: Sequence[ScenarioPool]) -> PoolSizeReport:
    sizes = tuple(sorted(len(p.memories) for p in pools))
    if not sizes:
        return PoolSizeReport(dataset_name, 0, (), 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    return PoolSizeReport(
        dataset_name=dataset_name, n_pools=len(sizes), sizes=sizes,
        minimum=sizes[0], maximum=sizes[-1],
        mean=statistics.mean(sizes), median=statistics.median(sizes),
        stdev=statistics.pstdev(sizes) if len(sizes) > 1 else 0.0,
        p25=statistics.quantiles(sizes, n=4)[0] if len(sizes) >= 4 else float(sizes[0]),
        p75=statistics.quantiles(sizes, n=4)[2] if len(sizes) >= 4 else float(sizes[-1]),
        p90=statistics.quantiles(sizes, n=10)[8] if len(sizes) >= 10 else float(sizes[-1]),
    )
