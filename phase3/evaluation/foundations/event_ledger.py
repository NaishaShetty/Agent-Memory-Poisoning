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
from typing import Dict, List, Tuple, Union

from phase3.evaluation.foundations.canonical_event import (
    CanonicalEvent,
    EVENT_CREATED,
    EVENT_DERIVED,
    EVENT_RETIRED,
    EVENT_SUPERSEDED,
)
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger

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


class SingleOccurrenceViolationError(ValueError):
    """Raised when a second, DIFFERENT (non-idempotent) `created`/`derived`/`superseded`/
    `retired` event is appended for a memory that already has one. See module docstring
    "SINGLE-OCCURRENCE EVENT TYPES" section -- this enforces event-ledger data integrity,
    not H.3 supersession policy."""


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

    def __init__(self, storage_dir: Union[str, Path], memory_ledger: CanonicalMemoryLedger) -> None:
        self._dir = Path(storage_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._events_path = self._dir / _EVENTS_FILE
        self._memory_ledger = memory_ledger

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
        append leaves no partial trace. Raises `CanonicalEventCollisionError` if
        `event.event_id` already exists with a different payload.
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


__all__ = [
    "APPEND_CREATED",
    "APPEND_IDEMPOTENT",
    "APPEND_RESULTS",
    "CanonicalEventCollisionError",
    "UnknownCanonicalMemoryError",
    "SingleOccurrenceViolationError",
    "CanonicalEventLedger",
]
