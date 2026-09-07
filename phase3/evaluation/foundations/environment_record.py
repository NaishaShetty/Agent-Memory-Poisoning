"""Phase 3.3-H4-ENVIRONMENT-RECORD -- closes the two `REPRODUCIBILITY_CONTRACT.md §3`
requirements nothing in this codebase previously recorded: "software environment (library
versions...)" and "artifact hashes for any generated memory store or index."

WHY A NEW, SEPARATE RECORD -- NOT AN EXTENSION OF RunConfigRecord (H.4-F)
--------------------------------------------------------------------------------
`run_config.py::RunConfigRecord` is a frozen dataclass whose `config_fingerprint` is
verified, at construction, to match what `compute_config_fingerprint()` derives from the
record's OTHER fields (canonical_event.py's own established convention: a caller-supplied
identity is checked against a recomputation, never trusted blindly). Adding fields to that
record would mean either (a) folding them into the fingerprint computation, which would
silently change every existing `config_fingerprint` value already computed and STORED by
real runs this session (`h4a-real-locomo-smoke-1*`, the two Initiative D qualification
runs), invalidating already-resolvable references without those runs ever having done
anything wrong, or (b) excluding them from the fingerprint while still living on that
dataclass, which would be a confusing, unstated exception to that record's own established
"every field participates in identity" discipline. Both are worse than a new, small,
independently-keyed record -- the same reasoning H.3 used for `SupersessionRecord` and
H.4-BC used for `rejected`/`relationship_detected`: a new fact that does not fit an
existing frozen type's shape gets a new, additive type, not a retrofit.

`EnvironmentRecord` is therefore keyed by `campaign_id` (not folded into any
`config_fingerprint`-identified object), append-only, and captured once per real campaign
run -- never inferred, never fabricated: every `package_versions` entry is either the real,
`importlib.metadata`-resolved version string for a package actually importable in the
CURRENT interpreter, or absent entirely (never a placeholder). A caller running under
`C:\\h4venv` (where `mem0ai`/`chromadb`/`sentence-transformers` are installed) captures a
materially different, and more complete, record than one running in the main environment
-- this is expected and correct, not a bug: the record describes the interpreter that
actually did the work, honestly.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from dataclasses import dataclass, field
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple, Union

# The packages this contract cares about "at minimum for anything affecting model
# inference" (§3) -- the real, installed foundation/embedding/LLM-serving libraries this
# codebase's real adapters depend on. Best-effort: a package not importable in the CURRENT
# interpreter is simply absent from the captured record, never fabricated as "unknown"/"".
_RELEVANT_PACKAGES: Tuple[str, ...] = (
    "mem0ai", "chromadb", "sentence-transformers", "torch", "litellm", "qdrant-client",
)


class EnvironmentRecordValidationError(ValueError):
    pass


def _capture_package_versions(packages: Sequence[str] = _RELEVANT_PACKAGES) -> Dict[str, str]:
    versions: Dict[str, str] = {}
    for name in packages:
        try:
            versions[name] = importlib_metadata.version(name)
        except importlib_metadata.PackageNotFoundError:
            continue  # honestly absent -- never a placeholder value
    return versions


def _hash_directory_contents(directory: Union[str, Path]) -> Optional[str]:
    """A single SHA-256 over the sorted (relative_path, file_content) pairs of every file
    under `directory` -- a real, verifiable "artifact hash for a generated memory store"
    (REPRODUCIBILITY_CONTRACT.md §3), computed from the actual canonical-ledger files on
    disk, never a fabricated/random token. Returns `None` if `directory` does not exist or
    is empty (honestly absent, not a hash of nothing pretending to mean something)."""
    directory = Path(directory)
    if not directory.exists():
        return None
    file_paths = sorted(p for p in directory.rglob("*") if p.is_file())
    if not file_paths:
        return None
    hasher = hashlib.sha256()
    for p in file_paths:
        hasher.update(str(p.relative_to(directory)).replace("\\", "/").encode("utf-8"))
        hasher.update(p.read_bytes())
    return hasher.hexdigest()


@dataclass(frozen=True)
class EnvironmentRecord:
    """One real campaign/experiment run's software-environment and artifact-hash record.
    Immutable once constructed -- matches every other record's frozen-dataclass discipline
    in this framework."""

    campaign_id: str
    recorded_at: str
    python_version: str
    platform_summary: str
    package_versions: Mapping[str, str] = field(default_factory=dict)
    artifact_hash: Optional[str] = None
    artifact_hash_source: Optional[str] = None  # which directory the hash covers, for auditability

    def __post_init__(self) -> None:
        if not (isinstance(self.campaign_id, str) and self.campaign_id):
            raise EnvironmentRecordValidationError("campaign_id must be a non-empty string.")
        if not (isinstance(self.recorded_at, str) and self.recorded_at):
            raise EnvironmentRecordValidationError("recorded_at must be a non-empty string.")
        if self.artifact_hash is not None and not self.artifact_hash_source:
            raise EnvironmentRecordValidationError(
                "artifact_hash_source is required whenever artifact_hash is set -- a hash "
                "with no stated source is not auditable."
            )

    def to_dict(self) -> dict:
        return {
            "campaign_id": self.campaign_id,
            "recorded_at": self.recorded_at,
            "python_version": self.python_version,
            "platform_summary": self.platform_summary,
            "package_versions": dict(self.package_versions),
            "artifact_hash": self.artifact_hash,
            "artifact_hash_source": self.artifact_hash_source,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EnvironmentRecord":
        return cls(
            campaign_id=data["campaign_id"], recorded_at=data["recorded_at"],
            python_version=data["python_version"], platform_summary=data["platform_summary"],
            package_versions=dict(data.get("package_versions") or {}),
            artifact_hash=data.get("artifact_hash"), artifact_hash_source=data.get("artifact_hash_source"),
        )


def capture_environment_record(
    campaign_id: str,
    recorded_at: str,
    *,
    artifact_hash_source_dir: Optional[Union[str, Path]] = None,
    packages: Sequence[str] = _RELEVANT_PACKAGES,
) -> EnvironmentRecord:
    """Build an `EnvironmentRecord` for the CURRENT interpreter, right now. Pure w.r.t. the
    codebase (no ledger/network access) except for reading `sys`/`platform`/
    `importlib.metadata` and, if `artifact_hash_source_dir` is given, that directory's own
    already-persisted files -- never a foundation/adapter call."""
    artifact_hash = None
    if artifact_hash_source_dir is not None:
        artifact_hash = _hash_directory_contents(artifact_hash_source_dir)
    return EnvironmentRecord(
        campaign_id=campaign_id,
        recorded_at=recorded_at,
        python_version=sys.version,
        platform_summary=f"{platform.system()} {platform.release()} ({platform.machine()})",
        package_versions=_capture_package_versions(packages),
        artifact_hash=artifact_hash,
        artifact_hash_source=str(artifact_hash_source_dir) if artifact_hash is not None else None,
    )


def _append_jsonl(path: Path, obj: dict) -> None:
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


class EnvironmentRecordLedger:
    """Append-only store, identical persistence discipline to every other ledger in this
    framework. Keyed by `campaign_id` -- one record per real campaign run, not per task
    (the environment does not change within a single run)."""

    _FILE = "environment_records.jsonl"

    def __init__(self, storage_dir: Union[str, Path]) -> None:
        self._dir = Path(storage_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / self._FILE
        self._by_campaign: Dict[str, EnvironmentRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        with open(self._path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                record = EnvironmentRecord.from_dict(json.loads(line))
                self._by_campaign[record.campaign_id] = record

    def append(self, record: EnvironmentRecord) -> str:
        existing = self._by_campaign.get(record.campaign_id)
        if existing is not None:
            if existing == record:
                return "APPEND_IDEMPOTENT"
            raise EnvironmentRecordValidationError(
                f"campaign_id {record.campaign_id!r} already has a different recorded "
                "EnvironmentRecord -- refusing to silently overwrite."
            )
        _append_jsonl(self._path, record.to_dict())
        self._by_campaign[record.campaign_id] = record
        return "APPEND_CREATED"

    def get(self, campaign_id: str) -> Optional[EnvironmentRecord]:
        return self._by_campaign.get(campaign_id)

    def exists(self, campaign_id: str) -> bool:
        return campaign_id in self._by_campaign


__all__ = [
    "EnvironmentRecordValidationError",
    "EnvironmentRecord",
    "EnvironmentRecordLedger",
    "capture_environment_record",
]
