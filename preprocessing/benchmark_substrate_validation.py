"""Phase 2.6: benchmark-substrate validation -- the final, cross-phase
quality-control gate before Phase 2 is frozen (Phase 2.7).

SCOPE (see docs/phase2/BENCHMARK_SUBSTRATE_VALIDATION.md for the full
statement): earlier Phase 2 modules each validate ONE component in
isolation --

    unified_validation.py        (Phase 2.2 -- UMR correctness)
    temporal_validation.py        (Phase 2.3 -- temporal correctness)
    benchmark_validation.py       (Phase 2.4 -- resource organization)
    reproducibility_validation.py (Phase 2.5 -- reproducibility metadata)

Phase 2.6 does not re-validate any single component's internals a second
time with new logic -- it RE-RUNS each component's own real validator
fresh (never reads an old report) and then adds a layer those validators
cannot see by construction: whether the four layers agree with EACH OTHER
(cross-manifest consistency, version consistency, record-count
consistency), plus a handful of substrate-wide invariants (experimental-
activation boundary, phase-boundary/scope enforcement, Phase 2 component
completeness) that only make sense once every layer exists.

Phase 2.6 creates no dataset, redesigns no UMR field, reorganizes no
resource, and implements no attack/defense. It is validation only -- see
Section 4 ("VALIDATION, not REPAIR") of the implementation prompt this
module was built from: a finding is reported, never silently fixed by
mutating data, weakening a check, or changing an expected value.

PERFORMANCE: `validate_reproducibility_manifest()` (Phase 2.5's own
validator) already internally re-runs Phase 2.2's, 2.3's, and 2.4's real
validators fresh as part of its own regression checks. Phase 2.6 calls it
exactly once and reuses its result for the Phase 2.2/2.3/2.4/2.5
regression domains (Domains 21-24), rather than invoking those four
validators a second independent time. Phase 2.6 does make two additional
direct calls -- `validate_cross_dataset()` and `validate_temporal()` --
because Domains 3 and 5/6 need each validator's own per-check *detail*
(the specific collision list, the per-dataset temporal-provenance
distribution), which the nested calls inside `validate_benchmark_organization`
do not expose. This is a deliberate, documented trade of a small amount of
duplicate scanning for check-level detail Phase 2.6's own acceptance
criteria require -- not an accident. Raw-file re-hashing is scoped to
files below a size threshold (see `_HASH_SIZE_LIMIT_BYTES`); larger raw
files are checked by size only, both documented in the report itself so a
reader never mistakes a sampled check for a full-corpus one.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Optional

from preprocessing.benchmark_organization import (
    APPROVED_MEMORY_FOUNDATION,
    ROLE_ATTACK,
    ROLE_EVALUATION,
    ROLE_MEMORY,
    ROLE_SLEEPER,
    ROLE_WORKLOAD,
    build_benchmark_organization,
)
from preprocessing.benchmark_validation import (
    _EXPECTED_MEMORY_RECORD_COUNTS,
    _EXPECTED_TOTAL,
    validate_benchmark_organization,
)
from preprocessing.config import PipelineConfig
from preprocessing.io_utils import read_json, sha256_file, write_json
from preprocessing.phase2_manifest import build_phase2_manifest
from preprocessing.registry import REPO_ROOT, build_registry_report
from preprocessing.reproducibility import (
    REPRODUCIBILITY_MANIFEST_VERSION,
    build_reproducibility_manifest,
)
from preprocessing.reproducibility_validation import validate_reproducibility_manifest
from preprocessing.temporal import NORMALIZATION_POLICY_VERSION
from preprocessing.temporal_validation import validate_temporal
from preprocessing.unified_schema import CORE_DATASETS, SCHEMA_VERSION as UMR_SCHEMA_VERSION
from preprocessing.unified_validation import validate_cross_dataset

SUBSTRATE_VALIDATION_VERSION = "1.0.0"

_EXPECTED_ROLE_COUNTS = {
    ROLE_MEMORY: 4, ROLE_WORKLOAD: 9, ROLE_ATTACK: 6, ROLE_SLEEPER: 2, ROLE_EVALUATION: 7,
}

# Datasets whose source ever provides a real calendar timestamp -- used to
# check Domain 5/6's "source-absolute vs source-relative" split is exactly
# what the four datasets' own documented temporal signals say it should be
# (see preprocessing/temporal.py TEMPORAL_POLICY).
_SOURCE_ABSOLUTE_DATASETS = frozenset({"locomo", "longmemeval"})
_SOURCE_RELATIVE_ONLY_DATASETS = frozenset({"msc", "conversation_chronicles"})

# Raw files at or below this size are re-hashed for Domain 14/19 data-
# integrity; larger ones are checked by size only (see module docstring).
# 5 MiB comfortably covers LoCoMo's ~2.8MB raw file while excluding
# LongMemEval's ~277MB and Conversation Chronicles' ~1.3GB raw files,
# which dataset_manifest.json's own sha256 (computed once at acquisition
# time) already covers.
_HASH_SIZE_LIMIT_BYTES = 5 * 1024 * 1024

# Forbidden later-phase functionality stems (Domain 18 / Section 23).
# Matched only against `def`/`class` names -- not prose, not field names,
# not role-vocabulary string literals -- because those legitimately appear
# throughout Phase 1/2 (role names, registry descriptions of external
# papers, reserved-null schema fields). A `def`/`class` actually
# implementing one of these would be later-phase functionality; a string
# or comment describing one is not.
_FORBIDDEN_DEFINITION_STEMS = (
    "poison", "attack", "sleeper", "propagat", "lifecycle", "defense",
    "defence", "mitigat", "contain", "attribut", "gnn", "gln",
)
_FORBIDDEN_DEF_RE = re.compile(
    r"^\s*(def|class)\s+\w*(" + "|".join(_FORBIDDEN_DEFINITION_STEMS) + r")\w*",
    re.IGNORECASE,
)

# Files expected to exist once Phase 2.1 through 2.5 have all run (Domain 20).
_EXPECTED_METADATA_FILES = [
    "data/metadata/resource_registry.json",
    "data/metadata/phase2_input_manifest.json",
    "data/metadata/benchmark_resources.json",
    "data/metadata/reproducibility_manifest.json",
    "data/metadata/dataset_manifest.json",
]
_EXPECTED_REPORT_FILES = [
    "data/reports/phase2_2_unified_memory_validation_report.json",
    "data/reports/phase2_3_temporal_validation_report.json",
    "data/reports/phase2_4_benchmark_organization_validation_report.json",
    "data/reports/phase2_5_reproducibility_validation_report.json",
]
_EXPECTED_DOC_FILES = [
    "docs/phase2/UNIFIED_MEMORY_RECORD.md",
    "docs/phase2/TEMPORAL_NORMALIZATION.md",
    "docs/phase2/BENCHMARK_ORGANIZATION.md",
    "docs/phase2/BENCHMARK_METADATA_AND_MANIFESTS.md",
]


def _c(name: str, status: str, detail: Optional[dict] = None, scope: str = "artifact") -> dict:
    return {"name": name, "status": status, "scope": scope, "detail": detail or {}}


def _scan_forbidden_definitions(root: Path) -> list[dict]:
    """Domain 18 -- scans every tracked-relevant .py file for a `def`/
    `class` whose name implements forbidden later-phase functionality.
    Prose, comments, docstrings, role-name string literals, and field
    names are never flagged -- only an actual definition."""
    violations = []
    for py_file in sorted((root / "preprocessing").rglob("*.py")):
        try:
            text = py_file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = py_file.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _FORBIDDEN_DEF_RE.match(line):
                violations.append({
                    "file": str(py_file.relative_to(root)),
                    "line": lineno,
                    "text": line.strip(),
                })
    return violations


def _targeted_raw_checksum_check(cfg: PipelineConfig, root: Path) -> dict:
    """Domain 14/19 -- data integrity, without a full-corpus rehash.
    Small raw files are re-hashed against dataset_manifest.json's own
    sha256; larger files are confirmed unchanged by size only. Both
    outcomes are recorded per-file so the report never implies a full
    rehash happened when it did not."""
    manifest = read_json(cfg.metadata_dir / "dataset_manifest.json")
    rehashed, size_checked_only, mismatches, missing = [], [], [], []
    for dataset, facts in manifest.get("datasets", {}).items():
        for f in facts.get("files", []):
            rel_path = f["path"].replace("\\", "/")
            abs_path = root / rel_path
            if not abs_path.exists():
                missing.append(rel_path)
                continue
            size = abs_path.stat().st_size
            if size != f.get("size_bytes"):
                mismatches.append({"path": rel_path, "reason": "size changed", "expected": f.get("size_bytes"), "actual": size})
                continue
            if size <= _HASH_SIZE_LIMIT_BYTES:
                actual_sha = sha256_file(abs_path)
                if actual_sha != f.get("sha256"):
                    mismatches.append({"path": rel_path, "reason": "sha256 mismatch", "expected": f.get("sha256"), "actual": actual_sha})
                else:
                    rehashed.append(rel_path)
            else:
                size_checked_only.append(rel_path)
    return {
        "rehashed_files": rehashed,
        "size_only_checked_files": size_checked_only,
        "missing_files": missing,
        "mismatches": mismatches,
    }


def _mtime_stability_check(cfg: PipelineConfig) -> dict:
    """A second, cheap data-integrity signal: representative frozen Phase
    1/2.2 output files must not have been touched (mtime/size) by simply
    calling every Phase 2 builder again."""
    watched = [
        cfg.processed_dir / "locomo" / "memory_records.jsonl",
        cfg.processed_dir / "longmemeval" / "memory_records.jsonl",
        cfg.processed_dir / "msc" / "memory_records.jsonl",
        cfg.processed_dir / "conversation_chronicles" / "memory_records.jsonl",
        cfg.processed_dir / "unified_memory" / "locomo" / "memory_records.jsonl",
    ]
    before = {str(p): (p.stat().st_mtime_ns, p.stat().st_size) for p in watched if p.exists()}
    build_benchmark_organization(cfg, "2026-01-01T00:00:00Z")
    build_reproducibility_manifest(cfg, "2026-01-01T00:00:00Z")
    after = {str(p): (p.stat().st_mtime_ns, p.stat().st_size) for p in watched if p.exists()}
    return {"unchanged": before == after, "watched_file_count": len(before), "before": {k: list(v) for k, v in before.items()}, "after": {k: list(v) for k, v in after.items()}}


def validate_benchmark_substrate(cfg: PipelineConfig, generated_at: str) -> dict:
    checks: list[dict] = []
    root = REPO_ROOT

    # ---- Cheap, non-corpus-scanning reads --------------------------------
    registry = build_registry_report(cfg)
    phase2_manifest = build_phase2_manifest(cfg, generated_at)
    org = build_benchmark_organization(cfg, generated_at)
    repro_manifest = build_reproducibility_manifest(cfg, generated_at)

    registry_by_id = {e["resource_id"]: e for e in registry["resources"]}
    phase2_by_id = {e["resource_id"]: e for e in phase2_manifest["resources"]}
    org_by_id = {e["resource_id"]: e for e in org["resources"]}
    repro_by_id = {e["resource_id"]: e for e in repro_manifest["resources"]}

    # ---- Expensive, full-corpus-scanning fresh validator runs ------------
    # (exactly one call each; see module docstring PERFORMANCE note)
    umr_report = validate_cross_dataset(cfg)               # Phase 2.2, fresh
    temporal_report = validate_temporal(cfg)                # Phase 2.3, fresh
    org_validation = validate_benchmark_organization(cfg, generated_at)  # Phase 2.4, fresh
    repro_validation = validate_reproducibility_manifest(cfg, generated_at)  # Phase 2.5, fresh (re-runs 2.2/2.3/2.4 internally)

    # =======================================================================
    # Domain 1 -- memory foundation
    # =======================================================================
    memory_ids = {rid for rid, e in org_by_id.items() if e["primary_role"] == ROLE_MEMORY}
    checks.append(_c(
        "domain1_memory_foundation_exactly_four_approved_datasets",
        "PASS" if memory_ids == APPROVED_MEMORY_FOUNDATION == set(CORE_DATASETS) else "FAIL",
        {"expected": sorted(APPROVED_MEMORY_FOUNDATION), "actual": sorted(memory_ids)},
    ))
    checks.append(_c(
        "domain1_memory_foundation_record_counts_match_expected",
        "PASS" if (
            umr_report["per_dataset_counts"] == _EXPECTED_MEMORY_RECORD_COUNTS
            and umr_report["total_records"] == _EXPECTED_TOTAL
            and org["umr_integrity"]["umr_per_dataset_record_counts"] == _EXPECTED_MEMORY_RECORD_COUNTS
            and org["umr_integrity"]["umr_total_records"] == _EXPECTED_TOTAL
            and repro_manifest["record_counts"]["umr_per_dataset_record_counts"] == _EXPECTED_MEMORY_RECORD_COUNTS
        ) else "FAIL",
        {
            "expected_per_dataset": _EXPECTED_MEMORY_RECORD_COUNTS, "expected_total": _EXPECTED_TOTAL,
            "fresh_umr_validator": umr_report["per_dataset_counts"],
            "benchmark_organization_layer": org["umr_integrity"]["umr_per_dataset_record_counts"],
            "reproducibility_layer": repro_manifest["record_counts"]["umr_per_dataset_record_counts"],
        },
        scope="full_corpus",
    ))

    # =======================================================================
    # Domain 2 -- UMR integrity
    # =======================================================================
    schema_sources = {
        "unified_schema.SCHEMA_VERSION": UMR_SCHEMA_VERSION,
        "benchmark_organization.umr_integrity": org["umr_integrity"]["umr_schema_version"],
        "reproducibility_manifest.schema_and_policy_versions": repro_manifest["schema_and_policy_versions"]["unified_memory_record_schema_version"],
    }
    checks.append(_c(
        "domain2_umr_schema_version_consistent_across_all_layers",
        "PASS" if len(set(schema_sources.values())) == 1 and UMR_SCHEMA_VERSION == "1.1.0" else "FAIL",
        {"sources": schema_sources},
    ))
    checks.append(_c(
        "domain2_umr_validator_passes_fresh",
        umr_report["overall_status"],
        {"failed_checks": [c["name"] for c in umr_report["checks"] if c["status"] != "PASS"]},
        scope="full_corpus",
    ))

    # =======================================================================
    # Domain 3 -- memory identity
    # =======================================================================
    collision_check = next((c for c in umr_report["checks"] if c["name"] == "no_cross_dataset_id_collision"), None)
    checks.append(_c(
        "domain3_no_cross_dataset_memory_id_collisions",
        collision_check["status"] if collision_check else "FAIL",
        {"source_check": collision_check},
        scope="full_corpus",
    ))

    # =======================================================================
    # Domain 4 -- provenance
    # =======================================================================
    provenance_gaps = [
        rid for rid in CORE_DATASETS
        if "provenance dataclass populated" not in (phase2_by_id.get(rid, {}).get("provenance_status") or "")
    ]
    checks.append(_c(
        "domain4_provenance_chain_intact_for_memory_foundation",
        "PASS" if not provenance_gaps else "FAIL",
        {"violations": provenance_gaps},
    ))
    missing_provenance = [
        rid for rid, e in org_by_id.items()
        if not e.get("source_reference") or not e.get("provenance", {}).get("source") or not e.get("provenance", {}).get("mambench_created")
    ]
    checks.append(_c(
        "domain4_provenance_preserved_for_all_28_resources",
        "PASS" if not missing_provenance else "FAIL",
        {"violations": missing_provenance},
    ))

    # =======================================================================
    # Domain 5/6 -- temporal integrity and temporal provenance
    # =======================================================================
    checks.append(_c(
        "domain5_temporal_validator_passes_fresh",
        temporal_report["overall_status"],
        {"failed_checks": [c["name"] for c in temporal_report["checks"] if c["status"] != "PASS"]},
        scope="full_corpus",
    ))
    coverage_check = next((c for c in temporal_report["checks"] if c["name"] == "all_four_core_datasets_produce_temporal_fields"), None)
    per_dataset_provenance = (coverage_check or {}).get("detail", {}).get("per_dataset_provenance_counts", {})
    temporal_split_violations = []
    for ds in _SOURCE_ABSOLUTE_DATASETS:
        if not per_dataset_provenance.get(ds, {}).get("source_absolute"):
            temporal_split_violations.append({"dataset": ds, "reason": "expected at least some source_absolute records"})
    for ds in _SOURCE_RELATIVE_ONLY_DATASETS:
        if per_dataset_provenance.get(ds, {}).get("source_absolute"):
            temporal_split_violations.append({"dataset": ds, "reason": "source_absolute must never occur -- this dataset has no real calendar timestamp"})
    checks.append(_c(
        "domain6_temporal_provenance_split_matches_each_datasets_documented_signal",
        "PASS" if not temporal_split_violations else "FAIL",
        {"violations": temporal_split_violations, "per_dataset_provenance_counts": per_dataset_provenance},
        scope="full_corpus",
    ))
    fabrication_check = next((c for c in temporal_report["checks"] if c["name"] == "no_accidental_fabrication_source_absolute_vs_normalized_timestamp"), None)
    checks.append(_c(
        "domain6_no_fabricated_source_absolute_timestamps",
        fabrication_check["status"] if fabrication_check else "FAIL",
        {"source_check": fabrication_check},
        scope="full_corpus",
    ))

    # =======================================================================
    # Domain 7/8/9 -- resource organization, role vs. status, availability
    # =======================================================================
    checks.append(_c(
        "domain7_resource_role_counts_match_expected",
        "PASS" if org["resource_count_by_role"] == _EXPECTED_ROLE_COUNTS else "FAIL",
        {"expected": _EXPECTED_ROLE_COUNTS, "actual": org["resource_count_by_role"]},
    ))
    boundary_violations = [
        rid for rid, e in org_by_id.items()
        if e["primary_role"] != ROLE_MEMORY and rid in APPROVED_MEMORY_FOUNDATION
    ] + [
        rid for rid in APPROVED_MEMORY_FOUNDATION if org_by_id.get(rid, {}).get("primary_role") != ROLE_MEMORY
    ]
    checks.append(_c(
        "domain7_memory_foundation_boundary_enforced",
        "PASS" if not boundary_violations else "FAIL",
        {"violations": sorted(set(boundary_violations))},
    ))
    dsrm = org_by_id.get("dsrm", {})
    role_status_ok = (
        dsrm.get("primary_role") == ROLE_ATTACK
        and dsrm.get("implementation_status") == "specification_only_no_public_implementation_found"
        and dsrm.get("phase2_input_approved") is not True
        and dsrm.get("local_path") is None
    )
    checks.append(_c(
        "domain8_role_status_implementation_activation_kept_separate",
        "PASS" if role_status_ok else "FAIL",
        {"dsrm": {"primary_role": dsrm.get("primary_role"), "implementation_status": dsrm.get("implementation_status"), "phase2_input_approved": dsrm.get("phase2_input_approved")}},
    ))
    approved_ids = {rid for rid, e in org_by_id.items() if e.get("phase2_input_approved") is True}
    checks.append(_c(
        "domain9_resource_availability_honest",
        "PASS" if approved_ids == APPROVED_MEMORY_FOUNDATION else "FAIL",
        {"approved_ids": sorted(approved_ids), "expected": sorted(APPROVED_MEMORY_FOUNDATION)},
    ))

    # =======================================================================
    # Domain 10 -- reproducibility metadata
    # =======================================================================
    missing_repro_fields = [
        rid for rid, e in repro_by_id.items()
        if "canonical_identity" not in e or "canonical_identity_hash" not in e or "artifact_identity" not in e
    ]
    checks.append(_c(
        "domain10_reproducibility_metadata_present_for_all_resources",
        "PASS" if not missing_repro_fields and len(repro_by_id) == 28 else "FAIL",
        {"violations": missing_repro_fields, "total_resources": len(repro_by_id)},
    ))
    checks.append(_c(
        "domain10_reproducibility_validator_passes_fresh",
        repro_validation["overall_status"],
        {"failed_checks": [c["name"] for c in repro_validation["checks"] if c["status"] != "PASS"]},
        scope="full_corpus",
    ))

    # =======================================================================
    # Domain 11-17 -- cross-manifest, version, record-count consistency
    # =======================================================================
    id_sets = {
        "resource_registry": set(registry_by_id), "phase2_input_manifest": set(phase2_by_id),
        "benchmark_resources": set(org_by_id), "reproducibility_manifest": set(repro_by_id),
    }
    id_mismatches = {k: sorted(v.symmetric_difference(id_sets["resource_registry"])) for k, v in id_sets.items() if v != id_sets["resource_registry"]}
    checks.append(_c(
        "domain11_cross_manifest_resource_id_consistency",
        "PASS" if not id_mismatches else "FAIL",
        {"violations": id_mismatches},
    ))
    field_disagreements = []
    for rid in org_by_id:
        o, r = org_by_id[rid], repro_by_id.get(rid, {})
        if not r:
            field_disagreements.append({"resource_id": rid, "reason": "missing from reproducibility_manifest"})
            continue
        if o["primary_role"] != r["primary_role"]:
            field_disagreements.append({"resource_id": rid, "field": "primary_role"})
        if o["source_reference"] != r["source_identity"]["source_reference"]:
            field_disagreements.append({"resource_id": rid, "field": "source_reference"})
        if o["phase2_status"] != r["phase2_status"] or o["phase2_input_approved"] != r["phase2_input_approved"]:
            field_disagreements.append({"resource_id": rid, "field": "phase2_status_or_approval"})
    checks.append(_c(
        "domain11_cross_manifest_role_and_status_agree",
        "PASS" if not field_disagreements else "FAIL",
        {"violations": field_disagreements},
    ))
    version_sources = {
        "umr_schema": {"unified_schema": UMR_SCHEMA_VERSION, "org_umr_integrity": org["umr_integrity"]["umr_schema_version"], "repro_manifest": repro_manifest["schema_and_policy_versions"]["unified_memory_record_schema_version"]},
        "temporal_policy": {"temporal_module": NORMALIZATION_POLICY_VERSION, "org_umr_integrity": org["umr_integrity"]["temporal_normalization_policy_version"], "repro_manifest": repro_manifest["schema_and_policy_versions"]["temporal_normalization_policy_version"]},
        "benchmark_organization_version": {"module": org["organization_version"], "repro_manifest": repro_manifest["generated_from"]["benchmark_resources"]},
    }
    version_violations = []
    if len(set(version_sources["umr_schema"].values())) != 1 or UMR_SCHEMA_VERSION != "1.1.0":
        version_violations.append({"field": "umr_schema", "sources": version_sources["umr_schema"]})
    if len(set(version_sources["temporal_policy"].values())) != 1 or NORMALIZATION_POLICY_VERSION != "2.3.0":
        version_violations.append({"field": "temporal_policy", "sources": version_sources["temporal_policy"]})
    if f"organization_version={org['organization_version']}" not in version_sources["benchmark_organization_version"]["repro_manifest"]:
        version_violations.append({"field": "benchmark_organization_version", "sources": version_sources["benchmark_organization_version"]})
    checks.append(_c(
        "domain12_version_consistency_across_layers",
        "PASS" if not version_violations else "FAIL",
        {"violations": version_violations},
    ))
    checks.append(_c(
        "domain13_record_count_consistency_across_layers",
        "PASS" if (
            org["umr_integrity"]["umr_total_records"] == repro_manifest["record_counts"]["umr_total_records"] == umr_report["total_records"] == _EXPECTED_TOTAL
        ) else "FAIL",
        {
            "benchmark_organization": org["umr_integrity"]["umr_total_records"],
            "reproducibility_manifest": repro_manifest["record_counts"]["umr_total_records"],
            "fresh_umr_validator": umr_report["total_records"],
            "expected": _EXPECTED_TOTAL,
        },
        scope="full_corpus",
    ))

    # =======================================================================
    # Domain 14/19 -- data integrity (targeted, not a full-corpus rehash)
    # =======================================================================
    checksum_result = _targeted_raw_checksum_check(cfg, root)
    checks.append(_c(
        "domain14_raw_file_integrity_targeted_checksums",
        "PASS" if not checksum_result["mismatches"] and not checksum_result["missing_files"] else "FAIL",
        checksum_result,
        scope="targeted_sample",
    ))
    mtime_result = _mtime_stability_check(cfg)
    checks.append(_c(
        "domain14_frozen_output_files_untouched_by_phase2_builders",
        "PASS" if mtime_result["unchanged"] else "FAIL",
        {"watched_file_count": mtime_result["watched_file_count"]},
    ))

    # =======================================================================
    # Domain 18 -- phase boundary / scope enforcement
    # =======================================================================
    forbidden_defs = _scan_forbidden_definitions(root)
    checks.append(_c(
        "domain18_no_later_phase_functionality_implemented",
        "PASS" if not forbidden_defs else "FAIL",
        {"violations": forbidden_defs, "scanned_stems": list(_FORBIDDEN_DEFINITION_STEMS)},
    ))

    # =======================================================================
    # Domain 19 -- experimental activation boundary
    # =======================================================================
    activation_leaks = [
        rid for rid, e in org_by_id.items()
        if e["primary_role"] in (ROLE_ATTACK, ROLE_SLEEPER) and e.get("phase2_input_approved") is True
    ]
    checks.append(_c(
        "domain19_experimental_activation_boundary_respected",
        "PASS" if not activation_leaks else "FAIL",
        {"violations": activation_leaks},
    ))

    # =======================================================================
    # Domain 20 -- Phase 2 completeness
    # =======================================================================
    missing_artifacts = [p for p in (_EXPECTED_METADATA_FILES + _EXPECTED_REPORT_FILES + _EXPECTED_DOC_FILES) if not (root / p).exists()]
    checks.append(_c(
        "domain20_phase2_component_artifacts_all_present",
        "PASS" if not missing_artifacts else "FAIL",
        {"missing": missing_artifacts},
    ))

    # =======================================================================
    # Domain 21-24 -- fresh regression of Phase 2.2 / 2.3 / 2.4 / 2.5
    # =======================================================================
    checks.append(_c("domain21_phase2_2_regression", umr_report["overall_status"], {"total_records": umr_report["total_records"]}, scope="full_corpus"))
    checks.append(_c("domain22_phase2_3_regression", temporal_report["overall_status"], {"total_records": temporal_report["total_records"]}, scope="full_corpus"))
    checks.append(_c("domain23_phase2_4_regression", org_validation["overall_status"], {"total_resources_organized": org_validation["total_resources_organized"]}, scope="full_corpus"))
    checks.append(_c("domain24_phase2_5_regression", repro_validation["overall_status"], {"total_resources": repro_validation["total_resources"]}, scope="full_corpus"))

    overall_status = "PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL"
    return {
        "schema_version": "1.0.0",
        "substrate_validation_version": SUBSTRATE_VALIDATION_VERSION,
        "generated_at": generated_at,
        "overall_status": overall_status,
        "total_checks": len(checks),
        "canonical_state": {
            "memory_foundation": sorted(APPROVED_MEMORY_FOUNDATION),
            "memory_record_counts": _EXPECTED_MEMORY_RECORD_COUNTS,
            "memory_record_total": _EXPECTED_TOTAL,
            "umr_schema_version": UMR_SCHEMA_VERSION,
            "temporal_normalization_policy_version": NORMALIZATION_POLICY_VERSION,
            "benchmark_organization_version": org["organization_version"],
            "reproducibility_manifest_version": REPRODUCIBILITY_MANIFEST_VERSION,
            "resource_role_counts": org["resource_count_by_role"],
            "total_resources": org["total_resources"],
        },
        "checks": checks,
    }


def write_benchmark_substrate_validation_report(cfg: PipelineConfig, generated_at: str | None = None) -> Path:
    if generated_at is None:
        import datetime as _dt

        generated_at = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = validate_benchmark_substrate(cfg, generated_at)
    out_path = cfg.reports_dir / "phase2_6_benchmark_substrate_validation_report.json"
    write_json(out_path, report)
    return out_path


if __name__ == "__main__":
    from preprocessing.config import load_config

    _cfg = load_config()
    _path = write_benchmark_substrate_validation_report(_cfg)
    print(f"Wrote {_path}")
