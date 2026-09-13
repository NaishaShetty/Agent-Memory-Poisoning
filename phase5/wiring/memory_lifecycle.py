"""Phase 5.4 -- Memory Lifecycle Instrumentation.

WHAT EXISTS ALREADY
--------------------------------------------------------------------------------
- `canonical_write.write_canonical_memory()` -- the real, tested, authoritative write
  path (canonical record -> ledger -> foundation -> alias). Reused verbatim below.
- `event_identity.build_canonical_event()` -- mints an `event_id` and constructs a
  `CanonicalEvent` in one call. Reused verbatim below for `created`/`derived` events.
- `memory_versioning.supersede_memory()` -- H.3's authoritative supersession mechanism
  (writes `superseded` then `retired` `CanonicalEvent`s plus a `SupersessionRecord`).
  Reused verbatim below.
- `canonical_wiring.py` -- proves this exact pattern (build events, call the existing
  mechanism, do not reinvent it) already works for Phase 3's Condition B (Mem0) campaign
  path. This module generalizes the same pattern to be attack-agnostic and available to
  Phase 4, not a replacement of `canonical_wiring.py`.

THE GAP THIS MODULE CLOSES
--------------------------------------------------------------------------------
The audit's single most load-bearing finding: "no wiring between Phase 4 attack
campaigns and the Phase 3 ledgers at all." Every real attack campaign writes memories via
bare `foundation.add_memory()`; none call `write_canonical_memory()`; no `created`
`CanonicalEvent` is ever appended for an attack-injected memory. This module provides the
common (per Section 18 of the master prompt: "instrumentation must be common across all
seven attacks") entry points a campaign script can call, in addition to (never instead
of) its own existing `add_memory()`/injector call, to close that gap -- without editing
any of the 7 attacks' own injector code, and without editing any frozen Phase 3 file.

WHY THIS TAKES NORMALIZED KEYWORD ARGUMENTS, NOT AN ATTACK'S OWN RESULT DATACLASS
--------------------------------------------------------------------------------
The audit found each attack's injection result is a differently-shaped dataclass
(`FARMAInjectionResult.artifact_id` vs AgentPoison's `poison_id` vs MINJA's `step_id`,
etc.). A function that branched on `isinstance(result, FARMAInjectionResult)` etc. would
itself be attack-specific instrumentation -- exactly what Section 18 forbids. Instead,
`record_memory_creation()`'s `attack_context` parameter takes an already-normalized
mapping (`attack_id`, `injection_id`, `artifact_id`, `admission_status`) -- extracting an
attack's own field names into this common shape is a one-line adaptation left to each
attack's own (future) call site, not logic living inside the shared instrumentation.

WRITE ORDER (mirrors the existing ledgers' own "authoritative write order" discipline)
--------------------------------------------------------------------------------
1. `write_canonical_memory()` -- the memory must exist in `CanonicalMemoryLedger` before
   any event can reference it (`CanonicalEventLedger.append()` enforces this already).
2. Append the `created` (or `derived`) `CanonicalEvent`.
3. Register `EventRunMembership` for that `CanonicalEvent`'s `event_id`.
4. Only if `attack_context` is given: append an `attack_injection` `Phase5Event` and
   register its own membership too. Steps 1-3 happen unconditionally (a non-attacker
   memory has its lifecycle instrumented identically) -- attack instrumentation is
   additive on top, never a fork in the memory-lifecycle path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from phase3.evaluation.foundations.adapter import MemoryFoundationAdapter
from phase3.evaluation.foundations.canonical import CanonicalMemoryRecord, LIFECYCLE_CREATED, MEMORY_TYPE_DERIVED
from phase3.evaluation.foundations.canonical_event import CanonicalEvent, EVENT_CREATED, EVENT_DERIVED
from phase3.evaluation.foundations.canonical_write import CanonicalWriteResult, write_canonical_memory
from phase3.evaluation.foundations.event_identity import build_canonical_event
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase3.evaluation.foundations.memory_versioning import (
    SupersessionLedger,
    SupersessionResult,
    supersede_memory,
)
from phase5.identity.run_identity import EVENT_SCHEMA_CANONICAL_EVENT, EVENT_SCHEMA_PHASE5_EVENT, EventRunMembership, EventRunMembershipLedger
from phase5.schema.event import ADMISSION_STATUS_ADMITTED, ATTACK_INJECTION, Phase5Event, generate_phase5_event_id
from phase5.schema.event_ledger import Phase5EventLedger


@dataclass(frozen=True)
class MemoryCreationInstrumentationResult:
    """Everything Stage 5.4 recorded for one `record_memory_creation()` call, so a caller
    (or a test) can inspect what actually happened without re-querying every ledger."""

    write_result: CanonicalWriteResult
    created_event: CanonicalEvent
    attack_injection_event: Optional[Phase5Event] = None


def record_attack_injection(
    *,
    phase5_event_ledger: Phase5EventLedger,
    membership_ledger: EventRunMembershipLedger,
    run_id: str,
    attack_id: str,
    injection_id: str,
    artifact_id: str,
    admission_status: str,
    actor: str,
    reason: str,
    timestamp: str,
    memory_id: Optional[str] = None,
    episode_id: Optional[str] = None,
) -> Phase5Event:
    """Instrument one attack injection ATTEMPT (contract OR-11), independently of
    whether it resulted in a memory (`memory_id` is `None` for a rejected/failed
    admission). This is the ONE shared recording path every attack's injection outcome
    must go through -- it takes only normalized, generic keyword arguments (never an
    attack's own result dataclass), so no attack-specific branching exists here or in any
    caller of this function (see `phase5.wiring.attack_integration` for the
    per-attack field-mapping layer that produces these arguments).

    Called unconditionally for EVERY injection attempt, admitted or not -- a rejected
    artifact is exactly as important to Phase 5's evidence trail as an admitted one (an
    attack that is rejected 100% of the time is itself a real, citable finding), so this
    function is never skipped for the rejected case.
    """
    if admission_status == ADMISSION_STATUS_ADMITTED:
        if not (isinstance(memory_id, str) and memory_id):
            raise ValueError("memory_id is required (non-empty) when admission_status='ADMITTED'.")
    else:
        if memory_id is not None:
            raise ValueError("memory_id must be None when admission_status is not 'ADMITTED' -- nothing was created to reference.")

    injection_kwargs = dict(
        event_type=ATTACK_INJECTION,
        timestamp=timestamp,
        actor=actor,
        reason=reason,
        attack_id=attack_id,
        injection_id=injection_id,
        artifact_id=artifact_id,
        admission_status=admission_status,
        memory_id=memory_id,
    )
    event_id = generate_phase5_event_id(**injection_kwargs)
    event = Phase5Event(event_id=event_id, **injection_kwargs)
    phase5_event_ledger.append(event)
    membership_ledger.append(
        EventRunMembership(
            event_id=event.event_id,
            event_schema=EVENT_SCHEMA_PHASE5_EVENT,
            run_id=run_id,
            episode_id=episode_id,
            recorded_at=timestamp,
        )
    )
    return event


def record_memory_creation(
    *,
    memory_ledger: CanonicalMemoryLedger,
    event_ledger: CanonicalEventLedger,
    membership_ledger: EventRunMembershipLedger,
    run_id: str,
    record: CanonicalMemoryRecord,
    actor: str,
    reason: str,
    timestamp: str,
    episode_id: Optional[str] = None,
    foundation: Optional[MemoryFoundationAdapter] = None,
    foundation_name: Optional[str] = None,
    metadata_extra: Optional[Mapping[str, Any]] = None,
    attack_context: Optional[Mapping[str, Any]] = None,
    phase5_event_ledger: Optional[Phase5EventLedger] = None,
) -> MemoryCreationInstrumentationResult:
    """Instrument one memory creation (contract OR-1), optionally also recording the
    attack injection that produced it (contract OR-11) via `record_attack_injection()`.

    `attack_context`, when given, must supply `attack_id`, `injection_id`, `artifact_id`,
    `admission_status` (see `phase5.schema.event` for the two conventional values) --
    and `phase5_event_ledger` must then also be given. This path only ever covers the
    ADMITTED case (a memory to create implies admission); a REJECTED injection attempt is
    never accompanied by a `record`, so it must be recorded directly via
    `record_attack_injection()` instead -- this function does not attempt to also cover
    that case, to keep the "record the memory" and "record the injection attempt"
    concerns independent, per contract OR-11's own requirement.
    """
    write_result = write_canonical_memory(
        memory_ledger, record, foundation=foundation, foundation_name=foundation_name, metadata_extra=metadata_extra,
    )

    created_event = build_canonical_event(
        EVENT_CREATED,
        memory_ids=(record.memory_id,),
        timestamp=timestamp,
        actor=actor,
        reason=reason,
        new_state=LIFECYCLE_CREATED,
    )
    event_ledger.append(created_event)
    membership_ledger.append(
        EventRunMembership(
            event_id=created_event.event_id,
            event_schema=EVENT_SCHEMA_CANONICAL_EVENT,
            run_id=run_id,
            episode_id=episode_id,
            recorded_at=timestamp,
        )
    )

    attack_injection_event: Optional[Phase5Event] = None
    if attack_context is not None:
        if phase5_event_ledger is None:
            raise ValueError("phase5_event_ledger is required when attack_context is given.")
        if attack_context["admission_status"] != ADMISSION_STATUS_ADMITTED:
            raise ValueError(
                "record_memory_creation()'s attack_context path requires admission_status="
                f"{ADMISSION_STATUS_ADMITTED!r} (a memory was created) -- got "
                f"{attack_context['admission_status']!r}. A rejected/failed injection has no "
                "memory to create; call record_attack_injection() directly for that case."
            )
        attack_injection_event = record_attack_injection(
            phase5_event_ledger=phase5_event_ledger,
            membership_ledger=membership_ledger,
            run_id=run_id,
            attack_id=attack_context["attack_id"],
            injection_id=attack_context["injection_id"],
            artifact_id=attack_context["artifact_id"],
            admission_status=attack_context["admission_status"],
            actor=actor,
            reason=reason,
            timestamp=timestamp,
            memory_id=record.memory_id,
            episode_id=episode_id,
        )

    return MemoryCreationInstrumentationResult(
        write_result=write_result, created_event=created_event, attack_injection_event=attack_injection_event,
    )


def record_memory_derivation(
    *,
    memory_ledger: CanonicalMemoryLedger,
    event_ledger: CanonicalEventLedger,
    membership_ledger: EventRunMembershipLedger,
    run_id: str,
    derived_record: CanonicalMemoryRecord,
    source_memory_ids: tuple,
    actor: str,
    reason: str,
    timestamp: str,
    episode_id: Optional[str] = None,
    foundation: Optional[MemoryFoundationAdapter] = None,
    foundation_name: Optional[str] = None,
    metadata_extra: Optional[Mapping[str, Any]] = None,
) -> MemoryCreationInstrumentationResult:
    """Instrument a memory derivation (contract OR-5): one or more existing memories
    (`source_memory_ids`) produce a new one (`derived_record`, `memory_type='derived'`).
    Write order matches `record_memory_creation()`: the derived memory must exist before
    the `derived` event referencing it can be appended."""
    if derived_record.memory_type != MEMORY_TYPE_DERIVED:
        raise ValueError(f"derived_record.memory_type must be {MEMORY_TYPE_DERIVED!r}, got {derived_record.memory_type!r}.")

    write_result = write_canonical_memory(
        memory_ledger, derived_record, foundation=foundation, foundation_name=foundation_name, metadata_extra=metadata_extra,
    )

    derived_event = build_canonical_event(
        EVENT_DERIVED,
        memory_ids=tuple(source_memory_ids) + (derived_record.memory_id,),
        timestamp=timestamp,
        actor=actor,
        reason=reason,
        source_memory_ids=tuple(source_memory_ids),
        target_memory_id=derived_record.memory_id,
    )
    event_ledger.append(derived_event)
    membership_ledger.append(
        EventRunMembership(
            event_id=derived_event.event_id,
            event_schema=EVENT_SCHEMA_CANONICAL_EVENT,
            run_id=run_id,
            episode_id=episode_id,
            recorded_at=timestamp,
        )
    )
    return MemoryCreationInstrumentationResult(write_result=write_result, created_event=derived_event)


def record_memory_lifecycle_transition(
    *,
    event_ledger: CanonicalEventLedger,
    memory_ledger: CanonicalMemoryLedger,
    supersession_ledger: SupersessionLedger,
    membership_ledger: EventRunMembershipLedger,
    run_id: str,
    superseded_memory_id: str,
    superseding_memory_id: str,
    superseded_event: CanonicalEvent,
    retired_event: CanonicalEvent,
    episode_id: Optional[str] = None,
) -> SupersessionResult:
    """Instrument a supersession/retirement (contract OR-2). A thin wrapper: constructs
    no new mechanism, calls `memory_versioning.supersede_memory()` verbatim, and
    registers membership for whichever event ids it reports as actually appended
    (an honest partial result is possible per that function's own documented write-order
    semantics -- this wrapper never assumes both events succeeded)."""
    result = supersede_memory(
        event_ledger, memory_ledger, supersession_ledger, superseded_memory_id, superseding_memory_id,
        superseded_event=superseded_event, retired_event=retired_event,
    )
    if result.superseded_event_id is not None:
        membership_ledger.append(
            EventRunMembership(
                event_id=result.superseded_event_id,
                event_schema=EVENT_SCHEMA_CANONICAL_EVENT,
                run_id=run_id,
                episode_id=episode_id,
                recorded_at=superseded_event.timestamp,
            )
        )
    if result.retired_event_id is not None:
        membership_ledger.append(
            EventRunMembership(
                event_id=result.retired_event_id,
                event_schema=EVENT_SCHEMA_CANONICAL_EVENT,
                run_id=run_id,
                episode_id=episode_id,
                recorded_at=retired_event.timestamp,
            )
        )
    return result


__all__ = [
    "MemoryCreationInstrumentationResult",
    "record_attack_injection",
    "record_memory_creation",
    "record_memory_derivation",
    "record_memory_lifecycle_transition",
]
