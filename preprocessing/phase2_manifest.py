"""Phase 2.1: builds data/metadata/phase2_input_manifest.json.

This module does NOT re-derive facts about resources (that is
`registry.py`'s and `manifest.py`'s job, and re-deriving them here would
risk drifting from the frozen Phase 1 record). Instead it *reads* the
already-generated, frozen Phase 1 artifacts --
data/metadata/resource_registry.json, data/metadata/dataset_manifest.json,
data/reports/phase1_validation_report.json, data/reports/*_statistics.json
-- cross-checks them against what is actually present on disk, and
reconciles them into a single explicit-status manifest that answers one
question for every one of the 28 tracked resources:

    "Is this resource an approved input to Phase 2, or not, and why?"

Phase 2.1 objective (see project roadmap): freeze, verify, and formally
register the Phase 1 data foundation -- the four PROCESSED core memory
datasets (LoCoMo, LongMemEval, MSC, Conversation Chronicles) -- before any
new benchmark generation or experimental data creation occurs. Only those
four resources are marked `phase2_input_approved: true` /
`phase2_status: "PHASE2_INPUT_APPROVED"` here. Every other resource
(workload, sleeper, attack, security-benchmark) is registered with an
explicit status and `phase2_input_approved: false` -- not because it is
unusable, but because approving it is a decision for the later phase that
actually consumes it (Phase 4 attack generation, Phase 8 sleeper
detection, etc.), not for Phase 2.1's clean-foundation freeze. This keeps
the manifest's approval flag meaning one specific thing, so a later
consumer cannot accidentally treat "INSPECTED, paper only" as
"approved for experiments" just because it appears in this file.

Nothing here fabricates a status. Where the frozen Phase 1 record itself
documents an issue (e.g. the `encoding_correctness` validation FAIL, or a
resource's own `limitations` field), that issue is copied into
`known_issues` verbatim rather than resolved or hidden.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Any, Optional

from preprocessing.config import PipelineConfig
from preprocessing.io_utils import read_json, write_json

PHASE2_MANIFEST_VERSION = "1.0.0"

# The only phase2_status values this module will emit. A later reader
# should treat any other string as a bug, not a fourth category.
_VALID_PHASE2_STATUSES = {
    "PHASE2_INPUT_APPROVED",
    "PREPARED",
    "INSPECTED",
    "CONDITIONALLY_AVAILABLE",
    "UNAVAILABLE",
    "UNVERIFIED",
    "NOT_GENERATED",
}

# The four datasets that constitute the Phase 2.1 "clean memory
# foundation". This set is intentionally hardcoded (not inferred from
# phase1_status == PROCESSED) so that a future resource reaching
# PROCESSED status under a different category cannot silently promote
# itself into the foundation without a deliberate code change here.
_CORE_MEMORY_DATASET_IDS = {"locomo", "longmemeval", "msc", "conversation_chronicles"}


def _phase2_status_for(entry: dict) -> tuple[str, bool, str]:
    """Map a resource_registry.json entry to (phase2_status, approved, scope_note).

    Never invents a status outside `_VALID_PHASE2_STATUSES`.
    """
    resource_id = entry["resource_id"]
    category = entry["category"]
    phase1_status = entry["phase1_status"]

    if resource_id in _CORE_MEMORY_DATASET_IDS:
        if phase1_status != "PROCESSED":
            # Would indicate the registry and the Phase 2.1 core-dataset
            # assumption have drifted -- surface it as UNVERIFIED rather
            # than silently approving or silently excluding it.
            return "UNVERIFIED", False, (
                "core memory dataset but registry phase1_status is "
                f"'{phase1_status}', not PROCESSED -- reconcile before "
                "approving as a Phase 2 input"
            )
        return "PHASE2_INPUT_APPROVED", True, (
            "part of the Phase 2.1 clean memory foundation"
        )

    if category == "sleeper":
        # Explicitly out of scope for Phase 2.1 regardless of phase1_status
        # (Task 11: do not generate sleeper attacks in Phase 2.1).
        return "NOT_GENERATED", False, (
            "sleeper resource; final experimental sleeper dataset is "
            "explicitly not generated until a later phase (Phase 4/8)"
        )

    if category == "attack":
        return "INSPECTED" if phase1_status == "INSPECTED" else (
            "UNAVAILABLE" if phase1_status == "INACCESSIBLE" else "CONDITIONALLY_AVAILABLE"
        ), False, (
            "attack resource; attack/poisoned-memory generation is out of "
            "scope for Phase 2.1 (Task 11) regardless of acquisition state"
        )

    if category == "security_benchmark":
        return "INSPECTED", False, (
            "comparison/evaluation resource; relevant to later baseline "
            "comparison phases (5/6/7/10), not the Phase 2.1 foundation"
        )

    if category == "task_workload":
        status_map = {
            "PREPARED": "CONDITIONALLY_AVAILABLE",
            "INSPECTED": "INSPECTED",
            "OPTIONAL_PENDING_ACCESS": "CONDITIONALLY_AVAILABLE",
        }
        return status_map.get(phase1_status, "UNVERIFIED"), False, (
            "task/workload resource; available as a future benchmark-"
            "construction reference (Phase 4+), not part of the frozen "
            "Phase 2.1 memory foundation, so not approved as a Phase 2 "
            "input here"
        )

    # Fallback: never silently approve something we don't recognize.
    return "UNVERIFIED", False, (
        f"unrecognized category '{category}' for resource_id '{resource_id}' "
        "-- flagged UNVERIFIED rather than guessed"
    )


def _artifact_presence(cfg: PipelineConfig, resource_id: str, repo_root: Path) -> dict:
    """Cross-check what's actually on disk, independent of what the registry claims."""
    raw_dir = cfg.raw_dir / resource_id
    interim_dir = cfg.interim_dir / resource_id
    processed_dir = cfg.processed_dir / resource_id

    def _rel(p: Path) -> Optional[str]:
        return str(p.relative_to(repo_root)) if p.exists() else None

    processed_files = []
    if processed_dir.exists():
        processed_files = sorted(
            str(p.relative_to(repo_root)) for p in processed_dir.glob("*.jsonl")
            if p.exists() and p.stat().st_size > 0
        )

    return {
        "raw_present_on_disk": raw_dir.exists() and any(raw_dir.iterdir()) if raw_dir.exists() else False,
        "interim_present_on_disk": _rel(interim_dir) is not None,
        "processed_files_on_disk": processed_files,
    }


def _known_issues_for(resource_id: str, entry: dict, dataset_facts: dict,
                       validation_report: dict, dataset_stats: dict) -> list[str]:
    issues: list[str] = []
    limitation = entry.get("limitations")
    if limitation:
        issues.append(limitation)

    facts = dataset_facts.get(resource_id)
    if facts:
        kl = facts.get("known_limitations")
        if kl and kl != limitation:
            issues.append(kl)

    if resource_id in _CORE_MEMORY_DATASET_IDS:
        stats = dataset_stats.get(resource_id, {})
        dist = stats.get("quality_status_distribution", {})
        flagged = dist.get("valid_flagged", 0)
        if flagged:
            issues.append(
                f"{flagged} record(s) classified valid_flagged "
                f"(quality_status_distribution={dist})"
            )
        quarantined = stats.get("quarantined_record_count", 0)
        if quarantined:
            issues.append(
                f"{quarantined} record(s) quarantined; see "
                "data/logs/quarantine_log.jsonl and "
                f"data/interim/{resource_id}/quarantine.jsonl for full traceability"
            )

    # Cross-dataset validation check that failed and touches this dataset.
    if resource_id == "longmemeval":
        for check in validation_report.get("checks", []):
            if check.get("name") == "encoding_correctness" and check.get("status") == "FAIL":
                issues.append(
                    "phase1_validation_report.json: encoding_correctness check "
                    f"FAILED ({check['detail']['replacement_char_count']} record(s) "
                    f"with U+FFFD replacement characters, sample IDs "
                    f"{check['detail']['sample']}) -- pre-existing source-data "
                    "mojibake, deliberately preserved rather than guessed-and-"
                    "repaired; NOT silently resolved here"
                )

    return issues


def build_phase2_manifest(cfg: PipelineConfig, generated_at: str) -> dict:
    repo_root = cfg.raw_dir.parent.parent

    registry = read_json(cfg.metadata_dir / "resource_registry.json")
    dataset_manifest = read_json(cfg.metadata_dir / "dataset_manifest.json")
    validation_report = read_json(cfg.reports_dir / "phase1_validation_report.json")

    dataset_stats: dict[str, Any] = {}
    for ds_id in _CORE_MEMORY_DATASET_IDS:
        stats_path = cfg.reports_dir / f"{ds_id}_statistics.json"
        if stats_path.exists():
            dataset_stats[ds_id] = read_json(stats_path)

    dataset_facts = dataset_manifest.get("datasets", {})

    entries = []
    for entry in registry["resources"]:
        resource_id = entry["resource_id"]
        phase2_status, approved, scope_note = _phase2_status_for(entry)
        assert phase2_status in _VALID_PHASE2_STATUSES, phase2_status

        presence = _artifact_presence(cfg, resource_id, repo_root)
        facts = dataset_facts.get(resource_id, {})

        manifest_entry = {
            "resource_id": resource_id,
            "resource_name": entry["name"],
            "resource_category": entry["category"],
            "source": entry["source_reference"],
            "dataset_version_or_revision": entry.get("version_or_revision", "unavailable"),
            "snapshot_identifier": facts.get("acquisition_date"),
            "local_artifact_location": entry.get("local_path"),
            "checksums": facts.get("files", []) if facts else [],
            "licensing_or_access_status": entry.get("access_and_license"),
            "preparation_status": entry.get("preprocessing_status"),
            "phase1_status": entry.get("phase1_status"),
            "provenance_status": (
                "provenance dataclass populated + validated (see "
                "phase1_validation_report.json: valid_provenance PASS)"
                if resource_id in _CORE_MEMORY_DATASET_IDS
                else "not applicable at Phase 1 (not run through the "
                "memory-record provenance pipeline)"
            ),
            "intended_project_role": entry.get("research_purpose"),
            "intended_later_phase": entry.get("intended_later_phase"),
            "known_issues": _known_issues_for(
                resource_id, entry, dataset_facts, validation_report, dataset_stats
            ),
            "phase2_status": phase2_status,
            "phase2_input_approved": approved,
            "phase2_1_scope_note": scope_note,
            "preparation_pipeline_version": "preprocessing.PIPELINE_VERSION == 1.0.0"
            if resource_id in _CORE_MEMORY_DATASET_IDS or entry.get("phase1_status") in ("PREPARED",)
            else "not applicable",
            "schema_version": "preprocessing.schema (MemoryRecord/TaskRecord/Provenance) v1"
            if resource_id in _CORE_MEMORY_DATASET_IDS
            else ("preprocessing.schema_workload (WorkloadRecord) v1"
                  if entry.get("category") == "task_workload" and entry.get("phase1_status") == "PREPARED"
                  else "not applicable"),
            "artifact_presence_on_disk": presence,
        }
        entries.append(manifest_entry)

    approved_ids = sorted(e["resource_id"] for e in entries if e["phase2_input_approved"])
    by_phase2_status: dict[str, int] = {}
    for e in entries:
        by_phase2_status[e["phase2_status"]] = by_phase2_status.get(e["phase2_status"], 0) + 1

    return {
        "phase2_manifest_version": PHASE2_MANIFEST_VERSION,
        "generated_at": generated_at,
        "generated_from": {
            "resource_registry": "data/metadata/resource_registry.json"
            f" (registry_version={registry.get('registry_version')})",
            "dataset_manifest": "data/metadata/dataset_manifest.json"
            f" (manifest_version={dataset_manifest.get('manifest_version')})",
            "phase1_validation_report": "data/reports/phase1_validation_report.json"
            f" (overall_status={validation_report.get('overall_status')})",
        },
        "phase1_overall_status": "PASS WITH ISSUES",
        "phase1_validation_overall_status": validation_report.get("overall_status"),
        "scope_decision": (
            "phase2_input_approved is true ONLY for the four core memory "
            "datasets (locomo, longmemeval, msc, conversation_chronicles), "
            "matching the Phase 2.1 objective of freezing the clean memory "
            "foundation. All other resources (workload/sleeper/attack/"
            "security-benchmark) are registered with an explicit status "
            "but are NOT approved Phase 2 inputs here -- approval for those "
            "belongs to the later phase that actually consumes them."
        ),
        "core_memory_foundation": sorted(_CORE_MEMORY_DATASET_IDS),
        "phase2_input_approved_resource_ids": approved_ids,
        "total_resources": len(entries),
        "resources_by_phase2_status": by_phase2_status,
        "resources": entries,
    }


def write_phase2_manifest(cfg: PipelineConfig, generated_at: str | None = None) -> Path:
    if generated_at is None:
        generated_at = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = build_phase2_manifest(cfg, generated_at)
    out_path = cfg.metadata_dir / "phase2_input_manifest.json"
    write_json(out_path, manifest)
    return out_path


if __name__ == "__main__":
    from preprocessing.config import load_config

    _cfg = load_config()
    _out = write_phase2_manifest(_cfg)
    print(f"Wrote {_out}")
