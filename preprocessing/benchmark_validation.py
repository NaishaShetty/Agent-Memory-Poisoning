"""Phase 2.4: benchmark-organization validation, in the same streaming
check-list-report style as unified_validation.py (Phase 2.2) and
temporal_validation.py (Phase 2.3). Also re-runs the Phase 2.2/2.3
validators themselves so a single Phase 2.4 report answers "did Phase 2.4
break anything earlier" without the caller needing to know which older
module to re-invoke.
"""
from __future__ import annotations

from pathlib import Path

from preprocessing.benchmark_organization import (
    APPROVED_MEMORY_FOUNDATION,
    ROLE_ATTACK,
    ROLE_EVALUATION,
    ROLE_MEMORY,
    ROLE_SLEEPER,
    ROLE_WORKLOAD,
    VALID_ROLES,
    build_benchmark_organization,
)
from preprocessing.config import PipelineConfig
from preprocessing.io_utils import write_json
from preprocessing.registry import build_registry_report
from preprocessing.temporal import NORMALIZATION_POLICY_VERSION
from preprocessing.temporal_validation import validate_temporal
from preprocessing.unified_schema import CORE_DATASETS, SCHEMA_VERSION
from preprocessing.unified_validation import validate_cross_dataset

# The real corpus's expected per-dataset record counts, as established and
# validated by Phase 2.2/2.3 (see docs/phase2/UNIFIED_MEMORY_RECORD.md and
# docs/phase2/TEMPORAL_NORMALIZATION.md). Phase 2.4 does not recompute these --
# it asserts they are still exactly what Phase 2.2/2.3 already proved, by
# reading (not regenerating) the validators' own fresh output below.
_EXPECTED_MEMORY_RECORD_COUNTS = {
    "locomo": 5882,
    "longmemeval": 210365,
    "msc": 227185,
    "conversation_chronicles": 822762,
}
_EXPECTED_TOTAL = sum(_EXPECTED_MEMORY_RECORD_COUNTS.values())


def validate_benchmark_organization(cfg: PipelineConfig, generated_at: str) -> dict:
    checks = []

    registry_report = build_registry_report(cfg)
    all_resource_ids = {e["resource_id"] for e in registry_report["resources"]}

    org_a = build_benchmark_organization(cfg, generated_at)
    org_b = build_benchmark_organization(cfg, generated_at)  # Test 9: determinism

    by_id = {e["resource_id"]: e for e in org_a["resources"]}

    # Test 1 -- all known resources are classified
    unclassified = sorted(all_resource_ids - set(by_id))
    checks.append({
        "name": "all_registry_resources_have_a_primary_role",
        "status": "PASS" if not unclassified else "FAIL",
        "detail": {"unclassified_resource_ids": unclassified},
    })

    # Test 2 -- no unknown role
    bad_roles = [
        {"resource_id": rid, "primary_role": e["primary_role"]}
        for rid, e in by_id.items() if e["primary_role"] not in VALID_ROLES
    ]
    checks.append({
        "name": "every_primary_role_is_from_the_approved_vocabulary",
        "status": "PASS" if not bad_roles else "FAIL",
        "detail": {"violations": bad_roles},
    })

    # Test 3 -- memory foundation boundary
    memory_role_ids = {rid for rid, e in by_id.items() if e["primary_role"] == ROLE_MEMORY}
    checks.append({
        "name": "memory_foundation_is_exactly_the_four_approved_datasets",
        "status": "PASS" if memory_role_ids == APPROVED_MEMORY_FOUNDATION else "FAIL",
        "detail": {"expected": sorted(APPROVED_MEMORY_FOUNDATION), "actual": sorted(memory_role_ids)},
    })

    # Test 4 -- no attack resource in the memory foundation
    attack_in_memory = sorted({rid for rid, e in by_id.items() if e["primary_role"] == ROLE_ATTACK} & APPROVED_MEMORY_FOUNDATION)
    checks.append({
        "name": "no_attack_resource_in_memory_foundation",
        "status": "PASS" if not attack_in_memory else "FAIL",
        "detail": {"violations": attack_in_memory},
    })

    # Test 5 -- no sleeper resource in the memory foundation
    sleeper_in_memory = sorted({rid for rid, e in by_id.items() if e["primary_role"] == ROLE_SLEEPER} & APPROVED_MEMORY_FOUNDATION)
    checks.append({
        "name": "no_sleeper_resource_in_memory_foundation",
        "status": "PASS" if not sleeper_in_memory else "FAIL",
        "detail": {"violations": sleeper_in_memory},
    })

    # Test 6 -- workload separation (and, for completeness, evaluation too)
    workload_in_memory = sorted({rid for rid, e in by_id.items() if e["primary_role"] == ROLE_WORKLOAD} & APPROVED_MEMORY_FOUNDATION)
    evaluation_in_memory = sorted({rid for rid, e in by_id.items() if e["primary_role"] == ROLE_EVALUATION} & APPROVED_MEMORY_FOUNDATION)
    checks.append({
        "name": "no_workload_or_evaluation_resource_in_memory_foundation",
        "status": "PASS" if not workload_in_memory and not evaluation_in_memory else "FAIL",
        "detail": {"workload_violations": workload_in_memory, "evaluation_violations": evaluation_in_memory},
    })

    # Test 7 -- provenance preservation: every organized resource still
    # carries a non-empty source_reference and an explicit source/
    # mambench_created provenance split.
    missing_provenance = [
        rid for rid, e in by_id.items()
        if not e.get("source_reference")
        or not e.get("provenance", {}).get("source")
        or not e.get("provenance", {}).get("mambench_created")
    ]
    checks.append({
        "name": "every_resource_retains_source_provenance",
        "status": "PASS" if not missing_provenance else "FAIL",
        "detail": {"violations": sorted(missing_provenance)},
    })

    # Test 8 -- availability honesty: phase2_input_approved is True only
    # for the exact memory foundation (mirrors Phase 2.1's own invariant,
    # re-checked here rather than assumed), and a resource with no on-disk
    # artifact evidence at all is never marked phase2_input_approved.
    approved_ids = {rid for rid, e in by_id.items() if e.get("phase2_input_approved") is True}
    honesty_violations = []
    if approved_ids != APPROVED_MEMORY_FOUNDATION:
        honesty_violations.append({"reason": "phase2_input_approved set does not equal the memory foundation", "actual": sorted(approved_ids)})
    for rid, e in by_id.items():
        presence = e.get("artifact_presence_on_disk") or {}
        nothing_on_disk = (
            not presence.get("raw_present_on_disk")
            and not presence.get("interim_present_on_disk")
            and not presence.get("processed_files_on_disk")
        )
        if nothing_on_disk and e.get("phase2_input_approved") is True:
            honesty_violations.append({"resource_id": rid, "reason": "approved with no artifact evidence on disk"})
    checks.append({
        "name": "availability_is_represented_honestly",
        "status": "PASS" if not honesty_violations else "FAIL",
        "detail": {"violations": honesty_violations},
    })

    # Test 9 -- deterministic organization (two independent runs, same input)
    checks.append({
        "name": "organization_is_deterministic_across_independent_runs",
        "status": "PASS" if org_a["resources"] == org_b["resources"] and org_a["resources_by_role"] == org_b["resources_by_role"] else "FAIL",
        "detail": {},
    })

    # Test 10 -- no data mutation: Phase 2.4 must not have touched the
    # frozen Phase 1 processed files. Re-checked by re-reading the record
    # counts unified_validation.py already independently verified equal
    # Phase 1's own processed output (its own
    # 'record_counts_match_phase1_processed_output' check), rather than
    # re-hashing the corpus here.
    umr_report = validate_cross_dataset(cfg)
    counts_check = next((c for c in umr_report["checks"] if c["name"] == "record_counts_match_phase1_processed_output"), None)
    checks.append({
        "name": "phase1_processed_data_not_mutated_by_phase2_4",
        "status": "PASS" if counts_check and counts_check["status"] == "PASS" else "FAIL",
        "detail": {"source_check": counts_check},
    })

    # Test 11 -- existing Phase 2.2 / 2.3 regression: re-run both real
    # validators fresh (not just read their last-written report) and
    # require PASS.
    temporal_report = validate_temporal(cfg)
    checks.append({
        "name": "phase2_2_unified_memory_validation_still_passes",
        "status": umr_report["overall_status"],
        "detail": {"total_records": umr_report["total_records"]},
    })
    checks.append({
        "name": "phase2_3_temporal_validation_still_passes",
        "status": temporal_report["overall_status"],
        "detail": {"total_records": temporal_report["total_records"]},
    })

    # Test 12 -- UMR integrity: schema/policy versions unchanged, exact
    # expected record counts, no cross-dataset collisions.
    umr_integrity_violations = []
    if SCHEMA_VERSION != "1.1.0":
        umr_integrity_violations.append(f"unified_schema.SCHEMA_VERSION is {SCHEMA_VERSION!r}, expected '1.1.0'")
    if NORMALIZATION_POLICY_VERSION != "2.3.0":
        umr_integrity_violations.append(f"temporal.NORMALIZATION_POLICY_VERSION is {NORMALIZATION_POLICY_VERSION!r}, expected '2.3.0'")
    if umr_report["per_dataset_counts"] != _EXPECTED_MEMORY_RECORD_COUNTS:
        umr_integrity_violations.append({"reason": "per-dataset record counts changed", "expected": _EXPECTED_MEMORY_RECORD_COUNTS, "actual": umr_report["per_dataset_counts"]})
    if umr_report["total_records"] != _EXPECTED_TOTAL:
        umr_integrity_violations.append({"reason": "total record count changed", "expected": _EXPECTED_TOTAL, "actual": umr_report["total_records"]})
    collision_check = next((c for c in umr_report["checks"] if c["name"] == "no_cross_dataset_id_collision"), None)
    if not collision_check or collision_check["status"] != "PASS":
        umr_integrity_violations.append({"reason": "cross-dataset ID collisions detected", "detail": collision_check})
    checks.append({
        "name": "umr_schema_temporal_policy_and_record_counts_unchanged",
        "status": "PASS" if not umr_integrity_violations else "FAIL",
        "detail": {"violations": umr_integrity_violations, "expected_total": _EXPECTED_TOTAL, "expected_per_dataset": _EXPECTED_MEMORY_RECORD_COUNTS},
    })

    overall_status = "PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL"
    return {
        "schema_version": "1.0.0",
        "generated_at": generated_at,
        "overall_status": overall_status,
        "total_resources_organized": len(by_id),
        "resource_count_by_role": org_a["resource_count_by_role"],
        "checks": checks,
    }


def write_benchmark_validation_report(cfg: PipelineConfig, generated_at: str | None = None) -> Path:
    if generated_at is None:
        import datetime as _dt

        generated_at = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = validate_benchmark_organization(cfg, generated_at)
    out_path = cfg.reports_dir / "phase2_4_benchmark_organization_validation_report.json"
    write_json(out_path, report)
    return out_path


if __name__ == "__main__":
    from preprocessing.config import load_config

    _cfg = load_config()
    _path = write_benchmark_validation_report(_cfg)
    print(f"Wrote {_path}")
