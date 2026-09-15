"""Phase 5.3 -- Experiment / Run / Episode identity.

WHAT EXISTS ALREADY (inspected before writing this)
--------------------------------------------------------------------------------
- `contracts/evaluation_run.schema.json::EvaluationRun` already has a caller-supplied,
  plain-string `run_id` and `task_id` ("IMMUTABLE identity field... never reassigned or
  reused"), but no `experiment_id` above it and no sub-run grouping below it. It is also
  Phase-3-only -- no Phase 4 attack campaign constructs one.
- `run_config.py::RunConfigRecord`/`RunConfigLedger` identify a deterministic
  *configuration* (embedding/reranker/retrieval settings) via a content-derived
  `config_fingerprint` -- this is NOT run identity. Two different runs (different times,
  different attacks, different campaigns) can and should share the same
  `config_fingerprint` if their configuration is literally identical; that is the whole
  point of that module (§ "so a clean run and a later manipulated run can be proven
  identical except for the injected manipulation"). Run identity is therefore a
  genuinely separate concern from configuration identity, and this module does not
  duplicate or replace `RunConfigLedger`.
- `experiment_boundary.py::ExperimentBoundaryRecord` already establishes the precedent
  this module follows: when a new concept (there: a store-reset boundary; here: a
  run/episode grouping) does not fit naturally as an eighth `CanonicalEvent` type or an
  extra field grafted onto an existing frozen record, the codebase's own decided answer
  is "a genuinely separate record/ledger, not a shoehorned extension" (see that module's
  own "WHY A SEPARATE TYPE/LEDGER" section, which this module's design directly follows).
- "episode" as a word appears in this repository only inside Graphiti's own
  vendor-specific adapter/mocks (`graphiti_real_adapter.py`, `mock_graphiti.py`) -- a
  foundation-native concept, not a benchmark-owned one. There is no existing
  benchmark-owned episode concept to reuse or collide with.
- `experiment_boundary.py`'s own docstring independently names the real unit of grouping
  this framework already uses operationally: "a fresh RESET+INGEST happens once per
  unique (dataset, session_or_haystack) group" (`campaign_formal_runner.py`). This is the
  natural, evidence-grounded definition of "episode" adopted below -- not an invented
  one: one episode = one (dataset, session_or_haystack) isolation group within a run,
  which may itself contain many tasks (e.g. many LoCoMo questions asked against the same
  ingested conversation).

THE GAP THIS MODULE CLOSES (contract requirement OR-14)
--------------------------------------------------------------------------------
No `experiment_id`/`run_id`/`episode_id` hierarchy exists anywhere Phase 4 can use, and
Phase 3's own `run_id` has no `experiment_id` above it. Reconstructing "which events
belong to the same controlled experiment" today would require reading directory names or
script literals -- exactly what the master prompt's Stage 5.3 PASS condition
("reconstructable... without relying on filenames, timestamps, directory structure, or
implicit relationships") rules out.

WHY A SEPARATE MEMBERSHIP LEDGER, NOT NEW FIELDS ON CanonicalEvent
--------------------------------------------------------------------------------
`CanonicalEvent` (frozen) has no `experiment_id`/`run_id`/`episode_id` fields, and
Stage 5.2 already decided not to edit that file. `Phase5Event` (Stage 5.2, this
package) DOES carry optional `experiment_id`/`run_id`/`task_id` fields, but relying on
per-event, caller-populated copies as the sole source of truth would let two events
silently disagree about which run they belong to, with nothing to catch the
inconsistency. Following the exact precedent `CanonicalEventLedger` itself set (append
validated against `CanonicalMemoryLedger`'s existence, never a second, independent
bookkeeping mechanism), this module adds `EventRunMembership`/`EventRunMembershipLedger`:
one authoritative, append-only, existence-checked join between ANY event id (from either
schema -- `EVT-...` or `P5EVT-...`) and the run/episode it belongs to. A `Phase5Event`'s
own `experiment_id`/`run_id` fields, where populated, are a convenience denormalization
for callers that already know them at construction time -- `EventRunMembershipLedger` is
the authority Stage 5.8's trace/graph assembly must actually query.

STORAGE / COLLISION / IMMUTABILITY DISCIPLINE
--------------------------------------------------------------------------------
Mirrors `ledger.py`/`event_ledger.py`/`experiment_boundary.py` exactly: one append-only
JSONL file per record type, `json.dumps(..., sort_keys=True)` + `flush()` + `os.fsync()`
per write, no `update()`/`delete()`, identical-payload re-append is an idempotent no-op,
differing-payload re-append raises loudly. No new persistence mechanism is introduced.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple, Union

from phase3.evaluation.security.reproducibility import fingerprint

RUN_ID_PREFIX = "RUN"
EPISODE_ID_PREFIX = "EPI"

APPEND_CREATED = "CREATED"
APPEND_IDEMPOTENT = "IDEMPOTENT_NOOP"
APPEND_RESULTS: Tuple[str, ...] = (APPEND_CREATED, APPEND_IDEMPOTENT)

EVENT_SCHEMA_CANONICAL_EVENT = "canonical_event"
EVENT_SCHEMA_PHASE5_EVENT = "phase5_event"
EVENT_SCHEMAS: Tuple[str, ...] = (EVENT_SCHEMA_CANONICAL_EVENT, EVENT_SCHEMA_PHASE5_EVENT)

_RUNS_FILE = "experiment_runs.jsonl"
_MEMBERSHIP_FILE = "event_run_membership.jsonl"


class RunIdentityValidationError(ValueError):
    """Raised when an `ExperimentRunRecord` or `EventRunMembership` is malformed. Fails
    loudly -- no silent coercion, mirroring every other identity record in this
    framework."""


class RunCollisionError(ValueError):
    """Raised when a `run_id` already present in the ledger is appended again with a
    different payload."""


class UnknownRunError(KeyError):
    """Raised by `EventRunMembershipLedger.append()` when the referenced `run_id` has no
    `ExperimentRunRecord` -- mirrors `CanonicalEventLedger`'s existence-check discipline
    against `CanonicalMemoryLedger`."""


class MembershipCollisionError(ValueError):
    """Raised when an `event_id` already has a membership record with a different
    `run_id`/`episode_id` -- an event belongs to exactly one run, never two."""


class UnknownEventError(KeyError):
    """P1 fix (2026-09-14) -- raised by `EventRunMembershipLedger.append()` when the
    relevant event ledger for `membership.event_schema` was supplied to this ledger's
    constructor AND the referenced `event_id` does not exist there. Only raised when
    that existence-check is actually possible (see `EventRunMembershipLedger`'s own
    docstring for why the check is optional-but-strict rather than unconditional)."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RunIdentityValidationError(message)


def _validate_timestamp(value: str) -> None:
    _require(isinstance(value, str) and bool(value), "timestamp must be a non-empty string.")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise RunIdentityValidationError(f"timestamp {value!r} is not a valid ISO-8601 date-time: {exc}") from exc


def _append_jsonl(path: Path, obj: Mapping) -> None:
    line = json.dumps(obj, sort_keys=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
        fh.flush()
        os.fsync(fh.fileno())


# ---------------------------------------------------------------------------
# Factories -- content-derived, same reasoning as event_identity.generate_event_id():
# deterministic (never uuid4()), so two calls describing the identical run/episode
# coalesce onto the same id. A caller MAY use its own id instead (factory-optional,
# exactly like generate_event_id()) -- ExperimentRunRecord does not require ids to come
# from these functions.
# ---------------------------------------------------------------------------


def generate_run_id(experiment_id: str, dataset: str, scope: Mapping[str, Any], actor: str, started_at: str) -> str:
    payload = {
        "experiment_id": experiment_id,
        "dataset": dataset,
        "scope": dict(scope),
        "actor": actor,
        "started_at": started_at,
    }
    return f"{RUN_ID_PREFIX}-{fingerprint(payload)}"


def generate_episode_id(run_id: str, dataset: str, session_or_haystack: str) -> str:
    """One episode = one (dataset, session_or_haystack) isolation group within a run --
    the same grouping `campaign_formal_runner.py`'s RESET+INGEST-per-group pattern
    already performs operationally (see module docstring). Deterministic: the same
    isolation group within the same run always yields the same episode_id, so repeated
    events against that group (e.g. several tasks asked of the same ingested
    conversation) naturally share one episode identity without a caller needing to mint
    or cache one.
    """
    payload = {"run_id": run_id, "dataset": dataset, "session_or_haystack": session_or_haystack}
    return f"{EPISODE_ID_PREFIX}-{fingerprint(payload)}"


@dataclass(frozen=True)
class ExperimentRunRecord:
    """One registered run within an experiment. `experiment_id` is a stable, caller-chosen
    label spanning potentially many runs (e.g. `"phase4-farma-campaign"`,
    `"phase3-condition-b-locomo"`) -- deliberately NOT content-derived, for the same
    reason `attack_id` is a plain chosen constant rather than a fingerprint: it names a
    persistent unit of work, not one immutable observed fact.

    `scope` is free-form (mirrors `ExperimentBoundaryRecord.scope` /
    `EvaluationRun.configuration_identity`'s own "require SOME identity be recorded, not
    a fixed shape" precedent) -- e.g. `{"condition": "RETRIEVED_MEMORY"}` for a Phase 3
    run or `{"attack_id": "farma", "campaign": "milestone5"}` for a Phase 4 attack
    campaign. This module does not force Phase 4 attacks to add a new rigid field to
    their own artifact dataclasses merely to register a run.
    """

    experiment_id: str
    run_id: str
    dataset: str
    scope: Mapping[str, Any]
    started_at: str
    actor: str
    reason: str
    dataset_version: Optional[str] = None

    def __post_init__(self) -> None:
        _require(isinstance(self.experiment_id, str) and bool(self.experiment_id), "experiment_id must be a non-empty string.")
        _require(isinstance(self.run_id, str) and bool(self.run_id), "run_id must be a non-empty string.")
        _require(isinstance(self.dataset, str) and bool(self.dataset), "dataset must be a non-empty string.")
        _require(isinstance(self.scope, Mapping), "scope must be an object/mapping.")
        _validate_timestamp(self.started_at)
        _require(isinstance(self.actor, str) and bool(self.actor), "actor must be a non-empty string.")
        _require(isinstance(self.reason, str) and bool(self.reason), "reason must be a non-empty string.")
        if self.dataset_version is not None:
            _require(isinstance(self.dataset_version, str) and bool(self.dataset_version), "dataset_version, if given, must be a non-empty string.")

    def to_dict(self) -> dict:
        return {
            "experiment_id": self.experiment_id,
            "run_id": self.run_id,
            "dataset": self.dataset,
            "dataset_version": self.dataset_version,
            "scope": dict(self.scope),
            "started_at": self.started_at,
            "actor": self.actor,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExperimentRunRecord":
        return cls(
            experiment_id=data["experiment_id"],
            run_id=data["run_id"],
            dataset=data["dataset"],
            dataset_version=data.get("dataset_version"),
            scope=data["scope"],
            started_at=data["started_at"],
            actor=data["actor"],
            reason=data["reason"],
        )

    def identity_fields(self) -> Tuple[Any, ...]:
        return (
            self.experiment_id, self.run_id, self.dataset, self.dataset_version,
            tuple(sorted(self.scope.items())), self.started_at, self.actor, self.reason,
        )


class ExperimentRunLedger:
    """Benchmark-owned, append-only store of `ExperimentRunRecord`s, keyed by `run_id`.
    Mirrors `CanonicalMemoryLedger`'s exact persistence/collision/reload discipline."""

    def __init__(self, storage_dir: Union[str, Path]) -> None:
        self._dir = Path(storage_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / _RUNS_FILE
        self._runs: Dict[str, ExperimentRunRecord] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            with open(self._path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    record = ExperimentRunRecord.from_dict(json.loads(line))
                    self._runs[record.run_id] = record

    def register(self, record: ExperimentRunRecord) -> str:
        existing = self._runs.get(record.run_id)
        if existing is not None:
            if existing.identity_fields() == record.identity_fields():
                return APPEND_IDEMPOTENT
            raise RunCollisionError(
                f"run_id {record.run_id!r} already registered with different content -- "
                f"refusing to overwrite. Existing={existing.to_dict()!r} New={record.to_dict()!r}"
            )
        self._runs[record.run_id] = record
        _append_jsonl(self._path, record.to_dict())
        return APPEND_CREATED

    def get(self, run_id: str) -> Optional[ExperimentRunRecord]:
        return self._runs.get(run_id)

    def exists(self, run_id: str) -> bool:
        return run_id in self._runs

    def runs_for_experiment(self, experiment_id: str) -> Tuple[ExperimentRunRecord, ...]:
        return tuple(r for r in self._runs.values() if r.experiment_id == experiment_id)

    def list_runs(self) -> Tuple[ExperimentRunRecord, ...]:
        return tuple(self._runs.values())


@dataclass(frozen=True)
class EventRunMembership:
    """One event's membership in exactly one run (and, optionally, one episode within
    that run). `event_id` is deliberately untyped as to which schema minted it (`EVT-...`
    from `CanonicalEvent` or `P5EVT-...` from `Phase5Event`) -- `event_schema` records
    which, so a reader never has to guess from the id's prefix (which `event_identity.py`
    itself documents as advisory-only, never authoritative)."""

    event_id: str
    event_schema: str
    run_id: str
    recorded_at: str
    episode_id: Optional[str] = None

    def __post_init__(self) -> None:
        _require(isinstance(self.event_id, str) and bool(self.event_id), "event_id must be a non-empty string.")
        _require(self.event_schema in EVENT_SCHEMAS, f"event_schema {self.event_schema!r} is not one of {EVENT_SCHEMAS!r}.")
        _require(isinstance(self.run_id, str) and bool(self.run_id), "run_id must be a non-empty string.")
        _validate_timestamp(self.recorded_at)
        if self.episode_id is not None:
            _require(isinstance(self.episode_id, str) and bool(self.episode_id), "episode_id, if given, must be a non-empty string.")

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_schema": self.event_schema,
            "run_id": self.run_id,
            "episode_id": self.episode_id,
            "recorded_at": self.recorded_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EventRunMembership":
        return cls(
            event_id=data["event_id"],
            event_schema=data["event_schema"],
            run_id=data["run_id"],
            episode_id=data.get("episode_id"),
            recorded_at=data["recorded_at"],
        )

    def identity_fields(self) -> Tuple[Any, ...]:
        return (self.event_id, self.event_schema, self.run_id, self.episode_id, self.recorded_at)


class EventRunMembershipLedger:
    """Append-only join between an event id (either schema) and the run/episode it
    belongs to. Constructed WITH an `ExperimentRunLedger` so `append()` can enforce
    "every membership references a registered run" -- exactly the existence-check
    relationship `CanonicalEventLedger` holds with `CanonicalMemoryLedger`.

    P1 fix (2026-09-14): this module's own docstring already claims membership is
    "one authoritative, append-only, EXISTENCE-CHECKED join between ANY event id...
    and the run/episode it belongs to" -- but `append()` previously only checked that
    `run_id` was registered, never that `event_id` itself actually existed in the
    matching event ledger, so a caller could register membership for a fabricated
    event_id and nothing would catch it. `canonical_event_ledger`/`phase5_event_ledger`
    are now OPTIONAL constructor parameters (default `None`, preserving every existing
    call site's exact behavior unchanged) -- when the relevant ledger for a
    membership's `event_schema` is supplied, `append()` now verifies the event_id
    actually exists there before accepting the membership. Not made a hard, non-optional
    requirement here because many real call sites and this module's own test fixtures
    construct this ledger before, or independently of, the event ledgers it would need
    to check -- an optional, additive check that is strict whenever the caller has
    the relevant ledger available is the safe way to close this gap without a breaking
    signature change across every `EventRunMembershipLedger(...)` construction in the
    repository.
    """

    def __init__(
        self,
        storage_dir: Union[str, Path],
        run_ledger: ExperimentRunLedger,
        *,
        canonical_event_ledger: Optional[object] = None,
        phase5_event_ledger: Optional[object] = None,
    ) -> None:
        self._dir = Path(storage_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / _MEMBERSHIP_FILE
        self._run_ledger = run_ledger
        self._canonical_event_ledger = canonical_event_ledger
        self._phase5_event_ledger = phase5_event_ledger
        self._memberships: Dict[str, EventRunMembership] = {}
        self._load()

    def _event_exists(self, event_id: str, event_schema: str) -> Optional[bool]:
        """Returns True/False when the relevant event ledger for `event_schema` was
        supplied to this ledger's constructor, or `None` when it was not (meaning: no
        existence-check is possible, matching this ledger's pre-fix behavior)."""
        if event_schema == EVENT_SCHEMA_CANONICAL_EVENT:
            if self._canonical_event_ledger is None:
                return None
            return self._canonical_event_ledger.get_event(event_id) is not None
        if event_schema == EVENT_SCHEMA_PHASE5_EVENT:
            if self._phase5_event_ledger is None:
                return None
            return self._phase5_event_ledger.exists(event_id)
        return None

    def _load(self) -> None:
        if self._path.exists():
            with open(self._path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    m = EventRunMembership.from_dict(json.loads(line))
                    self._memberships[m.event_id] = m

    def append(self, membership: EventRunMembership) -> str:
        if not self._run_ledger.exists(membership.run_id):
            raise UnknownRunError(
                f"cannot record membership for event_id {membership.event_id!r}: run_id "
                f"{membership.run_id!r} is not registered in the ExperimentRunLedger. "
                "Runs must be registered before any event membership referencing them "
                "(authoritative write order, mirroring canonical memory-before-event ordering)."
            )
        exists = self._event_exists(membership.event_id, membership.event_schema)
        if exists is False:
            raise UnknownEventError(
                f"cannot record membership for event_id {membership.event_id!r} "
                f"(event_schema={membership.event_schema!r}): no such event exists in the "
                "event ledger supplied to this EventRunMembershipLedger. A membership "
                "record must reference a real, already-persisted event -- never a "
                "fabricated or not-yet-written one."
            )
        existing = self._memberships.get(membership.event_id)
        if existing is not None:
            if existing.identity_fields() == membership.identity_fields():
                return APPEND_IDEMPOTENT
            raise MembershipCollisionError(
                f"event_id {membership.event_id!r} already has a membership record with "
                f"different run/episode -- an event belongs to exactly one run. "
                f"Existing={existing.to_dict()!r} New={membership.to_dict()!r}"
            )
        self._memberships[membership.event_id] = membership
        _append_jsonl(self._path, membership.to_dict())
        return APPEND_CREATED

    def run_for_event(self, event_id: str) -> Optional[EventRunMembership]:
        return self._memberships.get(event_id)

    def events_for_run(self, run_id: str) -> Tuple[str, ...]:
        return tuple(m.event_id for m in self._memberships.values() if m.run_id == run_id)

    def events_for_episode(self, episode_id: str) -> Tuple[str, ...]:
        return tuple(m.event_id for m in self._memberships.values() if m.episode_id == episode_id)


__all__ = [
    "RUN_ID_PREFIX",
    "EPISODE_ID_PREFIX",
    "EVENT_SCHEMA_CANONICAL_EVENT",
    "EVENT_SCHEMA_PHASE5_EVENT",
    "EVENT_SCHEMAS",
    "APPEND_CREATED",
    "APPEND_IDEMPOTENT",
    "APPEND_RESULTS",
    "RunIdentityValidationError",
    "RunCollisionError",
    "UnknownRunError",
    "MembershipCollisionError",
    "UnknownEventError",
    "generate_run_id",
    "generate_episode_id",
    "ExperimentRunRecord",
    "ExperimentRunLedger",
    "EventRunMembership",
    "EventRunMembershipLedger",
]
