"""Phase 2.1 freeze-boundary tests.

These verify the invariants that must hold at the Phase 1 -> Phase 2
boundary: the frozen Phase 1 artifacts are what they claim to be, the
Phase 2 input manifest is internally consistent and deterministic, raw
source data is untouched, and no unavailable/attack/sleeper resource can
be mistaken for an approved clean-foundation input.

Runs against the real repository data/ directory (read-only) rather than
synthetic fixtures, because the freeze boundary is a property of the
actual frozen Phase 1 outputs, not of the pipeline code in the abstract.
"""
from __future__ import annotations

import hashlib
import json

from preprocessing.config import load_config
from preprocessing.io_utils import read_json
from preprocessing.phase2_manifest import (
    _CORE_MEMORY_DATASET_IDS,
    _VALID_PHASE2_STATUSES,
    build_phase2_manifest,
)

_REQUIRED_MANIFEST_ENTRY_FIELDS = {
    "resource_id", "resource_name", "resource_category", "source",
    "dataset_version_or_revision", "snapshot_identifier",
    "local_artifact_location", "checksums", "licensing_or_access_status",
    "preparation_status", "phase1_status", "provenance_status",
    "intended_project_role", "intended_later_phase", "known_issues",
    "phase2_status", "phase2_input_approved", "phase2_1_scope_note",
    "preparation_pipeline_version", "schema_version",
    "artifact_presence_on_disk",
}


def _cfg():
    return load_config()


def _manifest():
    cfg = _cfg()
    return build_phase2_manifest(cfg, generated_at="2026-08-16T00:00:00Z")


# 1. Core dataset registration is complete.
def test_core_datasets_all_registered():
    m = _manifest()
    ids = {e["resource_id"] for e in m["resources"]}
    assert _CORE_MEMORY_DATASET_IDS.issubset(ids)
    assert set(m["core_memory_foundation"]) == _CORE_MEMORY_DATASET_IDS


# 2. Required metadata exists.
def test_every_manifest_entry_has_required_fields():
    m = _manifest()
    for e in m["resources"]:
        missing = _REQUIRED_MANIFEST_ENTRY_FIELDS - e.keys()
        assert not missing, f"{e['resource_id']} missing fields: {missing}"


# 3. Resource statuses are valid.
def test_phase2_statuses_are_from_known_vocabulary():
    m = _manifest()
    for e in m["resources"]:
        assert e["phase2_status"] in _VALID_PHASE2_STATUSES, e["resource_id"]


# 4. Unavailable resources cannot be accidentally treated as available inputs.
def test_unavailable_and_inspected_resources_are_not_approved():
    m = _manifest()
    by_id = {e["resource_id"]: e for e in m["resources"]}
    # DSRM's identity was resolved in Phase 2.1-R (paper verified against a
    # supplied citation), moving it from UNAVAILABLE to INSPECTED -- but it
    # must still never be an approved Phase 2.1 input (attack category,
    # no public implementation).
    assert by_id["dsrm"]["phase2_status"] == "INSPECTED"
    assert by_id["dsrm"]["phase2_input_approved"] is False
    for e in m["resources"]:
        if e["phase2_status"] in ("UNAVAILABLE", "INSPECTED", "NOT_GENERATED"):
            assert e["phase2_input_approved"] is False, (
                f"{e['resource_id']}: status {e['phase2_status']} must never be approved"
            )


# 5. Raw source artifacts are not overwritten (checksums in the frozen
#    dataset_manifest.json still match the files on disk).
def test_raw_files_unchanged_since_dataset_manifest_was_generated():
    cfg = _cfg()
    dataset_manifest = read_json(cfg.metadata_dir / "dataset_manifest.json")
    repo_root = cfg.raw_dir.parent.parent
    checked = 0
    for ds in dataset_manifest["datasets"].values():
        for f in ds["files"]:
            path = repo_root / f["path"]
            assert path.exists(), f"raw file missing: {f['path']}"
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            assert actual == f["sha256"], f"raw file modified since manifest: {f['path']}"
            checked += 1
    assert checked > 0


# 6. Phase 1 provenance links exist for representative records.
def test_processed_memory_records_carry_provenance():
    cfg = _cfg()
    for ds_id in _CORE_MEMORY_DATASET_IDS:
        path = cfg.processed_dir / ds_id / "memory_records.jsonl"
        assert path.exists(), f"missing processed output for {ds_id}"
        with path.open("r", encoding="utf-8") as f:
            first_line = f.readline()
        record = json.loads(first_line)
        assert record.get("provenance"), f"{ds_id}: first record has no provenance"
        prov = record["provenance"]
        assert prov.get("source_dataset") == ds_id
        assert prov.get("source_file")
        assert prov.get("extraction_pipeline_version")


# 7. Quality classifications are preserved.
def test_quality_status_distributions_cover_known_vocabulary():
    cfg = _cfg()
    known = {"valid", "repaired", "valid_flagged", "irrecoverably_invalid"}
    for ds_id in _CORE_MEMORY_DATASET_IDS:
        stats = read_json(cfg.reports_dir / f"{ds_id}_statistics.json")
        dist = stats.get("quality_status_distribution", {})
        assert dist, f"{ds_id}: no quality_status_distribution recorded"
        assert set(dist.keys()).issubset(known), f"{ds_id}: unknown quality status in {dist}"


# 8. Quarantined records remain traceable.
def test_quarantine_log_entries_are_traceable_to_source():
    cfg = _cfg()
    log_path = cfg.logs_dir / "quarantine_log.jsonl"
    assert log_path.exists()
    checked = 0
    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            assert entry.get("dataset")
            assert entry.get("source_file")
            assert entry.get("exclusion_reason")
            assert "raw_content" in entry, "quarantined record must preserve original content"
            checked += 1
    assert checked > 0


# 9. Manifest schema is valid (top-level + per-entry shape).
def test_manifest_top_level_schema():
    m = _manifest()
    assert m["phase2_manifest_version"]
    assert m["total_resources"] == len(m["resources"])
    assert sum(m["resources_by_phase2_status"].values()) == m["total_resources"]
    assert m["phase1_overall_status"] == "PASS WITH ISSUES"


# 10. Dataset/version identifiers are present where available.
def test_core_datasets_have_snapshot_and_checksum_identifiers():
    m = _manifest()
    by_id = {e["resource_id"]: e for e in m["resources"]}
    for ds_id in _CORE_MEMORY_DATASET_IDS:
        e = by_id[ds_id]
        assert e["snapshot_identifier"], f"{ds_id}: missing snapshot_identifier"
        assert e["checksums"], f"{ds_id}: missing per-file checksums"
        for f in e["checksums"]:
            assert f.get("sha256") and f.get("size_bytes") is not None


# 11. Phase 2 input selection is deterministic.
def test_manifest_generation_is_deterministic_given_fixed_timestamp():
    m1 = build_phase2_manifest(_cfg(), generated_at="2026-08-16T00:00:00Z")
    m2 = build_phase2_manifest(_cfg(), generated_at="2026-08-16T00:00:00Z")
    assert m1 == m2


# 12. No attack/poisoned data is included in the clean Phase 2.1 foundation.
def test_no_attack_or_sleeper_resource_is_approved():
    m = _manifest()
    for e in m["resources"]:
        if e["resource_category"] in ("attack", "sleeper"):
            assert e["phase2_input_approved"] is False, (
                f"{e['resource_id']}: {e['resource_category']} resource must "
                "never be an approved Phase 2.1 input"
            )
    assert set(m["phase2_input_approved_resource_ids"]) == _CORE_MEMORY_DATASET_IDS
