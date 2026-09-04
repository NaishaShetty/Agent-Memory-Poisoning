"""Phase 3.3-H.2 (Canonical Event Ledger) -- `CanonicalEvent`, a strict runtime
representation of one entry in `phase3/schemas/relationship_schema.md` section 3's event
log.

WHY THIS MODULE EXISTS
--------------------------------------------------------------------------------
`relationship_schema.md` is a FROZEN DECISION for event types and their required fields,
but until this stage nothing in the runtime persisted an event log at all: the existing
runtime traces (`foundations/trace.py::FoundationTraceArtifact`,
`agent_runtime/trace.py::evaluate_and_trace()`, `contracts/trace_artifact.schema.json`)
each capture a snapshot of ONE task's or ONE foundation call's outcome, not a durable,
append-only, benchmark-owned HISTORY of what happened to a given canonical memory over
time. This module is the event-record type; `event_ledger.py` is the durable,
append-only store built on top of it.

RELATIONSHIP TO EXISTING TRACES -- NOT A REPLACEMENT
--------------------------------------------------------------------------------
This module does not delete, subsume, or redesign `FoundationTraceArtifact`,
`evaluate_and_trace()`'s trace dict, or `trace_artifact.schema.json`. Those remain exactly
as they are; see `PHASE3_3_H2_CANONICAL_EVENT_LEDGER.md` section 15 for the (deliberately
deferred) trace-reconciliation strategy. This module answers a different question than any
of them: "what happened to canonical memory X, across its whole lifecycle, independent of
any one task or one foundation call."

EVENT VOCABULARY -- TAKEN VERBATIM FROM relationship_schema.md SECTION 3
--------------------------------------------------------------------------------
Exactly the seven event types the frozen relationship schema defines, in its own exact
(lowercase) spelling: `created`, `retrieved`, `selected`, `used`, `derived`, `superseded`,
`retired`. No second event vocabulary is invented. `relationship_schema.md` does not define
an `experiment_reset` (or equivalent) event type -- this is a genuine gap, documented (not
silently patched) in `PHASE3_3_H2_CANONICAL_EVENT_LEDGER.md` section 14; H.2 does not
invent one, and structurally cannot conflate an experiment/foundation reset with a
`retired` event because nothing in this stage auto-generates ANY event from a foundation
operation -- every event in this module is explicitly, manually constructed by a caller.

Every event's required fields are exactly `relationship_schema.md` section 3's list:
`event_id`, `event_type`, `memory_id`/`memory_ids`, `task_id` (where applicable),
`timestamp`, `actor`, `reason`, `previous_state`/`new_state` (for `created`/`superseded`/
`retired`). This module uses `memory_ids: Tuple[str, ...]` uniformly (never a separate
`memory_id` scalar field) -- the schema doc explicitly permits `memory_ids` "for events
touching several" and every event type this module represents concerns at least one
canonical memory, so one non-empty tuple field covers both the single- and multi-memory
cases without a redundant second field.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, Tuple

from phase3.evaluation.foundations.canonical import LIFECYCLE_STATES

# ---------------------------------------------------------------------------
# Event-type vocabulary -- verbatim from relationship_schema.md section 3. Preserves the
# schema doc's own lowercase spelling exactly; this module invents no alternate spelling.
# ---------------------------------------------------------------------------

EVENT_CREATED = "created"
EVENT_RETRIEVED = "retrieved"
EVENT_SELECTED = "selected"
EVENT_USED = "used"
EVENT_DERIVED = "derived"
EVENT_SUPERSEDED = "superseded"
EVENT_RETIRED = "retired"

EVENT_TYPES: Tuple[str, ...] = (
    EVENT_CREATED,
    EVENT_RETRIEVED,
    EVENT_SELECTED,
    EVENT_USED,
    EVENT_DERIVED,
    EVENT_SUPERSEDED,
    EVENT_RETIRED,
)

# "retrieved, selected, used are always task-scoped" -- relationship_schema.md section 3.
_TASK_SCOPED_EVENT_TYPES: Tuple[str, ...] = (EVENT_RETRIEVED, EVENT_SELECTED, EVENT_USED)

# "previous_state / new_state -- for state-changing events (created, superseded, retired)"
# -- relationship_schema.md section 3.
_STATE_CHANGING_EVENT_TYPES: Tuple[str, ...] = (EVENT_CREATED, EVENT_SUPERSEDED, EVENT_RETIRED)

# Phase 3.3-H.2-R2: memory_schema.json models `creation_event`, `superseded_by`, and
# `lifecycle_state` as SINGULAR per-memory fields (one creation event, at most one
# superseder, one current lifecycle state) -- so `created`/`superseded`/`retired` each
# concern exactly ONE memory, never a batch. `derived` is deliberately excluded here: its
# `memory_ids` legitimately spans multiple memories (sources + target), constrained
# instead by the source_memory_ids/target_memory_id consistency check below.
# `retrieved`/`selected`/`used` are deliberately excluded too: a single retrieval/
# selection/usage occurrence can legitimately touch several memories at once (e.g. one
# retrieval call returning several candidates as one recorded event).
_SINGLE_MEMORY_EVENT_TYPES: Tuple[str, ...] = (EVENT_CREATED, EVENT_SUPERSEDED, EVENT_RETIRED)


class CanonicalEventValidationError(ValueError):
    """Raised when a `CanonicalEvent` violates `relationship_schema.md` section 3's
    required-field/event-type constraints. Construction of an invalid event must fail
    loudly -- there is no silent-coercion path anywhere in this module."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CanonicalEventValidationError(message)


def _validate_timestamp(value: str) -> None:
    _require(isinstance(value, str) and bool(value), "timestamp must be a non-empty string.")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise CanonicalEventValidationError(f"timestamp {value!r} is not a valid ISO-8601 date-time: {exc}") from exc


@dataclass(frozen=True)
class CanonicalEvent:
    """Strict, immutable runtime representation of one `relationship_schema.md` section 3
    event log entry.

    Construction validates every constraint the schema doc states:
    - `event_type` is one of `EVENT_TYPES` (the schema doc's own seven).
    - `memory_ids` is a non-empty tuple (every event type here concerns at least one
      canonical memory -- there is no event type in this framework that concerns none).
    - `task_id` is required (non-empty) for `retrieved`/`selected`/`used`; left as
      caller-supplied (possibly `None`) for the others -- never fabricated.
    - `previous_state`/`new_state` are required (and must be one of
      `canonical.LIFECYCLE_STATES`) for `created`/`superseded`/`retired`; MUST be `None`
      for every other event type (this module does not overload them with a meaning the
      schema doc does not state for non-state-changing events).
    - `foundation_memory_id` requires `foundation_name` to also be set -- a vendor alias
      is meaningless without knowing which vendor.
    - `source_memory_ids`/`target_memory_id` (Phase 3.3-H.2-R): required for `derived`,
      forbidden for every other event type. See "LINEAGE ROLES" below.

    Fields mirror `relationship_schema.md` section 3 exactly; no speculative field (e.g. a
    closed `actor` category enum the schema doc does not define -- its own examples,
    `candidate_discovery`/`evidence_selection`/`creation_policy`, are finer-grained than
    any small closed set) was added beyond it.

    LINEAGE ROLES (Phase 3.3-H.2-R remediation)
    --------------------------------------------------------------------------------
    The original H.2 shape used a single flat `memory_ids` tuple for every event type,
    including `derived` -- for `derived` this was genuinely ambiguous: given
    `memory_ids = (M1, M2, M3)` for "M1 + M2 -> M3", nothing distinguished the two SOURCE
    (parent) memories from the one derived (child) memory except an unstated, brittle
    positional convention ("the last id is the target"). `relationship_schema.md` section 2
    already defines this relationship directionally (`parent_of`/`derived_from: A -> C`),
    and `memory_schema.json` already models it on the CHILD record itself via `parent_ids`
    (required non-empty for `memory_type=derived`, required empty for `memory_type=
    foundation`). This module reuses that EXACT existing ontology rather than inventing a
    new "role" vocabulary: `source_memory_ids` mirrors the derived memory's own
    `parent_ids`, and `target_memory_id` is the one derived (child) memory's own
    `memory_id`.

    `memory_ids` remains present on a `derived` event (used uniformly by
    `event_ledger.py`'s linkage-existence check and `events_for_memory()` queries, exactly
    as for every other event type), but for `derived` events it MUST exactly equal
    `set(source_memory_ids) | {target_memory_id}` -- checked explicitly, never silently
    auto-derived. This codebase's established convention (`canonical.py`, `ledger.py`) is
    to fail loudly on an inconsistent caller input rather than silently "fixing" it for
    them; auto-deriving `memory_ids` from `source_memory_ids`/`target_memory_id` would be
    a new, different convention introduced nowhere else in this framework, so this module
    does not adopt it.

    No such role pair was added for `superseded` (which relationship_schema.md's
    `superseded_by` also models directionally, A -> B) -- deliberately deferred. Recording
    "retired/superseded memory A, superseded BY memory B" at the event level starts to
    overlap with H.3's actual supersession-chain semantics (what a superseder pointer
    *means*, how it's validated, whether it's one-to-one), which is explicitly out of
    H.2-R's scope (see `PHASE3_3_H2_CANONICAL_EVENT_LEDGER.md` section 23-equivalent /
    "H.3 boundary"). `superseded`/`retired` events keep their original H.2 single-memory
    shape unchanged.
    """

    event_id: str
    event_type: str
    memory_ids: Tuple[str, ...]
    timestamp: str
    actor: str
    reason: str
    task_id: Optional[str] = None
    previous_state: Optional[str] = None
    new_state: Optional[str] = None
    foundation_name: Optional[str] = None
    foundation_memory_id: Optional[str] = None
    source_memory_ids: Optional[Tuple[str, ...]] = None
    target_memory_id: Optional[str] = None

    def __post_init__(self) -> None:
        _require(isinstance(self.event_id, str) and bool(self.event_id), "event_id must be a non-empty string.")
        _require(self.event_type in EVENT_TYPES, f"event_type {self.event_type!r} is not one of {EVENT_TYPES!r}.")
        _require(isinstance(self.memory_ids, tuple), "memory_ids must be a tuple (canonicalized, immutable).")
        _require(len(self.memory_ids) > 0, "memory_ids must be non-empty -- every event concerns at least one canonical memory.")
        _require(all(isinstance(m, str) and m for m in self.memory_ids), "every memory_id must be a non-empty string.")
        if self.event_type in _SINGLE_MEMORY_EVENT_TYPES:
            _require(
                len(self.memory_ids) == 1,
                f"memory_ids must contain exactly one memory_id for event_type={self.event_type!r} "
                "(memory_schema.json models creation_event/superseded_by/lifecycle_state as "
                "singular per-memory fields).",
            )
        _validate_timestamp(self.timestamp)
        _require(isinstance(self.actor, str) and bool(self.actor), "actor must be a non-empty string.")
        _require(isinstance(self.reason, str) and bool(self.reason), "reason must be a non-empty string.")

        if self.event_type in _TASK_SCOPED_EVENT_TYPES:
            _require(
                isinstance(self.task_id, str) and bool(self.task_id),
                f"task_id is required (non-empty) for event_type={self.event_type!r} "
                "(retrieved/selected/used are always task-scoped, per relationship_schema.md).",
            )
        elif self.task_id is not None:
            _require(isinstance(self.task_id, str) and bool(self.task_id), "task_id, if given, must be a non-empty string.")

        if self.event_type in _STATE_CHANGING_EVENT_TYPES:
            _require(
                self.new_state is not None,
                f"new_state is required for state-changing event_type={self.event_type!r}.",
            )
            _require(self.new_state in LIFECYCLE_STATES, f"new_state {self.new_state!r} is not one of {LIFECYCLE_STATES!r}.")
            if self.event_type != EVENT_CREATED:
                # 'created' has no prior state (nothing existed before); superseded/retired
                # transition FROM a real prior state.
                _require(
                    self.previous_state is not None,
                    f"previous_state is required for event_type={self.event_type!r}.",
                )
            if self.previous_state is not None:
                _require(
                    self.previous_state in LIFECYCLE_STATES,
                    f"previous_state {self.previous_state!r} is not one of {LIFECYCLE_STATES!r}.",
                )
        else:
            _require(
                self.previous_state is None and self.new_state is None,
                f"previous_state/new_state must be None for non-state-changing event_type={self.event_type!r} "
                "(relationship_schema.md scopes these fields to created/superseded/retired only).",
            )

        if self.foundation_memory_id is not None:
            _require(
                isinstance(self.foundation_name, str) and bool(self.foundation_name),
                "foundation_name is required whenever foundation_memory_id is set.",
            )
        if self.foundation_name is not None:
            _require(isinstance(self.foundation_name, str) and bool(self.foundation_name), "foundation_name, if given, must be a non-empty string.")

        if self.event_type == EVENT_DERIVED:
            _require(
                self.source_memory_ids is not None and isinstance(self.source_memory_ids, tuple) and len(self.source_memory_ids) > 0,
                "source_memory_ids is required (non-empty tuple) for event_type='derived'.",
            )
            _require(
                all(isinstance(m, str) and m for m in self.source_memory_ids),
                "every source_memory_id must be a non-empty string.",
            )
            _require(
                isinstance(self.target_memory_id, str) and bool(self.target_memory_id),
                "target_memory_id is required (non-empty string) for event_type='derived'.",
            )
            _require(
                self.target_memory_id not in self.source_memory_ids,
                f"target_memory_id {self.target_memory_id!r} must not also appear in source_memory_ids "
                "-- a memory cannot be its own parent.",
            )
            expected_memory_ids = frozenset(self.source_memory_ids) | {self.target_memory_id}
            _require(
                frozenset(self.memory_ids) == expected_memory_ids,
                f"memory_ids {self.memory_ids!r} must exactly equal source_memory_ids "
                f"{self.source_memory_ids!r} union {{target_memory_id}} ({self.target_memory_id!r}) for "
                "event_type='derived' -- lineage roles are never inferred from memory_ids' positions.",
            )
        else:
            _require(
                self.source_memory_ids is None and self.target_memory_id is None,
                f"source_memory_ids/target_memory_id must be None for event_type={self.event_type!r} "
                "-- explicit lineage roles are defined only for 'derived' events.",
            )

    # -- serialization ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "memory_ids": list(self.memory_ids),
            "timestamp": self.timestamp,
            "actor": self.actor,
            "reason": self.reason,
            "task_id": self.task_id,
            "previous_state": self.previous_state,
            "new_state": self.new_state,
            "foundation_name": self.foundation_name,
            "foundation_memory_id": self.foundation_memory_id,
            "source_memory_ids": list(self.source_memory_ids) if self.source_memory_ids is not None else None,
            "target_memory_id": self.target_memory_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CanonicalEvent":
        return cls(
            event_id=data["event_id"],
            event_type=data["event_type"],
            memory_ids=tuple(data["memory_ids"]),
            timestamp=data["timestamp"],
            actor=data["actor"],
            reason=data["reason"],
            task_id=data.get("task_id"),
            previous_state=data.get("previous_state"),
            new_state=data.get("new_state"),
            foundation_name=data.get("foundation_name"),
            foundation_memory_id=data.get("foundation_memory_id"),
            source_memory_ids=tuple(data["source_memory_ids"]) if data.get("source_memory_ids") is not None else None,
            target_memory_id=data.get("target_memory_id"),
        )

    def identity_fields(self) -> Tuple[Any, ...]:
        """Every field, used by `event_ledger.CanonicalEventLedger.append()` to distinguish
        an idempotent duplicate append (identical `event_id` + identical payload) from a
        genuine collision (identical `event_id`, different payload) -- mirrors
        `canonical.CanonicalMemoryRecord.identity_fields()`'s exact discipline."""
        return (
            self.event_id,
            self.event_type,
            self.memory_ids,
            self.timestamp,
            self.actor,
            self.reason,
            self.task_id,
            self.previous_state,
            self.new_state,
            self.foundation_name,
            self.foundation_memory_id,
            self.source_memory_ids,
            self.target_memory_id,
        )


__all__ = [
    "EVENT_CREATED",
    "EVENT_RETRIEVED",
    "EVENT_SELECTED",
    "EVENT_USED",
    "EVENT_DERIVED",
    "EVENT_SUPERSEDED",
    "EVENT_RETIRED",
    "EVENT_TYPES",
    "CanonicalEventValidationError",
    "CanonicalEvent",
]
