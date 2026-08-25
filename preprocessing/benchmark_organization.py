"""Phase 2.4: benchmark-level resource organization.

SCOPE (see docs/phase2/BENCHMARK_ORGANIZATION.md for the full statement):
this module answers "what job does each acquired/prepared resource do in
the benchmark" -- it assigns exactly one primary benchmark role to every
resource already tracked in the Phase 1 resource registry, and exposes a
machine-readable view grouped by that role. It does NOT implement
attacks, poisoned-memory generation, propagation/lifecycle analysis,
sleeper detection, or defenses; it does not regenerate, re-normalize, or
re-score any dataset. Those are later phases (or, for temporal
normalization, an earlier one -- see preprocessing/temporal.py).

WHY THIS IS A THIN LAYER, NOT A NEW REGISTRY: Phase 1's
`preprocessing/registry.py` already tracks every resource's identity,
provenance, and acquisition/processing status; Phase 2.1's
`preprocessing/phase2_manifest.py` already reconciles that against actual
on-disk presence into an honest availability/approval status. Neither of
those files' data is re-derived or duplicated here -- this module reads
both (never writing to either), classifies each resource's `category`
into one of five benchmark roles via a fixed, total, deterministic
mapping, and joins the two into one queryable manifest,
`data/metadata/benchmark_resources.json`. Nothing in this module fetches,
downloads, generates, or copies resource data.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from preprocessing.config import PipelineConfig
from preprocessing.io_utils import read_json, write_json
from preprocessing.phase2_manifest import build_phase2_manifest
from preprocessing.registry import build_registry_report
from preprocessing.temporal import NORMALIZATION_POLICY_VERSION as TEMPORAL_POLICY_VERSION
from preprocessing.unified_schema import CORE_DATASETS
from preprocessing.unified_schema import SCHEMA_VERSION as UMR_SCHEMA_VERSION

ORGANIZATION_VERSION = "1.0.0"

ROLE_MEMORY = "memory"
ROLE_WORKLOAD = "workload"
ROLE_ATTACK = "attack"
ROLE_SLEEPER = "sleeper"
ROLE_EVALUATION = "evaluation"

VALID_ROLES = {ROLE_MEMORY, ROLE_WORKLOAD, ROLE_ATTACK, ROLE_SLEEPER, ROLE_EVALUATION}

# The ONLY place a registry `category` is mapped to a benchmark role.
# Total (every category Phase 1's registry ever emits has an entry) and
# 1:1 -- see tests/test_registry.py:_VALID_CATEGORIES for the frozen set
# of five categories this must stay in sync with.
_CATEGORY_TO_ROLE = {
    "memory_data": ROLE_MEMORY,
    "task_workload": ROLE_WORKLOAD,
    "attack": ROLE_ATTACK,
    "sleeper": ROLE_SLEEPER,
    "security_benchmark": ROLE_EVALUATION,
}

# The four approved Phase 2 memory-foundation datasets. Reused verbatim
# from preprocessing/unified_schema.py -- the same canonical identifier
# tuple Phase 2.2/2.3 already build the real corpus from -- rather than a
# second, independently-typed constant that could silently drift from it.
APPROVED_MEMORY_FOUNDATION = frozenset(CORE_DATASETS)


class RoleClassificationError(ValueError):
    pass


def classify_role(category: str) -> str:
    """Maps a registry `category` to exactly one benchmark role. Raises
    rather than silently defaulting on an unrecognized category -- a new
    category showing up in a future registry update must be classified
    deliberately, not swallowed into an arbitrary default role."""
    try:
        return _CATEGORY_TO_ROLE[category]
    except KeyError:
        raise RoleClassificationError(
            f"unrecognized resource category {category!r}; no benchmark role "
            f"mapping exists for it in preprocessing.benchmark_organization."
            f"_CATEGORY_TO_ROLE -- add one deliberately rather than guessing"
        ) from None


def _implementation_status(local_path: Optional[str], acquisition_status: str) -> str:
    """A resource's ROLE (what job it does) is never the same claim as its
    STATUS (whether it has actually been implemented/acquired locally).
    Derived purely from the registry's own existing, already-verified
    fields -- never a per-resource hardcoded judgment -- exactly the
    'general rule, not a hardcoded ID filter' pattern this project already
    uses for `admission_status` in preprocessing/unified_memory.py."""
    if local_path:
        return "local_copy_present"
    text = acquisition_status.upper()
    if "CODE AVAILABLE" in text:
        return "public_code_available_not_locally_implemented"
    if "PAPER VERIFIED" in text or "SOURCE AVAILABLE" in text:
        return "specification_only_no_public_implementation_found"
    return "unresolved"  # never silently guessed beyond the evidence above


def _memory_foundation_integrity(cfg: PipelineConfig) -> dict:
    """Reads Phase 2.2/2.3's already-computed validation reports -- never
    rescans the 1.27M-record corpus itself, so this stays cheap and never
    duplicates the large real dataset."""
    integrity: dict = {
        "umr_schema_version": UMR_SCHEMA_VERSION,
        "temporal_normalization_policy_version": TEMPORAL_POLICY_VERSION,
        "approved_dataset_ids": sorted(APPROVED_MEMORY_FOUNDATION),
    }
    umr_report_path = cfg.reports_dir / "phase2_2_unified_memory_validation_report.json"
    if umr_report_path.exists():
        v = read_json(umr_report_path)
        integrity["umr_validation_overall_status"] = v.get("overall_status")
        integrity["umr_per_dataset_record_counts"] = v.get("per_dataset_counts")
        integrity["umr_total_records"] = v.get("total_records")
    else:
        integrity["umr_validation_overall_status"] = None
        integrity["umr_per_dataset_record_counts"] = None
        integrity["umr_total_records"] = None

    temporal_report_path = cfg.reports_dir / "phase2_3_temporal_validation_report.json"
    if temporal_report_path.exists():
        t = read_json(temporal_report_path)
        integrity["temporal_validation_overall_status"] = t.get("overall_status")
    else:
        integrity["temporal_validation_overall_status"] = None
    return integrity


def build_benchmark_organization(cfg: PipelineConfig, generated_at: str) -> dict:
    """Joins Phase 1's resource registry (identity/provenance/category)
    with Phase 2.1's phase2_input_manifest (honest availability/approval
    status) into one role-organized, deterministically-ordered manifest.
    Reads both; writes neither. Never fabricates a field not already
    present in one of the two source documents."""
    registry_report = build_registry_report(cfg)
    phase2_manifest = build_phase2_manifest(cfg, generated_at)
    phase2_by_id = {e["resource_id"]: e for e in phase2_manifest["resources"]}

    resources: list[dict] = []
    for reg_entry in registry_report["resources"]:
        resource_id = reg_entry["resource_id"]
        category = reg_entry["category"]
        primary_role = classify_role(category)

        is_memory_foundation = resource_id in APPROVED_MEMORY_FOUNDATION
        if is_memory_foundation and primary_role != ROLE_MEMORY:
            raise RoleClassificationError(
                f"{resource_id} is an approved memory-foundation dataset but "
                f"classified role={primary_role!r} (category={category!r}) -- "
                f"registry/foundation-list inconsistency, refusing to organize"
            )
        if primary_role == ROLE_MEMORY and not is_memory_foundation:
            raise RoleClassificationError(
                f"{resource_id} classified role={ROLE_MEMORY!r} but is NOT in "
                f"APPROVED_MEMORY_FOUNDATION -- a 5th memory_data-category "
                f"resource would silently expand the memory foundation; "
                f"refusing to organize until this is deliberately reconciled"
            )

        p2 = phase2_by_id.get(resource_id, {})

        entry = {
            "resource_id": resource_id,
            "name": reg_entry["name"],
            "primary_role": primary_role,
            "secondary_roles": [],  # none of the 28 tracked resources currently documents a second role; see docs
            "source_category": category,  # Phase 1's own category, preserved verbatim (not overwritten by the role)
            "research_purpose": reg_entry["research_purpose"],
            "source_reference": reg_entry["source_reference"],
            "version_or_revision": reg_entry["version_or_revision"],
            "access_and_license": reg_entry["access_and_license"],
            "local_path": reg_entry["local_path"],
            "phase1_status": reg_entry["phase1_status"],
            "preprocessing_status": reg_entry["preprocessing_status"],
            "acquisition_status": reg_entry["acquisition_status"],
            "implementation_status": _implementation_status(reg_entry["local_path"], reg_entry["acquisition_status"]),
            "phase2_status": p2.get("phase2_status"),
            "phase2_input_approved": p2.get("phase2_input_approved"),
            "artifact_presence_on_disk": p2.get("artifact_presence_on_disk"),
            "known_issues": p2.get("known_issues", []),
            "reproducibility": reg_entry["reproducibility"],
            "limitations": reg_entry["limitations"],
            "intended_later_phase": reg_entry["intended_later_phase"],
            "provenance": {
                "source": "external -- see source_reference; not authored by MAMBench",
                "mambench_created": (
                    "this manifest entry's role classification and status join "
                    "only; no new dataset content, label, or file was generated "
                    "by Phase 2.4"
                ),
            },
        }
        resources.append(entry)

    resources.sort(key=lambda e: e["resource_id"])  # deterministic regardless of upstream ordering

    resources_by_role: dict[str, list[str]] = {role: [] for role in sorted(VALID_ROLES)}
    for e in resources:
        resources_by_role[e["primary_role"]].append(e["resource_id"])
    for role in resources_by_role:
        resources_by_role[role].sort()

    return {
        "organization_version": ORGANIZATION_VERSION,
        "generated_at": generated_at,
        "generated_from": {
            "resource_registry": f"data/metadata/resource_registry.json (registry_version={registry_report['registry_version']})",
            "phase2_input_manifest": f"data/metadata/phase2_input_manifest.json (phase2_manifest_version={phase2_manifest['phase2_manifest_version']})",
        },
        "role_vocabulary": sorted(VALID_ROLES),
        "memory_foundation": {
            "approved_dataset_ids": sorted(APPROVED_MEMORY_FOUNDATION),
            "note": (
                "Exactly these four datasets constitute the Phase 2 clean "
                "memory foundation. Their Phase 2.2 Unified Memory Records "
                "and Phase 2.3 temporal normalization are unchanged by "
                "Phase 2.4 -- see umr_integrity below."
            ),
        },
        "resources_by_role": resources_by_role,
        "resource_count_by_role": {role: len(ids) for role, ids in resources_by_role.items()},
        "total_resources": len(resources),
        "umr_integrity": _memory_foundation_integrity(cfg),
        "resources": resources,
    }


def write_benchmark_organization(cfg: PipelineConfig, generated_at: Optional[str] = None) -> Path:
    if generated_at is None:
        import datetime as _dt

        generated_at = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = build_benchmark_organization(cfg, generated_at)
    out_path = cfg.metadata_dir / "benchmark_resources.json"
    write_json(out_path, manifest)
    return out_path


if __name__ == "__main__":
    from preprocessing.config import load_config

    _cfg = load_config()
    _path = write_benchmark_organization(_cfg)
    print(f"Wrote {_path}")
