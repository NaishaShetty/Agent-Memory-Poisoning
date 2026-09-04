"""Phase 3.3-H.1 (Canonical Memory Ledger) -- `CanonicalMemoryLedger`, the benchmark-owned,
foundation-independent store of authoritative `CanonicalMemoryRecord`s and their vendor
alias mappings.

ARCHITECTURAL ROLE
--------------------------------------------------------------------------------
    Source / Dataset -> CanonicalMemoryRecord -> CanonicalMemoryLedger -+-> Foundation Adapter -> Vendor Store

This ledger is the left-hand branch: it never talks to Mem0/A-MEM/Graphiti/Letta directly
(see `canonical_write.py` for the orchestration that also drives the right-hand branch). A
`CanonicalMemoryLedger` instance, on its own, can always answer "what is memory X, and what
is its provenance" without asking any vendor foundation anything -- this is INVARIANT 5
(`PHASE3_3_H1_CANONICAL_MEMORY_LEDGER.md`).

STORAGE MODEL
--------------------------------------------------------------------------------
Two append-only JSONL files under one `storage_dir`:

    records.jsonl  -- one line per successful `put()`, the canonical record's `to_dict()`.
    aliases.jsonl  -- one line per successful `set_alias()`,
                      `{"memory_id", "foundation_name", "foundation_memory_id"}`.

Rebuilding the in-memory index is a pure fold over these two files, in order (see `_load`)
-- this is the "canonical ledger reload"/"canonical reconstruction" contract tests exercise.
No SQLite/external database is introduced: the H.1 mission brief asks for "the simplest
robust implementation compatible with the repository," and this framework has no existing
database dependency to build on.

CONCURRENCY -- EXPLICIT LIMITATION
--------------------------------------------------------------------------------
This is a SINGLE-PROCESS, single-writer store. Each `put()`/`set_alias()` call opens the
relevant file in append mode, writes one JSON line, flushes, and fsyncs before returning --
so a single process crashing mid-run leaves at most the file's last line incomplete (never a
torn multi-line write, since each write is one `write()` call of one already-fully-formed
line). There is no cross-process file lock. A campaign that runs multiple OS processes
against the SAME `storage_dir` concurrently (e.g. the currently-running G.1 campaign's
per-dataset worker processes) is out of scope for H.1's ledger -- see
`PHASE3_3_H1_IMPLEMENTATION_REPORT.md` limitations. In practice this is not a regression:
G.1 does not use this ledger at all (H.1 is purely additive), and any future H.1-adopting
caller is expected to give each isolated (dataset, session_or_haystack) ingestion group its
own `storage_dir`, matching the isolation model `PHASE3_3_F_PRECAMPAIGN_METHODOLOGY.md`
already documents for foundation state itself.

COLLISION POLICY
--------------------------------------------------------------------------------
`put()` on a `memory_id` already present in the ledger:
  - IDENTICAL (`identity_fields()` equal) -> idempotent no-op, returns `PUT_IDEMPOTENT`.
    Documented and tested explicitly (`test_canonical_memory_ledger_h1.py`); this is NOT an
    invented general update/versioning semantic -- H.3 owns that.
  - DIFFERENT -> raises `CanonicalCollisionError` immediately. Never overwrites, never
    silently merges, never mints a new id to hide the collision.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Optional, Tuple, Union

from phase3.evaluation.foundations.canonical import CanonicalMemoryRecord

PUT_CREATED = "CREATED"
PUT_IDEMPOTENT = "IDEMPOTENT_NOOP"
PUT_RESULTS: Tuple[str, ...] = (PUT_CREATED, PUT_IDEMPOTENT)


class CanonicalCollisionError(ValueError):
    """Raised when a `memory_id` already present in the ledger is written again with
    different canonical content/provenance/metadata. Per H.1's ID COLLISION POLICY: fail
    loudly, never overwrite, never merge, never mint a substitute id."""


class CanonicalAliasError(KeyError):
    """Raised by `set_alias()` when the referenced `memory_id` has no canonical record in
    this ledger yet -- an alias may only ever be attached to a canonical record that
    already exists (the authoritative write order: canonical write, THEN alias write)."""


_RECORDS_FILE = "records.jsonl"
_ALIASES_FILE = "aliases.jsonl"


def _append_jsonl(path: Path, obj: Mapping) -> None:
    line = json.dumps(obj, sort_keys=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
        fh.flush()
        os.fsync(fh.fileno())


class CanonicalMemoryLedger:
    """Benchmark-owned, foundation-independent ledger of `CanonicalMemoryRecord`s and
    their per-foundation vendor alias mappings.

    Every operation is scoped to `storage_dir`; two `CanonicalMemoryLedger` instances
    pointed at the same directory (e.g. one that wrote, one constructed fresh via
    `CanonicalMemoryLedger(storage_dir)` later) reconstruct identical in-memory state --
    this is the "canonical ledger persistence" / "canonical ledger reload" contract.
    """

    def __init__(self, storage_dir: Union[str, Path]) -> None:
        self._dir = Path(storage_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._records_path = self._dir / _RECORDS_FILE
        self._aliases_path = self._dir / _ALIASES_FILE

        self._records: Dict[str, CanonicalMemoryRecord] = {}
        # (foundation_name, foundation_memory_id) -> memory_id
        self._alias_reverse: Dict[Tuple[str, str], str] = {}
        # memory_id -> {foundation_name: foundation_memory_id}
        self._alias_forward: Dict[str, Dict[str, str]] = {}

        self._load()

    # -- reconstruction from disk --------------------------------------------------------

    def _load(self) -> None:
        if self._records_path.exists():
            with open(self._records_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    record = CanonicalMemoryRecord.from_dict(json.loads(line))
                    self._records[record.memory_id] = record
        if self._aliases_path.exists():
            with open(self._aliases_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    entry = json.loads(line)
                    self._set_alias_in_memory(
                        entry["memory_id"], entry["foundation_name"], entry["foundation_memory_id"]
                    )

    # -- canonical record operations -----------------------------------------------------

    def put(self, record: CanonicalMemoryRecord) -> str:
        """Write `record` as this ledger's authoritative representation of
        `record.memory_id`. Returns `PUT_CREATED` or `PUT_IDEMPOTENT`.

        Raises `CanonicalCollisionError` if `record.memory_id` already exists with
        different identity fields (see `CanonicalMemoryRecord.identity_fields()`).
        """
        existing = self._records.get(record.memory_id)
        if existing is not None:
            if existing.identity_fields() == record.identity_fields():
                return PUT_IDEMPOTENT
            raise CanonicalCollisionError(
                f"canonical memory_id {record.memory_id!r} already exists with different "
                "content/provenance -- refusing to overwrite. Existing="
                f"{existing.to_dict()!r} New={record.to_dict()!r}"
            )
        self._records[record.memory_id] = record
        _append_jsonl(self._records_path, record.to_dict())
        return PUT_CREATED

    def get(self, memory_id: str) -> Optional[CanonicalMemoryRecord]:
        """Reconstruct the canonical memory for `memory_id`, or `None` if absent. This
        NEVER consults a vendor foundation -- INVARIANT 5."""
        return self._records.get(memory_id)

    def exists(self, memory_id: str) -> bool:
        return memory_id in self._records

    def list_records(self) -> Tuple[CanonicalMemoryRecord, ...]:
        return tuple(self._records.values())

    # -- foundation alias table -----------------------------------------------------------

    def _set_alias_in_memory(self, memory_id: str, foundation_name: str, foundation_memory_id: str) -> None:
        self._alias_forward.setdefault(memory_id, {})[foundation_name] = foundation_memory_id
        self._alias_reverse[(foundation_name, foundation_memory_id)] = memory_id

    def set_alias(self, memory_id: str, foundation_name: str, foundation_memory_id: str) -> None:
        """Record that `memory_id` is known to `foundation_name` under
        `foundation_memory_id`. `memory_id` MUST already have a canonical record (the
        authoritative write order enforces this) -- raises `CanonicalAliasError`
        otherwise. A vendor id is NEVER accepted as a substitute canonical identity: this
        method only ever ADDS an entry to the alias table, never mutates `self._records`.
        """
        if memory_id not in self._records:
            raise CanonicalAliasError(
                f"cannot set alias for memory_id {memory_id!r}: no canonical record exists. "
                "Canonical records must be written before foundation aliases (authoritative "
                "write order)."
            )
        self._set_alias_in_memory(memory_id, foundation_name, foundation_memory_id)
        _append_jsonl(
            self._aliases_path,
            {"memory_id": memory_id, "foundation_name": foundation_name, "foundation_memory_id": foundation_memory_id},
        )

    def get_aliases(self, memory_id: str) -> Mapping[str, str]:
        """foundation_name -> foundation_memory_id, for every foundation this canonical
        memory has been written to. Empty mapping if none yet (e.g. CANONICAL_ONLY writes,
        or a foundation write that failed before an alias could be recorded)."""
        return dict(self._alias_forward.get(memory_id, {}))

    def resolve_alias(self, foundation_name: str, foundation_memory_id: str) -> Optional[str]:
        """vendor (foundation_name, foundation_memory_id) -> canonical memory_id, or
        `None` if this vendor id is not known to this ledger."""
        return self._alias_reverse.get((foundation_name, foundation_memory_id))


__all__ = [
    "PUT_CREATED",
    "PUT_IDEMPOTENT",
    "PUT_RESULTS",
    "CanonicalCollisionError",
    "CanonicalAliasError",
    "CanonicalMemoryLedger",
]
