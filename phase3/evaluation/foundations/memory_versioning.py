"""Phase 3.3-H.3 (Immutable Memory Versioning, Supersession & Retirement).

============================================================================
CRITICAL EVIDENCE-BASED REFRAMING -- READ THIS FIRST
============================================================================
The H.3 mission brief's own illustrative diagram ("canonical memory identity -> version 1
CREATED -> version 2 SUPERSEDES version 1 -> version 3 SUPERSEDES version 2 -> RETIRED")
describes a model where multiple immutable CONTENT versions share one logical memory
identity. That model is **not what the frozen schema actually defines**, and implementing
it literally would silently redefine H.1's frozen canonical-identity semantics -- exactly
the outcome the mission's own STOP conditions (#1, #5, #9) prohibit. This module instead
implements the model the frozen schema documents evidence for. The two disagree, so this
section states the evidence and the resulting design decision explicitly, per the
mission's own instruction ("if a field's ownership is ambiguous: STOP, inspect existing
schema/documentation, resolve from repository evidence, do not invent semantics casually").

EVIDENCE (verbatim, from the FROZEN `memory_schema.md`/`memory_schema.json`):

    memory_schema.md section 2 ("Memory identity"):
        "Identity is assigned once at creation and never reassigned, reused, or mutated --
        not even when a memory is superseded or retired. Two memories are never merged
        into a single identity after creation."

    memory_schema.md section 6 ("Conflict and supersession"):
        "If B legitimately supersedes A ...: A -- superseded_by --> B. A transitions to a
        retired lifecycle state but is never deleted."

    memory_schema.json's `superseded_by` field:
        "the memory_id of the memory that legitimately supersedes this one."

    relationship_schema.md section 2: `superseded_by: A -> B` is explicitly a relationship
    between TWO DISTINCT memory identities, "one-to-one per memory (a memory has at most
    one superseder)".

CONCLUSION: "supersession" in this frozen ontology is never "memory M1 gets a new content
version" -- content, source, parent_ids, memory_type, creation_event, and creation_
timestamp are permanently fixed at creation for every `memory_id`, forever (H.1's
`CanonicalMemoryRecord` is a frozen dataclass specifically because of this). What
LEGITIMATELY changes over one `memory_id`'s lifetime is exactly the four relationship/
lifecycle fields `memory_schema.json` lists last: `lifecycle_state`, `superseded_by`,
`equivalent_to`, `conflicts_with` -- and H.1's own design doc said so directly: "H.1 does
not implement update semantics... reject ambiguous mutation... This protects the ontology
until H.3 introduces formal versioning." THIS is the exact gap H.3 exists to close.

THE H.3 MODEL THIS MODULE IMPLEMENTS:

    canonical memory identity (memory_id, H.1, frozen, permanent)
            |
            v
    a LINEAR sequence of immutable LIFECYCLE VERSIONS for that SAME memory_id --
    each version is a snapshot of (lifecycle_state, superseded_by) at one point in that
    memory's history. Content is IDENTICAL across every version of one memory_id (it
    cannot change, ever) -- what changes between versions is ONLY the lifecycle/
    relationship state. `equivalent_to`/`conflicts_with` evolution is explicitly OUT OF
    SCOPE for H.3 (see "Explicit non-goals" below) -- the mission scopes H.3 to
    supersession/retirement specifically, and evolving those two relationship fields
    post-creation is a genuinely separate, undecided question this module does not answer.

    "Supersession" (B replaces A) is represented as: A stays exactly what it always was
    (frozen `CanonicalMemoryRecord`, unchanged); B is a SEPARATE, independently-created
    canonical memory (created via the EXISTING, unmodified H.1 write path -- this module
    never constructs B's content); a new SupersessionRecord links A -> B; and A's OWN
    lifecycle-version history gains a new version reflecting `superseded_by=B.memory_id`,
    `lifecycle_state=RETIRED`.

VERSION IDENTITY DECISION (mission section 6, explicitly asked for)
--------------------------------------------------------------------------------
A `CanonicalMemoryVersion` is NEVER independently authored/appended by a caller the way a
`CanonicalEvent` is -- it is a PURE, DETERMINISTIC PROJECTION, recomputed on demand from
already-persisted, already-collision/idempotency-protected state (the H.2
`CanonicalEventLedger`'s `created`/`derived`/`superseded`/`retired` events for one
`memory_id`, plus this module's own `SupersessionRecord`s). There is therefore no
"duplicate submission" scenario to resolve the way H.2-R2 resolved for events (two
independent callers minting the same content never happens here, because nothing ever
calls a version constructor directly from arbitrary caller code). Given that, `version_id`
is simply `f"{memory_id}::v{version_number}"` -- benchmark-owned, deterministic, and
directly meaningful, rather than a content-fingerprint (fingerprinting a value that is
already fully determined by (memory_id, version_number) would be redundant machinery, not
an identity decision with any real ambiguity to resolve). `event_identity.py`'s content-
derived design was deliberately NOT copied here, per the mission's explicit warning not to
blindly reuse it -- versions and events are different ontology objects with different
authorship models.

WHY NO SEPARATE "versions.jsonl" STORE (mission section 15: "Do NOT duplicate the complete
event history inside every version. Use references.")
--------------------------------------------------------------------------------
A `CanonicalMemoryVersion` is computed, never separately persisted -- it references the
`CanonicalEvent` that established it (`established_by_event_id`) rather than duplicating
that event's content. The only NEW persisted state this module introduces is
`SupersessionRecord` (the A->B linkage `relationship_schema.md` describes, which has no
home on the frozen `CanonicalEvent` shape -- see "Why a new SupersessionRecord, not a new
CanonicalEvent field" below), stored append-only in `supersessions.jsonl`, mirroring every
prior stage's exact persistence discipline (open-append/flush/fsync, loud malformed-record
failure, deterministic reload).

WHY A NEW SupersessionRecord, NOT A NEW CanonicalEvent FIELD
--------------------------------------------------------------------------------
H.2-R2 (frozen) requires `len(memory_ids)==1` for a `superseded` event and forbids
`source_memory_ids`/`target_memory_id` on any non-`derived` event type -- so there is
genuinely no existing `CanonicalEvent` field that can carry "which memory superseded this
one" without modifying `canonical_event.py`, which is frozen and MUST NOT be modified by
H.3 (mission section 23: "must remain valid... do not silently remove/redefine"). This
module therefore introduces a small, new, ADDITIVE side-record (mirrors H.2-R's own
`ExperimentBoundaryRecord` precedent -- "a genuinely separate type" is exactly the
established pattern this repository already uses when a frozen type's shape cannot express
a new fact) rather than touching `canonical_event.py` at all.

EXPLICIT NON-GOALS (H.4+ / undecided, not invented here)
--------------------------------------------------------------------------------
- `equivalent_to`/`conflicts_with` evolution after creation -- out of scope; these remain
  exactly as H.1 defined them (immutable, set once at construction).
- Any policy for WHEN a memory should be superseded/retired (novelty/creation-policy
  thresholds) -- `memory_schema.md` section 8 explicitly defers this to a "not-yet-frozen"
  creation policy; H.3 provides the MECHANISM, never the POLICY.
- Retrieval/selection awareness of retirement (e.g. excluding RETIRED memories from
  candidate discovery) -- H.4's job, per the mission's own scope table.
- Runtime integration with `campaign_formal_runner.py` or any real foundation adapter.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from phase3.evaluation.foundations.canonical import LIFECYCLE_RETIRED, LIFECYCLE_STATES
from phase3.evaluation.foundations.canonical_event import (
    CanonicalEvent,
    EVENT_CREATED,
    EVENT_DERIVED,
    EVENT_RETIRED,
    EVENT_SUPERSEDED,
)
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger

_CREATION_EVENT_TYPES: Tuple[str, ...] = (EVENT_CREATED, EVENT_DERIVED)
_LIFECYCLE_EVENT_TYPES: Tuple[str, ...] = (EVENT_CREATED, EVENT_DERIVED, EVENT_SUPERSEDED, EVENT_RETIRED)


class MemoryVersioningError(ValueError):
    """Base class for every H.3 validation/precondition failure. Fails loudly -- no
    silent coercion, mirroring every prior stage's discipline."""


class UnknownMemoryError(MemoryVersioningError):
    """Raised when an operation references a `memory_id` absent from the linked
    `CanonicalMemoryLedger`. H.3 never creates a memory record as a side effect."""


class NoLifecycleHistoryError(MemoryVersioningError):
    """Raised when a memory exists in the `CanonicalMemoryLedger` (H.1) but has no
    `created`/`derived` event recorded in the `CanonicalEventLedger` (H.2) yet -- H.3
    cannot reconstruct a version history for a memory whose creation was never logged as
    an event. This is a genuine precondition, not an internal bug: H.1 and H.2 are
    independent ledgers, and nothing enforces that every `CanonicalMemoryLedger.put()`
    is always paired with a `created`/`derived` event append (a caller could legitimately
    use H.1 alone, e.g. during migration or ad hoc ledger construction, without H.2)."""


class AlreadyRetiredError(MemoryVersioningError):
    """Raised by `supersede_memory()`/`retire_memory()` when the target memory's current
    version already has `lifecycle_state=RETIRED` -- retirement is terminal in this model
    (mirrors the append-only "never resurrect" discipline every prior stage established)."""


class SupersessionCollisionError(MemoryVersioningError):
    """Raised when a `SupersessionRecord` for a given `superseded_memory_id` already
    exists with a DIFFERENT `superseding_memory_id` -- relationship_schema.md states a
    memory has AT MOST ONE superseder; a second, different one is a genuine collision,
    never silently overwritten."""


# ---------------------------------------------------------------------------
# SupersessionRecord + its append-only ledger
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SupersessionRecord:
    """The A -> B linkage `relationship_schema.md` section 2 describes
    (`superseded_by: A -> B`), persisted independently of the frozen `CanonicalEvent`
    shape (see module docstring). `superseded_event_id` is a REFERENCE to the
    `CanonicalEvent` that established this fact -- the event's own content
    (timestamp/actor/reason) is never duplicated here."""

    superseded_memory_id: str
    superseding_memory_id: str
    superseded_event_id: str

    def __post_init__(self) -> None:
        if not (isinstance(self.superseded_memory_id, str) and self.superseded_memory_id):
            raise MemoryVersioningError("superseded_memory_id must be a non-empty string.")
        if not (isinstance(self.superseding_memory_id, str) and self.superseding_memory_id):
            raise MemoryVersioningError("superseding_memory_id must be a non-empty string.")
        if self.superseded_memory_id == self.superseding_memory_id:
            raise MemoryVersioningError("a memory cannot supersede itself.")
        if not (isinstance(self.superseded_event_id, str) and self.superseded_event_id):
            raise MemoryVersioningError("superseded_event_id must be a non-empty string.")

    def to_dict(self) -> dict:
        return {
            "superseded_memory_id": self.superseded_memory_id,
            "superseding_memory_id": self.superseding_memory_id,
            "superseded_event_id": self.superseded_event_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SupersessionRecord":
        return cls(**data)


def _append_jsonl(path: Path, obj: dict) -> None:
    line = json.dumps(obj, sort_keys=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
        fh.flush()
        os.fsync(fh.fileno())


class SupersessionLedger:
    """Benchmark-owned, append-only store of `SupersessionRecord`s. Single-process/
    single-writer, identical persistence discipline to every other ledger in this
    framework (`records.jsonl`-style append/flush/fsync; malformed lines raise loudly on
    reload, never silently skipped)."""

    _FILE = "supersessions.jsonl"

    def __init__(self, storage_dir: Union[str, Path]) -> None:
        self._dir = Path(storage_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / self._FILE
        self._by_superseded: Dict[str, SupersessionRecord] = {}
        self._by_event_id: Dict[str, SupersessionRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        with open(self._path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                record = SupersessionRecord.from_dict(json.loads(line))
                self._by_superseded[record.superseded_memory_id] = record
                self._by_event_id[record.superseded_event_id] = record

    def append(self, record: SupersessionRecord) -> None:
        existing = self._by_superseded.get(record.superseded_memory_id)
        if existing is not None:
            if existing == record:
                return  # idempotent no-op -- identical fact re-recorded
            raise SupersessionCollisionError(
                f"memory {record.superseded_memory_id!r} already has a superseder "
                f"({existing.superseding_memory_id!r}) -- relationship_schema.md permits at "
                f"most one; refusing to record a different one ({record.superseding_memory_id!r})."
            )
        self._by_superseded[record.superseded_memory_id] = record
        self._by_event_id[record.superseded_event_id] = record
        _append_jsonl(self._path, record.to_dict())

    def superseder_of(self, memory_id: str) -> Optional[str]:
        record = self._by_superseded.get(memory_id)
        return record.superseding_memory_id if record is not None else None

    def get_by_event_id(self, event_id: str) -> Optional[SupersessionRecord]:
        return self._by_event_id.get(event_id)


# ---------------------------------------------------------------------------
# CanonicalMemoryVersion -- a pure, computed lifecycle snapshot
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CanonicalMemoryVersion:
    """One immutable lifecycle-state snapshot of a single canonical `memory_id`. NEVER
    independently constructed by a caller outside this module -- always produced by
    `reconstruct_version_history()`/`get_current_version()`, which compute it fresh, every
    time, from the H.2 `CanonicalEventLedger` + this module's `SupersessionLedger`."""

    version_id: str
    memory_id: str
    version_number: int
    lifecycle_state: str
    superseded_by: Optional[str]
    established_by_event_id: str
    recorded_at: str

    def __post_init__(self) -> None:
        if self.lifecycle_state not in LIFECYCLE_STATES:
            raise MemoryVersioningError(f"lifecycle_state {self.lifecycle_state!r} is not one of {LIFECYCLE_STATES!r}.")
        if self.version_number < 1:
            raise MemoryVersioningError("version_number must be >= 1.")


def _version_id(memory_id: str, version_number: int) -> str:
    return f"{memory_id}::v{version_number}"


def reconstruct_version_history(
    event_ledger: CanonicalEventLedger,
    memory_ledger: CanonicalMemoryLedger,
    supersession_ledger: SupersessionLedger,
    memory_id: str,
) -> Tuple[CanonicalMemoryVersion, ...]:
    """The mission's central H.3 capability: given `memory_id`, reconstruct its complete
    lifecycle-version history from canonical infrastructure ALONE -- no vendor foundation
    is ever consulted (no `MemoryFoundationAdapter` import exists anywhere in this
    module). One version is produced per lifecycle-relevant event
    (`created`/`derived`/`superseded`/`retired`) found for this memory, in the EXACT
    append order `CanonicalEventLedger` already guarantees -- never re-sorted by
    timestamp, matching every prior stage's ordering discipline.

    Raises `UnknownMemoryError` if `memory_id` has no `CanonicalMemoryRecord`.
    Raises `NoLifecycleHistoryError` if the memory exists but has no `created`/`derived`
    event recorded yet (H.3 cannot version a memory whose creation was never logged).
    """
    if not memory_ledger.exists(memory_id):
        raise UnknownMemoryError(f"memory_id {memory_id!r} does not exist in the linked CanonicalMemoryLedger.")

    lifecycle_events: List[CanonicalEvent] = [
        e for e in event_ledger.events_for_memory(memory_id) if e.event_type in _LIFECYCLE_EVENT_TYPES
    ]
    if not lifecycle_events or lifecycle_events[0].event_type not in _CREATION_EVENT_TYPES:
        raise NoLifecycleHistoryError(
            f"memory_id {memory_id!r} has no created/derived event recorded in the linked "
            "CanonicalEventLedger -- H.3 cannot reconstruct a version history without one."
        )

    versions: List[CanonicalMemoryVersion] = []
    current_superseded_by: Optional[str] = None
    for index, event in enumerate(lifecycle_events, start=1):
        if event.event_type == EVENT_SUPERSEDED:
            linkage = supersession_ledger.get_by_event_id(event.event_id)
            current_superseded_by = linkage.superseding_memory_id if linkage is not None else None
        versions.append(
            CanonicalMemoryVersion(
                version_id=_version_id(memory_id, index),
                memory_id=memory_id,
                version_number=index,
                lifecycle_state=event.new_state,
                superseded_by=current_superseded_by,
                established_by_event_id=event.event_id,
                recorded_at=event.timestamp,
            )
        )
    return tuple(versions)


def get_current_version(
    event_ledger: CanonicalEventLedger,
    memory_ledger: CanonicalMemoryLedger,
    supersession_ledger: SupersessionLedger,
    memory_id: str,
) -> CanonicalMemoryVersion:
    """The authoritative "what is memory X's current lifecycle state right now" query.
    Always the LAST entry of `reconstruct_version_history()` -- never last-appended-
    to-the-vendor, never timestamp-sorted independently, never inferred from
    `CanonicalMemoryRecord.lifecycle_state` directly (that field is frozen at its
    AT-CREATION value forever -- see module docstring's identity decision; reading it
    post-creation as if it were "current" would be a real bug this module avoids by
    construction, since `CanonicalMemoryRecord`'s own frozen field is never consulted
    here at all beyond the `exists()` check).
    """
    history = reconstruct_version_history(event_ledger, memory_ledger, supersession_ledger, memory_id)
    return history[-1]


def get_version(
    event_ledger: CanonicalEventLedger,
    memory_ledger: CanonicalMemoryLedger,
    supersession_ledger: SupersessionLedger,
    memory_id: str,
    version_number: int,
) -> Optional[CanonicalMemoryVersion]:
    """One specific historical version by number, or `None` if that version_number does
    not exist for this memory."""
    history = reconstruct_version_history(event_ledger, memory_ledger, supersession_ledger, memory_id)
    for version in history:
        if version.version_number == version_number:
            return version
    return None


# ---------------------------------------------------------------------------
# Operational layer -- supersede_memory() / retire_memory()
# ---------------------------------------------------------------------------

STATUS_RETIRED_EVENT_ONLY = "RETIRED_EVENT_ONLY"
STATUS_FULLY_RETIRED = "FULLY_RETIRED"
STATUS_SUPERSEDED_EVENT_ONLY = "SUPERSEDED_EVENT_ONLY"
STATUS_SUPERSEDED_EVENT_AND_LINKAGE = "SUPERSEDED_EVENT_AND_LINKAGE"
STATUS_FULLY_SUPERSEDED = "FULLY_SUPERSEDED"


@dataclass(frozen=True)
class RetirementResult:
    status: str
    memory_id: str
    retired_event_id: Optional[str] = None
    note: str = ""


@dataclass(frozen=True)
class SupersessionResult:
    status: str
    superseded_memory_id: str
    superseding_memory_id: str
    superseded_event_id: Optional[str] = None
    retired_event_id: Optional[str] = None
    note: str = ""


def retire_memory(
    event_ledger: CanonicalEventLedger,
    memory_ledger: CanonicalMemoryLedger,
    supersession_ledger: SupersessionLedger,
    memory_id: str,
    *,
    retired_event: CanonicalEvent,
) -> RetirementResult:
    """Retire `memory_id` with NO successor (a legitimate, `superseded_by`-optional
    outcome per `memory_schema.json`). `retired_event` must already be a validated
    `CanonicalEvent` (`event_type='retired'`, `memory_ids=(memory_id,)`,
    `new_state='RETIRED'`) -- construct it via `event_identity.build_canonical_event()` or
    directly; this function does not construct it FOR the caller, mirroring
    `canonical_write.write_canonical_memory()`'s own "caller supplies the validated
    record, this function orchestrates the write" division of responsibility.

    Raises `AlreadyRetiredError` if `memory_id`'s current version is already RETIRED --
    retirement is terminal. Raises whatever `event_ledger.append()` itself raises
    (`UnknownCanonicalMemoryError`, `CanonicalEventCollisionError`,
    `SingleOccurrenceViolationError`) unchanged -- this function adds a precondition
    check, it does not weaken any existing one.
    """
    if retired_event.event_type != EVENT_RETIRED or retired_event.memory_ids != (memory_id,):
        raise MemoryVersioningError(
            f"retired_event must have event_type='retired' and memory_ids=({memory_id!r},); "
            f"got event_type={retired_event.event_type!r}, memory_ids={retired_event.memory_ids!r}."
        )

    current = get_current_version(event_ledger, memory_ledger, supersession_ledger, memory_id)
    if current.lifecycle_state == LIFECYCLE_RETIRED:
        raise AlreadyRetiredError(f"memory_id {memory_id!r} is already RETIRED (version {current.version_id!r}).")

    event_ledger.append(retired_event)  # propagates any ledger-level rejection unchanged
    return RetirementResult(status=STATUS_FULLY_RETIRED, memory_id=memory_id, retired_event_id=retired_event.event_id)


def supersede_memory(
    event_ledger: CanonicalEventLedger,
    memory_ledger: CanonicalMemoryLedger,
    supersession_ledger: SupersessionLedger,
    superseded_memory_id: str,
    superseding_memory_id: str,
    *,
    superseded_event: CanonicalEvent,
    retired_event: CanonicalEvent,
) -> SupersessionResult:
    """Record that `superseding_memory_id` legitimately supersedes `superseded_memory_id`
    (`relationship_schema.md`'s `superseded_by: A -> B`). `superseding_memory_id` MUST
    already be a separately, independently created canonical memory in `memory_ledger` --
    this function never constructs it (per `memory_schema.md` section 8: the actual
    creation-policy DECISION of what supersedes what is explicitly not H.3's job; H.3 only
    records the fact once both memories already exist and a caller has decided B
    supersedes A).

    Write order (mission section 17/18 -- explicit, never claimed atomic across the three
    persisted facts):
      1. validate both memories exist and A is not already retired/superseded
      2. append the `superseded` CanonicalEvent for A (durable historical fact: "A was
         marked superseded", independent of whether step 3 below succeeds)
      3. append the SupersessionRecord (A -> B linkage)
      4. append the `retired` CanonicalEvent for A (A's lifecycle_state -> RETIRED)

    Each step's success is independently durable the instant it completes (JSONL
    append+fsync, per every ledger in this framework) -- a failure between steps leaves
    an HONEST partial state, reported via `status`, never a corrupted or silently-repaired
    one: `reconstruct_version_history()` run afterward will show exactly what actually
    completed (e.g. a `superseded` event with no resolvable linkage if step 3 failed,
    reported as `superseded_by=None` on that version -- never fabricated).
    """
    if superseded_event.event_type != EVENT_SUPERSEDED or superseded_event.memory_ids != (superseded_memory_id,):
        raise MemoryVersioningError(
            f"superseded_event must have event_type='superseded' and memory_ids="
            f"({superseded_memory_id!r},); got event_type={superseded_event.event_type!r}, "
            f"memory_ids={superseded_event.memory_ids!r}."
        )
    if retired_event.event_type != EVENT_RETIRED or retired_event.memory_ids != (superseded_memory_id,):
        raise MemoryVersioningError(
            f"retired_event must have event_type='retired' and memory_ids="
            f"({superseded_memory_id!r},); got event_type={retired_event.event_type!r}, "
            f"memory_ids={retired_event.memory_ids!r}."
        )
    if not memory_ledger.exists(superseding_memory_id):
        raise UnknownMemoryError(
            f"superseding_memory_id {superseding_memory_id!r} does not exist in the linked "
            "CanonicalMemoryLedger -- it must already be a separately-created canonical memory."
        )

    current = get_current_version(event_ledger, memory_ledger, supersession_ledger, superseded_memory_id)
    if current.lifecycle_state == LIFECYCLE_RETIRED:
        raise AlreadyRetiredError(
            f"memory_id {superseded_memory_id!r} is already RETIRED (version {current.version_id!r})."
        )
    if current.superseded_by is not None:
        raise SupersessionCollisionError(
            f"memory_id {superseded_memory_id!r} already has a superseder "
            f"({current.superseded_by!r}) -- relationship_schema.md permits at most one."
        )

    event_ledger.append(superseded_event)

    try:
        supersession_ledger.append(
            SupersessionRecord(
                superseded_memory_id=superseded_memory_id,
                superseding_memory_id=superseding_memory_id,
                superseded_event_id=superseded_event.event_id,
            )
        )
    except SupersessionCollisionError as exc:
        return SupersessionResult(
            status=STATUS_SUPERSEDED_EVENT_ONLY,
            superseded_memory_id=superseded_memory_id,
            superseding_memory_id=superseding_memory_id,
            superseded_event_id=superseded_event.event_id,
            note=f"superseded event recorded, but linkage failed: {exc}",
        )

    event_ledger.append(retired_event)

    return SupersessionResult(
        status=STATUS_FULLY_SUPERSEDED,
        superseded_memory_id=superseded_memory_id,
        superseding_memory_id=superseding_memory_id,
        superseded_event_id=superseded_event.event_id,
        retired_event_id=retired_event.event_id,
    )


__all__ = [
    "MemoryVersioningError",
    "UnknownMemoryError",
    "NoLifecycleHistoryError",
    "AlreadyRetiredError",
    "SupersessionCollisionError",
    "SupersessionRecord",
    "SupersessionLedger",
    "CanonicalMemoryVersion",
    "reconstruct_version_history",
    "get_current_version",
    "get_version",
    "STATUS_RETIRED_EVENT_ONLY",
    "STATUS_FULLY_RETIRED",
    "STATUS_SUPERSEDED_EVENT_ONLY",
    "STATUS_SUPERSEDED_EVENT_AND_LINKAGE",
    "STATUS_FULLY_SUPERSEDED",
    "RetirementResult",
    "SupersessionResult",
    "retire_memory",
    "supersede_memory",
]
