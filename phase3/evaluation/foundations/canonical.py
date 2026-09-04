"""Phase 3.3-H.1 (Canonical Memory Ledger) -- `CanonicalMemoryRecord`, a strict runtime
representation of `phase3/schemas/memory_schema.json`.

WHY THIS MODULE EXISTS
--------------------------------------------------------------------------------
`phase3/schemas/memory_schema.json` is the frozen, authoritative canonical memory
ontology, but until this stage nothing in the runtime enforced it: `MemoryFoundationAdapter
.add_memory()` accepts a bare `(memory_id, content, metadata)` triple with no structural
relationship to the schema's required fields (`memory_type`, `source`, `parent_ids`,
`creation_event`, `creation_timestamp`, `lifecycle_state`), so a vendor foundation was, in
practice, the only thing that ever saw anything resembling a persisted "memory" -- the
canonical object existed only on paper. This module makes the canonical schema a strict,
validated, immutable Python object so it can become the AUTHORITATIVE representation at the
write boundary (see `ledger.py` and `canonical_write.py`), never a second competing schema:
every field name, type, and required-ness below is taken directly from
`phase3/schemas/memory_schema.json` and is not extended speculatively.

WHAT THIS MODULE DELIBERATELY DOES NOT DO
--------------------------------------------------------------------------------
No event-ledger semantics (`created`/`retrieved`/`selected`/`used`/... -- see
`relationship_schema.md` section 3), no update/versioning/supersession *enforcement* (the
schema's `superseded_by` field is represented and preserved, but nothing here implements the
supersession workflow), no retrieval/selection logic, no derivation-policy logic. Those are
explicitly out of scope for H.1 (see PHASE3_3_H1_CANONICAL_MEMORY_LEDGER.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Optional, Tuple

from phase3.evaluation.foundations.security import enforce_foundation_call_boundary

# ---------------------------------------------------------------------------
# Enum vocabulary -- copied verbatim from phase3/schemas/memory_schema.json. This module
# does not invent, rename, or extend any of these values.
# ---------------------------------------------------------------------------

MEMORY_TYPE_FOUNDATION = "foundation"
MEMORY_TYPE_DERIVED = "derived"
MEMORY_TYPES: Tuple[str, ...] = (MEMORY_TYPE_FOUNDATION, MEMORY_TYPE_DERIVED)

SOURCE_TYPE_PHASE2_UMR = "phase2_umr"
SOURCE_TYPE_DERIVATION_EVENT = "derivation_event"
SOURCE_TYPE_FUTURE_OBSERVATION = "future_observation"
SOURCE_TYPES: Tuple[str, ...] = (
    SOURCE_TYPE_PHASE2_UMR,
    SOURCE_TYPE_DERIVATION_EVENT,
    SOURCE_TYPE_FUTURE_OBSERVATION,
)

LIFECYCLE_CREATED = "CREATED"
LIFECYCLE_ACTIVE = "ACTIVE"
LIFECYCLE_RETIRED = "RETIRED"
LIFECYCLE_STATES: Tuple[str, ...] = (LIFECYCLE_CREATED, LIFECYCLE_ACTIVE, LIFECYCLE_RETIRED)


class CanonicalValidationError(ValueError):
    """Raised when a `CanonicalMemoryRecord` (or data destined to become one) violates
    `phase3/schemas/memory_schema.json`. Construction of an invalid record must fail loudly
    -- there is no silent-coercion path anywhere in this module."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CanonicalValidationError(message)


def _validate_source(source: Mapping[str, Any]) -> None:
    _require(isinstance(source, Mapping), "source must be an object/mapping.")
    _require("source_type" in source, "source.source_type is required.")
    _require(
        source["source_type"] in SOURCE_TYPES,
        f"source.source_type {source.get('source_type')!r} is not one of {SOURCE_TYPES!r}.",
    )


def _validate_timestamp(value: str) -> None:
    _require(isinstance(value, str) and bool(value), "creation_timestamp must be a non-empty string.")
    # ISO-8601 UTC, per the schema's format: date-time. `datetime.fromisoformat` rejects a
    # bare trailing "Z" prior to Python 3.11's relaxed parser; this repo pins 3.11 (see
    # PHASE3_3_H1 audit), but we normalize defensively rather than depend on that pin.
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise CanonicalValidationError(
            f"creation_timestamp {value!r} is not a valid ISO-8601 date-time: {exc}"
        ) from exc


@dataclass(frozen=True)
class CanonicalMemoryRecord:
    """Strict, immutable runtime representation of one `memory_schema.json` record.

    This is MAMBench's authoritative memory identity/content/metadata/provenance object --
    see `PHASE3_3_H1_CANONICAL_MEMORY_LEDGER.md` for the architectural role this plays
    relative to a vendor foundation's own storage. Construction validates every schema
    constraint (required fields, enum membership, the parent_ids/memory_type relationship)
    and additionally runs `content` through the existing evaluator/agent leakage boundary
    (`foundations.security.enforce_foundation_call_boundary`, reused verbatim, never
    reimplemented) -- no evaluator-only/gold-shaped field can enter a canonical record.

    Fields mirror `phase3/schemas/memory_schema.json` exactly; no speculative field is
    added beyond it.
    """

    memory_id: str
    memory_type: str
    content: Mapping[str, Any]
    source: Mapping[str, Any]
    parent_ids: Tuple[str, ...]
    creation_event: str
    creation_timestamp: str
    lifecycle_state: str
    equivalent_to: Optional[Tuple[str, ...]] = None
    conflicts_with: Optional[Tuple[str, ...]] = None
    superseded_by: Optional[str] = None

    def __post_init__(self) -> None:
        _require(isinstance(self.memory_id, str) and bool(self.memory_id), "memory_id must be a non-empty string.")
        _require(self.memory_type in MEMORY_TYPES, f"memory_type {self.memory_type!r} is not one of {MEMORY_TYPES!r}.")
        _require(isinstance(self.content, Mapping), "content must be an object/mapping.")
        _validate_source(self.source)
        _require(isinstance(self.parent_ids, tuple), "parent_ids must be a tuple (canonicalized, immutable).")
        _require(all(isinstance(p, str) and p for p in self.parent_ids), "every parent_id must be a non-empty string.")
        if self.memory_type == MEMORY_TYPE_FOUNDATION:
            _require(len(self.parent_ids) == 0, "parent_ids MUST be empty for memory_type=foundation.")
        else:
            _require(len(self.parent_ids) > 0, "parent_ids MUST be non-empty for memory_type=derived.")
        _require(
            isinstance(self.creation_event, str) and bool(self.creation_event),
            "creation_event must be a non-empty string.",
        )
        _validate_timestamp(self.creation_timestamp)
        _require(
            self.lifecycle_state in LIFECYCLE_STATES,
            f"lifecycle_state {self.lifecycle_state!r} is not one of {LIFECYCLE_STATES!r}.",
        )
        if self.equivalent_to is not None:
            _require(isinstance(self.equivalent_to, tuple), "equivalent_to must be a tuple when present.")
        if self.conflicts_with is not None:
            _require(isinstance(self.conflicts_with, tuple), "conflicts_with must be a tuple when present.")
        if self.superseded_by is not None:
            _require(isinstance(self.superseded_by, str) and bool(self.superseded_by), "superseded_by must be a non-empty string when present.")

        # No evaluator/gold data may enter the canonical record's content -- the
        # authoritative write boundary, reused verbatim from the existing security module.
        enforce_foundation_call_boundary(dict(self.content))

    # -- serialization ------------------------------------------------------------------
    # Explicit, documented, round-trip-tested (see test_canonical_memory_ledger_h1.py) --
    # the ledger persists exactly this shape, never a foundation-native shape.

    def to_dict(self) -> dict:
        return {
            "memory_id": self.memory_id,
            "memory_type": self.memory_type,
            "content": dict(self.content),
            "source": dict(self.source),
            "parent_ids": list(self.parent_ids),
            "creation_event": self.creation_event,
            "creation_timestamp": self.creation_timestamp,
            "lifecycle_state": self.lifecycle_state,
            "equivalent_to": list(self.equivalent_to) if self.equivalent_to is not None else None,
            "conflicts_with": list(self.conflicts_with) if self.conflicts_with is not None else None,
            "superseded_by": self.superseded_by,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CanonicalMemoryRecord":
        return cls(
            memory_id=data["memory_id"],
            memory_type=data["memory_type"],
            content=data["content"],
            source=data["source"],
            parent_ids=tuple(data.get("parent_ids") or ()),
            creation_event=data["creation_event"],
            creation_timestamp=data["creation_timestamp"],
            lifecycle_state=data["lifecycle_state"],
            equivalent_to=tuple(data["equivalent_to"]) if data.get("equivalent_to") is not None else None,
            conflicts_with=tuple(data["conflicts_with"]) if data.get("conflicts_with") is not None else None,
            superseded_by=data.get("superseded_by"),
        )

    def identity_fields(self) -> Tuple[Any, ...]:
        """The fields that define whether two records with the same `memory_id` are the
        SAME canonical memory (byte/content/provenance identical, per the H.1 idempotency
        policy) versus a genuine collision. Deliberately excludes nothing that the schema
        treats as content/provenance -- includes everything except nothing; see
        `ledger.CanonicalMemoryLedger.put` for how this is used."""
        return (
            self.memory_id,
            self.memory_type,
            _freeze(self.content),
            _freeze(self.source),
            self.parent_ids,
            self.creation_event,
            self.creation_timestamp,
            self.lifecycle_state,
            self.equivalent_to,
            self.conflicts_with,
            self.superseded_by,
        )


def _freeze(value: Any) -> Any:
    """Deterministic, hashable/comparable projection of a JSON-like value, for the
    identical-vs-collision comparison in `identity_fields()`. Not used for persistence."""
    if isinstance(value, Mapping):
        return tuple(sorted((k, _freeze(v)) for k, v in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v) for v in value)
    return value


__all__ = [
    "MEMORY_TYPE_FOUNDATION",
    "MEMORY_TYPE_DERIVED",
    "MEMORY_TYPES",
    "SOURCE_TYPE_PHASE2_UMR",
    "SOURCE_TYPE_DERIVATION_EVENT",
    "SOURCE_TYPE_FUTURE_OBSERVATION",
    "SOURCE_TYPES",
    "LIFECYCLE_CREATED",
    "LIFECYCLE_ACTIVE",
    "LIFECYCLE_RETIRED",
    "LIFECYCLE_STATES",
    "CanonicalValidationError",
    "CanonicalMemoryRecord",
]
