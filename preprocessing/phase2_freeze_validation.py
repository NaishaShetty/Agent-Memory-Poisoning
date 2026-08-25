"""Phase 2.7: Phase 2 acceptance, freeze & canonical baseline.

SCOPE (see docs/phase2/PHASE2_FREEZE.md for the full statement): Phase 2.7
is the final acceptance gate. It is not a new data-processing phase, not
an attack phase, not an experimentation phase, and not a redesign phase.
It does not change the UMR, temporal normalization, resource roles,
resource identities, record counts, provenance semantics, or
reproducibility semantics established by Phases 2.2-2.6. Its only job is
to (a) re-confirm, fresh, that the whole Phase 2 substrate still passes
every earlier gate, (b) compute one deterministic, machine-independent
identity for the *entire* Phase 2 state, and (c) write the single
canonical freeze manifest a later phase can point to instead of
re-deriving Phase 2's state itself.

SINGLE AUTHORITATIVE CHAIN -- Phase 2.7 is the fifth and final link:

    registry.py                    -- resource IDENTITY
    phase2_manifest.py              -- Phase 2 input APPROVAL
    benchmark_organization.py       -- benchmark ROLE
    reproducibility.py              -- REPRODUCIBILITY IDENTITY (per resource)
    benchmark_substrate_validation.py -- CROSS-PHASE CONSISTENCY (Phase 2.6)
    phase2_freeze_validation.py (this) -- WHOLE-PHASE-2 CANONICAL IDENTITY + FREEZE

Phase 2.7 does not duplicate Phase 2.6's internal validation logic -- it
calls `validate_benchmark_substrate()` exactly once and folds its verdict
in directly, then adds only what a whole-phase freeze needs on top: a
Phase-2-wide canonical identity hash (built from the already-computed
per-resource canonical identity hashes plus every schema/policy/
organization version, never re-deriving any of them), a freeze manifest,
and git-state/known-limitations bookkeeping.

FREEZE MECHANISM: Phase 2.7 does not chmod any file or otherwise make the
repository harder to develop against (Section 21 of the implementation
prompt this module was built from explicitly warns against "filesystem
theater"). "Frozen" here means: a canonical identity hash is recorded: any
future change to Phase 2's scientific state (a resource's canonical
identity, a schema/policy/organization version, the memory-foundation
membership, or the record counts) will produce a *different* hash, making
an accidental or silent mutation immediately detectable by comparing
against the recorded `data/metadata/phase2_freeze_manifest.json`. This is
a tripwire, not a lock.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
from pathlib import Path
from typing import Optional

from preprocessing import PIPELINE_VERSION
from preprocessing.benchmark_organization import (
    APPROVED_MEMORY_FOUNDATION,
    ORGANIZATION_VERSION,
    build_benchmark_organization,
)
from preprocessing.benchmark_substrate_validation import (
    SUBSTRATE_VALIDATION_VERSION,
    _EXPECTED_MEMORY_RECORD_COUNTS,
    _EXPECTED_TOTAL,
    _scan_forbidden_definitions,
    validate_benchmark_substrate,
)
from preprocessing.config import PipelineConfig
from preprocessing.io_utils import write_json
from preprocessing.registry import REPO_ROOT
from preprocessing.reproducibility import (
    REPRODUCIBILITY_MANIFEST_VERSION,
    build_reproducibility_manifest,
    get_code_state,
    get_configuration_identity,
)
from preprocessing.temporal import NORMALIZATION_POLICY_VERSION
from preprocessing.unified_schema import SCHEMA_VERSION as UMR_SCHEMA_VERSION

PHASE2_FREEZE_VERSION = "2.7.0"

_EXPECTED_RESOURCE_ROLE_COUNTS = {"memory": 4, "workload": 9, "attack": 6, "sleeper": 2, "evaluation": 7}
_EXPECTED_TOTAL_RESOURCES = 28

# Manifests/reports/docs the freeze references (never duplicates their
# content) -- existence of every one is itself part of the acceptance gate.
_MANIFEST_REFERENCES = {
    "resource_registry": "data/metadata/resource_registry.json",
    "phase2_input_manifest": "data/metadata/phase2_input_manifest.json",
    "benchmark_resources": "data/metadata/benchmark_resources.json",
    "reproducibility_manifest": "data/metadata/reproducibility_manifest.json",
    "dataset_manifest": "data/metadata/dataset_manifest.json",
}
_VALIDATION_REFERENCES = {
    "phase2_2": "data/reports/phase2_2_unified_memory_validation_report.json",
    "phase2_3": "data/reports/phase2_3_temporal_validation_report.json",
    "phase2_4": "data/reports/phase2_4_benchmark_organization_validation_report.json",
    "phase2_5": "data/reports/phase2_5_reproducibility_validation_report.json",
    "phase2_6": "data/reports/phase2_6_benchmark_substrate_validation_report.json",
    "phase2_7": "data/reports/phase2_7_freeze_validation_report.json",
}


def _canonical_hash(fields: dict) -> str:
    return hashlib.sha256(json.dumps(fields, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def build_canonical_phase2_identity(cfg: PipelineConfig, org: dict, repro_manifest: dict) -> dict:
    """The whole-Phase-2 canonical identity. Deliberately excludes
    generated_at, absolute local paths, and machine identity -- built only
    from stable scientific/project state: every resource's own already-
    computed canonical_identity_hash (Phase 2.5), every schema/policy/
    organization version, the memory-foundation membership and record
    counts, and the pipeline configuration's content hash. Does not
    re-derive any of these values; it only aggregates them."""
    resource_hashes = {
        e["resource_id"]: e["canonical_identity_hash"]
        for e in sorted(repro_manifest["resources"], key=lambda r: r["resource_id"])
    }
    configuration_id = get_configuration_identity(cfg)["configuration_id"]
    fields = {
        "preprocessing_pipeline_version": PIPELINE_VERSION,
        "umr_schema_version": UMR_SCHEMA_VERSION,
        "temporal_normalization_policy_version": NORMALIZATION_POLICY_VERSION,
        "benchmark_organization_version": ORGANIZATION_VERSION,
        "reproducibility_manifest_version": REPRODUCIBILITY_MANIFEST_VERSION,
        "substrate_validation_version": SUBSTRATE_VALIDATION_VERSION,
        "phase2_freeze_version": PHASE2_FREEZE_VERSION,
        "configuration_id": configuration_id,
        "memory_foundation_dataset_ids": sorted(APPROVED_MEMORY_FOUNDATION),
        "memory_record_counts": dict(sorted(_EXPECTED_MEMORY_RECORD_COUNTS.items())),
        "memory_record_total": _EXPECTED_TOTAL,
        "resource_role_counts": dict(sorted(org["resource_count_by_role"].items())),
        "total_resources": org["total_resources"],
        "per_resource_canonical_identity_hashes": resource_hashes,
    }
    return {"fields": fields, "canonical_phase2_identity_hash": _canonical_hash(fields)}


def validate_phase2_freeze(cfg: PipelineConfig, generated_at: str) -> dict:
    checks: list[dict] = []

    def _c(name, status, detail=None):
        checks.append({"name": name, "status": status, "detail": detail or {}})

    # ---- Delegate the entire cross-phase re-validation to Phase 2.6 -----
    # (exactly one call; internally re-runs 2.2/2.3/2.4/2.5 fresh -- see
    # module docstring and benchmark_substrate_validation.py's own
    # PERFORMANCE note for why this is not duplicated here)
    substrate_report = validate_benchmark_substrate(cfg, generated_at)
    _c(
        "phase2_6_benchmark_substrate_validation_passes_fresh",
        substrate_report["overall_status"],
        {"total_checks": substrate_report["total_checks"], "failed_checks": [c["name"] for c in substrate_report["checks"] if c["status"] != "PASS"]},
    )

    org = build_benchmark_organization(cfg, generated_at)
    repro_manifest = build_reproducibility_manifest(cfg, generated_at)
    identity = build_canonical_phase2_identity(cfg, org, repro_manifest)

    # ---- Canonical state re-confirmation (cheap, reads Domain-1-style facts
    # already verified fresh inside substrate_report above) --------------
    state = substrate_report["canonical_state"]
    _c(
        "canonical_memory_foundation_matches_expected",
        "PASS" if state["memory_foundation"] == sorted(APPROVED_MEMORY_FOUNDATION) else "FAIL",
        {"expected": sorted(APPROVED_MEMORY_FOUNDATION), "actual": state["memory_foundation"]},
    )
    _c(
        "canonical_record_counts_match_expected",
        "PASS" if state["memory_record_counts"] == _EXPECTED_MEMORY_RECORD_COUNTS and state["memory_record_total"] == _EXPECTED_TOTAL else "FAIL",
        {"expected_total": _EXPECTED_TOTAL, "actual_total": state["memory_record_total"]},
    )
    _c(
        "canonical_versions_match_expected",
        "PASS" if (state["umr_schema_version"], state["temporal_normalization_policy_version"], state["benchmark_organization_version"]) == ("1.1.0", "2.3.0", "1.0.0") else "FAIL",
        {"umr": state["umr_schema_version"], "temporal": state["temporal_normalization_policy_version"], "org": state["benchmark_organization_version"]},
    )
    _c(
        "canonical_resource_counts_match_expected",
        "PASS" if state["resource_role_counts"] == _EXPECTED_RESOURCE_ROLE_COUNTS and state["total_resources"] == _EXPECTED_TOTAL_RESOURCES else "FAIL",
        {"expected": _EXPECTED_RESOURCE_ROLE_COUNTS, "actual": state["resource_role_counts"]},
    )

    # ---- Canonical Phase 2 identity determinism & path-independence -----
    identity_b_fields = build_canonical_phase2_identity(cfg, org, repro_manifest)["fields"]
    _c(
        "canonical_phase2_identity_is_deterministic",
        "PASS" if identity_b_fields == identity["fields"] else "FAIL",
        {},
    )
    other_ts_org = build_benchmark_organization(cfg, "1999-01-01T00:00:00Z")
    other_ts_repro = build_reproducibility_manifest(cfg, "1999-01-01T00:00:00Z")
    other_ts_identity = build_canonical_phase2_identity(cfg, other_ts_org, other_ts_repro)
    _c(
        "canonical_phase2_identity_unaffected_by_generated_at",
        "PASS" if other_ts_identity["canonical_phase2_identity_hash"] == identity["canonical_phase2_identity_hash"] else "FAIL",
        {},
    )

    # ---- Freeze policy artifact completeness -----------------------------
    missing_manifest_refs = [k for k, p in _MANIFEST_REFERENCES.items() if not (REPO_ROOT / p).exists()]
    _c(
        "all_referenced_manifests_exist",
        "PASS" if not missing_manifest_refs else "FAIL",
        {"missing": missing_manifest_refs},
    )
    # phase2_7's own report doesn't exist yet on the run that generates it
    # -- checked separately, not against _VALIDATION_REFERENCES, so this
    # check is meaningful on both the first and every subsequent run.
    missing_validation_refs = [k for k, p in _VALIDATION_REFERENCES.items() if k != "phase2_7" and not (REPO_ROOT / p).exists()]
    _c(
        "all_referenced_validation_reports_exist",
        "PASS" if not missing_validation_refs else "FAIL",
        {"missing": missing_validation_refs},
    )

    # ---- Final scope scan (reuses Phase 2.6's scanner, not re-implemented)
    forbidden_defs = _scan_forbidden_definitions(REPO_ROOT)
    _c(
        "final_scope_scan_zero_forbidden_functionality",
        "PASS" if not forbidden_defs else "FAIL",
        {"violations": forbidden_defs},
    )

    # ---- Git baseline captured (never invents a commit/tag) --------------
    code_state = get_code_state()
    _c(
        "git_code_state_captured",
        "PASS" if code_state["git_available"] else "FAIL",
        {"code_state": code_state},
    )

    overall_status = "PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL"
    return {
        "schema_version": "1.0.0",
        "phase2_freeze_version": PHASE2_FREEZE_VERSION,
        "generated_at": generated_at,
        "overall_status": overall_status,
        "total_checks": len(checks),
        "canonical_phase2_identity": identity,
        "code_state": code_state,
        "checks": checks,
    }


def build_phase2_freeze_manifest(cfg: PipelineConfig, generated_at: str, freeze_validation: dict) -> dict:
    """The single canonical Phase 2 freeze manifest -- a pointer/summary,
    not a new independent registry. Every substantive fact it states is
    read through from an existing manifest or validation report; it adds
    only the whole-phase canonical identity and freeze status."""
    org = build_benchmark_organization(cfg, generated_at)
    freeze_status = "FROZEN" if freeze_validation["overall_status"] == "PASS" else "NOT_FROZEN"
    return {
        "phase_id": "phase2",
        "phase_version": PHASE2_FREEZE_VERSION,
        "freeze_status": freeze_status,
        "frozen_at": generated_at,  # informational only -- excluded from canonical_identity
        "memory_foundation": {
            "dataset_ids": sorted(APPROVED_MEMORY_FOUNDATION),
            "record_counts": _EXPECTED_MEMORY_RECORD_COUNTS,
            "total_records": _EXPECTED_TOTAL,
        },
        "resource_counts": {
            "by_role": org["resource_count_by_role"],
            "total": org["total_resources"],
        },
        "schema_versions": {"unified_memory_record": UMR_SCHEMA_VERSION},
        "policy_versions": {
            "temporal_normalization": NORMALIZATION_POLICY_VERSION,
            "benchmark_organization": ORGANIZATION_VERSION,
            "reproducibility_manifest": REPRODUCIBILITY_MANIFEST_VERSION,
            "substrate_validation": SUBSTRATE_VALIDATION_VERSION,
        },
        "manifest_references": _MANIFEST_REFERENCES,
        "validation_references": _VALIDATION_REFERENCES,
        "reproducibility_reference": "data/metadata/reproducibility_manifest.json",
        "repository_state": freeze_validation["code_state"],
        "canonical_identity": freeze_validation["canonical_phase2_identity"],
        "freeze_policy_reference": "docs/phase2/PHASE2_FREEZE.md",
    }


def write_phase2_freeze_artifacts(cfg: PipelineConfig, generated_at: Optional[str] = None) -> tuple[Path, Path]:
    if generated_at is None:
        generated_at = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    freeze_validation = validate_phase2_freeze(cfg, generated_at)
    validation_path = cfg.reports_dir / "phase2_7_freeze_validation_report.json"
    write_json(validation_path, freeze_validation)

    manifest = build_phase2_freeze_manifest(cfg, generated_at, freeze_validation)
    manifest_path = cfg.metadata_dir / "phase2_freeze_manifest.json"
    write_json(manifest_path, manifest)
    return validation_path, manifest_path


if __name__ == "__main__":
    from preprocessing.config import load_config

    _cfg = load_config()
    _vpath, _mpath = write_phase2_freeze_artifacts(_cfg)
    print(f"Wrote {_vpath}")
    print(f"Wrote {_mpath}")
