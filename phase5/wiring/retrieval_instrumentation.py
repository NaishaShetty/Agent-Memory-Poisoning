"""Phase 5.5 -- Retrieval & Selection Instrumentation.

WHAT EXISTS ALREADY
--------------------------------------------------------------------------------
- `hybrid_selection.select_by_hybrid_score()` -- the real, frozen Phase 3 selection
  mechanism every Phase 4 attack's `campaign_runner.retrieve_select_generate()` call
  already uses. Computes a `HybridScoredCandidate` (cosine/token-overlap/entity-overlap/
  blended score) for EVERY candidate in the pool, selected or not, returned as
  `HybridSelectionResult(selected, rejected, top_k, weights)`.
- `phase4/shared/campaign_runner.py::retrieve_select_generate()` -- the real, frozen
  Phase 4 shared pipeline (`foundation.retrieve()` -> `select_by_hybrid_score()` ->
  `build_agent_visible_context()` -> `render_messages()` -> `generate_with_retries()`).
  Confirmed by direct read: it reduces `sel.selected` to bare `(memory_id, content)`
  pairs and never touches `sel.rejected` at all -- this is the exact, audited gap this
  stage closes (contract OR-6).
- `canonical_wiring.py::record_retrieval_and_selection_events()` -- real, working
  precedent for constructing `retrieved`/`selected`/`rejected` `CanonicalEvent`s, but
  scoped to Condition B (Mem0) and its vendor-id resolution step
  (`resolve_source_identities()`, `STRATEGY_METADATA_LOOKUP`) -- necessary there because
  Condition B's ingestion writes THROUGH `write_canonical_memory()`, whose foundation
  metadata carries the resolvable breadcrumb.

WHY THIS MODULE DOES NOT REUSE `resolve_source_identities()`
--------------------------------------------------------------------------------
Confirmed by reading `mocks/mock_mem0.py::MockMem0Adapter.add_memory()`/`retrieve()`:
when a caller supplies its own `memory_id` (which is exactly what every Phase 4 attack
injector does -- `foundation.add_memory(memory_id=<attack-chosen id>, ...)`), the mock
never reassigns a separate vendor-native id; `retrieve()`/`inspect_memory()` return that
SAME id back verbatim. This is the "DIRECT_ASSIGNMENT" case `canonical_wiring.py`'s own
module comment already names as the simpler sibling of Condition B's `METADATA_LOOKUP`
resolution case -- so for the mock-foundation instrumented runs this stage tests against
(the same class of validation Stage 5.4's `live_attack_runs.py` already established as
meaningful), the retrieved id already equals the canonical `memory_id`, and no resolution
step is needed or invented.

DISCLOSED LIMITATION: this reasoning does NOT necessarily hold against a REAL Mem0
backend, which may assign its own internal id independent of the `memory_id` a caller
supplies. This module does not claim to have solved that case -- it is out of scope here
exactly as it was out of scope for Condition C/A-MEM's DIRECT_ASSIGNMENT functions in
`canonical_wiring.py`. A future stage pointing this instrumentation at
`RealMem0Adapter`/`RealAMemAdapter` would need to add a resolution step analogous to
Condition B's, reusing `resolve_source_identities()` rather than inventing a second one.

HONEST ACCOUNTING, NOT SILENT DROPPING (mirrors `RetrievalEventReport`'s discipline)
--------------------------------------------------------------------------------
A retrieved candidate whose `memory_id` does not exist in `CanonicalMemoryLedger` (e.g.
an attack memory that was never wired through Stage 5.4's `record_memory_creation()`, or
a foundation-returned id this ledger simply doesn't know about) gets NO `retrieved`/
`selected`/`rejected` `CanonicalEvent` -- `CanonicalEventLedger.append()` would reject it
anyway (`UnknownCanonicalMemoryError`), so this module checks existence first.

CANONICAL-GAP STATE IS A DURABLE, MACHINE-CHECKABLE FACT, NOT JUST AN IN-PROCESS REPORT
FIELD (Stage 5.5 review fix, issue 2)
--------------------------------------------------------------------------------
`InstrumentedRetrievalReport.not_in_canonical_ledger` is a convenience for the immediate
caller, but it is an in-memory Python list -- gone the moment the calling process exits,
and no future reader (a human, or Stage 5.8's trace assembler) could reconstruct it from
the ledgers alone. The `RETRIEVAL_CANDIDATE_SCORED` `Phase5Event` (OR-6) -- which IS
persisted, for every scored candidate, regardless of canonical-ledger membership -- now
carries a required, closed `canonical_status` field
(`CANONICAL_STATUS_IN_LEDGER`/`CANONICAL_STATUS_NOT_IN_LEDGER`). This makes "this
candidate's canonical identity was never resolved" a THIRD, explicit, persisted state,
never to be inferred from the mere ABSENCE of a `retrieved`/`selected`/`rejected`
`CanonicalEvent` -- an absence which, without this field, could be misread as "this
candidate doesn't exist," "this candidate was rejected," or "this candidate was not
selected," none of which is what it actually means. Any future reader of
`Phase5EventLedger` (a human, a validation script, or Stage 5.8's trace assembler) can
distinguish all three states -- `selected`, `rejected` (both requiring
`canonical_status=IN_LEDGER`), and `NOT_IN_LEDGER` (which says nothing about
selected/rejected at all, since that decision was never wired into the canonical ledger
to begin with) -- directly from one persisted field, without needing to also cross-check
`CanonicalEventLedger` for an absence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Mapping, Optional, Sequence, Tuple

from phase3.evaluation.foundations.canonical_event import (
    EVENT_REJECTED,
    EVENT_RETRIEVED,
    EVENT_SELECTED,
    REJECTED_REASON_CAPACITY_CUT,
)
from phase3.evaluation.foundations.event_identity import build_canonical_event
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.hybrid_selection import DEFAULT_TOP_K, HybridSelectionResult, select_by_hybrid_score
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger

from phase5.identity.run_identity import EVENT_SCHEMA_CANONICAL_EVENT, EVENT_SCHEMA_PHASE5_EVENT, EventRunMembership, EventRunMembershipLedger
from phase5.schema.event import (
    CANONICAL_STATUS_IN_LEDGER,
    CANONICAL_STATUS_NOT_IN_LEDGER,
    CONTEXT_ASSEMBLED,
    RETRIEVAL_CANDIDATE_SCORED,
    Phase5Event,
    compute_rendered_context_fingerprint,
    generate_phase5_event_id,
)
from phase5.schema.event_ledger import Phase5EventLedger

REASON_RETRIEVED_HYBRID = "retrieved into the candidate pool via foundation.retrieve() ahead of hybrid scoring."
REASON_SELECTED_HYBRID = "selected into the agent-visible top-K by select_by_hybrid_score()'s blended-score ranking."


@dataclass
class InstrumentedRetrievalReport:
    """Honest, per-task accounting of what this instrumentation pass actually recorded --
    mirrors `canonical_wiring.RetrievalEventReport`'s "never silently drop" discipline."""

    task_id: str
    hybrid_result: HybridSelectionResult
    candidate_scored_events: List[Phase5Event] = field(default_factory=list)
    retrieved_event_ids: List[str] = field(default_factory=list)
    selected_event_ids: List[str] = field(default_factory=list)
    rejected_event_ids: List[str] = field(default_factory=list)
    not_in_canonical_ledger: List[str] = field(default_factory=list)


def instrument_retrieval_and_selection(
    *,
    memory_ledger: CanonicalMemoryLedger,
    event_ledger: CanonicalEventLedger,
    phase5_event_ledger: Phase5EventLedger,
    membership_ledger: EventRunMembershipLedger,
    run_id: str,
    task_id: str,
    query: str,
    candidates: Sequence[Tuple[str, str]],
    config_fingerprint: str,
    actor: str,
    timestamp: str,
    top_k: int = DEFAULT_TOP_K,
    episode_id: Optional[str] = None,
) -> InstrumentedRetrievalReport:
    """Runs the real, frozen `select_by_hybrid_score()` exactly once (never
    reimplemented), then instruments its full output -- every candidate's score (OR-6,
    `Phase5Event`), plus `retrieved`/`selected`/`rejected` `CanonicalEvent`s (OR-3/OR-4)
    for every candidate that resolves to a known canonical memory.

    `candidates` is the same `(memory_id, content)` pair sequence
    `campaign_runner.retrieve_select_generate()` already builds from
    `foundation.retrieve()` + `foundation.inspect_memory()` -- this function does not
    call the foundation itself, so it composes with that existing retrieval step rather
    than duplicating it.
    """
    sel = select_by_hybrid_score(query, candidates, top_k=top_k)
    report = InstrumentedRetrievalReport(task_id=task_id, hybrid_result=sel)

    # Rank is the candidate's position in blended-score order -- selected first (already
    # top_k, in descending order), then rejected (also already sorted descending by
    # select_by_hybrid_score's own sort) -- so a straight concatenation preserves the
    # true, full-pool rank ordering without this module re-sorting anything itself.
    ranked = sel.selected + sel.rejected
    selected_ids = {c.memory_id for c in sel.selected}

    for rank, candidate in enumerate(ranked, start=1):
        is_selected = candidate.memory_id in selected_ids
        is_in_ledger = memory_ledger.exists(candidate.memory_id)
        scored_kwargs = dict(
            event_type=RETRIEVAL_CANDIDATE_SCORED,
            timestamp=timestamp,
            actor=actor,
            reason="scored during hybrid selection over the full retrieval candidate pool.",
            task_id=task_id,
            config_fingerprint=config_fingerprint,
            memory_id=candidate.memory_id,
            candidate_rank=rank,
            cosine_score=candidate.cosine_score,
            token_overlap_score=candidate.token_overlap_score,
            entity_overlap_score=candidate.entity_overlap_score,
            blended_score=candidate.blended_score,
            selected=is_selected,
            canonical_status=CANONICAL_STATUS_IN_LEDGER if is_in_ledger else CANONICAL_STATUS_NOT_IN_LEDGER,
        )
        event_id = generate_phase5_event_id(**scored_kwargs)
        scored_event = Phase5Event(event_id=event_id, **scored_kwargs)
        phase5_event_ledger.append(scored_event)
        membership_ledger.append(
            EventRunMembership(
                event_id=scored_event.event_id, event_schema=EVENT_SCHEMA_PHASE5_EVENT,
                run_id=run_id, episode_id=episode_id, recorded_at=timestamp,
            )
        )
        report.candidate_scored_events.append(scored_event)

        if not is_in_ledger:
            report.not_in_canonical_ledger.append(candidate.memory_id)
            continue

        retrieved_event = build_canonical_event(
            EVENT_RETRIEVED, memory_ids=(candidate.memory_id,), timestamp=timestamp, actor=actor,
            reason=REASON_RETRIEVED_HYBRID, task_id=task_id, config_fingerprint=config_fingerprint,
        )
        event_ledger.append(retrieved_event)
        membership_ledger.append(
            EventRunMembership(
                event_id=retrieved_event.event_id, event_schema=EVENT_SCHEMA_CANONICAL_EVENT,
                run_id=run_id, episode_id=episode_id, recorded_at=timestamp,
            )
        )
        report.retrieved_event_ids.append(retrieved_event.event_id)

        if is_selected:
            selected_event = build_canonical_event(
                EVENT_SELECTED, memory_ids=(candidate.memory_id,), timestamp=timestamp, actor=actor,
                reason=REASON_SELECTED_HYBRID, task_id=task_id, config_fingerprint=config_fingerprint,
            )
            event_ledger.append(selected_event)
            membership_ledger.append(
                EventRunMembership(
                    event_id=selected_event.event_id, event_schema=EVENT_SCHEMA_CANONICAL_EVENT,
                    run_id=run_id, episode_id=episode_id, recorded_at=timestamp,
                )
            )
            report.selected_event_ids.append(selected_event.event_id)
        else:
            rejected_event = build_canonical_event(
                EVENT_REJECTED, memory_ids=(candidate.memory_id,), timestamp=timestamp, actor=actor,
                reason=REJECTED_REASON_CAPACITY_CUT, task_id=task_id,
            )
            event_ledger.append(rejected_event)
            membership_ledger.append(
                EventRunMembership(
                    event_id=rejected_event.event_id, event_schema=EVENT_SCHEMA_CANONICAL_EVENT,
                    run_id=run_id, episode_id=episode_id, recorded_at=timestamp,
                )
            )
            report.rejected_event_ids.append(rejected_event.event_id)

    return report


def record_context_assembly(
    *,
    phase5_event_ledger: Phase5EventLedger,
    membership_ledger: EventRunMembershipLedger,
    run_id: str,
    task_id: str,
    context_memory_ids: Tuple[str, ...],
    rendered_messages: Sequence[Mapping[str, str]],
    actor: str,
    reason: str,
    timestamp: str,
    episode_id: Optional[str] = None,
) -> Phase5Event:
    """Instruments the agent-visible context assembly step (contract OR-7).

    `rendered_messages` MUST be the ACTUAL output of `render_messages()` (or whichever
    real renderer a caller used) for this task -- not re-derived, not reconstructed from
    `context_memory_ids` after the fact. Persisting the literal rendered messages (not
    merely the memory ids that fed them) is the Stage 5.5 review fix for contract OR-7:
    "ensure the actual model-visible rendered context is deterministically
    reconstructable... do not rely only on memory IDs." `rendered_context_fingerprint`
    is computed here (via `compute_rendered_context_fingerprint()`) and re-verified by
    `Phase5Event.__post_init__` itself against a fresh recomputation -- an inconsistent
    caller input fails loudly, exactly like `RunConfigRecord`'s own supplied-fingerprint
    verification.

    `context_memory_ids` remains a required, separate field (not derived from
    `rendered_messages`) precisely because `render_messages()`'s own output is free-form
    prose (`"[{memory_id}] {content}"` lines) -- re-parsing memory ids back out of
    rendered text would be a second, fragile identity mechanism. The caller (who already
    has both the ordered list of selected memory ids AND the real rendered messages from
    the same `retrieve_select_generate()`-shaped pipeline step) supplies both, and this
    function does not attempt to derive one from the other.

    This event is deliberately separate from `selected` -- `selected_memory_ids` (top-K
    by score) and `exposed_memory_ids` (what actually reached `memory_items`) are the
    SAME set today in the current pipeline, but the contract treats "selected" and
    "agent-visible" as distinct claims -- this event preserves that distinction
    structurally even though it is not currently exercised by a divergence in the frozen
    pipeline.
    """
    if not context_memory_ids:
        raise ValueError("context_memory_ids must be non-empty -- contract OR-7 concerns actual agent-visible context, not an empty one.")
    if not rendered_messages:
        raise ValueError(
            "rendered_messages must be non-empty -- contract OR-7 requires the actual model-visible "
            "rendered context, not just memory ids."
        )
    rendered_messages_tuple = tuple(dict(m) for m in rendered_messages)
    kwargs = dict(
        event_type=CONTEXT_ASSEMBLED, timestamp=timestamp, actor=actor, reason=reason,
        task_id=task_id, context_memory_ids=tuple(context_memory_ids),
        rendered_messages=rendered_messages_tuple,
        rendered_context_fingerprint=compute_rendered_context_fingerprint(rendered_messages_tuple),
    )
    event_id = generate_phase5_event_id(**kwargs)
    event = Phase5Event(event_id=event_id, **kwargs)
    phase5_event_ledger.append(event)
    membership_ledger.append(
        EventRunMembership(
            event_id=event.event_id, event_schema=EVENT_SCHEMA_PHASE5_EVENT,
            run_id=run_id, episode_id=episode_id, recorded_at=timestamp,
        )
    )
    return event


__all__ = [
    "REASON_RETRIEVED_HYBRID",
    "REASON_SELECTED_HYBRID",
    "InstrumentedRetrievalReport",
    "instrument_retrieval_and_selection",
    "record_context_assembly",
]
