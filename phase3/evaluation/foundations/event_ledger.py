"""Phase 3.3-H.2 (Canonical Event Ledger) -- `CanonicalEventLedger`, the benchmark-owned,
append-only, foundation-independent history of `CanonicalEvent`s.

ARCHITECTURAL ROLE
--------------------------------------------------------------------------------
    CanonicalMemoryLedger  (H.1 -- "what is this memory?")
            +
    CanonicalEventLedger   (H.2 -- "what happened to this memory?")
            |
            v
    durable benchmark-owned history, independent of any vendor foundation

A `CanonicalEventLedger` is constructed WITH a `CanonicalMemoryLedger` (not merely
alongside one) specifically so `append()` can enforce "every memory-related event
references a canonical memory ID" (relationship_schema.md never mentions a forward-
reference allowance for an event pointing at a not-yet-created memory, so H.2 does not
invent one -- see `PHASE3_3_H2_CANONICAL_EVENT_LEDGER.md` section 5) without a second,
separate existence-check mechanism.

STORAGE MODEL
--------------------------------------------------------------------------------
One append-only JSONL file, `events.jsonl`, under `storage_dir` -- mirrors
`ledger.CanonicalMemoryLedger`'s exact persistence discipline (open in append mode, write
one already-fully-formed JSON line, flush, `os.fsync`). Rebuilding the in-memory index is a
pure, order-preserving fold over this file -- this is what makes "event ledger reload" and
"reconstruction without vendor availability" provable rather than assumed.

APPEND-ONLY / IMMUTABILITY -- BY OMISSION, NOT BY GUARD
--------------------------------------------------------------------------------
There is no `update_event()` or `delete_event()` method anywhere in this class, on
purpose: immutability here is enforced by the PUBLIC API's shape, not by a runtime check
a caller could route around. `test_canonical_event_ledger_h2.py` asserts this literal
absence (`not hasattr(ledger, "update_event")`, etc.) as a standing contract test, so a
future change that reintroduced either method would fail a test explaining why not to.

CONCURRENCY -- EXPLICIT LIMITATION (same model as H.1)
--------------------------------------------------------------------------------
Single-process, single-writer. No cross-process file lock. See `ledger.py`'s module
docstring for the full reasoning, which applies unchanged here: no caller adopts this
ledger in H.2 (it is purely additive infrastructure), so nothing exercises multi-process
contention against it yet.

DUPLICATE / COLLISION POLICY (mirrors H.1's ID COLLISION POLICY exactly)
--------------------------------------------------------------------------------
`append()` on an `event_id` already present: identical `CanonicalEvent.identity_fields()`
-> idempotent no-op (`APPEND_IDEMPOTENT`); different -> `CanonicalEventCollisionError`,
raised immediately, never caught internally, existing event left untouched.

EVENT IDENTITY SEMANTICS (Phase 3.3-H.2-R2)
--------------------------------------------------------------------------------
H.2-R2 formally resolves the question the review raised: "are two observations with
identical canonical event content the SAME historical event, or two DISTINCT ones?"

Decision: **identical canonical event content is the SAME historical fact.** This is not
an implementation convenience -- it follows from what a `CanonicalEvent` actually records.
Every field on it (`event_type`, `memory_ids`, `timestamp`, `actor`, `reason`, `task_id`,
state-transition fields, foundation alias, lineage roles) is part of the OBSERVATION
itself, not an incidental label. Two calls supplying the exact same values for every one
of those fields are, by definition, describing the same observation -- there is no
sixteenth field recording "which of two otherwise-identical occurrences was this," and
this module does not invent one. `event_identity.generate_event_id()`'s content-derived
design (H.2-R) directly encodes this decision: identical inputs -> identical id -> the
existing `APPEND_IDEMPOTENT` path.

This is verified NOT to erase real multiplicity: `retrieved`/`selected`/`used` events for
the SAME memory legitimately recur across DIFFERENT tasks (a different `task_id` is a real
difference in the recorded fact, producing a different fingerprint/id) or with a
genuinely different `reason`/`timestamp` (also real differences) -- multiplicity is
preserved exactly where the ontology allows it, and only truly field-for-field-identical
calls coalesce (tested directly: `test_h2_r2_hardening.py`'s "distinct observations"
tests).

SINGLE-OCCURRENCE EVENT TYPES (Phase 3.3-H.2-R2 -- new)
--------------------------------------------------------------------------------
Independent of the identity question above, a SEPARATE gap was found: nothing prevented
two DIFFERENT (non-idempotent) `created`/`superseded`/`retired`/`derived` events from being
appended for the very same memory -- e.g. two distinct "created" events (different
`event_id`s, because they differ in `timestamp` or `reason`) both claiming to be the origin
of memory M1. `memory_schema.json` models `creation_event`, `superseded_by`, and
`lifecycle_state` as SINGULAR per-memory fields -- a memory has exactly one creation
event, at most one superseder, and one current lifecycle state -- so two conflicting
"origin" or "terminal transition" facts for the same memory is a genuine data-integrity
violation, not a legitimate multiplicity case (unlike `retrieved`/`selected`/`used`, which
correctly may recur). `append()` now rejects a second, non-idempotent `created`/`derived`
event for a memory that already has one (the two types share one "creation slot", since a
memory is either `foundation`-created XOR `derived` -- never both, per
`memory_schema.json`'s `memory_type` enum), and separately rejects a second, non-idempotent
`superseded` or `retired` event per memory. This is event-ledger data-integrity
enforcement, not H.3 supersession POLICY: this module does not decide when a `superseded`
event should be emitted, only that at most one may exist once emitted.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from phase3.evaluation.foundations.canonical_event import (
    CanonicalEvent,
    EVENT_CREATED,
    EVENT_DERIVED,
    EVENT_REJECTED,
    EVENT_RELATIONSHIP_DETECTED,
    EVENT_RETIRED,
    EVENT_RETRIEVED,
    EVENT_SELECTED,
    EVENT_SUPERSEDED,
)
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase3.evaluation.foundations.run_config import RunConfigLedger

# Phase 3.3-H.4-F: only `retrieved`/`selected` events carry a `config_fingerprint` --
# mirrors canonical_event.py's own `_CONFIG_SCOPED_EVENT_TYPES` (not imported directly,
# since that name is module-private there; kept in sync by the same design decision this
# module already leans on for its other event-type groupings).
_CONFIG_SCOPED_EVENT_TYPES: Tuple[str, ...] = (EVENT_RETRIEVED, EVENT_SELECTED)

APPEND_CREATED = "CREATED"
APPEND_IDEMPOTENT = "IDEMPOTENT_NOOP"
APPEND_RESULTS: Tuple[str, ...] = (APPEND_CREATED, APPEND_IDEMPOTENT)

_EVENTS_FILE = "events.jsonl"

# Phase 3.3-H.2-R2: `created` and `derived` share one "creation slot" per resulting memory
# (a memory is either foundation-created XOR derived, never both -- memory_schema.json's
# `memory_type` enum). `superseded` and `retired` each own a separate single slot.
_CREATION_EVENT_TYPES: Tuple[str, ...] = (EVENT_CREATED, EVENT_DERIVED)


class CanonicalEventCollisionError(ValueError):
    """Raised when an `event_id` already present in the ledger is appended again with a
    different payload. Per H.2's duplicate-event policy: fail loudly, never overwrite."""


class UnknownCanonicalMemoryError(KeyError):
    """Raised when a `CanonicalEvent` references a `memory_id` that does not exist in the
    linked `CanonicalMemoryLedger`. relationship_schema.md states no forward-reference
    allowance for events, so this is rejected outright -- the event ledger must never
    become a second memory store by silently creating one."""


class UnknownConfigFingerprintError(KeyError):
    """Phase 3.3-H.4-F: raised when a `retrieved`/`selected` `CanonicalEvent` references a
    `config_fingerprint` that does not exist in the linked `RunConfigLedger` (when one is
    supplied). Mirrors `UnknownCanonicalMemoryError`'s exact role: a configuration record
    must exist (the run must have started) before any event referencing it can legitimately
    be appended -- this is checked eagerly, unlike `check_retrieval_resolution()`'s
    reconstruction-time check, because (unlike a selection decision) nothing about a
    configuration's existence depends on events that haven't happened yet."""


class SingleOccurrenceViolationError(ValueError):
    """Raised when a second, DIFFERENT (non-idempotent) `created`/`derived`/`superseded`/
    `retired` event is appended for a memory that already has one, or when a second,
    DIFFERENT `rejected` event is appended for the same `(memory_id, task_id)` pair. See
    module docstring "SINGLE-OCCURRENCE EVENT TYPES" section -- this enforces event-ledger
    data integrity, not H.3 supersession policy nor H.4-BC selection policy."""


class RetrievalResolutionViolation(ValueError):
    """Raised by `check_retrieval_resolution()` (Phase 3.3-H.4-BC) when a task's event
    history leaves a `retrieved` candidate with neither a `selected` nor a `rejected`
    event, or with both. This is a reconstruction-time consistency check, not an
    append()-time rejection -- `retrieved` necessarily precedes the eventual selection
    decision, so the invariant cannot be enforced eagerly at append time."""


def _append_jsonl(path: Path, obj: dict) -> None:
    line = json.dumps(obj, sort_keys=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
        fh.flush()
        os.fsync(fh.fileno())


class CanonicalEventLedger:
    """Benchmark-owned, append-only, foundation-independent event history.

    Every operation is scoped to `storage_dir`; two instances pointed at the same
    directory reconstruct identical in-memory state (event-ledger persistence/reload
    contract, mirroring `CanonicalMemoryLedger`'s).
    """

    def __init__(
        self,
        storage_dir: Union[str, Path],
        memory_ledger: CanonicalMemoryLedger,
        config_ledger: Optional[RunConfigLedger] = None,
    ) -> None:
        self._dir = Path(storage_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._events_path = self._dir / _EVENTS_FILE
        self._memory_ledger = memory_ledger
        # Phase 3.3-H.4-F: additive, optional. Every existing call site constructing
        # `CanonicalEventLedger(storage_dir, memory_ledger)` continues to work unmodified --
        # when omitted, `append()` skips the eager config_fingerprint-resolution check (see
        # `check_config_resolution()` for the deferred, reconstruction-time equivalent).
        self._config_ledger = config_ledger

        self._events_by_id: Dict[str, CanonicalEvent] = {}
        # Append order is the authoritative order -- a monotonically increasing sequence
        # number assigned at append time, distinct from (and never inferred from) the
        # event's own `timestamp` field. See module docstring "EVENT ORDERING" discussion
        # in the design doc for why timestamp ties are never used to invent an order.
        self._order: List[str] = []  # event_id, in append/persisted order

        self._load()

    # -- reconstruction from disk --------------------------------------------------------

    def _load(self) -> None:
        if not self._events_path.exists():
            return
        with open(self._events_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                event = CanonicalEvent.from_dict(json.loads(line))
                self._events_by_id[event.event_id] = event
                self._order.append(event.event_id)

    # -- append-only write ----------------------------------------------------------------

    def append(self, event: CanonicalEvent) -> str:
        """Append `event` to this ledger. Returns `APPEND_CREATED` or `APPEND_IDEMPOTENT`.

        Raises `UnknownCanonicalMemoryError` if any of `event.memory_ids` does not exist
        in the linked `CanonicalMemoryLedger` -- checked BEFORE any write, so a rejected
        append leaves no partial trace. Raises `UnknownConfigFingerprintError` (Phase
        3.3-H.4-F) if a `config_ledger` was supplied at construction and `event` is a
        `retrieved`/`selected` event whose `config_fingerprint` does not exist in it.
        Raises `CanonicalEventCollisionError` if `event.event_id` already exists with a
        different payload.
        """
        for memory_id in event.memory_ids:
            if not self._memory_ledger.exists(memory_id):
                raise UnknownCanonicalMemoryError(
                    f"event {event.event_id!r} references memory_id {memory_id!r}, which does "
                    "not exist in the linked CanonicalMemoryLedger. No forward reference is "
                    "permitted -- relationship_schema.md does not state one, and the event "
                    "ledger must never create a memory record as a side effect of recording "
                    "an event."
                )

        if (
            self._config_ledger is not None
            and event.event_type in _CONFIG_SCOPED_EVENT_TYPES
            and not self._config_ledger.exists(event.config_fingerprint)
        ):
            raise UnknownConfigFingerprintError(
                f"event {event.event_id!r} references config_fingerprint "
                f"{event.config_fingerprint!r}, which does not exist in the linked "
                "RunConfigLedger. A configuration record must exist before any event "
                "referencing it can legitimately be appended."
            )

        existing = self._events_by_id.get(event.event_id)
        if existing is not None:
            if existing.identity_fields() == event.identity_fields():
                return APPEND_IDEMPOTENT
            raise CanonicalEventCollisionError(
                f"event_id {event.event_id!r} already exists with a different payload -- "
                f"refusing to overwrite historical evidence. Existing={existing.to_dict()!r} "
                f"New={event.to_dict()!r}"
            )

        self._check_single_occurrence(event)

        self._events_by_id[event.event_id] = event
        self._order.append(event.event_id)
        _append_jsonl(self._events_path, event.to_dict())
        return APPEND_CREATED

    def _check_single_occurrence(self, event: CanonicalEvent) -> None:
        """Phase 3.3-H.2-R2: reject a second, non-idempotent `created`/`derived`/
        `superseded`/`retired` event for a memory that already has one of that slot. Only
        reached when `event.event_id` is genuinely new (the identical-event_id idempotency
        check above already handled the "same event appended twice" case) -- this guards
        the DIFFERENT case: a distinct event_id also claiming a single-occurrence fact.
        """
        if event.event_type in _CREATION_EVENT_TYPES:
            subject = event.memory_ids[0] if event.event_type == EVENT_CREATED else event.target_memory_id
            existing_creation = [
                e for e in self.events_for_memory(subject) if e.event_type in _CREATION_EVENT_TYPES
            ]
            if existing_creation:
                raise SingleOccurrenceViolationError(
                    f"memory {subject!r} already has a creation-type event "
                    f"({existing_creation[0].event_id!r}, type={existing_creation[0].event_type!r}); "
                    f"a memory has exactly one creation_event per memory_schema.json -- refusing to "
                    f"append a second, different one ({event.event_id!r}, type={event.event_type!r})."
                )
        elif event.event_type in (EVENT_SUPERSEDED, EVENT_RETIRED):
            subject = event.memory_ids[0]
            existing_same_type = [
                e for e in self.events_for_memory(subject) if e.event_type == event.event_type
            ]
            if existing_same_type:
                raise SingleOccurrenceViolationError(
                    f"memory {subject!r} already has a {event.event_type!r} event "
                    f"({existing_same_type[0].event_id!r}); memory_schema.json models "
                    f"{'superseded_by' if event.event_type == EVENT_SUPERSEDED else 'lifecycle_state=RETIRED'} "
                    f"as a singular per-memory fact -- refusing to append a second, different one "
                    f"({event.event_id!r})."
                )
        elif event.event_type == EVENT_REJECTED:
            # Phase 3.3-H.4-BC section 9: two `rejected` events for the same
            # (memory_id, task_id) pair with different `reason` values are a collision, not
            # a legitimate re-evaluation -- a candidate is rejected from a given task's
            # selection decision for exactly one reason.
            subject = event.memory_ids[0]
            existing_rejections = [
                e
                for e in self.events_for_memory(subject)
                if e.event_type == EVENT_REJECTED and e.task_id == event.task_id
            ]
            if existing_rejections:
                raise SingleOccurrenceViolationError(
                    f"memory {subject!r} already has a 'rejected' event "
                    f"({existing_rejections[0].event_id!r}) for task_id={event.task_id!r}; a candidate "
                    "is rejected from a given task's selection decision for exactly one reason -- "
                    f"refusing to append a second, different one ({event.event_id!r})."
                )

    # -- query API --------------------------------------------------------------------------

    def get_event(self, event_id: str) -> "CanonicalEvent | None":
        return self._events_by_id.get(event_id)

    def _ordered(self, event_ids) -> Tuple[CanonicalEvent, ...]:
        wanted = set(event_ids)
        return tuple(self._events_by_id[eid] for eid in self._order if eid in wanted)

    def events_for_memory(self, memory_id: str) -> Tuple[CanonicalEvent, ...]:
        """Every event referencing `memory_id`, in append (persisted) order. Reads only
        this ledger's own in-memory/on-disk state -- never consults a vendor foundation."""
        matching = (eid for eid, ev in self._events_by_id.items() if memory_id in ev.memory_ids)
        return self._ordered(matching)

    def events_for_task(self, task_id: str) -> Tuple[CanonicalEvent, ...]:
        matching = (eid for eid, ev in self._events_by_id.items() if ev.task_id == task_id)
        return self._ordered(matching)

    def events_for_foundation(self, foundation_name: str) -> Tuple[CanonicalEvent, ...]:
        matching = (eid for eid, ev in self._events_by_id.items() if ev.foundation_name == foundation_name)
        return self._ordered(matching)

    def reconstruct_memory_history(self, memory_id: str) -> Tuple[CanonicalEvent, ...]:
        """The mission's named "given canonical_memory_id, retrieve its complete canonical
        event history" operation. Identical to `events_for_memory()` -- kept as a
        separately-named entry point because the mission brief names it explicitly as the
        primary reconstruction capability this stage exists to provide; both names are
        supported so neither a caller reading the design doc nor one reading the query API
        section has to guess which name is authoritative."""
        return self.events_for_memory(memory_id)

    def all_events(self) -> Tuple[CanonicalEvent, ...]:
        """Every event in this ledger, in append/persisted order."""
        return tuple(self._events_by_id[eid] for eid in self._order)

    def events_for_relationship(self, memory_id_a: str, memory_id_b: str) -> Tuple[CanonicalEvent, ...]:
        """Phase 3.3-H.4-BC: every `relationship_detected` event concerning the unordered
        pair `{memory_id_a, memory_id_b}`, in append order. Order-independent on the
        caller's side (querying `(A, B)` or `(B, A)` returns the same events) even though a
        `superseded_by` event's own `memory_ids` field records a semantic order -- this
        query matches on set membership, not positional order."""
        wanted_pair = frozenset((memory_id_a, memory_id_b))
        matching = (
            eid
            for eid, ev in self._events_by_id.items()
            if ev.event_type == EVENT_RELATIONSHIP_DETECTED and frozenset(ev.memory_ids) == wanted_pair
        )
        return self._ordered(matching)

    # -- reconstruction-time consistency checks --------------------------------------------

    def check_retrieval_resolution(self, task_id: str) -> None:
        """Phase 3.3-H.4-BC section 8: for `task_id`'s complete event history, every
        `retrieved` candidate must eventually be paired with exactly one of a `selected` or
        a `rejected` event for the same `(memory_id, task_id)` pair -- never both, never
        neither. Raises `RetrievalResolutionViolation` listing every offending memory_id;
        returns `None` (no violation) otherwise.

        Deliberately NOT enforced inside `append()`: a `retrieved` event necessarily
        precedes the eventual selection decision, so at the moment a `retrieved` event is
        appended, no resolution can exist yet. This is a query a caller runs once a task's
        candidate-selection decision is believed complete.
        """
        task_events = self.events_for_task(task_id)
        retrieved_ids = {m for e in task_events if e.event_type == EVENT_RETRIEVED for m in e.memory_ids}
        selected_ids = {m for e in task_events if e.event_type == EVENT_SELECTED for m in e.memory_ids}
        rejected_ids = {m for e in task_events if e.event_type == EVENT_REJECTED for m in e.memory_ids}

        neither = retrieved_ids - selected_ids - rejected_ids
        both = retrieved_ids & selected_ids & rejected_ids
        if neither or both:
            problems = []
            if neither:
                problems.append(f"retrieved but neither selected nor rejected: {sorted(neither)!r}")
            if both:
                problems.append(f"both selected and rejected: {sorted(both)!r}")
            raise RetrievalResolutionViolation(
                f"task_id={task_id!r} has unresolved retrieved candidates -- {'; '.join(problems)}."
            )


def check_config_resolution(
    event_ledger: "CanonicalEventLedger", config_ledger: RunConfigLedger
) -> List[CanonicalEvent]:
    """Phase 3.3-H.4-F: deferred, reconstruction-time equivalent of `append()`'s eager
    `UnknownConfigFingerprintError` check -- for a caller that constructed `event_ledger`
    WITHOUT a `config_ledger` (so no eager check ran at append time), find every
    `retrieved`/`selected` event whose `config_fingerprint` does not resolve against
    `config_ledger`. Returns the list of offending events (empty if every one resolves);
    never raises on its own -- "the event is not considered reproducibly interpretable" is
    surfaced as data for the caller to act on, exactly like `check_retrieval_resolution()`
    returns cleanly and lets the caller decide what a violation means for their run.
    """
    violations = []
    for event in event_ledger.all_events():
        if event.event_type in _CONFIG_SCOPED_EVENT_TYPES and not config_ledger.exists(event.config_fingerprint):
            violations.append(event)
    return violations


__all__ = [
    "APPEND_CREATED",
    "APPEND_IDEMPOTENT",
    "APPEND_RESULTS",
    "CanonicalEventCollisionError",
    "UnknownCanonicalMemoryError",
    "UnknownConfigFingerprintError",
    "SingleOccurrenceViolationError",
    "RetrievalResolutionViolation",
    "CanonicalEventLedger",
    "check_config_resolution",
]
