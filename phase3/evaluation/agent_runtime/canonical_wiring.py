"""Phase 3.3-H.4-WIRE -- canonical-ledger wiring for Condition B (Mem0) of
`campaign_formal_runner.py::run_condition_b_mem0()`.

WHY A SEPARATE MODULE
--------------------------------------------------------------------------------
Kept out of `campaign_formal_runner.py` itself so that module's own diff for this mission
stays purely additive (a handful of new call sites, no new inline logic) and easy to review
against a live campaign path that already produced real, expensive, trusted results. Every
function here is a thin, explicit wrapper over EXISTING, unmodified machinery
(`canonical_write.write_canonical_memory()`, `agent_runtime.identity.resolve_source_
identities()`, `run_config.RunConfigRecord`/`RunConfigLedger`, `canonical_event.
CanonicalEvent`, `event_ledger.CanonicalEventLedger`) -- this module invents no new
identity-resolution mechanism, no new hashing scheme, no new ledger persistence discipline.

SCOPE: CONDITION B (MEM0) ONLY
--------------------------------------------------------------------------------
This module assumes `STRATEGY_METADATA_LOOKUP` (Mem0's own identity strategy, per
`agent_runtime/identity.py`'s module docstring) -- every retrieved/selected foundation
memory id is resolved back to its canonical `source_memory_id` via one real
`inspect_memory()` call per id, exactly as `resolve_source_identities()` already does.
Condition C (A-MEM, `STRATEGY_DIRECT_ASSIGNMENT`) is explicitly out of scope for this
mission (a smaller, natural follow-up once this pattern is proven) -- nothing here assumes
or special-cases that strategy.

WHAT THIS MODULE DOES NOT DO
--------------------------------------------------------------------------------
- Does not touch `memory_versioning.py` -- no lifecycle-state cross-referencing, no version
  reconstruction. This mission wires `retrieved`/`selected`/`rejected` events and canonical
  memory records only; nothing here calls `get_current_version()`.
- Does not append a `created` `CanonicalEvent` for each ingested memory. `CanonicalMemory
  Record.creation_event` (H.1's own required field, `memory_schema.md` section on it: "a
  pointer to the logged creation event") is populated with a descriptive, per-memory label
  string for traceability, but no corresponding `CanonicalEvent` is appended to the event
  ledger for creation in this mission -- that is a slightly larger scope (full event-sourced
  ingestion) than this mission's own deliverables (canonical memory WRITES at ingestion,
  §4; resolved retrieved/selected/rejected events, §5) ask for. Documented explicitly here,
  not silently omitted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from phase3.evaluation.agent_runtime.identity import STATUS_RESOLVED, resolve_source_identities
from phase3.evaluation.foundations.adapter import MemoryFoundationAdapter
from phase3.evaluation.foundations.canonical import (
    CanonicalMemoryRecord,
    LIFECYCLE_CREATED,
    MEMORY_TYPE_FOUNDATION,
    SOURCE_TYPE_PHASE2_UMR,
)
from phase3.evaluation.foundations.canonical_event import (
    CanonicalEvent,
    EVENT_REJECTED,
    EVENT_RETRIEVED,
    EVENT_SELECTED,
    REJECTED_REASON_CAPACITY_CUT,
)
from phase3.evaluation.foundations.canonical_write import CanonicalWriteResult, write_canonical_memory
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase3.evaluation.foundations.run_config import (
    RunConfigLedger,
    RunConfigRecord,
    compute_config_fingerprint,
)

FOUNDATION_NAME_MEM0 = "mem0"

# Phase 3.3-H.4-WIRE-C (Condition C / A-MEM) -- the smaller, natural follow-up this
# module's own original docstring named as "out of scope for this mission." A-mem-sys uses
# STRATEGY_DIRECT_ASSIGNMENT (agent_runtime/identity.py): `run_agent_task()`'s
# `retrieved_memory_ids`/`selected_memory_ids` are ALREADY canonical source ids for
# Condition C (verified in 3.3-D/E/F.1, restated in `campaign_formal_runner.py::
# run_condition_c_amem()`'s own docstring), so the Condition-C-specific functions below
# perform NO identity resolution at all -- unlike the Condition-B functions above, which
# exist specifically BECAUSE Mem0 does not honor a caller-supplied id and a real
# `inspect_memory()` round-trip is required. Reusing METADATA_LOOKUP machinery for
# DIRECT_ASSIGNMENT ids would be wrong, not merely redundant: `resolve_source_identities()`
# assumes the id it is given is FOUNDATION-native and needs resolving; a DIRECT_ASSIGNMENT
# id is already canonical, and calling it anyway would either raise or silently pass
# through the wrong id.
FOUNDATION_NAME_AMEM = "amem"
RETRIEVAL_MECHANISM_AMEM_DENSE = "amem_chroma_dense_retrieve"

REASON_RETRIEVED_C = "retrieved via foundation.retrieve() during Condition C (A-MEM) formal campaign execution."
REASON_SELECTED_C = "selected via runner.select_from_retrieved()'s provisional top_k slice policy (Condition C)."

# Documented, honest placeholder (module docstring's "does not pin a separate embedding-
# model revision" note) -- this campaign path names the embedding model
# (sentence-transformers/all-MiniLM-L6-v2, the existing literal `run_condition_b_mem0()`
# already passes to `foundation.initialize()`) but does not track a separate git/package
# revision for it anywhere else in this codebase; recorded as a non-empty, named
# placeholder rather than a fabricated hash.
EMBEDDING_MODEL_REVISION_UNPINNED = "unpinned-default"

RETRIEVAL_MECHANISM_MEM0_DENSE = "mem0_dense_retrieve"
SELECTION_MECHANISM_TOP_K_SLICE = "select_from_retrieved_top_k"

REASON_RETRIEVED = "retrieved via foundation.retrieve() during Condition B (Mem0) formal campaign execution."
REASON_SELECTED = "selected via runner.select_from_retrieved()'s provisional top_k slice policy."
# See module docstring / PHASE3_3_H4_WIRE_IMPLEMENTATION_REPORT.md section on the
# near-vacuity of this path today: `select_from_retrieved()`'s current provisional policy
# is applied to a `retrieved_memory_ids` sequence `_retrieve_and_select()` already capped
# at the SAME `top_k` via `foundation.retrieve()` itself, so `selected_memory_ids` will
# typically equal `retrieved_memory_ids` exactly for Condition B's current configuration --
# this path is expected to rarely or never fire in practice today. `capacity_cut` is the
# closest-fitting existing closed-enum reason (relationship_schema.md section 3.1) for "not
# within the capacity-constrained selected subset" -- not a claim that a smarter selection
# policy exists today. The reason text itself is the free-text `reason` field on the
# `rejected` CanonicalEvent -- REJECTED_REASON_CAPACITY_CUT (the closed-enum value) is used
# directly as that field's value, per canonical_event.py's own requirement that `reason`
# be exactly one of the closed enum for a `rejected` event (not a separate description).


def canonical_store_dir_for_pool(experiments_dir: Path, campaign_id: str, dataset: str, collection_name: str) -> Path:
    """Storage path scheme for this mission's canonical-ledger state, documented here as
    the single source of truth for it: `<experiments_dir>/canonical_store/<campaign_id>/
    <dataset>-<collection_name>/`. `collection_name` is the SAME sha256-derived, filesystem-
    safe token `run_condition_b_mem0()` already computes for Mem0's own collection name
    (`"g_" + sha256(f"{dataset}:{pool_key}")[:16]`) -- reusing it here means the canonical
    store directory and the Mem0 collection it describes are traceable to each other by
    construction, and this scheme cannot collide with any existing storage convention
    (`<experiments_dir>/canonical_store/` is a new top-level directory this mission
    introduces, never previously used by `results/`, `manifests/`, or any other existing
    campaign artifact path).
    """
    return experiments_dir / "canonical_store" / campaign_id / f"{dataset}-{collection_name}"


@dataclass(frozen=True)
class PoolCanonicalLedgers:
    """Everything one pool's canonical-ledger wiring needs, constructed once per pool."""

    memory_ledger: CanonicalMemoryLedger
    event_ledger: CanonicalEventLedger
    config_ledger: RunConfigLedger
    config_fingerprint: str
    storage_dir: Path


def open_pool_canonical_ledgers(
    experiments_dir: Path,
    campaign_id: str,
    dataset: str,
    collection_name: str,
    *,
    adapter_revision: str,
    retrieval_k: int,
    embedding_model: str,
    retrieval_mechanism: str = RETRIEVAL_MECHANISM_MEM0_DENSE,
) -> PoolCanonicalLedgers:
    """Construct (or reopen, if this pool's storage dir already exists from a prior
    partial run) the three canonical ledgers for one pool, and ensure exactly one
    `RunConfigRecord` exists for this pool's retrieval/selection configuration -- every
    task in one pool shares one retrieval configuration by construction (embedding
    model/k/mechanism do not change per task within a pool), so one config_fingerprint is
    computed once and reused for every `retrieved`/`selected`/`counterfactually_influential`
    event this pool's tasks produce.

    `retrieval_mechanism` defaults to `RETRIEVAL_MECHANISM_MEM0_DENSE` -- Condition B's
    existing, already-live call sites pass nothing and get IDENTICAL behavior to before
    this parameter existed (Phase 3.3-H.4-WIRE-C: additive-only, zero behavior change for
    any existing caller). Condition C passes `RETRIEVAL_MECHANISM_AMEM_DENSE` explicitly.
    """
    storage_dir = canonical_store_dir_for_pool(experiments_dir, campaign_id, dataset, collection_name)
    memory_ledger = CanonicalMemoryLedger(storage_dir / "memory")
    event_ledger = CanonicalEventLedger(storage_dir / "events", memory_ledger)
    config_ledger = RunConfigLedger(storage_dir / "run_config")

    config_fingerprint = compute_config_fingerprint(
        embedding_model=embedding_model,
        embedding_model_revision=EMBEDDING_MODEL_REVISION_UNPINNED,
        retrieval_k=retrieval_k,
        retrieval_mechanism=retrieval_mechanism,
        selection_mechanism=SELECTION_MECHANISM_TOP_K_SLICE,
        adapter_revision=adapter_revision,
    )
    if not config_ledger.exists(config_fingerprint):
        config_ledger.append(
            RunConfigRecord(
                config_fingerprint=config_fingerprint,
                embedding_model=embedding_model,
                embedding_model_revision=EMBEDDING_MODEL_REVISION_UNPINNED,
                retrieval_k=retrieval_k,
                retrieval_mechanism=retrieval_mechanism,
                selection_mechanism=SELECTION_MECHANISM_TOP_K_SLICE,
                adapter_revision=adapter_revision,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
        )

    return PoolCanonicalLedgers(
        memory_ledger=memory_ledger,
        event_ledger=event_ledger,
        config_ledger=config_ledger,
        config_fingerprint=config_fingerprint,
        storage_dir=storage_dir,
    )


def write_ingested_canonical_memory(
    memory_ledger: CanonicalMemoryLedger,
    foundation: MemoryFoundationAdapter,
    *,
    source_id: str,
    content: Mapping[str, Any],
    metadata_extra: Mapping[str, Any],
    ingestion_label: str,
) -> CanonicalWriteResult:
    """The canonical-ledger side of one ingestion-loop iteration -- replaces the raw
    `foundation.add_memory(memory_id=source_id, content=..., metadata=...)` call with
    `write_canonical_memory()` (H.1's own, unmodified ingestion bridge). `content`/
    `metadata_extra` are passed through UNCHANGED from what the raw call already used;
    `write_canonical_memory()` additively injects its own `canonical_memory_id`/
    `mambench_memory_type` breadcrumb keys into the metadata dict actually sent to
    `foundation.add_memory()` (see `canonical_write.py::_foundation_metadata()`) --
    verified directly (module docstring "VERIFIED CALL SHAPE" below) to have no effect on
    what Mem0 actually embeds/stores as this memory's content, since
    `RealMem0Adapter.add_memory()` reads ONLY `content` for the embedded text and passes
    `metadata` through as opaque, non-embedded payload metadata.
    """
    record = CanonicalMemoryRecord(
        memory_id=source_id,
        memory_type=MEMORY_TYPE_FOUNDATION,
        content=dict(content),
        source={"source_type": SOURCE_TYPE_PHASE2_UMR, "reference_id": source_id},
        parent_ids=(),
        creation_event=f"{ingestion_label}-{source_id}",
        creation_timestamp=datetime.now(timezone.utc).isoformat(),
        lifecycle_state=LIFECYCLE_CREATED,
    )
    return write_canonical_memory(
        memory_ledger,
        record,
        foundation=foundation,
        foundation_name=FOUNDATION_NAME_MEM0,
        metadata_extra=metadata_extra,
    )


@dataclass
class RetrievalEventReport:
    """Per-task, honest accounting of identity resolution during event emission -- an
    unresolvable or unknown-to-the-ledger id is counted here, NEVER silently dropped with
    no trace (mission section 5, step 2/6; section 8, invariant 4)."""

    task_id: str
    retrieved_event_ids: List[str] = field(default_factory=list)
    selected_event_ids: List[str] = field(default_factory=list)
    rejected_event_ids: List[str] = field(default_factory=list)
    unresolved_foundation_ids: List[str] = field(default_factory=list)
    unresolved_reasons: Dict[str, str] = field(default_factory=dict)
    not_in_canonical_ledger: List[str] = field(default_factory=list)


def record_retrieval_and_selection_events(
    event_ledger: CanonicalEventLedger,
    memory_ledger: CanonicalMemoryLedger,
    foundation: MemoryFoundationAdapter,
    *,
    task_id: str,
    config_fingerprint: str,
    timestamp: str,
    retrieved_foundation_ids: Sequence[str],
    selected_foundation_ids: Sequence[str],
    retrieved_reason: str = REASON_RETRIEVED,
    selected_reason: str = REASON_SELECTED,
) -> RetrievalEventReport:
    """Resolve `retrieved_foundation_ids`/`selected_foundation_ids` (Mem0's own vendor-
    native ids, per `STRATEGY_METADATA_LOOKUP`) back to canonical `source_memory_id`s via
    `agent_runtime.identity.resolve_source_identities()` (reused verbatim, no second
    identity mechanism), then append `retrieved`/`selected`/`rejected` `CanonicalEvent`s
    for every id that resolves AND already exists in `memory_ledger`.

    An id that fails to resolve (`STATUS_NOT_RESOLVABLE`/`STATUS_INSPECT_UNAVAILABLE`), or
    that resolves to a canonical id not present in `memory_ledger` (should not happen given
    Condition B only ever ingests through this pool's own `write_ingested_canonical_
    memory()` calls, but never assumed), produces NO event for that id -- it is recorded in
    the returned `RetrievalEventReport` instead, always visible, never silently absent.
    """
    report = RetrievalEventReport(task_id=task_id)
    selected_set = set(selected_foundation_ids)

    resolutions = resolve_source_identities(foundation, list(retrieved_foundation_ids))

    for foundation_id in retrieved_foundation_ids:
        resolution = resolutions[foundation_id]
        if resolution.status != STATUS_RESOLVED:
            report.unresolved_foundation_ids.append(foundation_id)
            report.unresolved_reasons[foundation_id] = resolution.status
            continue

        canonical_id = resolution.source_memory_id
        if not memory_ledger.exists(canonical_id):
            report.not_in_canonical_ledger.append(canonical_id)
            continue

        retrieved_event = CanonicalEvent(
            event_id=f"retrieved-{task_id}-{canonical_id}",
            event_type=EVENT_RETRIEVED,
            memory_ids=(canonical_id,),
            task_id=task_id,
            timestamp=timestamp,
            actor="candidate_discovery",
            reason=retrieved_reason,
            config_fingerprint=config_fingerprint,
            foundation_name=FOUNDATION_NAME_MEM0,
            foundation_memory_id=foundation_id,
        )
        event_ledger.append(retrieved_event)
        report.retrieved_event_ids.append(retrieved_event.event_id)

        if foundation_id in selected_set:
            selected_event = CanonicalEvent(
                event_id=f"selected-{task_id}-{canonical_id}",
                event_type=EVENT_SELECTED,
                memory_ids=(canonical_id,),
                task_id=task_id,
                timestamp=timestamp,
                actor="evidence_selection",
                reason=selected_reason,
                config_fingerprint=config_fingerprint,
                foundation_name=FOUNDATION_NAME_MEM0,
                foundation_memory_id=foundation_id,
            )
            event_ledger.append(selected_event)
            report.selected_event_ids.append(selected_event.event_id)
        else:
            rejected_event = CanonicalEvent(
                event_id=f"rejected-{task_id}-{canonical_id}",
                event_type=EVENT_REJECTED,
                memory_ids=(canonical_id,),
                task_id=task_id,
                timestamp=timestamp,
                actor="evidence_selection",
                reason=REJECTED_REASON_CAPACITY_CUT,
            )
            event_ledger.append(rejected_event)
            report.rejected_event_ids.append(rejected_event.event_id)

    return report


# ---------------------------------------------------------------------------
# Phase 3.3-H.4-WIRE-C -- Condition C (A-MEM, STRATEGY_DIRECT_ASSIGNMENT) siblings of the
# two functions above. See the FOUNDATION_NAME_AMEM constant's own comment for why these
# cannot simply reuse the Condition-B functions: DIRECT_ASSIGNMENT ids are already
# canonical, so there is no resolution step to perform -- these functions are SIMPLER than
# their Condition-B counterparts, not a parallel reimplementation of the same logic.
# ---------------------------------------------------------------------------


def write_canonical_record_and_alias_direct_assignment(
    memory_ledger: CanonicalMemoryLedger,
    *,
    source_id: str,
    content: Mapping[str, Any],
    ingestion_label: str,
    foundation_memory_id: Optional[str],
) -> CanonicalWriteResult:
    """The canonical-ledger side of one Condition-C ingestion-loop iteration.

    UNLIKE `write_ingested_canonical_memory()` (Condition B), this does NOT call
    `foundation.add_memory()` -- `run_condition_c_amem()`'s own existing ingestion loop
    already made that call directly (unmodified by this mission; see
    `PHASE3_3_H4_WIRE_C_IMPLEMENTATION_REPORT.md` for why touching it was avoided:
    `resolve_via_direct_assignment()` needs the raw `add_memory()` return value, which
    `write_canonical_memory()`'s own `CanonicalWriteResult` does not expose). This function
    is called AFTER that existing call and AFTER `resolve_via_direct_assignment()` has
    already run, using `write_canonical_memory(..., foundation=None)` -- a documented,
    first-class mode (`STATUS_CANONICAL_ONLY`, `canonical_write.py`'s own docstring) that
    persists only the canonical record, calling the foundation a second time for the same
    memory. The alias is then set explicitly using the id the existing resolution step
    already computed, exactly matching what `write_canonical_memory()` would have set had
    it made the foundation call itself.

    `foundation_memory_id=None` (the existing resolution did not resolve, e.g.
    `STATUS_NOT_RESOLVABLE`) skips the alias-set step -- the canonical record is still
    written (a memory that could not be identity-resolved is still a real, ingested
    memory), but no alias is fabricated for an unresolved id.
    """
    record = CanonicalMemoryRecord(
        memory_id=source_id,
        memory_type=MEMORY_TYPE_FOUNDATION,
        content=dict(content),
        source={"source_type": SOURCE_TYPE_PHASE2_UMR, "reference_id": source_id},
        parent_ids=(),
        creation_event=f"{ingestion_label}-{source_id}",
        creation_timestamp=datetime.now(timezone.utc).isoformat(),
        lifecycle_state=LIFECYCLE_CREATED,
    )
    result = write_canonical_memory(memory_ledger, record, foundation=None)
    if foundation_memory_id is not None:
        memory_ledger.set_alias(source_id, FOUNDATION_NAME_AMEM, foundation_memory_id)
    return result


def record_retrieval_and_selection_events_direct_assignment(
    event_ledger: CanonicalEventLedger,
    memory_ledger: CanonicalMemoryLedger,
    *,
    task_id: str,
    config_fingerprint: str,
    timestamp: str,
    retrieved_canonical_ids: Sequence[str],
    selected_canonical_ids: Sequence[str],
    retrieved_reason: str = REASON_RETRIEVED_C,
    selected_reason: str = REASON_SELECTED_C,
) -> RetrievalEventReport:
    """Condition C (A-MEM) sibling of `record_retrieval_and_selection_events()`.

    `retrieved_canonical_ids`/`selected_canonical_ids` are ALREADY canonical source ids
    (per `STRATEGY_DIRECT_ASSIGNMENT` -- no `resolve_source_identities()` call here, unlike
    the Condition-B version, since there is nothing to resolve). An id not present in
    `memory_ledger` (should not happen given Condition C only ever ingests through this
    pool's own `write_canonical_record_and_alias_direct_assignment()` calls, but never
    assumed) is reported in `not_in_canonical_ledger`, never silently dropped.
    """
    report = RetrievalEventReport(task_id=task_id)
    selected_set = set(selected_canonical_ids)

    for canonical_id in retrieved_canonical_ids:
        if not memory_ledger.exists(canonical_id):
            report.not_in_canonical_ledger.append(canonical_id)
            continue

        retrieved_event = CanonicalEvent(
            event_id=f"retrieved-{task_id}-{canonical_id}",
            event_type=EVENT_RETRIEVED,
            memory_ids=(canonical_id,),
            task_id=task_id,
            timestamp=timestamp,
            actor="candidate_discovery",
            reason=retrieved_reason,
            config_fingerprint=config_fingerprint,
            foundation_name=FOUNDATION_NAME_AMEM,
            foundation_memory_id=canonical_id,
        )
        event_ledger.append(retrieved_event)
        report.retrieved_event_ids.append(retrieved_event.event_id)

        if canonical_id in selected_set:
            selected_event = CanonicalEvent(
                event_id=f"selected-{task_id}-{canonical_id}",
                event_type=EVENT_SELECTED,
                memory_ids=(canonical_id,),
                task_id=task_id,
                timestamp=timestamp,
                actor="evidence_selection",
                reason=selected_reason,
                config_fingerprint=config_fingerprint,
                foundation_name=FOUNDATION_NAME_AMEM,
                foundation_memory_id=canonical_id,
            )
            event_ledger.append(selected_event)
            report.selected_event_ids.append(selected_event.event_id)
        else:
            rejected_event = CanonicalEvent(
                event_id=f"rejected-{task_id}-{canonical_id}",
                event_type=EVENT_REJECTED,
                memory_ids=(canonical_id,),
                task_id=task_id,
                timestamp=timestamp,
                actor="evidence_selection",
                reason=REJECTED_REASON_CAPACITY_CUT,
            )
            event_ledger.append(rejected_event)
            report.rejected_event_ids.append(rejected_event.event_id)

    return report


__all__ = [
    "FOUNDATION_NAME_MEM0",
    "FOUNDATION_NAME_AMEM",
    "EMBEDDING_MODEL_REVISION_UNPINNED",
    "RETRIEVAL_MECHANISM_MEM0_DENSE",
    "RETRIEVAL_MECHANISM_AMEM_DENSE",
    "SELECTION_MECHANISM_TOP_K_SLICE",
    "canonical_store_dir_for_pool",
    "PoolCanonicalLedgers",
    "open_pool_canonical_ledgers",
    "write_ingested_canonical_memory",
    "write_canonical_record_and_alias_direct_assignment",
    "RetrievalEventReport",
    "record_retrieval_and_selection_events",
    "record_retrieval_and_selection_events_direct_assignment",
]
