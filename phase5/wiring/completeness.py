"""Phase 5.4 (fix) -- completeness verification for memory-lifecycle and attack-injection
instrumentation.

WHY THIS MODULE EXISTS
--------------------------------------------------------------------------------
`record_memory_creation()`/`record_attack_injection()` (`memory_lifecycle.py`) each make
several sequential writes across independent ledgers (`CanonicalMemoryLedger` ->
`CanonicalEventLedger` -> `EventRunMembershipLedger`, or `Phase5EventLedger` ->
`EventRunMembershipLedger`). Every individual ledger in this framework already fails
loudly on a bad write (collision, unknown-reference) -- that discipline is inherited
unchanged, and this module does not redesign it or attempt to make the multi-ledger
sequence transactional/atomic (no new commit/rollback mechanism is introduced; per
`ledger.py`'s own documented limitation, "no cross-process file lock," this framework has
never claimed atomicity across separate JSONL files, and this fix does not start now).

What was genuinely missing: a caller (a human reviewer, a Stage 5.9 validation pass, or a
Stage 5.8 trace assembler) had no cheap, direct way to ask "did instrumentation of THIS
particular memory/injection actually complete, or did something abort partway through
after already writing SOME of its records?" -- e.g. an exception in
`membership_ledger.append()` (say, `UnknownRunError` from a caller-supplied bad `run_id`)
raised AFTER `event_ledger.append()` already durably committed the `created` event, per
each ledger's own fsync-per-write discipline, leaves that event durably orphaned (no
membership record) with nothing that would otherwise notice. This module makes that
detectable by direct query, so an incomplete sequence can never be silently mistaken for
a complete one by a later reader that only checks "does the memory exist."

THIS IS OBSERVATION, NOT REPAIR
--------------------------------------------------------------------------------
Every function here is read-only: it queries existing ledgers and reports what it finds.
None of them repair, backfill, or retry a missing record -- consistent with this
framework's standing rule (`memory_versioning.supersede_memory()`'s own docstring:
"an HONEST partial state, reported via `status`, never a corrupted or silently-repaired
one").
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from phase3.evaluation.foundations.canonical_event import EVENT_CREATED, EVENT_DERIVED, EVENT_RETIRED, EVENT_SUPERSEDED
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase3.evaluation.foundations.memory_versioning import SupersessionLedger

from phase5.identity.run_identity import EventRunMembershipLedger
from phase5.schema.event import ATTACK_INJECTION
from phase5.schema.event_ledger import Phase5EventLedger

_CREATION_EVENT_TYPES: Tuple[str, ...] = (EVENT_CREATED, EVENT_DERIVED)


@dataclass(frozen=True)
class MemoryCreationCompleteness:
    """Every stage `record_memory_creation()`/`record_memory_derivation()` is supposed to
    have completed for `memory_id`, checked independently against each ledger's own
    current state -- never inferred from a cached in-process result object, so this
    catches a genuinely partial on-disk state even if the process that caused it already
    exited.

    Despite the name, this ALSO covers memory derivation (contract OR-5), not only
    foundation-origin creation: `_CREATION_EVENT_TYPES` includes both `created` and
    `derived`, so a derived memory produced by `record_memory_derivation()` is checked by
    this exact same function, using `derived_record.memory_id` as `memory_id`. No
    separate "derivation completeness" type was introduced -- both share the identical
    "does this memory exist, does it have the one creation-type event a memory is
    supposed to have, is that event's membership recorded" shape.
    """

    memory_id: str
    run_id: str
    memory_exists: bool
    creation_event_id: Optional[str]
    creation_event_recorded: bool
    membership_recorded: bool
    membership_run_id_matches: bool

    @property
    def is_complete(self) -> bool:
        return self.memory_exists and self.creation_event_recorded and self.membership_recorded and self.membership_run_id_matches

    def missing_stages(self) -> Tuple[str, ...]:
        missing = []
        if not self.memory_exists:
            missing.append("memory_not_in_canonical_memory_ledger")
        if not self.creation_event_recorded:
            missing.append("no_created_or_derived_event_in_canonical_event_ledger")
        if self.creation_event_recorded and not self.membership_recorded:
            missing.append("creation_event_has_no_run_membership")
        if self.membership_recorded and not self.membership_run_id_matches:
            missing.append("membership_recorded_under_a_different_run_id")
        return tuple(missing)


def check_memory_creation_completeness(
    *,
    memory_ledger: CanonicalMemoryLedger,
    event_ledger: CanonicalEventLedger,
    membership_ledger: EventRunMembershipLedger,
    memory_id: str,
    run_id: str,
) -> MemoryCreationCompleteness:
    memory_exists = memory_ledger.exists(memory_id)

    creation_events = tuple(
        e for e in event_ledger.events_for_memory(memory_id) if e.event_type in _CREATION_EVENT_TYPES
    )
    creation_event_id = creation_events[0].event_id if creation_events else None
    creation_event_recorded = creation_event_id is not None

    membership_recorded = False
    membership_run_id_matches = False
    if creation_event_id is not None:
        membership = membership_ledger.run_for_event(creation_event_id)
        membership_recorded = membership is not None
        if membership is not None:
            membership_run_id_matches = membership.run_id == run_id

    return MemoryCreationCompleteness(
        memory_id=memory_id,
        run_id=run_id,
        memory_exists=memory_exists,
        creation_event_id=creation_event_id,
        creation_event_recorded=creation_event_recorded,
        membership_recorded=membership_recorded,
        membership_run_id_matches=membership_run_id_matches,
    )


@dataclass(frozen=True)
class AttackInjectionCompleteness:
    """Every stage `record_attack_injection()` is supposed to have completed for
    `injection_id`."""

    injection_id: str
    run_id: str
    injection_event_id: Optional[str]
    injection_event_recorded: bool
    membership_recorded: bool
    membership_run_id_matches: bool

    @property
    def is_complete(self) -> bool:
        return self.injection_event_recorded and self.membership_recorded and self.membership_run_id_matches

    def missing_stages(self) -> Tuple[str, ...]:
        missing = []
        if not self.injection_event_recorded:
            missing.append("no_attack_injection_event_in_phase5_event_ledger")
        if self.injection_event_recorded and not self.membership_recorded:
            missing.append("injection_event_has_no_run_membership")
        if self.membership_recorded and not self.membership_run_id_matches:
            missing.append("membership_recorded_under_a_different_run_id")
        return tuple(missing)


def check_attack_injection_completeness(
    *,
    phase5_event_ledger: Phase5EventLedger,
    membership_ledger: EventRunMembershipLedger,
    injection_id: str,
    run_id: str,
) -> AttackInjectionCompleteness:
    matches = tuple(
        e for e in phase5_event_ledger.all_events()
        if e.event_type == ATTACK_INJECTION and e.injection_id == injection_id
    )
    injection_event_id = matches[0].event_id if matches else None
    injection_event_recorded = injection_event_id is not None

    membership_recorded = False
    membership_run_id_matches = False
    if injection_event_id is not None:
        membership = membership_ledger.run_for_event(injection_event_id)
        membership_recorded = membership is not None
        if membership is not None:
            membership_run_id_matches = membership.run_id == run_id

    return AttackInjectionCompleteness(
        injection_id=injection_id,
        run_id=run_id,
        injection_event_id=injection_event_id,
        injection_event_recorded=injection_event_recorded,
        membership_recorded=membership_recorded,
        membership_run_id_matches=membership_run_id_matches,
    )


@dataclass(frozen=True)
class MemorySupersessionCompleteness:
    """Every stage `record_memory_lifecycle_transition()` (a thin wrapper over
    `memory_versioning.supersede_memory()`) is supposed to have completed for one
    supersession fact: A supersede-and-retire event pair for the SUPERSEDED memory, plus
    the `SupersessionRecord` linking it to its superseder, plus membership for both
    events. `supersede_memory()`'s own docstring already documents that its three writes
    are not claimed atomic ("an HONEST partial state ... never a corrupted or
    silently-repaired one") -- this checker makes that honest partial state queryable
    directly, rather than requiring a caller to re-read `supersede_memory()`'s own
    `SupersessionResult.status` (which is only available to whoever made the original
    call, not to a later, independent reader)."""

    superseded_memory_id: str
    superseding_memory_id: str
    run_id: str
    superseded_event_id: Optional[str]
    superseded_event_recorded: bool
    superseded_event_membership_recorded: bool
    retired_event_id: Optional[str]
    retired_event_recorded: bool
    retired_event_membership_recorded: bool
    supersession_record_linked: bool

    @property
    def is_complete(self) -> bool:
        return (
            self.superseded_event_recorded
            and self.superseded_event_membership_recorded
            and self.retired_event_recorded
            and self.retired_event_membership_recorded
            and self.supersession_record_linked
        )

    def missing_stages(self) -> Tuple[str, ...]:
        missing = []
        if not self.superseded_event_recorded:
            missing.append("no_superseded_event_in_canonical_event_ledger")
        if self.superseded_event_recorded and not self.superseded_event_membership_recorded:
            missing.append("superseded_event_has_no_run_membership")
        if not self.supersession_record_linked:
            missing.append("no_supersession_record_linking_superseded_to_superseding")
        if not self.retired_event_recorded:
            missing.append("no_retired_event_in_canonical_event_ledger")
        if self.retired_event_recorded and not self.retired_event_membership_recorded:
            missing.append("retired_event_has_no_run_membership")
        return tuple(missing)


def check_memory_supersession_completeness(
    *,
    event_ledger: CanonicalEventLedger,
    supersession_ledger: SupersessionLedger,
    membership_ledger: EventRunMembershipLedger,
    superseded_memory_id: str,
    superseding_memory_id: str,
    run_id: str,
) -> MemorySupersessionCompleteness:
    superseded_events = tuple(
        e for e in event_ledger.events_for_memory(superseded_memory_id) if e.event_type == EVENT_SUPERSEDED
    )
    superseded_event_id = superseded_events[0].event_id if superseded_events else None
    superseded_event_recorded = superseded_event_id is not None
    superseded_membership = membership_ledger.run_for_event(superseded_event_id) if superseded_event_id else None
    superseded_event_membership_recorded = superseded_membership is not None and superseded_membership.run_id == run_id

    retired_events = tuple(
        e for e in event_ledger.events_for_memory(superseded_memory_id) if e.event_type == EVENT_RETIRED
    )
    retired_event_id = retired_events[0].event_id if retired_events else None
    retired_event_recorded = retired_event_id is not None
    retired_membership = membership_ledger.run_for_event(retired_event_id) if retired_event_id else None
    retired_event_membership_recorded = retired_membership is not None and retired_membership.run_id == run_id

    supersession_record_linked = supersession_ledger.superseder_of(superseded_memory_id) == superseding_memory_id

    return MemorySupersessionCompleteness(
        superseded_memory_id=superseded_memory_id,
        superseding_memory_id=superseding_memory_id,
        run_id=run_id,
        superseded_event_id=superseded_event_id,
        superseded_event_recorded=superseded_event_recorded,
        superseded_event_membership_recorded=superseded_event_membership_recorded,
        retired_event_id=retired_event_id,
        retired_event_recorded=retired_event_recorded,
        retired_event_membership_recorded=retired_event_membership_recorded,
        supersession_record_linked=supersession_record_linked,
    )


__all__ = [
    "MemoryCreationCompleteness",
    "check_memory_creation_completeness",
    "AttackInjectionCompleteness",
    "check_attack_injection_completeness",
    "MemorySupersessionCompleteness",
    "check_memory_supersession_completeness",
]
