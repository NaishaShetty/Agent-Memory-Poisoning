"""Phase 3.3-H.4-F (Configuration Fingerprinting) -- `RunConfigRecord`, the immutable
snapshot of the deterministic configuration that produced a `retrieved`/`selected` event,
and `RunConfigLedger`, its benchmark-owned, append-only store.

WHY THIS MODULE EXISTS
--------------------------------------------------------------------------------
`MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md` section 6 requires `retrieved`/`selected`
events to be traceable to the exact deterministic configuration that produced them
(embedding model + revision, reranker model + revision, retrieval k, sampling seed,
retrieval/selection mechanism, adapter revision), so a clean run and a later manipulated run
can be proven identical except for the injected manipulation. The revision explicitly
rejects embedding this configuration inline in every event -- redundant, and two events
could silently disagree about "the same" configuration -- in favor of a two-tier design: one
immutable configuration record, identified by a deterministic `config_fingerprint`,
referenced (never duplicated) by each event. This module is the record/ledger side of that
design; `canonical_event.py`'s new `config_fingerprint` field is the reference side.

RELATIONSHIP TO EXISTING LEDGERS -- SAME PRECEDENT, NOT A NEW PATTERN
--------------------------------------------------------------------------------
`RunConfigRecord` mirrors `canonical.CanonicalMemoryRecord`'s immutability discipline (H.1)
and `memory_versioning.CanonicalMemoryVersion`'s "pure snapshot, no content duplication"
discipline (H.3 section 5): it records only what is necessary to establish reproducibility
of one retrieval/selection operation, not every possible runtime setting (explicit
non-goal, per the revised plan's own wording). `RunConfigLedger` mirrors
`CanonicalMemoryLedger`/`CanonicalEventLedger`'s exact persistence discipline: one
append-only JSONL file, one already-fully-formed JSON line per `append()`, `flush()` +
`os.fsync()`, a malformed line on reload raises loudly rather than being silently skipped,
and there is no `update()`/`delete()` -- immutability here, as everywhere else in this
framework, is enforced by the PUBLIC API's shape, not by a runtime guard a caller could
route around.

FINGERPRINT DERIVATION -- REUSES H.2's EXISTING fingerprint(), NO SECOND HASHING SCHEME
--------------------------------------------------------------------------------
`event_identity.generate_event_id()` already established the pattern this module reuses
verbatim: `security.reproducibility.fingerprint()` (SHA-256 over a canonical, sorted-key
JSON serialization) is this framework's ONE content-hashing authority. `config_fingerprint`
is `fingerprint()` of every field except `config_fingerprint` itself and `created_at`
(the record's own creation timestamp is metadata, not semantic content -- two configuration
records with identical settings recorded at different times are the SAME configuration, by
the same reasoning `security/reproducibility.py::MANIFEST_METADATA_ONLY_FIELDS` already
applies to a manifest's own `timestamp`). No second, parallel hashing scheme is introduced;
Initiative D's future qualification-record extension should reuse this same
`_config_content_fingerprint()`-style helper rather than inventing a third one.

IMMUTABILITY MID-EXPERIMENT (mission section 7)
--------------------------------------------------------------------------------
A `RunConfigRecord` must be immutable once any event references its `config_fingerprint`.
`RunConfigLedger`'s lack of `update()`/`delete()` already makes this true by construction
for anything going through the ledger's own API -- this docstring states the invariant
explicitly (and it is tested, see `test_canonical_event_ledger_h4_f.py`), not because a
second enforcement mechanism exists, but because nothing in this framework previously
modeled "the configuration active during a run" as a first-class object at all.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

from phase3.evaluation.foundations.canonical_event import _validate_timestamp
from phase3.evaluation.security.reproducibility import fingerprint

APPEND_CREATED = "CREATED"
APPEND_IDEMPOTENT = "IDEMPOTENT_NOOP"
APPEND_RESULTS: Tuple[str, ...] = (APPEND_CREATED, APPEND_IDEMPOTENT)

_RUN_CONFIGS_FILE = "run_configs.jsonl"

# Mirrors `event_identity.EVENT_ID_PREFIX`'s namespace-separation convention -- advisory
# only, never runtime-enforced (see `event_identity.py`'s own "WHY THE PREFIX IS NOT
# RUNTIME-ENFORCED" reasoning, which applies unchanged here).
CONFIG_FINGERPRINT_PREFIX = "CFG"


class RunConfigValidationError(ValueError):
    """Raised when a `RunConfigRecord` violates this module's required-field/pairing
    constraints. Construction of an invalid record must fail loudly."""


class RunConfigCollisionError(ValueError):
    """Raised when a `config_fingerprint` already present in the ledger is appended again
    with a different payload. Mirrors `CanonicalEventCollisionError`'s exact idempotent-vs-
    collision distinction: fail loudly, never overwrite historical configuration."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RunConfigValidationError(message)


def compute_config_fingerprint(
    embedding_model: str,
    embedding_model_revision: str,
    retrieval_k: int,
    retrieval_mechanism: str,
    selection_mechanism: str,
    adapter_revision: str,
    reranker_model: Optional[str] = None,
    reranker_model_revision: Optional[str] = None,
    sampling_seed: Optional[int] = None,
) -> str:
    """Deterministically derive a `config_fingerprint` from every semantically-relevant
    field (i.e. every `RunConfigRecord` field except `config_fingerprint` itself and
    `created_at`). Identical inputs always produce the identical fingerprint; any single
    differing field (including `sampling_seed` alone) produces a different one -- `None` is
    never conflated with an absent/omitted value here, since `fingerprint()` serializes it
    as JSON `null`, distinct from any concrete seed value.
    """
    payload = {
        "embedding_model": embedding_model,
        "embedding_model_revision": embedding_model_revision,
        "retrieval_k": retrieval_k,
        "retrieval_mechanism": retrieval_mechanism,
        "selection_mechanism": selection_mechanism,
        "adapter_revision": adapter_revision,
        "reranker_model": reranker_model,
        "reranker_model_revision": reranker_model_revision,
        "sampling_seed": sampling_seed,
    }
    return f"{CONFIG_FINGERPRINT_PREFIX}-{fingerprint(payload)}"


@dataclass(frozen=True)
class RunConfigRecord:
    """Immutable snapshot of the deterministic configuration active for one or more
    `retrieved`/`selected` events. No content/memory/task field -- this is purely a
    configuration record, referenced by `CanonicalEvent.config_fingerprint`, never
    duplicated into the event itself.

    `config_fingerprint` is not re-derived by `__post_init__` (it is a required
    constructor argument, exactly like `CanonicalEvent.event_id`) -- a caller is expected to
    obtain it via `compute_config_fingerprint()` first, mirroring
    `event_identity.generate_event_id()` / `CanonicalEvent.event_id`'s own
    factory-then-construct division of responsibility. `__post_init__` DOES verify the
    supplied `config_fingerprint` matches what `compute_config_fingerprint()` would derive
    from the record's own other fields -- an inconsistent caller input fails loudly here,
    exactly this codebase's established convention (`canonical_event.py`'s `derived`
    `memory_ids`-consistency check is the direct precedent).
    """

    config_fingerprint: str
    embedding_model: str
    embedding_model_revision: str
    retrieval_k: int
    retrieval_mechanism: str
    selection_mechanism: str
    adapter_revision: str
    created_at: str
    reranker_model: Optional[str] = None
    reranker_model_revision: Optional[str] = None
    sampling_seed: Optional[int] = None

    def __post_init__(self) -> None:
        _require(
            isinstance(self.config_fingerprint, str) and bool(self.config_fingerprint),
            "config_fingerprint must be a non-empty string.",
        )
        _require(isinstance(self.embedding_model, str) and bool(self.embedding_model), "embedding_model must be a non-empty string.")
        _require(
            isinstance(self.embedding_model_revision, str) and bool(self.embedding_model_revision),
            "embedding_model_revision must be a non-empty string.",
        )
        _require(isinstance(self.retrieval_k, int) and not isinstance(self.retrieval_k, bool), "retrieval_k must be an int.")
        _require(self.retrieval_k > 0, "retrieval_k must be positive.")
        _require(
            isinstance(self.retrieval_mechanism, str) and bool(self.retrieval_mechanism),
            "retrieval_mechanism must be a non-empty string.",
        )
        _require(
            isinstance(self.selection_mechanism, str) and bool(self.selection_mechanism),
            "selection_mechanism must be a non-empty string.",
        )
        _require(isinstance(self.adapter_revision, str) and bool(self.adapter_revision), "adapter_revision must be a non-empty string.")
        _validate_timestamp(self.created_at)

        # Mirrors canonical_event.py's existing `foundation_memory_id` requires
        # `foundation_name` pattern (lines 295-299): a reranker revision is meaningless
        # without knowing which reranker model it revises, and a reranker model without a
        # pinned revision is not a reproducible configuration.
        if self.reranker_model is not None:
            _require(isinstance(self.reranker_model, str) and bool(self.reranker_model), "reranker_model, if given, must be a non-empty string.")
            _require(
                isinstance(self.reranker_model_revision, str) and bool(self.reranker_model_revision),
                "reranker_model_revision is required whenever reranker_model is set.",
            )
        else:
            _require(
                self.reranker_model_revision is None,
                "reranker_model_revision must be None when reranker_model is not set.",
            )

        if self.sampling_seed is not None:
            _require(
                isinstance(self.sampling_seed, int) and not isinstance(self.sampling_seed, bool),
                "sampling_seed, if given, must be an int.",
            )

        expected_fingerprint = compute_config_fingerprint(
            embedding_model=self.embedding_model,
            embedding_model_revision=self.embedding_model_revision,
            retrieval_k=self.retrieval_k,
            retrieval_mechanism=self.retrieval_mechanism,
            selection_mechanism=self.selection_mechanism,
            adapter_revision=self.adapter_revision,
            reranker_model=self.reranker_model,
            reranker_model_revision=self.reranker_model_revision,
            sampling_seed=self.sampling_seed,
        )
        _require(
            self.config_fingerprint == expected_fingerprint,
            f"config_fingerprint {self.config_fingerprint!r} does not match the fingerprint "
            f"derived from this record's own fields ({expected_fingerprint!r}) -- "
            "config_fingerprint is never independently authored, only computed via "
            "compute_config_fingerprint().",
        )

    def to_dict(self) -> dict:
        return {
            "config_fingerprint": self.config_fingerprint,
            "embedding_model": self.embedding_model,
            "embedding_model_revision": self.embedding_model_revision,
            "retrieval_k": self.retrieval_k,
            "retrieval_mechanism": self.retrieval_mechanism,
            "selection_mechanism": self.selection_mechanism,
            "adapter_revision": self.adapter_revision,
            "created_at": self.created_at,
            "reranker_model": self.reranker_model,
            "reranker_model_revision": self.reranker_model_revision,
            "sampling_seed": self.sampling_seed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RunConfigRecord":
        return cls(
            config_fingerprint=data["config_fingerprint"],
            embedding_model=data["embedding_model"],
            embedding_model_revision=data["embedding_model_revision"],
            retrieval_k=data["retrieval_k"],
            retrieval_mechanism=data["retrieval_mechanism"],
            selection_mechanism=data["selection_mechanism"],
            adapter_revision=data["adapter_revision"],
            created_at=data["created_at"],
            reranker_model=data.get("reranker_model"),
            reranker_model_revision=data.get("reranker_model_revision"),
            sampling_seed=data.get("sampling_seed"),
        )

    def identity_fields(self) -> Tuple[object, ...]:
        """Every field, used by `RunConfigLedger.append()` to distinguish an idempotent
        duplicate append (identical `config_fingerprint` + identical payload) from a
        genuine collision -- mirrors `CanonicalEvent.identity_fields()`'s exact
        discipline. `created_at` IS included here (unlike in the fingerprint derivation
        itself): identity/collision checking is about "is this literally the same
        recorded fact," which includes metadata, whereas the fingerprint is about
        "is this semantically the same configuration.\""""
        return (
            self.config_fingerprint,
            self.embedding_model,
            self.embedding_model_revision,
            self.retrieval_k,
            self.retrieval_mechanism,
            self.selection_mechanism,
            self.adapter_revision,
            self.created_at,
            self.reranker_model,
            self.reranker_model_revision,
            self.sampling_seed,
        )


def _append_jsonl(path: Path, obj: dict) -> None:
    line = json.dumps(obj, sort_keys=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
        fh.flush()
        os.fsync(fh.fileno())


class RunConfigLedger:
    """Benchmark-owned, append-only store of `RunConfigRecord`s, keyed by
    `config_fingerprint`. Same persistence/collision/immutability discipline as
    `CanonicalMemoryLedger` (H.1) and `CanonicalEventLedger` (H.2) -- see module docstring.
    """

    def __init__(self, storage_dir: Union[str, Path]) -> None:
        self._dir = Path(storage_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / _RUN_CONFIGS_FILE

        self._records: Dict[str, RunConfigRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        with open(self._path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                record = RunConfigRecord.from_dict(json.loads(line))
                self._records[record.config_fingerprint] = record

    def append(self, record: RunConfigRecord) -> str:
        """Append `record`. Returns `APPEND_CREATED` or `APPEND_IDEMPOTENT`.

        Raises `RunConfigCollisionError` if `record.config_fingerprint` already exists
        with a different payload.
        """
        existing = self._records.get(record.config_fingerprint)
        if existing is not None:
            if existing.identity_fields() == record.identity_fields():
                return APPEND_IDEMPOTENT
            raise RunConfigCollisionError(
                f"config_fingerprint {record.config_fingerprint!r} already exists with a "
                f"different payload -- refusing to overwrite. Existing={existing.to_dict()!r} "
                f"New={record.to_dict()!r}"
            )
        self._records[record.config_fingerprint] = record
        _append_jsonl(self._path, record.to_dict())
        return APPEND_CREATED

    def get(self, config_fingerprint: str) -> Optional[RunConfigRecord]:
        return self._records.get(config_fingerprint)

    def exists(self, config_fingerprint: str) -> bool:
        return config_fingerprint in self._records

    def all_records(self) -> Tuple[RunConfigRecord, ...]:
        return tuple(self._records.values())


__all__ = [
    "APPEND_CREATED",
    "APPEND_IDEMPOTENT",
    "APPEND_RESULTS",
    "CONFIG_FINGERPRINT_PREFIX",
    "RunConfigValidationError",
    "RunConfigCollisionError",
    "compute_config_fingerprint",
    "RunConfigRecord",
    "RunConfigLedger",
]
