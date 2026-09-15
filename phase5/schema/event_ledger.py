"""Phase 5.4 -- `Phase5EventLedger`, the append-only, benchmark-owned store for
`Phase5Event` (Stage 5.2's six new event families).

WHY THIS IS INTRODUCED IN STAGE 5.4, NOT 5.2
--------------------------------------------------------------------------------
Stage 5.2 defined the `Phase5Event` schema but deliberately did not build its
persistence -- a schema and its store are separable concerns, and 5.2's PASS condition
was about event *shape*, not storage. Stage 5.4 is the first stage that actually needs to
durably record a `Phase5Event` (an `attack_injection` event, alongside the `created`
`CanonicalEvent` memory-lifecycle wiring), so the ledger is introduced here, at the point
of first real use, rather than speculatively in 5.2.

DESIGN -- MIRRORS `CanonicalEventLedger` EXACTLY, NO NEW PERSISTENCE MECHANISM
--------------------------------------------------------------------------------
One append-only JSONL file (`phase5_events.jsonl`), `json.dumps(..., sort_keys=True)` +
`flush()` + `os.fsync()` per write, reconstruction-by-fold on load, no `update()`/
`delete()`. Collision policy identical to every other ledger in this framework:
identical `identity_fields()` on a re-append of an existing `event_id` is an idempotent
no-op; a differing payload under the same `event_id` raises loudly.

WHAT THIS LEDGER DOES NOT DO
--------------------------------------------------------------------------------
Unlike `CanonicalEventLedger`, this ledger does not existence-check `memory_id`/
`config_fingerprint` against another ledger at append time. `Phase5Event`'s six types
reference memories, tasks, and configurations by id, but Stage 5.4/5.5/5.6's wiring
layers are the ones responsible for calling this ledger only after the referenced
entities already exist -- mirroring the same "authoritative write order" discipline used
everywhere else in this framework, enforced by caller convention plus tests, not by a
second cross-ledger existence check duplicating `CanonicalEventLedger`'s own.

DUPLICATE-`memory_id` INVARIANT FOR `attack_injection` EVENTS (Phase 5.4 review fix)
--------------------------------------------------------------------------------
This ledger DOES enforce one integrity invariant of its own, analogous to (but distinct
from) `CanonicalEventLedger`'s "single creation slot per memory": two DIFFERENT
`attack_injection` events (different `event_id`s) must never both claim the same
non-`None` `memory_id`. Without this check, two different attacks (or two different
artifacts from the same attack) could both record themselves as the origin of the SAME
canonical memory -- a genuine data-integrity violation for attribution (contract OR-12's
downstream ground-truth derivation and Stage 5.7's lineage work both assume a memory's
attack origin is unambiguous). This is checked in `append()`, before the write, exactly
like `CanonicalEventLedger`'s own single-occurrence check -- see `DuplicateMemoryClaimError`.
An idempotent re-append of the literal same event (same `event_id`) is unaffected, since
the identical-event_id path is resolved before this invariant is even evaluated.

CONCURRENCY -- EXPLICIT LIMITATION (same model as every other ledger in this framework)
--------------------------------------------------------------------------------
Single-process, single-writer, no cross-process file lock -- identical limitation to
`ledger.py`/`event_ledger.py`/`run_identity.py`'s own documented model. A campaign that
runs multiple OS processes against the SAME `storage_dir` concurrently is out of scope;
each isolated run/campaign is expected to use its own `storage_dir` (or otherwise
externally serialize writers), exactly as every other ledger in this framework already
requires. This is not a new limitation introduced by Phase 5 -- it is inherited, and
stated explicitly here rather than left implicit, per the Phase 5.4 review.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Tuple, Union

from phase5.schema.event import ATTACK_INJECTION, Phase5Event

APPEND_CREATED = "CREATED"
APPEND_IDEMPOTENT = "IDEMPOTENT_NOOP"
APPEND_RESULTS: Tuple[str, ...] = (APPEND_CREATED, APPEND_IDEMPOTENT)

_EVENTS_FILE = "phase5_events.jsonl"


class Phase5EventCollisionError(ValueError):
    """Raised when an `event_id` already present in the ledger is appended again with a
    different payload. Mirrors `CanonicalEventCollisionError` exactly."""


class DuplicateMemoryClaimError(ValueError):
    """Raised when a NEW (non-idempotent) `attack_injection` event would claim a
    `memory_id` already claimed by a different, existing `attack_injection` event. See
    module docstring "DUPLICATE-memory_id INVARIANT" -- a memory's attack origin must be
    unambiguous."""


def _append_jsonl(path: Path, obj: dict) -> None:
    line = json.dumps(obj, sort_keys=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
        fh.flush()
        os.fsync(fh.fileno())


class Phase5EventLedger:
    def __init__(self, storage_dir: Union[str, Path]) -> None:
        self._dir = Path(storage_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / _EVENTS_FILE
        self._events_by_id: Dict[str, Phase5Event] = {}
        self._order: List[str] = []
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        with open(self._path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                event = Phase5Event.from_dict(json.loads(line))
                self._events_by_id[event.event_id] = event
                self._order.append(event.event_id)

    def append(self, event: Phase5Event) -> str:
        existing = self._events_by_id.get(event.event_id)
        if existing is not None:
            if existing.identity_fields() == event.identity_fields():
                return APPEND_IDEMPOTENT
            raise Phase5EventCollisionError(
                f"event_id {event.event_id!r} already exists with different content -- "
                f"refusing to overwrite. Existing={existing.to_dict()!r} New={event.to_dict()!r}"
            )

        if event.event_type == ATTACK_INJECTION and event.memory_id is not None:
            # P2 doc fix (2026-09-14): this read-check-write is unlocked, consistent
            # with (not an exception to) this module's own top-of-file "CONCURRENCY --
            # EXPLICIT LIMITATION" section -- single-process, single-writer, no
            # cross-process file lock, same as every other ledger in this framework.
            # Called out explicitly here too so this specific check's own safety isn't
            # read in isolation from that module-level disclosure.
            for other in self.all_events():
                if (
                    other.event_type == ATTACK_INJECTION
                    and other.memory_id == event.memory_id
                    and other.event_id != event.event_id
                ):
                    raise DuplicateMemoryClaimError(
                        f"memory_id {event.memory_id!r} is already claimed by attack_injection "
                        f"event_id {other.event_id!r} (attack_id={other.attack_id!r}, "
                        f"artifact_id={other.artifact_id!r}) -- refusing to record a second, "
                        f"different attack_injection event_id {event.event_id!r} "
                        f"(attack_id={event.attack_id!r}, artifact_id={event.artifact_id!r}) "
                        "for the same memory_id. A memory's attack origin must be unambiguous."
                    )

        self._events_by_id[event.event_id] = event
        self._order.append(event.event_id)
        _append_jsonl(self._path, event.to_dict())
        return APPEND_CREATED

    def get(self, event_id: str) -> Phase5Event:
        return self._events_by_id[event_id]

    def exists(self, event_id: str) -> bool:
        return event_id in self._events_by_id

    def all_events(self) -> Tuple[Phase5Event, ...]:
        return tuple(self._events_by_id[eid] for eid in self._order)

    def events_for_memory(self, memory_id: str) -> Tuple[Phase5Event, ...]:
        return tuple(e for e in self.all_events() if e.memory_id == memory_id)

    def events_for_attack(self, attack_id: str) -> Tuple[Phase5Event, ...]:
        return tuple(e for e in self.all_events() if e.attack_id == attack_id)

    def events_for_task(self, task_id: str) -> Tuple[Phase5Event, ...]:
        return tuple(e for e in self.all_events() if e.task_id == task_id)


__all__ = [
    "APPEND_CREATED",
    "APPEND_IDEMPOTENT",
    "APPEND_RESULTS",
    "Phase5EventCollisionError",
    "DuplicateMemoryClaimError",
    "Phase5EventLedger",
]
