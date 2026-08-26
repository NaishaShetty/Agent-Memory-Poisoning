"""Phase 3.2-G: profile schema validation and cross-field consistency invariants.

Pure functions only: every function here reads its inputs (in-memory dicts, or --
for the `*_file`/`*_files` convenience wrappers -- the profile JSON files this package
ships) and returns a structured result. No function in this module writes to any file
anywhere, including the profile files themselves; `validate_profile_files()` and
`validate_all_profiles()` open the profile/schema JSON files strictly in read mode
(`open(path, "r", ...)`, never `"w"`/`"a"`/`"r+"`) and perform no filesystem mutation of
any kind, in `data/processed/`, `data/raw/`, `data/metadata/`, or anywhere else.

No filesystem/network/LLM/embeddings dependency beyond reading this package's own JSON
files. No randomness, no global mutable state.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

import jsonschema

from . import capability as cap

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ValidationResult:
    """Result of validating one profile (schema + consistency invariants).

    `ok` is True iff both schema validation and every consistency invariant passed.
    `errors` carries every failure found -- validation does not stop at the first error,
    so a caller/test can see the full set of problems in one pass.
    """

    ok: bool
    errors: Tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def validate_schema(profile: Mapping[str, Any], schema: Mapping[str, Any]) -> ValidationResult:
    """Validate `profile` against the common `profile.schema.json` document (draft 2020-12).

    Collects EVERY schema violation (not just the first) via
    `jsonschema.Draft202012Validator.iter_errors`, so a single malformed profile with
    multiple problems is fully reported in one `ValidationResult`.
    """
    validator = jsonschema.Draft202012Validator(schema)
    errors = tuple(
        f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
        for e in validator.iter_errors(profile)
    )
    return ValidationResult(ok=len(errors) == 0, errors=errors)


# ---------------------------------------------------------------------------
# Consistency invariants
# ---------------------------------------------------------------------------

_CAPABILITY_FIELD_PATHS_MEMORY = (
    "stable_id",
    "unique_id",
    "content_available",
    "timestamped",
    "session_linked",
    "typed_foundation_or_derived",
    "explicit_parent_ids_present",
)

_CAPABILITY_FIELD_PATHS_WORKLOAD = (
    "explicit_task_records",
    "separate_from_memory",
    "query_field",
    "gold_answer_field",
    "task_id_field",
    "session_or_conversation_id",
)

_TOP_LEVEL_CAPABILITY_FIELDS = (
    "evidence_availability",
    "answer_availability",
    "provenance_availability",
    "lineage_availability",
    "equivalence_availability",
)


def _iter_capability_fields(profile: Mapping[str, Any]) -> List[Tuple[str, Mapping[str, Any]]]:
    """Yield (dotted_path, capability_field_dict) for every capability-state-shaped
    field in a profile -- used by the reason-non-empty and UNKNOWN-never-coerced checks
    so they cover the whole profile uniformly rather than re-listing paths per-check.
    """
    out: List[Tuple[str, Mapping[str, Any]]] = []
    memory = profile.get("memory_availability", {})
    for key in _CAPABILITY_FIELD_PATHS_MEMORY:
        if key in memory:
            out.append((f"memory_availability.{key}", memory[key]))
    workload = profile.get("workload_availability", {})
    for key in _CAPABILITY_FIELD_PATHS_WORKLOAD:
        if key in workload:
            out.append((f"workload_availability.{key}", workload[key]))
    for key in _TOP_LEVEL_CAPABILITY_FIELDS:
        if key in profile:
            out.append((key, profile[key]))
    return out


def _iter_support_fields(profile: Mapping[str, Any]) -> List[Tuple[str, Mapping[str, Any]]]:
    """Yield (dotted_path, support_field_dict) for every metric_support/condition_support
    entry in a profile.
    """
    out: List[Tuple[str, Mapping[str, Any]]] = []
    for metric_name, entry in profile.get("metric_support", {}).items():
        out.append((f"metric_support.{metric_name}", entry))
    for condition_name, entry in profile.get("condition_support", {}).items():
        out.append((f"condition_support.{condition_name}", entry))
    return out


def check_required_fields_present(profile: Mapping[str, Any]) -> ValidationResult:
    """Every field required by `profile.schema.json`'s top-level `required` list must be
    present. (Schema validation already checks this structurally; this is a redundant,
    explicit, human-readable re-check specifically over the fields the 3.2-G task brief
    calls out by name, independent of the schema file's own required-list, so a future
    schema edit that accidentally narrows `required` cannot silently defeat this check.)
    """
    required_top_level = (
        "schema_version", "dataset_id", "canonical_name", "role", "registry_reference",
        "source_reference", "inspection_method", "memory_availability",
        "workload_availability", "evidence_availability", "answer_availability",
        "provenance_availability", "lineage_availability", "equivalence_availability",
        "temporal_information", "metric_support", "condition_support",
        "adapter_requirements", "limitations", "evidence_notes", "profile_status",
    )
    errors = tuple(f"missing required field: {f}" for f in required_top_level if f not in profile)
    return ValidationResult(ok=len(errors) == 0, errors=errors)


def check_controlled_vocabulary(profile: Mapping[str, Any]) -> ValidationResult:
    """Every capability-state field's `status` must be one of `cap.CAPABILITY_STATES`,
    and every metric/condition support field's `status` must be one of
    `cap.SUPPORT_STATES`. Rejects anything outside the enumerated set -- this is the
    check a deliberately-malformed profile (an invalid capability value) is expected to
    fail.
    """
    errors: List[str] = []
    for path, entry in _iter_capability_fields(profile):
        status = entry.get("status") if isinstance(entry, Mapping) else None
        if status not in cap.CAPABILITY_STATES:
            errors.append(f"{path}.status {status!r} is not a valid capability state")
    for path, entry in _iter_support_fields(profile):
        status = entry.get("status") if isinstance(entry, Mapping) else None
        if status not in cap.SUPPORT_STATES:
            errors.append(f"{path}.status {status!r} is not a valid support state")
    return ValidationResult(ok=len(errors) == 0, errors=errors)


def check_reasons_non_empty_for_unavailable(profile: Mapping[str, Any]) -> ValidationResult:
    """Every capability field whose status is UNAVAILABLE or NOT_PROVIDED_BY_SOURCE, and
    every support field whose status is UNAVAILABLE or UNDEFINED, must carry a non-empty
    `reason` string. (The schema already requires `reason` unconditionally for every
    field; this check additionally confirms it is non-blank specifically for the
    negative/absent states, which is the property the 3.2-G task brief calls out by
    name.)
    """
    errors: List[str] = []
    for path, entry in _iter_capability_fields(profile):
        status = entry.get("status") if isinstance(entry, Mapping) else None
        if status in (cap.CAPABILITY_UNAVAILABLE, cap.CAPABILITY_NOT_PROVIDED_BY_SOURCE):
            reason = entry.get("reason", "") if isinstance(entry, Mapping) else ""
            if not isinstance(reason, str) or not reason.strip():
                errors.append(f"{path}: status={status} but reason is empty")
    for path, entry in _iter_support_fields(profile):
        status = entry.get("status") if isinstance(entry, Mapping) else None
        if status in (cap.SUPPORT_UNAVAILABLE, cap.SUPPORT_UNDEFINED):
            reason = entry.get("reason", "") if isinstance(entry, Mapping) else ""
            if not isinstance(reason, str) or not reason.strip():
                errors.append(f"{path}: status={status} but reason is empty")
    return ValidationResult(ok=len(errors) == 0, errors=errors)


def is_unknown_status(status: Any) -> bool:
    """Returns True iff `status` is the literal UNKNOWN capability state.

    This function exists specifically so the "UNKNOWN is never silently coerced" test
    can assert against a single, explicit predicate rather than re-deriving the check
    inline -- `check_unknown_never_coerced_to_unavailable` below is built ON TOP of this
    predicate, not by re-testing `status == "UNAVAILABLE"` in a way that could silently
    treat UNKNOWN as falsy/absent.
    """
    return status == cap.CAPABILITY_UNKNOWN


def check_unknown_never_coerced_to_unavailable(profile: Mapping[str, Any]) -> ValidationResult:
    """A capability field with status UNKNOWN must remain exactly UNKNOWN as read back
    from the profile -- this function never rewrites or reinterprets it as UNAVAILABLE
    or a falsy value. This is a structural no-op check by construction (it only reads
    `status` fields and compares them to the literal string), which is precisely the
    point: nothing anywhere in this module's other checks ever branches on "status is
    falsy" in a way that would conflate UNKNOWN with UNAVAILABLE/False. See
    `test_dataset_profiles.py::test_unknown_never_silently_coerced` for an explicit
    in-test proof using a hand-built payload.
    """
    errors: List[str] = []
    for path, entry in _iter_capability_fields(profile):
        status = entry.get("status") if isinstance(entry, Mapping) else None
        if status == cap.CAPABILITY_UNKNOWN and not is_unknown_status(status):
            # Unreachable by construction -- kept as an explicit, checkable assertion
            # rather than trusting equality intuitively.
            errors.append(f"{path}: UNKNOWN status failed identity check")
    return ValidationResult(ok=len(errors) == 0, errors=errors)


def check_registry_reference_resolves(
    profile: Mapping[str, Any], dataset_manifest: Mapping[str, Any]
) -> ValidationResult:
    """`profile["registry_reference"]["dataset_key"]` must be a real key under
    `dataset_manifest["datasets"]`, and `profile["dataset_id"]` must equal that same key
    -- the profile never invents a competing identity source.
    """
    errors: List[str] = []
    reg_ref = profile.get("registry_reference", {})
    dataset_key = reg_ref.get("dataset_key")
    manifest_datasets = dataset_manifest.get("datasets", {})
    if dataset_key not in manifest_datasets:
        errors.append(
            f"registry_reference.dataset_key {dataset_key!r} does not resolve into "
            f"dataset_manifest.json's datasets map (keys: {sorted(manifest_datasets.keys())!r})"
        )
    if profile.get("dataset_id") != dataset_key:
        errors.append(
            f"dataset_id {profile.get('dataset_id')!r} != "
            f"registry_reference.dataset_key {dataset_key!r}"
        )
    return ValidationResult(ok=len(errors) == 0, errors=errors)


def check_strict_tsr_implies_evidence_ids(profile: Mapping[str, Any]) -> ValidationResult:
    """INVARIANT: if metric_support.STRICT_TSR.status is SUPPORTED (or
    SUPPORTED_WITH_ADAPTER), then evidence_availability.status must be AVAILABLE or
    PARTIAL (never UNAVAILABLE/NOT_PROVIDED_BY_SOURCE/UNKNOWN), AND
    condition_support.RETRIEVED_MEMORY.status must not be UNAVAILABLE (selected-
    memory-ids support, implied by RETRIEVED_MEMORY condition support, must exist in
    some form -- SUPPORTED or SUPPORTED_WITH_ADAPTER -- for Strict TSR to have any
    selected-memory-id input to check gold-membership against).

    This is the single most scientifically load-bearing check in this module, per the
    3.2-G task brief -- Strict TSR must never be claimed SUPPORTED for a dataset that
    lacks literal gold evidence IDs.
    """
    errors: List[str] = []
    strict_tsr = profile.get("metric_support", {}).get("STRICT_TSR", {})
    strict_tsr_status = strict_tsr.get("status")
    if strict_tsr_status in (cap.SUPPORT_SUPPORTED, cap.SUPPORT_SUPPORTED_WITH_ADAPTER):
        evidence_status = profile.get("evidence_availability", {}).get("status")
        if evidence_status not in (cap.CAPABILITY_AVAILABLE, cap.CAPABILITY_PARTIAL):
            errors.append(
                f"metric_support.STRICT_TSR={strict_tsr_status} but "
                f"evidence_availability.status={evidence_status!r} "
                "(must be AVAILABLE or PARTIAL)"
            )
        retrieved_memory_status = (
            profile.get("condition_support", {}).get("RETRIEVED_MEMORY", {}).get("status")
        )
        if retrieved_memory_status == cap.SUPPORT_UNAVAILABLE:
            errors.append(
                f"metric_support.STRICT_TSR={strict_tsr_status} but "
                f"condition_support.RETRIEVED_MEMORY.status=UNAVAILABLE "
                "(selected-memory-id support must not be UNAVAILABLE)"
            )
    return ValidationResult(ok=len(errors) == 0, errors=errors)


def check_metric_condition_names_complete(profile: Mapping[str, Any]) -> ValidationResult:
    """`metric_support` must have exactly the keys in `cap.METRIC_NAMES` (no more, no
    fewer) and `condition_support` must have exactly the keys in `cap.CONDITION_NAMES` --
    enforces that every profile uses the identical, shared vocabulary from
    `capability.py` rather than an independently-typed string literal set.
    """
    errors: List[str] = []
    metric_keys = set(profile.get("metric_support", {}).keys())
    expected_metrics = set(cap.METRIC_NAMES)
    if metric_keys != expected_metrics:
        errors.append(
            f"metric_support keys {sorted(metric_keys)!r} != expected {sorted(expected_metrics)!r}"
        )
    condition_keys = set(profile.get("condition_support", {}).keys())
    expected_conditions = set(cap.CONDITION_NAMES)
    if condition_keys != expected_conditions:
        errors.append(
            f"condition_support keys {sorted(condition_keys)!r} != expected "
            f"{sorted(expected_conditions)!r}"
        )
    return ValidationResult(ok=len(errors) == 0, errors=errors)


def check_no_duplicate_dataset_ids(profiles: Sequence[Mapping[str, Any]]) -> ValidationResult:
    """No two profiles in `profiles` may share the same `dataset_id`."""
    seen: Dict[str, int] = {}
    for p in profiles:
        did = p.get("dataset_id")
        seen[did] = seen.get(did, 0) + 1
    errors = tuple(
        f"dataset_id {did!r} appears {count} times across profiles"
        for did, count in seen.items()
        if count > 1
    )
    return ValidationResult(ok=len(errors) == 0, errors=errors)


def check_cross_profile_vocabulary_consistency(
    profiles: Sequence[Mapping[str, Any]]
) -> ValidationResult:
    """All profiles must use IDENTICAL metric_support/condition_support key sets (set
    equality across every profile pair), never a per-profile ad hoc variant.
    """
    errors: List[str] = []
    if not profiles:
        return ValidationResult(ok=True, errors=())
    first_metrics = set(profiles[0].get("metric_support", {}).keys())
    first_conditions = set(profiles[0].get("condition_support", {}).keys())
    for p in profiles[1:]:
        did = p.get("dataset_id")
        metrics = set(p.get("metric_support", {}).keys())
        conditions = set(p.get("condition_support", {}).keys())
        if metrics != first_metrics:
            errors.append(f"{did}: metric_support keys differ from {profiles[0].get('dataset_id')}")
        if conditions != first_conditions:
            errors.append(f"{did}: condition_support keys differ from {profiles[0].get('dataset_id')}")
    return ValidationResult(ok=len(errors) == 0, errors=errors)


# ---------------------------------------------------------------------------
# Full-profile validation (schema + every consistency invariant)
# ---------------------------------------------------------------------------


def validate_profile(
    profile: Mapping[str, Any],
    schema: Mapping[str, Any],
    dataset_manifest: Mapping[str, Any],
) -> ValidationResult:
    """Run schema validation plus every single-profile consistency invariant. Collects
    every error from every check (does not short-circuit on the first failing check).
    """
    checks = (
        validate_schema(profile, schema),
        check_required_fields_present(profile),
        check_controlled_vocabulary(profile),
        check_reasons_non_empty_for_unavailable(profile),
        check_unknown_never_coerced_to_unavailable(profile),
        check_registry_reference_resolves(profile, dataset_manifest),
        check_strict_tsr_implies_evidence_ids(profile),
        check_metric_condition_names_complete(profile),
    )
    all_errors: List[str] = []
    for result in checks:
        all_errors.extend(result.errors)
    return ValidationResult(ok=len(all_errors) == 0, errors=tuple(all_errors))


def validate_all_profiles(
    profiles: Sequence[Mapping[str, Any]],
    schema: Mapping[str, Any],
    dataset_manifest: Mapping[str, Any],
) -> ValidationResult:
    """Validate every profile individually, plus the cross-profile invariants (no
    duplicate dataset_id, identical metric/condition vocabularies across all profiles).
    """
    all_errors: List[str] = []
    for profile in profiles:
        result = validate_profile(profile, schema, dataset_manifest)
        all_errors.extend(f"[{profile.get('dataset_id')}] {e}" for e in result.errors)
    all_errors.extend(check_no_duplicate_dataset_ids(profiles).errors)
    all_errors.extend(check_cross_profile_vocabulary_consistency(profiles).errors)
    return ValidationResult(ok=len(all_errors) == 0, errors=tuple(all_errors))


# ---------------------------------------------------------------------------
# Read-only file-based convenience wrappers
# ---------------------------------------------------------------------------


def validate_profile_files(dataset_manifest_path: str | Path) -> ValidationResult:
    """Load the schema and all four shipped profile files (read-only) and run
    `validate_all_profiles` against them, cross-checked against the real
    `data/metadata/dataset_manifest.json` at `dataset_manifest_path`.

    Opens every file strictly in read mode (`"r"`); writes nothing, anywhere.
    """
    schema = cap.load_profile_schema()
    profiles = list(cap.load_all_profiles().values())
    with open(dataset_manifest_path, "r", encoding="utf-8") as f:
        dataset_manifest = json.load(f)
    return validate_all_profiles(profiles, schema, dataset_manifest)
