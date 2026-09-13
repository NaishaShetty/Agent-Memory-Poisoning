"""Phase 5.8A -- Memory Behavior Dataset Derivation.

WHAT THIS IS, AND WHAT IT IS NOT
--------------------------------------------------------------------------------
A DERIVED ANALYTICAL ARTIFACT ONLY. Every record this module produces is a flattened,
read-only view over facts that already exist, durably, in the canonical/Phase 5 ledgers
(via Stage 5.8's `assemble_trace()`/`build_propagation_graph()`, both reused verbatim,
never reimplemented here). This dataset is NEVER the source of truth for anything --
deleting it and regenerating it from the same ledger state must always produce the
identical result (proven by test), and no downstream consumer should ever write back
into the ledgers based on something observed only in this dataset.

WHY ONE UNIFORM RECORD ENVELOPE, NOT SIX SEPARATE DATACLASSES
--------------------------------------------------------------------------------
The categories this stage must cover (memory lifecycle, retrieval/selection, agent
interactions, memory-to-memory relationships, propagation/lineage, attack/injection
events, counterfactual evidence) already have their own real, strict, validated schemas
-- `CanonicalEvent`, `Phase5Event`, `MemoryInteractionEdge`. Re-typing each of those into
a SEVENTH bespoke dataclass per category would be exactly the "second, parallel schema"
problem this project has avoided at every prior stage. Instead, `MemoryBehaviorRecord` is
one uniform, flat ENVELOPE: `record_type` (a closed category label), `run_id`,
`source_event_ids` (the real, citable event id(s) this record was flattened from --
NEVER invented, NEVER re-derived independently of the ledgers), and `fields` (a
plain, JSON-serializable mapping of that category's own real data, copied verbatim from
the underlying event/edge object's own `to_dict()`-equivalent, never re-computed).

DETERMINISM
--------------------------------------------------------------------------------
`derive_memory_behavior_dataset()` calls `assemble_trace()`/`build_propagation_graph()`
(both already proven deterministic in Stage 5.8's own tests) and maps their output to
records in a fixed, documented order (see `_RECORD_TYPE_ORDER`) with no randomness, no
wall-clock dependency, and no set/dict iteration where order is not first stably sorted.
Two calls against the same ledger state always produce byte-identical (after JSON
serialization) output.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Tuple, Union

from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase3.evaluation.foundations.memory_versioning import SupersessionLedger

from phase5.identity.run_identity import EventRunMembershipLedger
from phase5.schema.event_ledger import Phase5EventLedger
from phase5.wiring.lineage import MemoryInteractionEdge
from phase5.wiring.trace_assembly import ExperimentTrace, PropagationGraph, assemble_trace, build_propagation_graph

RECORD_TYPE_MEMORY_LIFECYCLE = "memory_lifecycle"
RECORD_TYPE_RETRIEVAL_SELECTION = "retrieval_selection"
RECORD_TYPE_AGENT_INTERACTION = "agent_interaction"
RECORD_TYPE_MEMORY_RELATIONSHIP = "memory_relationship"
RECORD_TYPE_ATTACK_INJECTION = "attack_injection"
RECORD_TYPE_COUNTERFACTUAL_EVIDENCE = "counterfactual_evidence"

RECORD_TYPES: Tuple[str, ...] = (
    RECORD_TYPE_MEMORY_LIFECYCLE,
    RECORD_TYPE_RETRIEVAL_SELECTION,
    RECORD_TYPE_AGENT_INTERACTION,
    RECORD_TYPE_MEMORY_RELATIONSHIP,
    RECORD_TYPE_ATTACK_INJECTION,
    RECORD_TYPE_COUNTERFACTUAL_EVIDENCE,
)


class MemoryBehaviorDatasetError(ValueError):
    """Raised when a `MemoryBehaviorRecord` is malformed. Fails loudly, no silent
    coercion -- mirrors every other schema in this framework."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise MemoryBehaviorDatasetError(message)


@dataclass(frozen=True)
class MemoryBehaviorRecord:
    """One row of the Memory Behavior Dataset. `source_event_ids` is REQUIRED non-empty
    -- exactly `MemoryInteractionEdge`'s own "no fact without a citable event" invariant,
    applied here to every record type, not just relationship edges."""

    record_type: str
    run_id: str
    source_event_ids: Tuple[str, ...]
    fields: Mapping[str, Any]

    def __post_init__(self) -> None:
        _require(self.record_type in RECORD_TYPES, f"record_type {self.record_type!r} is not one of {RECORD_TYPES!r}.")
        _require(isinstance(self.run_id, str) and bool(self.run_id), "run_id must be a non-empty string.")
        _require(
            isinstance(self.source_event_ids, tuple) and len(self.source_event_ids) > 0,
            "source_event_ids must be a non-empty tuple -- every dataset record must cite the real "
            "event(s) it was derived from; this dataset never asserts a fact independently of the ledgers.",
        )
        _require(isinstance(self.fields, Mapping), "fields must be a mapping.")

    def to_dict(self) -> dict:
        return {
            "record_type": self.record_type,
            "run_id": self.run_id,
            "source_event_ids": list(self.source_event_ids),
            "fields": dict(self.fields),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryBehaviorRecord":
        return cls(
            record_type=data["record_type"], run_id=data["run_id"],
            source_event_ids=tuple(data["source_event_ids"]), fields=data["fields"],
        )


def _canonical_event_record(run_id: str, event) -> MemoryBehaviorRecord:
    return MemoryBehaviorRecord(
        record_type=RECORD_TYPE_MEMORY_LIFECYCLE, run_id=run_id,
        source_event_ids=(event.event_id,), fields=event.to_dict(),
    )


def _retrieval_selection_record(run_id: str, event) -> MemoryBehaviorRecord:
    return MemoryBehaviorRecord(
        record_type=RECORD_TYPE_RETRIEVAL_SELECTION, run_id=run_id,
        source_event_ids=(event.event_id,), fields=event.to_dict(),
    )


def _agent_interaction_record(run_id: str, event) -> MemoryBehaviorRecord:
    return MemoryBehaviorRecord(
        record_type=RECORD_TYPE_AGENT_INTERACTION, run_id=run_id,
        source_event_ids=(event.event_id,), fields=event.to_dict(),
    )


def _relationship_record(run_id: str, edge: MemoryInteractionEdge) -> MemoryBehaviorRecord:
    return MemoryBehaviorRecord(
        record_type=RECORD_TYPE_MEMORY_RELATIONSHIP, run_id=run_id,
        source_event_ids=edge.established_by_event_ids,
        fields={
            "relationship_type": edge.relationship_type, "source_id": edge.source_id,
            "target_id": edge.target_id, "evidence_kind": edge.evidence_kind,
        },
    )


def _attack_injection_record(run_id: str, event) -> MemoryBehaviorRecord:
    return MemoryBehaviorRecord(
        record_type=RECORD_TYPE_ATTACK_INJECTION, run_id=run_id,
        source_event_ids=(event.event_id,), fields=event.to_dict(),
    )


def _counterfactual_record(run_id: str, event) -> MemoryBehaviorRecord:
    return MemoryBehaviorRecord(
        record_type=RECORD_TYPE_COUNTERFACTUAL_EVIDENCE, run_id=run_id,
        source_event_ids=(event.event_id,), fields=event.to_dict(),
    )


def derive_memory_behavior_dataset(
    run_id: str,
    *,
    memory_ledger: CanonicalMemoryLedger,
    event_ledger: CanonicalEventLedger,
    phase5_event_ledger: Phase5EventLedger,
    membership_ledger: EventRunMembershipLedger,
    supersession_ledger: Optional[SupersessionLedger] = None,
) -> Tuple[MemoryBehaviorRecord, ...]:
    """Derive the complete Memory Behavior Dataset for one run, in fixed, deterministic
    order: memory lifecycle, retrieval/selection, agent interactions, relationships
    (from the run-scoped propagation graph), attack injections, counterfactual evidence.

    Calls `assemble_trace()`/`build_propagation_graph()` (Stage 5.8) exactly once each,
    never re-querying the ledgers independently -- this function cannot disagree with
    Stage 5.8's own trace/graph, by construction.
    """
    trace: ExperimentTrace = assemble_trace(
        run_id, event_ledger=event_ledger, phase5_event_ledger=phase5_event_ledger, membership_ledger=membership_ledger,
    )
    graph: PropagationGraph = build_propagation_graph(
        run_id, memory_ledger=memory_ledger, event_ledger=event_ledger,
        phase5_event_ledger=phase5_event_ledger, membership_ledger=membership_ledger,
        supersession_ledger=supersession_ledger,
    )

    records: list = []

    for event in trace.memory_created:
        records.append(_canonical_event_record(run_id, event))
    for event in trace.memory_derived:
        records.append(_canonical_event_record(run_id, event))
    for event in trace.memory_superseded:
        records.append(_canonical_event_record(run_id, event))
    for event in trace.memory_retired:
        records.append(_canonical_event_record(run_id, event))

    for event in trace.memory_retrieved:
        records.append(_retrieval_selection_record(run_id, event))
    for event in trace.memory_selected:
        records.append(_retrieval_selection_record(run_id, event))
    for event in trace.memory_rejected:
        records.append(_retrieval_selection_record(run_id, event))
    for event in trace.memory_used:
        records.append(_retrieval_selection_record(run_id, event))
    for event in trace.retrieval_candidates_scored:
        records.append(_retrieval_selection_record(run_id, event))

    for event in trace.context_assembled:
        records.append(_agent_interaction_record(run_id, event))
    for event in trace.agent_decisions:
        records.append(_agent_interaction_record(run_id, event))
    for event in trace.agent_actions:
        records.append(_agent_interaction_record(run_id, event))

    for edge in graph.edges:
        records.append(_relationship_record(run_id, edge))

    for event in trace.injections:
        records.append(_attack_injection_record(run_id, event))

    for event in trace.counterfactual_findings:
        records.append(_counterfactual_record(run_id, event))

    return tuple(records)


def write_memory_behavior_dataset_jsonl(records: Tuple[MemoryBehaviorRecord, ...], path: Union[str, Path]) -> None:
    """Write `records` as newline-delimited JSON, one record per line, in the exact
    order given -- never re-sorted, so the file's own line order matches
    `derive_memory_behavior_dataset()`'s documented, deterministic record order."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record.to_dict(), sort_keys=True) + "\n")


def read_memory_behavior_dataset_jsonl(path: Union[str, Path]) -> Tuple[MemoryBehaviorRecord, ...]:
    """Read a JSONL file written by `write_memory_behavior_dataset_jsonl()` back into
    `MemoryBehaviorRecord`s -- a malformed line raises loudly, never silently skipped,
    mirroring every ledger's own reload discipline in this framework."""
    records = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            records.append(MemoryBehaviorRecord.from_dict(json.loads(line)))
    return tuple(records)


__all__ = [
    "RECORD_TYPE_MEMORY_LIFECYCLE",
    "RECORD_TYPE_RETRIEVAL_SELECTION",
    "RECORD_TYPE_AGENT_INTERACTION",
    "RECORD_TYPE_MEMORY_RELATIONSHIP",
    "RECORD_TYPE_ATTACK_INJECTION",
    "RECORD_TYPE_COUNTERFACTUAL_EVIDENCE",
    "RECORD_TYPES",
    "MemoryBehaviorDatasetError",
    "MemoryBehaviorRecord",
    "derive_memory_behavior_dataset",
    "write_memory_behavior_dataset_jsonl",
    "read_memory_behavior_dataset_jsonl",
]
