"""Phase 2.5: benchmark metadata & manifests -- exact reproducibility
identity for every organized resource.

SCOPE (see docs/phase2/BENCHMARK_METADATA_AND_MANIFESTS.md for the full
statement): Phase 2.4 (`preprocessing/benchmark_organization.py`) answers
"what job does this resource do in the benchmark" (its ROLE). Phase 2.5
answers a different question -- "exactly which version/configuration/
processing state of this resource are we using" (its REPRODUCIBILITY
IDENTITY): source version/snapshot, MAMBench preparation version, schema
version, active policies, seed, and configuration identity. It does not
implement attacks, poisoning, lifecycle, propagation, sleeper-detection,
or defenses, and it does not regenerate, re-normalize, or re-score any
dataset.

SINGLE AUTHORITATIVE CHAIN -- this module is the fourth and final link,
and adds no second registry:

    registry.py                -- resource IDENTITY + Phase 1 acquisition/
                                   processing status (WHAT is this thing)
    phase2_manifest.py          -- Phase 2 input APPROVAL status
    benchmark_organization.py   -- benchmark ROLE (what JOB does it do)
    reproducibility.py (this)   -- REPRODUCIBILITY IDENTITY

Each link reads every upstream link (never writes to one) and adds only
facts not already present upstream.

THREE DISTINCT LEVELS OF METADATA (kept as separate sub-objects, never
merged into one flat record -- see Section 16 of the Phase 2.5 brief):

  resource_identity     -- human-readable "what/where/how available" facts,
                            largely a read-through of benchmark_resources.json
  canonical_identity     -- the *minimal*, machine-independent, timestamp-
                            independent field set that answers "exactly
                            which version/config/policy/seed produced this
                            artifact" -- this is what gets hashed into
                            canonical_identity_hash
  artifact_identity      -- identity of the *prepared MAMBench artifact*
                            (only exists for resources actually run through
                            a preparation pipeline), derived from
                            canonical_identity via a stable content hash

CANONICAL IDENTITY POLICY (Sections 18-20 of the brief): the fields folded
into `canonical_identity_hash` are exactly: resource_id, source version/
revision, snapshot id, MAMBench preparation version, schema version,
temporal policy version, configuration_id, and seed (applicable + value).
`generated_at`, `local_path`, and any absolute filesystem path are NEVER
part of this set -- two runs on two different machines, on different days,
with different local raw-file layouts, must yield the identical hash
provided the seven canonical fields above are unchanged.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Optional

from preprocessing import PIPELINE_VERSION
from preprocessing.benchmark_organization import (
    ORGANIZATION_VERSION,
    build_benchmark_organization,
)
from preprocessing.config import PipelineConfig
from preprocessing.io_utils import deterministic_id, read_json, sha256_file, write_json
from preprocessing.phase2_manifest import PHASE2_MANIFEST_VERSION
from preprocessing.registry import REPO_ROOT
from preprocessing.temporal import NORMALIZATION_POLICY_VERSION
from preprocessing.unified_schema import CORE_DATASETS, SCHEMA_VERSION as UMR_SCHEMA_VERSION

REPRODUCIBILITY_MANIFEST_VERSION = "1.0.0"

_UNKNOWN = "unknown"          # value genuinely not established upstream -- never guessed
_NOT_APPLICABLE = "not_applicable"

# Resources whose Phase 1 pipeline actually consumes the master seed. A
# general rule (not a per-resource special case elsewhere): only
# conversation_chronicles' deterministic reservoir sample is randomized;
# every other dataset/mapping step is a pure function of its input. See
# config/pipeline_config.yaml `episode_sample_caps` and preprocessing/
# datasets/conversation_chronicles.py.
_SEED_CONSUMING_RESOURCES = frozenset({"conversation_chronicles"})

# Resources whose Phase 1 status means an actual MAMBench preparation
# pipeline ran and produced a local artifact -- vs. resources that were
# only inspected/specified. Artifact identity only exists for the former
# (Section 17: "prepared" is not the same claim as "registered").
_PREPARED_PHASE1_STATUSES = frozenset({"PROCESSED", "PREPARED"})


def _run_git(*args: str) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True,
            check=True, timeout=10,
        )
        return result.stdout.strip()
    except Exception:
        return None


def get_code_state() -> dict:
    """Captures the exact code-state identity (Phase 2.1-R's git baseline)
    automatically, rather than requiring a human to check `git log` by
    hand -- closing the gap docs/phase2/REPRODUCIBILITY_REPORT.md left
    open ("No automatic stamping"). If git is unavailable, every field is
    explicit `None` rather than a fabricated placeholder. Not part of
    canonical_identity (Section 18-19): code state identifies the
    *pipeline*, not any single resource's data identity."""
    commit_hash = _run_git("rev-parse", "HEAD")
    if commit_hash is None:
        return {
            "git_available": False,
            "commit_hash": None,
            "commit_hash_short": None,
            "branch": None,
            "is_dirty": None,
            "note": "git command unavailable or repository root is not a git work tree",
        }
    branch = _run_git("rev-parse", "--abbrev-ref", "HEAD")
    status_porcelain = _run_git("status", "--porcelain")
    return {
        "git_available": True,
        "commit_hash": commit_hash,
        "commit_hash_short": commit_hash[:12],
        "branch": branch,
        "is_dirty": bool(status_porcelain),
        "note": (
            "is_dirty=true means uncommitted changes existed in the working "
            "tree at manifest-generation time -- commit_hash alone does NOT "
            "fully identify the code that produced this manifest in that case"
        ),
    }


def get_configuration_identity(cfg: PipelineConfig) -> dict:
    """Configuration identity is a CONTENT hash of config/pipeline_config.yaml,
    not its filename or absolute path (Section 13: 'config_final.json' is
    not scientific identity). The relative repo path is recorded as
    convenience metadata only -- `configuration_id` (the content hash) is
    the field that actually participates in canonical_identity."""
    config_path = cfg.config_path
    return {
        "configuration_id": sha256_file(config_path) if config_path.exists() else None,
        "configuration_id_algorithm": "sha256 of config/pipeline_config.yaml raw file content",
        "config_relative_path": (
            str(config_path.relative_to(REPO_ROOT)) if config_path.is_relative_to(REPO_ROOT) else config_path.name
        ),
    }


def get_pipeline_identity(cfg: PipelineConfig, code_state: Optional[dict] = None,
                           configuration_identity: Optional[dict] = None) -> dict:
    """Everything needed to answer 'exactly which code + config + seed
    produced this?' at the pipeline level -- distinct from any single
    resource's own source version (see `_canonical_resource_fields`)."""
    return {
        "preprocessing_pipeline_version": PIPELINE_VERSION,
        "code_state": code_state if code_state is not None else get_code_state(),
        "master_seed": cfg.seed,
        "seed_usage_note": (
            "the master seed is consumed by exactly one randomized step in "
            "the pipeline -- Conversation Chronicles' deterministic reservoir "
            "sample (config/pipeline_config.yaml episode_sample_caps). Every "
            "other dataset/mapping step is seed-independent (content-hashed "
            "IDs, positional ordering). Per-resource seed applicability is "
            "recorded in each resource's canonical_identity.seed block -- "
            "never a single blanket 'seed=X' claim across all 28 resources."
        ),
        "configuration_identity": (
            configuration_identity if configuration_identity is not None else get_configuration_identity(cfg)
        ),
    }


def get_schema_and_policy_versions() -> dict:
    """Every schema/policy version this project currently maintains,
    referenced (read from its own single source of truth) rather than
    restated as an independent literal."""
    return {
        "unified_memory_record_schema_version": UMR_SCHEMA_VERSION,
        "temporal_normalization_policy_version": NORMALIZATION_POLICY_VERSION,
        "phase2_input_manifest_version": PHASE2_MANIFEST_VERSION,
        "benchmark_organization_version": ORGANIZATION_VERSION,
        "reproducibility_manifest_version": REPRODUCIBILITY_MANIFEST_VERSION,
        "workload_record_schema_version": _UNKNOWN,
        "workload_record_schema_version_note": (
            "preprocessing/schema_workload.py (WorkloadRecord) currently has "
            "no independent version constant of its own -- a schema change "
            "there and a logic-only change both leave PIPELINE_VERSION "
            "unchanged. Documented as an explicit, pre-existing gap (see "
            "docs/phase2/REPRODUCIBILITY_REPORT.md, 'Schema version (record "
            "shape): Implicit'), not fabricated here as if a version existed."
        ),
        "quality_policy": {
            "vocabulary_source": "preprocessing.unified_schema.VALID_QUALITY_STATUSES",
            "values": ["valid", "repaired", "valid_flagged", "irrecoverably_invalid"],
            "note": (
                "Phase 1's quality classification and Phase 2.2's admission_status "
                "derivation from it (see preprocessing/unified_memory.py) are the "
                "authoritative quality policy; Phase 2.5 references this vocabulary, "
                "it does not recompute or override any record's quality_status."
            ),
        },
        "provenance_policy": {
            "vocabulary_source": "preprocessing.unified_schema.VALID_FIELD_STATUSES",
            "origins": ["SOURCE_PROVIDED", "BENCHMARK_GENERATED", "INFERRED", "MODEL_PREDICTED"],
            "absence_reasons": ["NOT_AVAILABLE", "NOT_APPLICABLE", "UNRESOLVED", "NOT_EVALUATED"],
            "note": (
                "the UMR field_status model (see preprocessing/unified_schema.py "
                "module docstring) is the active provenance policy for every "
                "core-dataset record; Phase 2.5 does not introduce a second "
                "provenance vocabulary."
            ),
        },
    }


def _dataset_facts(cfg: PipelineConfig) -> dict:
    manifest = read_json(cfg.metadata_dir / "dataset_manifest.json")
    return manifest.get("datasets", {})


def _canonical_resource_fields(resource_id: str, org_entry: dict, dataset_facts: dict,
                                configuration_id: Optional[str], cfg: PipelineConfig) -> dict:
    """The minimal, machine-independent, timestamp-independent field set
    for this resource. NEVER includes local_path, generated_at, or any
    absolute filesystem path (Section 20). Unknown facts are the literal
    string 'unknown'/'not_applicable', never a guessed value (Section 25)."""
    is_core = resource_id in CORE_DATASETS
    is_prepared = org_entry["phase1_status"] in _PREPARED_PHASE1_STATUSES
    facts = dataset_facts.get(resource_id, {})

    raw_version = org_entry.get("version_or_revision")
    source_version = raw_version if raw_version and "unavailable" not in raw_version else _UNKNOWN
    snapshot_id = facts.get("acquisition_date") or _UNKNOWN

    seed_applicable = resource_id in _SEED_CONSUMING_RESOURCES
    seed_block = {
        "seed_applicable": seed_applicable,
        "seed_value": cfg.seed if seed_applicable else None,
        "seed_status": "seed_used" if seed_applicable else "seed_not_applicable",
    }

    return {
        "resource_id": resource_id,
        "source_dataset_version_or_revision": source_version,
        "snapshot_id": snapshot_id,
        "preparation_version": PIPELINE_VERSION if is_prepared else _NOT_APPLICABLE,
        "unified_memory_record_schema_version": UMR_SCHEMA_VERSION if is_core else _NOT_APPLICABLE,
        "temporal_normalization_policy_version": NORMALIZATION_POLICY_VERSION if is_core else _NOT_APPLICABLE,
        "configuration_id": configuration_id or _UNKNOWN,
        "seed": seed_block,
    }


def _canonical_hash(fields: dict) -> str:
    canonical_json = json.dumps(fields, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def _artifact_identity(resource_id: str, org_entry: dict, canonical_fields: dict) -> dict:
    """Artifact identity exists ONLY for resources actually run through a
    MAMBench preparation pipeline (Phase1 status PROCESSED/PREPARED) --
    registering a resource's metadata is never conflated with having
    prepared an artifact from it (Section 17/24). Derived deterministically
    from the canonical fields via the project's existing
    `io_utils.deterministic_id` (same content-hash convention already used
    for memory_id/task_id), so an artifact's identity changes exactly when
    its canonical inputs change -- never on a manifest reformat."""
    if org_entry["phase1_status"] not in _PREPARED_PHASE1_STATUSES:
        return {
            "artifact_id": None,
            "status": "not_applicable_no_prepared_artifact",
            "note": f"phase1_status={org_entry['phase1_status']!r}; no MAMBench preparation pipeline has run for this resource",
        }
    artifact_id = deterministic_id(
        resource_id,
        canonical_fields["source_dataset_version_or_revision"],
        canonical_fields["snapshot_id"],
        canonical_fields["preparation_version"],
        canonical_fields["unified_memory_record_schema_version"],
        canonical_fields["temporal_normalization_policy_version"],
        canonical_fields["configuration_id"],
        str(canonical_fields["seed"]["seed_value"]),
    )
    return {"artifact_id": artifact_id, "status": "prepared", "note": None}


def _source_identity(resource_id: str, org_entry: dict, dataset_facts: dict) -> dict:
    """Human-readable, convenience-only view (may include the resource's
    relative local_path). Distinct from canonical_identity: this block is
    NOT hashed and NOT relied on for reproducibility identity, only for a
    human reading the manifest."""
    facts = dataset_facts.get(resource_id, {})
    checksums = facts.get("files") or facts.get("extracted_files") or []
    return {
        "source_reference": org_entry["source_reference"],
        "source_dataset_version_or_revision": org_entry["version_or_revision"],
        "local_snapshot_acquisition_date": facts.get("acquisition_date"),
        "local_artifact_checksums": checksums,
        "local_path": org_entry.get("local_path"),
        "access_and_license": org_entry["access_and_license"],
        "acquisition_status": org_entry["acquisition_status"],
        "processing_state": org_entry["preprocessing_status"],
        "implementation_state": org_entry["implementation_status"],
    }


def _reproduction_instructions(resource_id: str, org_entry: dict, code_state: dict) -> str:
    commit = code_state.get("commit_hash") or "<git unavailable -- see pipeline_identity.code_state>"
    dirty_note = " (working tree had uncommitted changes at generation time)" if code_state.get("is_dirty") else ""
    if resource_id in CORE_DATASETS:
        return (
            f"git checkout {commit}{dirty_note}; place the raw source file(s) "
            f"listed under source_identity.local_artifact_checksums at the "
            f"paths their sha256 was computed from; run "
            f"`python -m preprocessing.run_all`, then "
            f"`python -m preprocessing.unified_memory`, then "
            f"`python -m preprocessing.temporal_validation` -- using "
            f"config/pipeline_config.yaml (configuration_id records its exact "
            f"content hash) and master_seed from pipeline_identity."
        )
    return (
        f"git checkout {commit}{dirty_note}; this resource's Phase1 status is "
        f"{org_entry['phase1_status']!r} and it is not part of the core memory "
        f"foundation pipeline -- see reproduction guidance under source_identity "
        f"in data/metadata/benchmark_resources.json for its own path, if any."
    )


def build_reproducibility_manifest(cfg: PipelineConfig, generated_at: str) -> dict:
    org = build_benchmark_organization(cfg, generated_at)
    dataset_facts = _dataset_facts(cfg)
    code_state = get_code_state()
    configuration_identity = get_configuration_identity(cfg)
    configuration_id = configuration_identity["configuration_id"]
    pipeline_identity = get_pipeline_identity(cfg, code_state=code_state, configuration_identity=configuration_identity)

    resources = []
    seen_ids: set[str] = set()
    for org_entry in org["resources"]:
        resource_id = org_entry["resource_id"]
        assert resource_id not in seen_ids, f"duplicate resource_id {resource_id!r} in benchmark_organization output"
        seen_ids.add(resource_id)

        canonical_fields = _canonical_resource_fields(resource_id, org_entry, dataset_facts, configuration_id, cfg)
        resources.append({
            "resource_id": resource_id,
            "resource_name": org_entry["name"],
            "primary_role": org_entry["primary_role"],
            "source_identity": _source_identity(resource_id, org_entry, dataset_facts),
            "canonical_identity": canonical_fields,
            "canonical_identity_hash": _canonical_hash(canonical_fields),
            "artifact_identity": _artifact_identity(resource_id, org_entry, canonical_fields),
            "phase2_status": org_entry["phase2_status"],
            "phase2_input_approved": org_entry["phase2_input_approved"],
            "reproduction_instructions": _reproduction_instructions(resource_id, org_entry, code_state),
        })
    resources.sort(key=lambda e: e["resource_id"])

    unresolved_identity_gaps = [
        "requirements.txt uses '>=' version ranges; no dependency lockfile "
        "or captured pip freeze exists (see docs/phase2/REPRODUCIBILITY_REPORT.md)",
        "preprocessing/schema_workload.py has no independent schema version "
        "constant (see schema_and_policy_versions.workload_record_schema_version_note)",
    ]
    unresolved_identity_gaps.extend(sorted({
        f"{e['resource_id']}: source_dataset_version_or_revision is unknown upstream"
        for e in resources
        if e["canonical_identity"]["source_dataset_version_or_revision"] == _UNKNOWN
    }))

    return {
        "reproducibility_manifest_version": REPRODUCIBILITY_MANIFEST_VERSION,
        "generated_at": generated_at,  # informational only -- NOT part of any canonical_identity_hash
        "generated_from": {
            "benchmark_resources": f"data/metadata/benchmark_resources.json (organization_version={org['organization_version']})",
            "dataset_manifest": "data/metadata/dataset_manifest.json",
        },
        "pipeline_identity": pipeline_identity,
        "schema_and_policy_versions": get_schema_and_policy_versions(),
        "memory_foundation": org["memory_foundation"],
        "record_counts": org["umr_integrity"],
        "total_resources": len(resources),
        "resources": resources,
        "unresolved_identity_gaps": unresolved_identity_gaps,
    }


def write_reproducibility_manifest(cfg: PipelineConfig, generated_at: Optional[str] = None) -> Path:
    if generated_at is None:
        generated_at = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = build_reproducibility_manifest(cfg, generated_at)
    out_path = cfg.metadata_dir / "reproducibility_manifest.json"
    write_json(out_path, manifest)
    return out_path


if __name__ == "__main__":
    from preprocessing.config import load_config

    _cfg = load_config()
    _path = write_reproducibility_manifest(_cfg)
    print(f"Wrote {_path}")
