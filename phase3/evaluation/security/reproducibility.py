"""Phase 3.2-F — canonical serialization, fingerprinting, and a reproducibility manifest.

Implements, for SYNTHETIC data only (no real dataset, no Qwen, no real agent):

- Deterministic canonical serialization with stable key ordering.
- SHA-256-based fingerprinting (never Python's built-in `hash()`, which is not
  guaranteed stable across processes/runs -- PYTHONHASHSEED randomizes `hash()` for str
  by default specifically so it must NEVER be used for a persistent fingerprint).
- A reproducibility manifest structure (a plain dict, deliberately NOT a fixed dataclass
  -- see "Why a dict, not a dataclass" below).
- Artifact integrity verification via SHA-256 digest comparison.
- A verifier distinguishing REPRODUCIBLE_MATCH / ARTIFACT_MISMATCH /
  CONFIGURATION_MISMATCH / INPUT_MISMATCH / INCOMPLETE_MANIFEST / VERIFICATION_UNDEFINED.
- A synthetic run-reconstruction helper.

================================================================================
THE SINGLE MOST IMPORTANT DESIGN DECISION IN THIS MODULE:

Canonical serialization sorts DICT KEYS (genuinely unordered structures) but never
reorders LISTS. `retrieved_ranked_ids` is a ranked list -- its order is semantically
load-bearing (see `phase3/evaluation/security/determinism.py`'s ORDER_SENSITIVE_METRIC_
NAMES) and reordering it changes what Recall@K/MRR mean. If this module "canonicalized"
lists by sorting them, two DIFFERENT rankings would silently collapse to the SAME
fingerprint, which would make fingerprinting actively hide a real difference in agent
behavior. Only genuinely unordered structures -- dict keys, and any Python `set`/
`frozenset` the caller passes in (converted to a sorted list ONLY because sets are not
JSON-serializable, not because list order is being asserted as meaningful there) -- are
canonicalized. Lists are serialized in the exact order the caller supplies, always.
================================================================================

Why a dict, not a dataclass, for the manifest: scenario 11 in this stage's test brief
("manifest missing required field -> INCOMPLETE_MANIFEST") requires representing a
manifest that is LEGITIMATELY missing a field -- a fixed dataclass with required
positional/keyword fields cannot represent "this field was never set" distinctly from
"this field is None" without extra machinery. A plain dict makes "key absent" a first-class,
directly-inspectable case (`"seed" not in manifest`), which is exactly the case
`validate_manifest_completeness()` needs to detect.

Pure, deterministic functions only, except the explicit, opt-in artifact-hashing helpers,
which read only bytes/paths the caller supplies (never discover files on their own, never
read from `data/raw/`, `data/processed/`, `data/metadata/`, or `data/reports/`).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import platform
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional, Sequence

# ---------------------------------------------------------------------------
# Canonical serialization
# ---------------------------------------------------------------------------


def _normalize(obj: Any) -> Any:
    """Convert dataclasses/tuples/sets into their canonical JSON-equivalent shape.

    - Dataclass instances -> dict of `{field_name: normalized_value}` (field order as
      declared, but the outer serialization step below sorts dict keys anyway).
    - `tuple` -> `list` (JSON has no tuple type; order preserved -- tuples are used in
      this codebase for ordered sequences like `retrieved_memory_ids`, never reordered
      here).
    - `set`/`frozenset` -> a SORTED list. This is the one place this module reorders
      anything: a Python set has no defined order to begin with, so representing it as a
      sorted list is recovering a canonical form, not discarding meaningful order (there
      was none to discard).
    - Everything else returned unchanged (dicts/lists recursed into; scalars returned
      as-is).
    """
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _normalize(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, dict):
        return {str(k): _normalize(v) for k, v in obj.items()}
    if isinstance(obj, (set, frozenset)):
        return sorted(_normalize(v) for v in obj)
    if isinstance(obj, (list, tuple)):
        return [_normalize(v) for v in obj]
    return obj


def canonical_serialize(obj: Any) -> str:
    """Deterministic canonical JSON serialization.

    - Dict keys are sorted (`sort_keys=True`) -- dict key order is not semantically
      meaningful anywhere in this codebase's JSON-like structures, so sorting recovers a
      single canonical form for otherwise-identical data.
    - Lists are serialized in the EXACT order given -- never sorted. See module docstring.
    - Compact, stable separators (`(",", ":")`) so incidental whitespace differences
      never change the fingerprint.
    - UTF-8 is implicit: Python `str` -> `json.dumps` -> this function returns `str`;
      callers that need bytes for hashing encode explicitly as UTF-8 (see `fingerprint`).
    - No `default=` fallback: an object that is not JSON-serializable after `_normalize`
      (e.g. a raw function, a socket, an arbitrary class instance) raises `TypeError`
      rather than being silently stringified into an unstable representation.
    """
    normalized = _normalize(obj)
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint(obj: Any) -> str:
    """SHA-256 hex digest of `canonical_serialize(obj)`, UTF-8 encoded.

    NEVER use Python's built-in `hash()` for this purpose: `hash()` of a `str` is
    randomized per-process by default (`PYTHONHASHSEED`) specifically so it must not be
    relied on across processes/runs -- using it for a "reproducibility" fingerprint would
    silently produce a DIFFERENT fingerprint for identical data on every run, which is the
    exact opposite of what this module exists to guarantee. `hashlib.sha256` is used
    instead: stable, cryptographic, and identical across processes/machines/Python
    versions for the same input bytes.
    """
    serialized = canonical_serialize(obj)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def digest_bytes(data: bytes) -> str:
    """SHA-256 hex digest of raw bytes (for artifact integrity checks, not for structured
    JSON-like data -- use `fingerprint()` for that)."""
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Environment metadata (safe subset only)
# ---------------------------------------------------------------------------


def safe_environment_metadata() -> Mapping[str, str]:
    """Minimal, safe environment metadata: Python version and platform string only.

    Explicitly NEVER includes: environment variables, API keys, credentials, tokens,
    file-system paths outside the repo, hostnames, usernames, or any other
    potentially-sensitive value. Per REPRODUCIBILITY_CONTRACT.md section 3, the software
    environment must be recorded "at minimum for anything affecting model inference" --
    this stage has no model-inference component (no Qwen integration, per scope), so this
    is deliberately a minimal placeholder, not a claim of completeness for a future
    Qwen-integrated stage's environment-capture needs.
    """
    return {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
    }


# ---------------------------------------------------------------------------
# Reproducibility manifest
# ---------------------------------------------------------------------------

# Fields REQUIRED to be present (key exists) for a manifest to be considered complete.
# `seed` is required to be PRESENT but its value may legitimately be the string
# "NOT_APPLICABLE" (see build_manifest below) -- "not applicable" is itself an honest,
# recorded answer, never an absent key.
REQUIRED_MANIFEST_FIELDS: frozenset[str] = frozenset(
    {
        "run_id",
        "task_ids",
        "conditions",
        "input_fingerprint",
        "agent_visible_context_fingerprint",
        "evaluator_reference_fingerprint",
        "configuration_fingerprint",
        "code_version",
        "contract_version",
        "metric_version",
        "seed",
        "timestamp",
        "artifact_refs",
    }
)

# Fields that are METADATA ONLY -- explicitly excluded from the semantic fingerprint
# computed by `manifest_semantic_fingerprint()`. `timestamp` is the canonical example:
# two manifests differing only in when they were created must be considered the SAME
# reproducible record.
MANIFEST_METADATA_ONLY_FIELDS: frozenset[str] = frozenset({"timestamp"})

SEED_NOT_APPLICABLE = "NOT_APPLICABLE"


def build_manifest(
    run_id: str,
    task_ids: Sequence[str],
    conditions: Sequence[str],
    input_fingerprint: str,
    agent_visible_context_fingerprint: str,
    evaluator_reference_fingerprint: str,
    configuration_fingerprint: str,
    code_version: str,
    contract_version: str,
    metric_version: str,
    timestamp: str,
    seed: Optional[str] = None,
    artifact_refs: Optional[Sequence[Mapping[str, str]]] = None,
    **extra: Any,
) -> dict:
    """Assemble a reproducibility manifest as a plain dict with every
    `REQUIRED_MANIFEST_FIELDS` key present.

    `seed`: if the caller does not supply one, defaults to `SEED_NOT_APPLICABLE`
    ("NOT_APPLICABLE") rather than `None` or omitting the key -- per
    REPRODUCIBILITY_CONTRACT.md section 3/4, a run with no stochastic component anywhere
    (true of every construct in this Phase 3.2-F stage -- no Qwen, no sampling-based
    retrieval) must HONESTLY record that no seed applies, not silently omit the field.

    `artifact_refs`: sequence of `{"name": ..., "digest": ...}` mappings (SHA-256 hex
    digests, from `digest_bytes()`), defaulting to an empty list if none supplied.

    `**extra`: any additional caller-supplied keys (e.g. a `result_fingerprint` used only
    by this stage's synthetic reconstruction test) are included verbatim. Extra keys are
    NOT part of `REQUIRED_MANIFEST_FIELDS` and have no effect on completeness checking.
    """
    manifest: dict = {
        "run_id": run_id,
        "task_ids": list(task_ids),
        "conditions": list(conditions),
        "input_fingerprint": input_fingerprint,
        "agent_visible_context_fingerprint": agent_visible_context_fingerprint,
        "evaluator_reference_fingerprint": evaluator_reference_fingerprint,
        "configuration_fingerprint": configuration_fingerprint,
        "code_version": code_version,
        "contract_version": contract_version,
        "metric_version": metric_version,
        "seed": seed if seed is not None else SEED_NOT_APPLICABLE,
        "timestamp": timestamp,
        "artifact_refs": [dict(ref) for ref in (artifact_refs or [])],
    }
    manifest.update(extra)
    return manifest


def validate_manifest_completeness(manifest: Mapping[str, Any]) -> tuple[bool, Sequence[str]]:
    """Return `(is_complete, missing_field_names)`. `is_complete` is True iff every name
    in `REQUIRED_MANIFEST_FIELDS` is a PRESENT key in `manifest` (value may be
    anything, including `None` -- only key ABSENCE counts as missing)."""
    missing = sorted(REQUIRED_MANIFEST_FIELDS - set(manifest.keys()))
    return (len(missing) == 0, missing)


def manifest_semantic_fingerprint(manifest: Mapping[str, Any]) -> str:
    """Fingerprint of the manifest's SEMANTIC content -- every key except
    `MANIFEST_METADATA_ONLY_FIELDS` (currently just `timestamp`). Two manifests that are
    identical except for `timestamp` MUST produce the same value here; this is asserted
    directly by a dedicated test, not merely claimed.
    """
    semantic_view = {k: v for k, v in manifest.items() if k not in MANIFEST_METADATA_ONLY_FIELDS}
    return fingerprint(semantic_view)


# ---------------------------------------------------------------------------
# Artifact integrity
# ---------------------------------------------------------------------------

STATUS_ARTIFACT_INTEGRITY_OK = "ARTIFACT_INTEGRITY_OK"
STATUS_ARTIFACT_INTEGRITY_FAILURE = "ARTIFACT_INTEGRITY_FAILURE"


@dataclass(frozen=True)
class ArtifactIntegrityResult:
    status: str
    name: str
    recorded_digest: str
    recomputed_digest: str


def verify_artifact_integrity(name: str, recorded_digest: str, current_data: bytes) -> ArtifactIntegrityResult:
    """Recompute the SHA-256 digest of `current_data` and compare it against
    `recorded_digest` (as captured in a manifest's `artifact_refs` at manifest-creation
    time). Returns `STATUS_ARTIFACT_INTEGRITY_FAILURE` on any mismatch -- this function
    never attempts to "auto-repair" or silently accept a modified artifact; a mismatch is
    always surfaced, never corrected.
    """
    recomputed = digest_bytes(current_data)
    status = (
        STATUS_ARTIFACT_INTEGRITY_OK
        if recomputed == recorded_digest
        else STATUS_ARTIFACT_INTEGRITY_FAILURE
    )
    return ArtifactIntegrityResult(
        status=status, name=name, recorded_digest=recorded_digest, recomputed_digest=recomputed
    )


# ---------------------------------------------------------------------------
# Reproducibility verifier
# ---------------------------------------------------------------------------

VERIFY_REPRODUCIBLE_MATCH = "REPRODUCIBLE_MATCH"
VERIFY_ARTIFACT_MISMATCH = "ARTIFACT_MISMATCH"
VERIFY_CONFIGURATION_MISMATCH = "CONFIGURATION_MISMATCH"
VERIFY_INPUT_MISMATCH = "INPUT_MISMATCH"
VERIFY_INCOMPLETE_MANIFEST = "INCOMPLETE_MANIFEST"
VERIFY_UNDEFINED = "VERIFICATION_UNDEFINED"


@dataclass(frozen=True)
class VerificationResult:
    status: str
    detail: Mapping[str, Any] = field(default_factory=dict)


def verify_reproducibility(
    manifest: Mapping[str, Any],
    current_artifacts: Mapping[str, bytes],
    current_input_fingerprint: Optional[str] = None,
    current_configuration_fingerprint: Optional[str] = None,
) -> VerificationResult:
    """Verify a manifest against the CURRENT state of its referenced artifacts/inputs/
    configuration.

    Precedence (checked in this order; the first applicable mismatch wins -- exactly one
    status is ever returned):

    1. `manifest` incomplete (missing a `REQUIRED_MANIFEST_FIELDS` key) ->
       `INCOMPLETE_MANIFEST`. Nothing else can be meaningfully checked against an
       incomplete record.
    2. Any artifact in `manifest["artifact_refs"]` whose `name` is present in
       `current_artifacts` but whose recomputed digest does not match the recorded one ->
       `ARTIFACT_MISMATCH`.
    3. `current_configuration_fingerprint` supplied and differs from
       `manifest["configuration_fingerprint"]` -> `CONFIGURATION_MISMATCH`.
    4. `current_input_fingerprint` supplied and differs from
       `manifest["input_fingerprint"]` -> `INPUT_MISMATCH`.
    5. Otherwise -> `REPRODUCIBLE_MATCH`.

    If neither `current_input_fingerprint` nor `current_configuration_fingerprint` is
    supplied and no artifact mismatch was found, this function still returns
    `REPRODUCIBLE_MATCH` for the checks it COULD perform (artifact integrity only) --
    a caller wanting the input/configuration checks must supply those fingerprints
    explicitly. This is never silently treated as `VERIFICATION_UNDEFINED`: artifact-only
    verification is still a meaningful (if partial) check, and `detail` records exactly
    which checks were performed.
    """
    is_complete, missing = validate_manifest_completeness(manifest)
    if not is_complete:
        return VerificationResult(
            status=VERIFY_INCOMPLETE_MANIFEST,
            detail={"missing_fields": missing},
        )

    artifact_checks = []
    for ref in manifest.get("artifact_refs", []):
        name = ref.get("name")
        recorded_digest = ref.get("digest")
        if name in current_artifacts:
            result = verify_artifact_integrity(name, recorded_digest, current_artifacts[name])
            artifact_checks.append(result)
            if result.status == STATUS_ARTIFACT_INTEGRITY_FAILURE:
                return VerificationResult(
                    status=VERIFY_ARTIFACT_MISMATCH,
                    detail={
                        "mismatched_artifact": name,
                        "recorded_digest": result.recorded_digest,
                        "recomputed_digest": result.recomputed_digest,
                    },
                )

    if (
        current_configuration_fingerprint is not None
        and current_configuration_fingerprint != manifest["configuration_fingerprint"]
    ):
        return VerificationResult(
            status=VERIFY_CONFIGURATION_MISMATCH,
            detail={
                "recorded": manifest["configuration_fingerprint"],
                "current": current_configuration_fingerprint,
            },
        )

    if (
        current_input_fingerprint is not None
        and current_input_fingerprint != manifest["input_fingerprint"]
    ):
        return VerificationResult(
            status=VERIFY_INPUT_MISMATCH,
            detail={
                "recorded": manifest["input_fingerprint"],
                "current": current_input_fingerprint,
            },
        )

    return VerificationResult(
        status=VERIFY_REPRODUCIBLE_MATCH,
        detail={
            "artifacts_checked": [c.name for c in artifact_checks],
            "num_artifacts_checked": len(artifact_checks),
        },
    )


# ---------------------------------------------------------------------------
# Synthetic run reconstruction
# ---------------------------------------------------------------------------


def reconstruct_and_verify(
    manifest: Mapping[str, Any],
    rerun_fn: Callable[[], Any],
) -> VerificationResult:
    """Synthetic run-reconstruction check: re-run `rerun_fn()` (a zero-argument callable
    that reconstructs and re-executes a synthetic evaluation from the manifest's recorded
    inputs) and verify its `fingerprint()` matches `manifest["result_fingerprint"]`
    (an extra, non-required field a caller may attach via `build_manifest(**extra)` when
    it wants this specific check -- reconstruction-fingerprint verification is not one of
    the `REQUIRED_MANIFEST_FIELDS` since it is specific to this synthetic-reconstruction
    scenario, not to every manifest use case).

    Returns `VERIFY_UNDEFINED` if the manifest carries no `result_fingerprint` to compare
    against -- reconstruction cannot be verified without a recorded expected fingerprint,
    and this function never guesses one.
    """
    if "result_fingerprint" not in manifest:
        return VerificationResult(
            status=VERIFY_UNDEFINED,
            detail={"reason": "manifest has no 'result_fingerprint' to reconstruct against"},
        )

    reconstructed_result = rerun_fn()
    reconstructed_fingerprint = fingerprint(reconstructed_result)
    matches = reconstructed_fingerprint == manifest["result_fingerprint"]

    return VerificationResult(
        status=VERIFY_REPRODUCIBLE_MATCH if matches else VERIFY_INPUT_MISMATCH,
        detail={
            "recorded_result_fingerprint": manifest["result_fingerprint"],
            "reconstructed_result_fingerprint": reconstructed_fingerprint,
            "matches": matches,
        },
    )
