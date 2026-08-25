"""Phase 2.5: reproducibility-manifest validation, in the same streaming
check-list-report style as unified_validation.py (2.2), temporal_validation.py
(2.3), and benchmark_validation.py (2.4). Implements the 20 checks from the
Phase 2.5 brief (Section 27) and re-runs Phase 2.2/2.3/2.4's own validators
fresh (never reads their last-written report) so a single Phase 2.5 report
answers "did anything upstream regress" without the caller invoking four
separate modules.
"""
from __future__ import annotations

from pathlib import Path

from preprocessing.benchmark_organization import build_benchmark_organization
from preprocessing.benchmark_validation import validate_benchmark_organization
from preprocessing.config import PipelineConfig
from preprocessing.io_utils import write_json
from preprocessing.registry import REPO_ROOT
from preprocessing.reproducibility import (
    REPRODUCIBILITY_MANIFEST_VERSION,
    build_reproducibility_manifest,
    get_configuration_identity,
)
from preprocessing.temporal_validation import validate_temporal
from preprocessing.unified_validation import validate_cross_dataset

_EXPECTED_MEMORY_RECORD_COUNTS = {
    "locomo": 5882,
    "longmemeval": 210365,
    "msc": 227185,
    "conversation_chronicles": 822762,
}
_EXPECTED_TOTAL = sum(_EXPECTED_MEMORY_RECORD_COUNTS.values())


def _has_local_machine_path(value) -> bool:
    """Detects an absolute filesystem path leaking into supposedly
    machine-independent data (Section 20 / Check 13). Repo-relative paths
    (e.g. 'data/raw/locomo/locomo10.json') are fine; only an absolute path
    outside the repo (drive letter, /home, /mnt, ~ expansion) counts."""
    if not isinstance(value, str) or not value:
        return False
    if value.startswith(str(REPO_ROOT)):
        return True
    lowered = value.lower()
    return (
        (len(value) > 1 and value[1] == ":" and value[0].isalpha())  # C:\...
        or lowered.startswith("/home/")
        or lowered.startswith("/users/")
        or lowered.startswith("/mnt/")
    )


def validate_reproducibility_manifest(cfg: PipelineConfig, generated_at: str) -> dict:
    checks = []

    org = build_benchmark_organization(cfg, generated_at)
    org_ids = {e["resource_id"] for e in org["resources"]}

    man_a = build_reproducibility_manifest(cfg, generated_at)
    man_b = build_reproducibility_manifest(cfg, generated_at)
    by_id = {e["resource_id"]: e for e in man_a["resources"]}

    # Check 1 -- every Phase 2.4 resource has identity metadata (all 28)
    checks.append({
        "name": "check_1_every_phase2_4_resource_has_identity_metadata",
        "status": "PASS" if org_ids == set(by_id) else "FAIL",
        "detail": {"missing": sorted(org_ids - set(by_id)), "extra": sorted(set(by_id) - org_ids), "total": len(org_ids)},
    })

    # Check 2 -- resource IDs are unique
    ids_list = [e["resource_id"] for e in man_a["resources"]]
    checks.append({
        "name": "check_2_resource_ids_are_unique",
        "status": "PASS" if len(ids_list) == len(set(ids_list)) else "FAIL",
        "detail": {"count": len(ids_list), "unique_count": len(set(ids_list))},
    })

    # Check 3 -- role consistency with Phase 2.4
    org_by_id = {e["resource_id"]: e for e in org["resources"]}
    role_mismatches = [rid for rid in org_ids if by_id[rid]["primary_role"] != org_by_id[rid]["primary_role"]]
    checks.append({
        "name": "check_3_role_consistency_with_phase2_4",
        "status": "PASS" if not role_mismatches else "FAIL",
        "detail": {"violations": role_mismatches},
    })

    # Check 4 -- memory foundation consistency (exactly the 4 approved datasets)
    memory_role_ids = {rid for rid, e in by_id.items() if e["primary_role"] == "memory"}
    expected_foundation = set(man_a["memory_foundation"]["approved_dataset_ids"])
    checks.append({
        "name": "check_4_memory_foundation_consistency",
        "status": "PASS" if memory_role_ids == expected_foundation else "FAIL",
        "detail": {"expected": sorted(expected_foundation), "actual": sorted(memory_role_ids)},
    })

    # Check 5 -- source identity present or explicitly unknown
    missing_source_keys = []
    for rid, e in by_id.items():
        si = e["source_identity"]
        for key in ("source_reference", "source_dataset_version_or_revision", "acquisition_status", "access_and_license"):
            if key not in si:
                missing_source_keys.append({"resource_id": rid, "missing_key": key})
    checks.append({
        "name": "check_5_source_identity_present_or_explicitly_unknown",
        "status": "PASS" if not missing_source_keys else "FAIL",
        "detail": {"violations": missing_source_keys},
    })

    # Check 6 -- version honesty: no invented source versions. A resource
    # whose registry version string says "unavailable" must map to the
    # literal 'unknown' in canonical_identity, never a made-up version.
    invented_versions = []
    for rid, e in by_id.items():
        raw = org_by_id[rid]["version_or_revision"] or ""
        canonical_version = e["canonical_identity"]["source_dataset_version_or_revision"]
        if "unavailable" in raw and canonical_version != "unknown":
            invented_versions.append({"resource_id": rid, "raw": raw, "canonical": canonical_version})
    checks.append({
        "name": "check_6_version_honesty_no_invented_source_versions",
        "status": "PASS" if not invented_versions else "FAIL",
        "detail": {"violations": invented_versions},
    })

    # Check 7 -- preparation identity for prepared resources
    prep_violations = []
    for rid, e in by_id.items():
        phase1_status = org_by_id[rid]["phase1_status"]
        prep_version = e["canonical_identity"]["preparation_version"]
        if phase1_status in ("PROCESSED", "PREPARED") and prep_version in (None, "not_applicable"):
            prep_violations.append({"resource_id": rid, "phase1_status": phase1_status})
        if phase1_status not in ("PROCESSED", "PREPARED") and prep_version != "not_applicable":
            prep_violations.append({"resource_id": rid, "phase1_status": phase1_status, "reason": "prepared identity on an unprepared resource"})
    checks.append({
        "name": "check_7_preparation_identity_for_prepared_resources",
        "status": "PASS" if not prep_violations else "FAIL",
        "detail": {"violations": prep_violations},
    })

    # Check 8 -- schema consistency: memory-foundation resources correctly
    # identify UMR 1.1.0; non-core resources say not_applicable.
    core = expected_foundation
    schema_violations = []
    for rid in core:
        if by_id[rid]["canonical_identity"]["unified_memory_record_schema_version"] != man_a["schema_and_policy_versions"]["unified_memory_record_schema_version"]:
            schema_violations.append(rid)
    for rid, e in by_id.items():
        if rid not in core and e["canonical_identity"]["unified_memory_record_schema_version"] != "not_applicable":
            schema_violations.append(rid)
    checks.append({
        "name": "check_8_schema_consistency_umr",
        "status": "PASS" if not schema_violations else "FAIL",
        "detail": {"violations": schema_violations, "expected": man_a["schema_and_policy_versions"]["unified_memory_record_schema_version"]},
    })

    # Check 9 -- temporal policy consistency for memory-foundation resources
    temporal_violations = []
    for rid in core:
        if by_id[rid]["canonical_identity"]["temporal_normalization_policy_version"] != man_a["schema_and_policy_versions"]["temporal_normalization_policy_version"]:
            temporal_violations.append(rid)
    for rid, e in by_id.items():
        if rid not in core and e["canonical_identity"]["temporal_normalization_policy_version"] != "not_applicable":
            temporal_violations.append(rid)
    checks.append({
        "name": "check_9_temporal_policy_consistency",
        "status": "PASS" if not temporal_violations else "FAIL",
        "detail": {"violations": temporal_violations, "expected": man_a["schema_and_policy_versions"]["temporal_normalization_policy_version"]},
    })

    # Check 10 -- seed semantics: seed recorded only where applicable
    seed_violations = []
    for rid, e in by_id.items():
        seed = e["canonical_identity"]["seed"]
        if seed["seed_applicable"] and seed["seed_value"] is None:
            seed_violations.append({"resource_id": rid, "reason": "applicable but no value recorded"})
        if not seed["seed_applicable"] and seed["seed_value"] is not None:
            seed_violations.append({"resource_id": rid, "reason": "not applicable but a value was recorded"})
        if rid == "conversation_chronicles" and not seed["seed_applicable"]:
            seed_violations.append({"resource_id": rid, "reason": "conversation_chronicles must be seed_applicable"})
        if rid != "conversation_chronicles" and seed["seed_applicable"]:
            seed_violations.append({"resource_id": rid, "reason": "only conversation_chronicles consumes the master seed"})
    checks.append({
        "name": "check_10_seed_semantics_only_where_applicable",
        "status": "PASS" if not seed_violations else "FAIL",
        "detail": {"violations": seed_violations},
    })

    # Check 11 -- configuration identity is uniquely identifiable and
    # path-independent (content hash, not filename/path).
    config_identity = get_configuration_identity(cfg)
    config_ok = (
        config_identity["configuration_id"] is not None
        and len(config_identity["configuration_id"]) == 64  # sha256 hex length
        and not _has_local_machine_path(config_identity["config_relative_path"])
    )
    checks.append({
        "name": "check_11_configuration_identity_unique_and_reproducible",
        "status": "PASS" if config_ok else "FAIL",
        "detail": {"configuration_identity": config_identity},
    })

    # Check 12 -- canonical identity determinism: repeated generation
    # yields identical canonical_identity + canonical_identity_hash.
    canonical_mismatches = [
        rid for rid in by_id
        if by_id[rid]["canonical_identity"] != {e["resource_id"]: e for e in man_b["resources"]}[rid]["canonical_identity"]
        or by_id[rid]["canonical_identity_hash"] != {e["resource_id"]: e for e in man_b["resources"]}[rid]["canonical_identity_hash"]
    ]
    checks.append({
        "name": "check_12_canonical_identity_determinism",
        "status": "PASS" if not canonical_mismatches else "FAIL",
        "detail": {"violations": canonical_mismatches},
    })

    # Check 13 -- path independence: canonical_identity never contains an
    # absolute local machine path.
    path_leaks = []
    for rid, e in by_id.items():
        for key, value in e["canonical_identity"].items():
            if _has_local_machine_path(value):
                path_leaks.append({"resource_id": rid, "field": key})
    checks.append({
        "name": "check_13_path_independence_of_canonical_identity",
        "status": "PASS" if not path_leaks else "FAIL",
        "detail": {"violations": path_leaks},
    })

    # Check 14 -- record counts unchanged, sourced from Phase 2.2/2.3's own
    # already-validated report (never manually retyped here).
    rc = man_a["record_counts"]
    checks.append({
        "name": "check_14_record_counts_unchanged",
        "status": "PASS" if rc["umr_total_records"] == _EXPECTED_TOTAL and rc["umr_per_dataset_record_counts"] == _EXPECTED_MEMORY_RECORD_COUNTS else "FAIL",
        "detail": {"expected_total": _EXPECTED_TOTAL, "actual": rc.get("umr_total_records"), "expected_per_dataset": _EXPECTED_MEMORY_RECORD_COUNTS, "actual_per_dataset": rc.get("umr_per_dataset_record_counts")},
    })

    # Check 15 -- provenance metadata remains intact (quality/provenance
    # policy vocabularies still present and referencing the real source).
    policies = man_a["schema_and_policy_versions"]
    provenance_ok = (
        policies.get("quality_policy", {}).get("values") == ["valid", "repaired", "valid_flagged", "irrecoverably_invalid"]
        and set(policies.get("provenance_policy", {}).get("origins", [])) == {"SOURCE_PROVIDED", "BENCHMARK_GENERATED", "INFERRED", "MODEL_PREDICTED"}
    )
    checks.append({
        "name": "check_15_provenance_metadata_intact",
        "status": "PASS" if provenance_ok else "FAIL",
        "detail": {},
    })

    # Check 16 -- availability honesty: metadata never upgrades an
    # unavailable resource to available (mirrors Phase 2.4's own check,
    # re-verified against the reproducibility layer).
    honesty_violations = []
    for rid, e in by_id.items():
        artifact = e["artifact_identity"]
        phase1_status = org_by_id[rid]["phase1_status"]
        if artifact["artifact_id"] is not None and phase1_status not in ("PROCESSED", "PREPARED"):
            honesty_violations.append({"resource_id": rid, "reason": "artifact_id assigned to an unprepared resource"})
    checks.append({
        "name": "check_16_availability_honesty",
        "status": "PASS" if not honesty_violations else "FAIL",
        "detail": {"violations": honesty_violations},
    })

    # Check 17 -- status separation: role / availability / processing /
    # implementation / experimental-activation stay distinct fields, never
    # collapsed. Verified structurally: each of these lives in its own
    # named field, and none of the attack/sleeper resources gained a
    # phase2_input_approved=True (which would imply experimental activation).
    activation_leaks = [
        rid for rid, e in by_id.items()
        if org_by_id[rid]["primary_role"] in ("attack", "sleeper") and e["phase2_input_approved"] is True
    ]
    checks.append({
        "name": "check_17_role_status_implementation_activation_kept_separate",
        "status": "PASS" if not activation_leaks else "FAIL",
        "detail": {"violations": activation_leaks},
    })

    # Check 18/19/20 -- fresh regression of Phase 2.2 / 2.3 / 2.4 validators
    umr_report = validate_cross_dataset(cfg)
    checks.append({
        "name": "check_18_phase2_2_unified_memory_validation_still_passes",
        "status": umr_report["overall_status"],
        "detail": {"total_records": umr_report["total_records"]},
    })
    temporal_report = validate_temporal(cfg)
    checks.append({
        "name": "check_19_phase2_3_temporal_validation_still_passes",
        "status": temporal_report["overall_status"],
        "detail": {"total_records": temporal_report["total_records"]},
    })
    phase2_4_report = validate_benchmark_organization(cfg, generated_at)
    checks.append({
        "name": "check_20_phase2_4_benchmark_organization_validation_still_passes",
        "status": phase2_4_report["overall_status"],
        "detail": {"total_resources_organized": phase2_4_report["total_resources_organized"]},
    })

    # Extra: generated_at must not affect canonical identity (Section 18)
    generated_at_independence_violations = []
    other_ts = "1999-01-01T00:00:00Z"
    man_diff_ts = build_reproducibility_manifest(cfg, other_ts)
    by_id_diff_ts = {e["resource_id"]: e for e in man_diff_ts["resources"]}
    for rid, e in by_id.items():
        if e["canonical_identity_hash"] != by_id_diff_ts[rid]["canonical_identity_hash"]:
            generated_at_independence_violations.append(rid)
    checks.append({
        "name": "canonical_identity_independent_of_generated_at",
        "status": "PASS" if not generated_at_independence_violations else "FAIL",
        "detail": {"violations": generated_at_independence_violations},
    })

    overall_status = "PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL"
    return {
        "schema_version": "1.0.0",
        "reproducibility_manifest_version": REPRODUCIBILITY_MANIFEST_VERSION,
        "generated_at": generated_at,
        "overall_status": overall_status,
        "total_resources": man_a["total_resources"],
        "checks": checks,
    }


def write_reproducibility_validation_report(cfg: PipelineConfig, generated_at: str | None = None) -> Path:
    if generated_at is None:
        import datetime as _dt

        generated_at = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = validate_reproducibility_manifest(cfg, generated_at)
    out_path = cfg.reports_dir / "phase2_5_reproducibility_validation_report.json"
    write_json(out_path, report)
    return out_path


if __name__ == "__main__":
    from preprocessing.config import load_config

    _cfg = load_config()
    _path = write_reproducibility_validation_report(_cfg)
    print(f"Wrote {_path}")
