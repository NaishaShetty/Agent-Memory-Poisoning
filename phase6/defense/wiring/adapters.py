"""Phase 6.10 -- real Phase 3/5 ledger-to-SignalContext wiring.

WHAT THIS MODULE IS, AND THE ENVIRONMENT LIMITATION THAT SHAPES ITS SCOPE
--------------------------------------------------------------------------------
Stages 6.4-6.9 deliberately deferred "build a `SignalContext`/`RetrievalCandidate`/
`AncestorRecord` from a REAL Phase 3/5 object" to this stage. This module does
exactly that -- and ONLY that. It was verified, before writing a line of this
module, that a full LIVE seven-attack campaign (real V3-Hybrid, real Mem0/A-MEM,
real LLM generation) cannot be executed in this working environment:
`mem0`/`mem0ai`/`qdrant_client`/`chromadb` are not installed here, and the local
LLM server every real Phase 3/4 campaign script points at
(`http://127.0.0.1:8811`) is unreachable. This is the SAME category of
environment limitation this project's own A-MEM real-vendor tests already
report honestly (`NOT_VALIDATED`, never a fabricated pass) -- Rule 15 applies
identically here: this module's own tests use REAL, directly-constructed
`CanonicalMemoryRecord`/`Phase5Event` objects (the same pattern
`phase5/tests/*.py` already uses throughout), never a live campaign, and this
document says so plainly rather than implying more than was actually run.

WHAT IS ACTUALLY DEMONSTRATED
--------------------------------------------------------------------------------
That Phase 6's defense components can consume REAL Phase 3/5 object shapes
correctly -- not synthetic stand-ins -- verified against the frozen schemas
those objects actually enforce (`CanonicalMemoryRecord.__post_init__`'s real
validation, `Phase5Event`'s real per-type field closure). This is real,
substantive integration work, distinct from (and a prerequisite for, not a
replacement of) an eventual live campaign run.
"""

from __future__ import annotations

from typing import Optional

from phase3.evaluation.foundations.canonical import CanonicalMemoryRecord
from phase5.schema.event import RETRIEVAL_CANDIDATE_SCORED, Phase5Event
from phase6.defense.propagation.signals import AncestorRecord
from phase6.defense.retrieval.consensus_guard import RetrievalCandidate
from phase6.defense.signals.contract import SignalContext, build_signal_context


def signal_context_from_canonical_record(record: CanonicalMemoryRecord) -> SignalContext:
    """Build a `SignalContext` from a REAL `CanonicalMemoryRecord`, reading
    only the fields Stage 6.4's Signal Contract already sanctions (Section
    2.1-2.2): `content["text"]`/`content["content_type"]`, `memory_type`,
    `parent_ids`, `lifecycle_state`, `creation_timestamp`. Never reads
    `record.source` wholesale -- exactly the leakage path Stage 6.4's own
    audit found and closed (Signal Contract document Section 1); this
    function reads only the two specific `content` sub-keys it names, nothing
    else from the record's metadata-adjacent fields.
    """
    content_text = record.content.get("text", "")
    content_type = record.content.get("content_type", "UNKNOWN")
    return build_signal_context(
        memory_id=record.memory_id,
        content_text=content_text,
        content_type=content_type,
        memory_type=record.memory_type,
        parent_ids=record.parent_ids,
        lifecycle_state=record.lifecycle_state,
        creation_timestamp=record.creation_timestamp,
    )


def retrieval_candidate_from_real_records(
    memory_record: CanonicalMemoryRecord,
    score_event: Phase5Event,
    *,
    security_state: str,
) -> RetrievalCandidate:
    """Build a `RetrievalCandidate` from a REAL `CanonicalMemoryRecord` (for
    content) and a REAL `retrieval_candidate_scored` `Phase5Event` (for the
    already-persisted, real per-candidate scores) -- two separate real ledgers
    joined on `memory_id`, exactly as a live pipeline would.
    """
    if score_event.event_type != RETRIEVAL_CANDIDATE_SCORED:
        raise ValueError(
            f"score_event must be a {RETRIEVAL_CANDIDATE_SCORED!r} event; got {score_event.event_type!r}"
        )
    if score_event.memory_id != memory_record.memory_id:
        raise ValueError(
            f"score_event.memory_id {score_event.memory_id!r} does not match "
            f"memory_record.memory_id {memory_record.memory_id!r}"
        )
    return RetrievalCandidate(
        memory_id=memory_record.memory_id,
        content_text=memory_record.content.get("text", ""),
        cosine_score=score_event.cosine_score,
        token_overlap_score=score_event.token_overlap_score,
        entity_overlap_score=score_event.entity_overlap_score,
        raw_blended_score=score_event.blended_score,
        security_state=security_state,
    )


def ancestor_record_from_real_record(
    ancestor_memory: CanonicalMemoryRecord,
    *,
    security_state: str,
    distance: int,
) -> AncestorRecord:
    """Build an `AncestorRecord` from a REAL `CanonicalMemoryRecord` -- the
    caller supplies `distance` (the real DERIVED_FROM hop count, from Phase
    5's actual `build_propagation_graph()` output) and `security_state` (from
    a real `GovernanceLedger.current_state()` lookup); this function does not
    walk the graph or read the ledger itself, consistent with every other
    Phase 6 wiring function's plain-data-carrier discipline.
    """
    return AncestorRecord(
        memory_id=ancestor_memory.memory_id,
        content_text=ancestor_memory.content.get("text", ""),
        security_state=security_state,
        distance=distance,
    )
