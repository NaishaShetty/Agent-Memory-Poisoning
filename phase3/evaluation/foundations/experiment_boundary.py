"""Phase 3.3-H.2-R (Canonical Event Ledger Remediation) -- `ExperimentBoundaryRecord` /
`ExperimentBoundaryLedger`: a genuinely SEPARATE, benchmark-owned representation of a
foundation/experiment isolation boundary (e.g. a RESET between two independent ingestion
groups), kept structurally distinct from `CanonicalEvent`'s memory-lifecycle history.

WHY A SEPARATE TYPE/LEDGER, NOT AN 8th CanonicalEvent TYPE
--------------------------------------------------------------------------------
`relationship_schema.md` section 3 defines exactly seven event types (`created`,
`retrieved`, `selected`, `used`, `derived`, `superseded`, `retired`) -- all seven concern
the lifecycle of ONE OR MORE SPECIFIC canonical memories (`CanonicalEvent.memory_ids` is
required non-empty, enforced by H.2). An experiment/foundation-store RESET concerns no
specific canonical memory at all -- it is an operation on the STORE (or a scoped subset of
it, e.g. one `(dataset, session_or_haystack)` isolation group's slice of a shared store, per
`PHASE3_3_F_PRECAMPAIGN_METHODOLOGY.md`'s isolation model and `campaign_formal_runner.py`'s
own "a fresh RESET+INGEST happens once per unique (dataset, session_or_haystack) group"
docstring), not on a memory.

Two designs were considered:

1. Add an 8th event type (e.g. `experiment_reset`) to `CanonicalEvent`, with
   `memory_ids` relaxed to allow empty for this one type.
2. A genuinely separate record/ledger with NO memory_ids field at all.

(1) was rejected for two reasons: it requires changing the frozen `relationship_schema.md`
event-type table (the mission's own "make the smallest explicit schema change necessary"
principle argues against a document change when a zero-schema-change alternative exists),
and it would require carving a `memory_ids`-required exception into `CanonicalEvent`'s
`__post_init__`, weakening an invariant H.2 established for every other event type for the
sake of one structurally-different case.

(2) -- what this module implements -- makes confusion with `MEMORY_RETIRED`/
`MEMORY_DELETED`/`MEMORY_SUPERSEDED` STRUCTURALLY IMPOSSIBLE, not merely avoided by
convention: `ExperimentBoundaryRecord` is a different Python type, stored in a different
file (`boundaries.jsonl`, never `events.jsonl`), with no shared identity namespace with
`CanonicalEvent`/`CanonicalMemoryRecord` at all, and no field of either type overlaps in
meaning with `lifecycle_state` (`memory_schema.json`'s `CREATED`/`ACTIVE`/`RETIRED`
vocabulary is never referenced by this module). There is no code path anywhere in this
framework that could construct an `ExperimentBoundaryRecord` and interpret it as a
`retired` memory event, because the two are not interchangeable at the type level, and
nothing converts one into the other.

MINIMAL SCOPE
--------------------------------------------------------------------------------
Exactly one boundary type is defined: `BOUNDARY_RESET`, because it is the ONLY boundary
operation this framework's existing, already-documented runtime behavior actually performs
(the RESET+INGEST-per-isolation-group pattern cited above). `BOUNDARY_TYPES` is a tuple
specifically so a future stage can extend it additively if a genuine second boundary kind
is ever needed -- this module does not speculatively add `campaign_start`/`campaign_end`/
any other boundary kind the current architecture does not exhibit.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple, Union

from phase3.evaluation.security.reproducibility import fingerprint

BOUNDARY_RESET = "RESET"
BOUNDARY_TYPES: Tuple[str, ...] = (BOUNDARY_RESET,)

BOUNDARY_ID_PREFIX = "BND"


class ExperimentBoundaryValidationError(ValueError):
    """Raised when an `ExperimentBoundaryRecord` is malformed. Fails loudly -- no silent
    coercion, mirroring `canonical.py`/`canonical_event.py`'s exact discipline."""


class ExperimentBoundaryCollisionError(ValueError):
    """Raised when a `boundary_id` already present in the ledger is appended again with a
    different payload."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ExperimentBoundaryValidationError(message)


def _validate_timestamp(value: str) -> None:
    _require(isinstance(value, str) and bool(value), "timestamp must be a non-empty string.")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ExperimentBoundaryValidationError(f"timestamp {value!r} is not a valid ISO-8601 date-time: {exc}") from exc


@dataclass(frozen=True)
class ExperimentBoundaryRecord:
    """One experiment/foundation-store isolation boundary. Concerns NO specific canonical
    memory -- there is deliberately no `memory_ids` field on this type at all (see module
    docstring). `scope` is a free-form (any JSON-serializable mapping) description of what
    was reset -- e.g. `{"dataset": "longmemeval", "pool_key": "haystack-3", "foundation_name":
    "a-mem"}` -- deliberately not tightly typed, mirroring `EvaluationRun.configuration_
    identity`'s own "the exact shape is experimental, only require SOME identity be
    recorded" design choice (`contracts/evaluation_run.schema.json`).
    """

    boundary_id: str
    boundary_type: str
    scope: Mapping[str, Any]
    timestamp: str
    actor: str
    reason: str

    def __post_init__(self) -> None:
        _require(isinstance(self.boundary_id, str) and bool(self.boundary_id), "boundary_id must be a non-empty string.")
        _require(self.boundary_type in BOUNDARY_TYPES, f"boundary_type {self.boundary_type!r} is not one of {BOUNDARY_TYPES!r}.")
        _require(isinstance(self.scope, Mapping), "scope must be an object/mapping.")
        _validate_timestamp(self.timestamp)
        _require(isinstance(self.actor, str) and bool(self.actor), "actor must be a non-empty string.")
        _require(isinstance(self.reason, str) and bool(self.reason), "reason must be a non-empty string.")

    def to_dict(self) -> dict:
        return {
            "boundary_id": self.boundary_id,
            "boundary_type": self.boundary_type,
            "scope": dict(self.scope),
            "timestamp": self.timestamp,
            "actor": self.actor,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExperimentBoundaryRecord":
        return cls(
            boundary_id=data["boundary_id"],
            boundary_type=data["boundary_type"],
            scope=data["scope"],
            timestamp=data["timestamp"],
            actor=data["actor"],
            reason=data["reason"],
        )

    def identity_fields(self) -> Tuple[Any, ...]:
        return (
            self.boundary_id,
            self.boundary_type,
            _freeze(self.scope),
            self.timestamp,
            self.actor,
            self.reason,
        )


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return tuple(sorted((k, _freeze(v)) for k, v in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v) for v in value)
    return value


_BOUNDARIES_FILE = "boundaries.jsonl"

APPEND_CREATED = "CREATED"
APPEND_IDEMPOTENT = "IDEMPOTENT_NOOP"


def _append_jsonl(path: Path, obj: dict) -> None:
    line = json.dumps(obj, sort_keys=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
        fh.flush()
        os.fsync(fh.fileno())


class ExperimentBoundaryLedger:
    """Benchmark-owned, append-only store of `ExperimentBoundaryRecord`s. Deliberately
    carries NO dependency on `CanonicalMemoryLedger`/`CanonicalEventLedger` -- a boundary
    record concerns no canonical memory, so there is nothing to link-check against (unlike
    `CanonicalEventLedger`, which requires one for exactly that reason).

    Same append-only/collision/idempotency/persistence discipline as
    `ledger.CanonicalMemoryLedger` and `event_ledger.CanonicalEventLedger`: identical
    `boundary_id` + identical payload -> idempotent no-op; identical `boundary_id` +
    different payload -> `ExperimentBoundaryCollisionError`, existing record untouched.
    Single-process/single-writer; no cross-process lock (same explicit limitation as the
    other two ledgers).
    """

    def __init__(self, storage_dir: Union[str, Path]) -> None:
        self._dir = Path(storage_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / _BOUNDARIES_FILE
        self._by_id: Dict[str, ExperimentBoundaryRecord] = {}
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
                record = ExperimentBoundaryRecord.from_dict(json.loads(line))
                self._by_id[record.boundary_id] = record
                self._order.append(record.boundary_id)

    def append(self, record: ExperimentBoundaryRecord) -> str:
        existing = self._by_id.get(record.boundary_id)
        if existing is not None:
            if existing.identity_fields() == record.identity_fields():
                return APPEND_IDEMPOTENT
            raise ExperimentBoundaryCollisionError(
                f"boundary_id {record.boundary_id!r} already exists with a different payload -- "
                f"refusing to overwrite. Existing={existing.to_dict()!r} New={record.to_dict()!r}"
            )
        self._by_id[record.boundary_id] = record
        self._order.append(record.boundary_id)
        _append_jsonl(self._path, record.to_dict())
        return APPEND_CREATED

    def get_boundary(self, boundary_id: str) -> "ExperimentBoundaryRecord | None":
        return self._by_id.get(boundary_id)

    def all_boundaries(self) -> Tuple[ExperimentBoundaryRecord, ...]:
        return tuple(self._by_id[bid] for bid in self._order)


# ---------------------------------------------------------------------------
# Phase 3.3-H.2-R2 -- benchmark-owned boundary ID factory + integration surface (mirrors
# event_identity.py's generate_event_id()/build_canonical_event() exactly, for the same
# reasons: content-derived via the same repository-standard `fingerprint()` primitive,
# never uuid4(); additive, never bypasses ExperimentBoundaryLedger.append()'s own
# collision/idempotency check).
# ---------------------------------------------------------------------------


def generate_boundary_id(boundary_type: str, scope: Mapping[str, Any], timestamp: str, actor: str, reason: str) -> str:
    """The MAMBench Boundary ID Factory -- deterministic, content-derived, mirrors
    `event_identity.generate_event_id()`'s exact design and rationale."""
    payload = {"boundary_type": boundary_type, "scope": dict(scope), "timestamp": timestamp, "actor": actor, "reason": reason}
    return f"{BOUNDARY_ID_PREFIX}-{fingerprint(payload)}"


def looks_like_generated_boundary_id(candidate: str) -> bool:
    """Advisory only -- mirrors `event_identity.looks_like_generated_event_id()`. Never
    used by `ExperimentBoundaryRecord`/`ExperimentBoundaryLedger` for validation."""
    return isinstance(candidate, str) and candidate.startswith(f"{BOUNDARY_ID_PREFIX}-")


def build_reset_boundary(scope: Mapping[str, Any], timestamp: str, actor: str, reason: str) -> ExperimentBoundaryRecord:
    """The recommended single integration surface for recording a RESET boundary --
    mirrors `event_identity.build_canonical_event()`. Deliberately supports ONLY
    `BOUNDARY_RESET` (the one boundary operation this framework's documented runtime
    behavior actually performs, per the module docstring) -- no `START`/`END`/
    `CHECKPOINT` variant is added speculatively. The lower-level
    `ExperimentBoundaryRecord(...)` constructor remains available and is not deprecated.
    """
    boundary_id = generate_boundary_id(BOUNDARY_RESET, scope, timestamp, actor, reason)
    return ExperimentBoundaryRecord(
        boundary_id=boundary_id, boundary_type=BOUNDARY_RESET, scope=scope,
        timestamp=timestamp, actor=actor, reason=reason,
    )


# ---------------------------------------------------------------------------
# Phase 3.3-H.2-R2 -- multi-writer ownership contract (section C)
# ---------------------------------------------------------------------------
#
# DECISION: retain the single-process/single-writer `ExperimentBoundaryLedger` unchanged --
# do NOT add cross-process file locking. `campaign_formal_runner.py`'s OWN existing,
# already-working answer to multi-worker concurrency (its module docstring: "each worker
# writes to its OWN checkpoint file... to avoid any concurrent-write race condition --
# merged only after all workers finish a batch, by `merge_longmemeval_worker_checkpoints
# ()`") is the repository-established convention this module follows: EACH WORKER OWNS ITS
# OWN `storage_dir` (hence its own `boundaries.jsonl`), eliminating concurrent writers to
# any single file by construction, rather than making concurrent writers to one file safe.
# `merge_experiment_boundary_ledgers()` below is the direct analogue of
# `merge_longmemeval_worker_checkpoints()` for this ledger: it folds N independent
# per-worker ledgers into one target ledger using the target's OWN `append()` (so a real
# conflict between two workers' boundary records -- same `boundary_id`, different payload
# -- is still caught by the existing `ExperimentBoundaryCollisionError` path, never
# silently merged away).
#
# This was chosen over introducing file locking because (a) the repository already has a
# working, tested pattern for exactly this problem, (b) locking would be new
# infrastructure this stage's mission explicitly discourages ("do not introduce
# distributed infrastructure unnecessarily"), and (c) no caller in this stage actually
# writes to a shared boundary ledger from multiple processes -- this remains additive,
# not-yet-integrated infrastructure (section D).


def merge_experiment_boundary_ledgers(
    target_storage_dir: Union[str, Path],
    worker_storage_dirs: Sequence[Union[str, Path]],
) -> ExperimentBoundaryLedger:
    """Fold every worker's independent `ExperimentBoundaryLedger` (each at its own
    `storage_dir`, per the ownership contract above) into one `target_storage_dir` ledger.
    Uses the target ledger's own `append()` throughout, so the merge is exactly as
    collision-safe/idempotent as any other append -- a genuine conflict between two
    workers' records raises `ExperimentBoundaryCollisionError` rather than being silently
    resolved. Returns the merged `ExperimentBoundaryLedger`.
    """
    target = ExperimentBoundaryLedger(target_storage_dir)
    for worker_dir in worker_storage_dirs:
        worker_ledger = ExperimentBoundaryLedger(worker_dir)
        for record in worker_ledger.all_boundaries():
            target.append(record)
    return target


__all__ = [
    "BOUNDARY_RESET",
    "BOUNDARY_TYPES",
    "BOUNDARY_ID_PREFIX",
    "ExperimentBoundaryValidationError",
    "ExperimentBoundaryCollisionError",
    "ExperimentBoundaryRecord",
    "ExperimentBoundaryLedger",
    "APPEND_CREATED",
    "APPEND_IDEMPOTENT",
    "generate_boundary_id",
    "looks_like_generated_boundary_id",
    "build_reset_boundary",
    "merge_experiment_boundary_ledgers",
]
