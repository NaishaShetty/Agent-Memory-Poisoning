"""Phase 3.3-H.4-D (Foundation Qualification Gate) -- `FoundationQualificationRecord`,
`QualificationLedger`, and the currency checker.

DEPENDENCY ON PHASE 3.2-H.4 (STRUCTURAL CRUD CONFORMANCE) -- READ FIRST
--------------------------------------------------------------------------------
`foundations_real.conformance_record.RealConformanceRecord` (Phase 3.2-H.4, a DIFFERENT
phase number, not this stage) proves a foundation's basic operations
(`INITIALIZE`/`ADD_MEMORY`/`RETRIEVE`/...) actually execute against the real, installed
library. This module answers a DIFFERENT, higher-level question that DEPENDS on that one:
given a foundation whose CRUD already conforms, does the canonical ledger correctly
reconstruct relationship/lineage semantics after round-tripping fixtures through it
(`qualification_harness.py`)? A foundation cannot be meaningfully qualified by passing every
fixture if its underlying CRUD never ran for real -- passing fixtures against a foundation
whose `add_memory()` was never actually exercised is not meaningful evidence. This is why
`overall_verdict` (below) is structurally impossible to be `QUALIFIED` unless
`conformance_tag == REAL_FOUNDATION_CONFORMANCE`
(`foundations_real.conformance_record.CONFORMANCE_TAGS`, imported read-only, never
redefined here -- mission section 2/3).

WHY A NEW RECORD TYPE, NOT A NEW `CanonicalEvent` FIELD
--------------------------------------------------------------------------------
Same reasoning `memory_versioning.py`'s `SupersessionRecord` already established for H.3,
and `run_config.py`'s `RunConfigRecord` for H.4-F: a frozen type's shape that cannot express
a new fact gets a new, additive side-record, never a modification to the frozen type. A
foundation qualification attempt is not a `CanonicalEvent` at all (it does not concern one
canonical memory or a pair) -- it is a fact about an entire (foundation, fixture-set,
config) combination, so it gets its own record and its own append-only ledger, following
every prior stage's exact persistence discipline.

RunConfigLedger REUSE, NOT A SECOND CONFIGURATION-RECORD TYPE
--------------------------------------------------------------------------------
`config_fingerprint` below is a reference to an existing `run_config.RunConfigRecord` (H.4-F)
-- this module never constructs its own parallel configuration-identity concept.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Tuple, Union

from phase3.evaluation.foundations.canonical_event import _validate_timestamp
from phase3.evaluation.foundations.run_config import RunConfigLedger
from phase3.evaluation.foundations_real.conformance_record import (
    CONFORMANCE_TAGS,
    REAL_FOUNDATION_CONFORMANCE,
)
from phase3.evaluation.foundations_real.qualification_fixtures import (
    FixtureManifestError,
    verify_fixture_manifest,
)

APPEND_CREATED = "CREATED"
APPEND_IDEMPOTENT = "IDEMPOTENT_NOOP"
APPEND_RESULTS: Tuple[str, ...] = (APPEND_CREATED, APPEND_IDEMPOTENT)

VERDICT_QUALIFIED = "QUALIFIED"
VERDICT_NOT_QUALIFIED = "NOT_QUALIFIED"
OVERALL_VERDICTS: Tuple[str, ...] = (VERDICT_QUALIFIED, VERDICT_NOT_QUALIFIED)

_QUALIFICATIONS_FILE = "qualifications.jsonl"


class QualificationValidationError(ValueError):
    """Raised when a `FoundationQualificationRecord` violates this module's required-field/
    verdict-consistency constraints. Construction of an invalid record must fail loudly."""


class QualificationCollisionError(ValueError):
    """Raised when appending a qualification record whose identity (foundation_id +
    adapter_revision + fixture_set_version + config_fingerprint + qualified_at) already
    exists in the ledger with a different payload. Mirrors every other ledger's exact
    idempotent-vs-collision distinction in this framework."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise QualificationValidationError(message)


@dataclass(frozen=True)
class FoundationQualificationRecord:
    """One qualification ATTEMPT for `foundation_id` against `fixture_set_version`, run
    under `config_fingerprint`. `per_fixture_results` never carries a vendor-native id --
    only canonical `memory_id`s (via mismatch strings) and fixture names ever appear in a
    persisted field here, consistent with this framework's "vendor IDs are aliases"
    principle throughout (mission section 8, invariant 5).

    `overall_verdict == QUALIFIED` is structurally impossible unless BOTH
    `conformance_tag == REAL_FOUNDATION_CONFORMANCE` AND every fixture in
    `per_fixture_results` passed -- enforced in `__post_init__`, mirroring
    `RealConformanceRecord`'s own `REAL_FOUNDATION_CONFORMANCE requires
    library_import_succeeded` invariant (`conformance_record.py` lines 124-129).
    """

    foundation_id: str
    adapter_revision: str
    fixture_set_version: str
    config_fingerprint: str
    per_fixture_results: Mapping[str, Mapping[str, Any]]
    conformance_tag: str
    overall_verdict: str
    qualified_at: str
    note: str = ""

    def __post_init__(self) -> None:
        _require(isinstance(self.foundation_id, str) and bool(self.foundation_id), "foundation_id must be a non-empty string.")
        _require(isinstance(self.adapter_revision, str) and bool(self.adapter_revision), "adapter_revision must be a non-empty string.")
        _require(isinstance(self.fixture_set_version, str) and bool(self.fixture_set_version), "fixture_set_version must be a non-empty string.")
        _require(isinstance(self.config_fingerprint, str) and bool(self.config_fingerprint), "config_fingerprint must be a non-empty string.")
        _require(isinstance(self.per_fixture_results, Mapping) and len(self.per_fixture_results) > 0, "per_fixture_results must be a non-empty mapping.")
        for name, outcome in self.per_fixture_results.items():
            _require(isinstance(outcome, Mapping) and "passed" in outcome, f"per_fixture_results[{name!r}] must be a mapping with a 'passed' key.")
        _require(self.conformance_tag in CONFORMANCE_TAGS, f"conformance_tag {self.conformance_tag!r} is not one of {CONFORMANCE_TAGS!r}.")
        _require(self.overall_verdict in OVERALL_VERDICTS, f"overall_verdict {self.overall_verdict!r} is not one of {OVERALL_VERDICTS!r}.")
        _validate_timestamp(self.qualified_at)

        all_fixtures_passed = all(bool(outcome["passed"]) for outcome in self.per_fixture_results.values())
        structurally_qualifiable = all_fixtures_passed and self.conformance_tag == REAL_FOUNDATION_CONFORMANCE
        if self.overall_verdict == VERDICT_QUALIFIED:
            _require(
                structurally_qualifiable,
                "overall_verdict='QUALIFIED' requires conformance_tag=='REAL_FOUNDATION_CONFORMANCE' "
                "AND every fixture in per_fixture_results to have passed -- refusing to record a "
                "qualification claim for a foundation whose underlying CRUD never ran for real, or "
                "that failed at least one fixture (mission section 2/8, invariant 3).",
            )
        # NOT_QUALIFIED is always permitted, including the (structurally_qualifiable=True)
        # case a caller might want for other reasons -- this module does not force
        # QUALIFIED just because it would have been ALLOWED; the caller's own verdict is
        # trusted in that direction, only the QUALIFIED-when-it-shouldn't-be direction is
        # blocked.

    def to_dict(self) -> dict:
        return {
            "foundation_id": self.foundation_id,
            "adapter_revision": self.adapter_revision,
            "fixture_set_version": self.fixture_set_version,
            "config_fingerprint": self.config_fingerprint,
            "per_fixture_results": {k: dict(v) for k, v in self.per_fixture_results.items()},
            "conformance_tag": self.conformance_tag,
            "overall_verdict": self.overall_verdict,
            "qualified_at": self.qualified_at,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FoundationQualificationRecord":
        return cls(
            foundation_id=data["foundation_id"],
            adapter_revision=data["adapter_revision"],
            fixture_set_version=data["fixture_set_version"],
            config_fingerprint=data["config_fingerprint"],
            per_fixture_results=data["per_fixture_results"],
            conformance_tag=data["conformance_tag"],
            overall_verdict=data["overall_verdict"],
            qualified_at=data["qualified_at"],
            note=data.get("note", ""),
        )

    def identity_key(self) -> Tuple[str, str, str, str, str]:
        """`(foundation_id, adapter_revision, fixture_set_version, config_fingerprint,
        qualified_at)` -- two qualification ATTEMPTS at the same instant for the same
        foundation/adapter/fixture-set/config would be a genuine duplicate submission;
        anything differing in any of these five is a distinct historical attempt, per
        mission section 9, adversarial case 3 ("both must be retained... it is a history")."""
        return (self.foundation_id, self.adapter_revision, self.fixture_set_version, self.config_fingerprint, self.qualified_at)

    def identity_fields(self) -> Tuple[Any, ...]:
        return (
            self.foundation_id, self.adapter_revision, self.fixture_set_version, self.config_fingerprint,
            tuple(sorted((k, tuple(sorted(v.items()))) for k, v in self.per_fixture_results.items())),
            self.conformance_tag, self.overall_verdict, self.qualified_at, self.note,
        )


def _append_jsonl(path: Path, obj: dict) -> None:
    line = json.dumps(obj, sort_keys=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
        fh.flush()
        os.fsync(fh.fileno())


class QualificationLedger:
    """Benchmark-owned, append-only history of `FoundationQualificationRecord`s
    (`qualifications.jsonl`). No `update()`/`delete()` -- structural invariant, mirroring
    every other ledger in this framework exactly."""

    def __init__(self, storage_dir: Union[str, Path]) -> None:
        self._dir = Path(storage_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / _QUALIFICATIONS_FILE
        self._by_key: dict = {}
        self._order: list = []
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        with open(self._path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                record = FoundationQualificationRecord.from_dict(json.loads(line))
                key = record.identity_key()
                self._by_key[key] = record
                self._order.append(key)

    def append(self, record: FoundationQualificationRecord) -> str:
        key = record.identity_key()
        existing = self._by_key.get(key)
        if existing is not None:
            if existing.identity_fields() == record.identity_fields():
                return APPEND_IDEMPOTENT
            raise QualificationCollisionError(
                f"qualification identity {key!r} already exists with a different payload -- "
                f"refusing to overwrite. Existing={existing.to_dict()!r} New={record.to_dict()!r}"
            )
        self._by_key[key] = record
        self._order.append(key)
        _append_jsonl(self._path, record.to_dict())
        return APPEND_CREATED

    def exists(self, foundation_id: str, adapter_revision: str, fixture_set_version: str, config_fingerprint: str, qualified_at: str) -> bool:
        return (foundation_id, adapter_revision, fixture_set_version, config_fingerprint, qualified_at) in self._by_key

    def all_for_foundation(self, foundation_id: str) -> Tuple[FoundationQualificationRecord, ...]:
        return tuple(self._by_key[k] for k in self._order if k[0] == foundation_id)

    def get_latest(self, foundation_id: str) -> Optional[FoundationQualificationRecord]:
        """The most recently `qualified_at` record for `foundation_id`, or `None` if none
        exists. Never inferred from append order alone -- `qualified_at` (ISO-8601 UTC) is
        compared directly, mirroring every other stage's "never trust append order as a
        stand-in for chronology" discipline (`event_ledger.py`'s own explicit ordering
        note applies the same principle in the opposite direction: append order is
        authoritative for EVENT replay history, but `qualified_at` is the authoritative
        field for "which qualification attempt is the CURRENT one")."""
        candidates = self.all_for_foundation(foundation_id)
        if not candidates:
            return None
        return max(candidates, key=lambda r: r.qualified_at)


# ---------------------------------------------------------------------------
# The gate -- currency checking (mission section 7)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CurrencyCheckResult:
    is_current: bool
    reasons: Tuple[str, ...]
    qualification_record: Optional[FoundationQualificationRecord]


def check_qualification_currency(
    manifest: Mapping[str, Any],
    qualification_ledger: QualificationLedger,
    *,
    current_adapter_revision: Optional[str] = None,
) -> CurrencyCheckResult:
    """Flag -- never silently pass -- a run manifest whose declared qualification basis is
    stale or absent.

    `manifest` must carry `foundation_id`, `adapter_revision`, and `fixture_set_version`
    (the mission's "which FoundationQualificationRecord it was run under" declaration).

    Flags (any of, all reported, never just the first):
    - No qualification record at all exists for `manifest["foundation_id"]`.
    - The referenced record's `fixture_set_version` differs from `manifest`'s declared one
      (mission section 9, adversarial case 4's spirit extended to the gate itself: a
      manifest cannot silently ride on a qualification against a DIFFERENT fixture set).
    - `current_adapter_revision` is supplied and differs from the qualification record's
      own `adapter_revision` -- the foundation adapter has moved on since qualification.
    - The qualification record's own `overall_verdict` is `NOT_QUALIFIED`.

    This is documentation/tooling (mission section 7) -- it does NOT itself raise or block
    anything; a caller (e.g. a future `campaign_formal_runner.py` pre-flight check, NOT
    wired by this stage -- see the implementation report) decides what to do with a
    non-current result.
    """
    foundation_id = manifest["foundation_id"]
    declared_fixture_set_version = manifest.get("fixture_set_version")
    reasons = []

    record = qualification_ledger.get_latest(foundation_id)
    if record is None:
        reasons.append(f"no qualification record exists for foundation_id={foundation_id!r}.")
        return CurrencyCheckResult(is_current=False, reasons=tuple(reasons), qualification_record=None)

    if declared_fixture_set_version is not None and record.fixture_set_version != declared_fixture_set_version:
        reasons.append(
            f"manifest declares fixture_set_version={declared_fixture_set_version!r} but the latest "
            f"qualification record for {foundation_id!r} was run under {record.fixture_set_version!r}."
        )
    if current_adapter_revision is not None and record.adapter_revision != current_adapter_revision:
        reasons.append(
            f"foundation adapter's current revision {current_adapter_revision!r} no longer matches the "
            f"qualification record's adapter_revision {record.adapter_revision!r}."
        )
    if record.overall_verdict != VERDICT_QUALIFIED:
        reasons.append(f"latest qualification record for {foundation_id!r} has overall_verdict={record.overall_verdict!r}.")

    return CurrencyCheckResult(is_current=len(reasons) == 0, reasons=tuple(reasons), qualification_record=record)


# ---------------------------------------------------------------------------
# Top-level orchestration -- ties qualification_fixtures.py + qualification_harness.py +
# conformance_record.py + run_config.py together into one FoundationQualificationRecord.
# ---------------------------------------------------------------------------


def run_foundation_qualification(
    *,
    foundation_id: str,
    foundation,
    foundation_name: str,
    adapter_revision: str,
    conformance_tag: str,
    config_fingerprint: str,
    qualified_at: str,
    storage_dir: Union[str, Path],
    config_ledger: Optional[RunConfigLedger] = None,
    note: str = "",
) -> FoundationQualificationRecord:
    """Run EVERY frozen qualification fixture against `foundation` and assemble the
    resulting `FoundationQualificationRecord`. Does not append it to a `QualificationLedger`
    itself -- the caller decides that (mirrors `write_canonical_memory()`'s own
    "orchestrates the write, caller owns the ledger instance" division of responsibility).

    Each fixture gets its OWN, freshly-constructed `(CanonicalMemoryLedger,
    CanonicalEventLedger, SupersessionLedger)` triple, under its own subdirectory of
    `storage_dir` -- several fixtures deliberately reuse the SAME `memory_id` for
    UNRELATED scenario content (e.g. `lineage/01_independent.json` and
    `lineage/02_direct_derivation.json` both declare a `mem-lin-A` with different `content`)
    -- these are independent, self-contained test scenarios, never meant to accumulate into
    one shared ledger; doing so would raise `CanonicalCollisionError` on the second fixture
    that reuses an id with different content, exactly as it should for a REAL shared ledger,
    which is precisely why this function does not use one.

    Raises `FixtureManifestError` (propagated, never swallowed) BEFORE running anything if
    the on-disk fixture set no longer matches the frozen `QUALIFICATION_FIXTURE_MANIFEST.
    json` -- mission section 9, adversarial case 4: "must be rejected/flagged before the
    harness runs, not silently qualified against an undeclared, driftable fixture set."

    `conformance_tag` is supplied by the caller (from Phase 3.2-H.4's own
    `RealConformanceRecord` results for this foundation's `ADD_MEMORY`/`RETRIEVE`
    operations -- see module docstring) -- this function never invents or infers one; if the
    caller passes anything other than `REAL_FOUNDATION_CONFORMANCE`,
    `FoundationQualificationRecord.__post_init__` structurally forces `overall_verdict` to
    resolve to `NOT_QUALIFIED` regardless of how many fixtures pass.
    """
    from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
    from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
    from phase3.evaluation.foundations.memory_versioning import SupersessionLedger
    from phase3.evaluation.foundations_real.qualification_fixtures import (
        FIXTURE_SET_VERSION,
        load_all_fixture_bundles,
        verify_fixture_manifest,
    )
    from phase3.evaluation.foundations_real.qualification_harness import run_qualification_fixture

    matches, detail = verify_fixture_manifest()
    if not matches:
        raise FixtureManifestError(f"fixture set no longer matches the frozen manifest: {detail!r}")

    # Mission section 8, invariant 5: a qualification record's config_fingerprint must
    # resolve against a real RunConfigLedger entry -- reusing H.4-F's own resolvability
    # discipline (RunConfigLedger.exists()), not inventing a second one.
    if config_ledger is not None and not config_ledger.exists(config_fingerprint):
        raise QualificationValidationError(
            f"config_fingerprint {config_fingerprint!r} does not resolve against the supplied "
            "RunConfigLedger -- a qualification run's configuration must already be recorded."
        )

    storage_dir = Path(storage_dir)
    per_fixture_results: dict = {}
    for name, bundle in load_all_fixture_bundles().items():
        fixture_dir = storage_dir / name.replace("/", "__")
        memory_ledger = CanonicalMemoryLedger(fixture_dir / "memory")
        event_ledger = CanonicalEventLedger(fixture_dir / "events", memory_ledger)
        supersession_ledger = SupersessionLedger(fixture_dir / "supersessions")
        result = run_qualification_fixture(
            bundle,
            foundation=foundation,
            foundation_name=foundation_name,
            memory_ledger=memory_ledger,
            event_ledger=event_ledger,
            supersession_ledger=supersession_ledger,
            config_fingerprint=config_fingerprint,
        )
        per_fixture_results[name] = result.to_dict()

    all_passed = all(v["passed"] for v in per_fixture_results.values())
    overall_verdict = (
        VERDICT_QUALIFIED if (all_passed and conformance_tag == REAL_FOUNDATION_CONFORMANCE) else VERDICT_NOT_QUALIFIED
    )

    return FoundationQualificationRecord(
        foundation_id=foundation_id,
        adapter_revision=adapter_revision,
        fixture_set_version=FIXTURE_SET_VERSION,
        config_fingerprint=config_fingerprint,
        per_fixture_results=per_fixture_results,
        conformance_tag=conformance_tag,
        overall_verdict=overall_verdict,
        qualified_at=qualified_at,
        note=note,
    )


__all__ = [
    "APPEND_CREATED",
    "APPEND_IDEMPOTENT",
    "APPEND_RESULTS",
    "VERDICT_QUALIFIED",
    "VERDICT_NOT_QUALIFIED",
    "OVERALL_VERDICTS",
    "QualificationValidationError",
    "QualificationCollisionError",
    "FoundationQualificationRecord",
    "QualificationLedger",
    "CurrencyCheckResult",
    "check_qualification_currency",
    "run_foundation_qualification",
]
