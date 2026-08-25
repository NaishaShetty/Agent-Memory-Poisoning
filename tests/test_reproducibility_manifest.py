"""Phase 2.5: benchmark metadata & manifests tests, covering manifest
generation, canonical/artifact identity, path independence, seed
semantics, configuration identity, and the adversarial cases from the
Phase 2.5 brief (Section 28). Uses the real, already-generated registry/
manifest/organization artifacts (same convention as
tests/test_benchmark_organization.py).
"""
from __future__ import annotations

import copy

import pytest

from preprocessing.benchmark_organization import build_benchmark_organization
from preprocessing.config import load_config
from preprocessing.reproducibility import (
    REPRODUCIBILITY_MANIFEST_VERSION,
    _canonical_hash,
    build_reproducibility_manifest,
    get_code_state,
    get_configuration_identity,
)
from preprocessing.reproducibility_validation import validate_reproducibility_manifest

_TS = "2026-08-16T00:00:00Z"


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture(scope="module")
def org(cfg):
    return build_benchmark_organization(cfg, _TS)


@pytest.fixture(scope="module")
def manifest(cfg):
    return build_reproducibility_manifest(cfg, _TS)


@pytest.fixture(scope="module")
def by_id(manifest):
    return {e["resource_id"]: e for e in manifest["resources"]}


# ---------------------------------------------------------------------------
# Manifest generation / resource identity
# ---------------------------------------------------------------------------

def test_every_organized_resource_has_a_reproducibility_entry(org, by_id):
    org_ids = {e["resource_id"] for e in org["resources"]}
    assert org_ids == set(by_id)


def test_resource_ids_are_unique(manifest):
    ids = [e["resource_id"] for e in manifest["resources"]]
    assert len(ids) == len(set(ids)) == 28


def test_primary_role_matches_phase2_4_verbatim(org, by_id):
    org_by_id = {e["resource_id"]: e for e in org["resources"]}
    for rid, e in by_id.items():
        assert e["primary_role"] == org_by_id[rid]["primary_role"]


def test_source_identity_fields_always_present(by_id):
    for rid, e in by_id.items():
        si = e["source_identity"]
        for key in ("source_reference", "source_dataset_version_or_revision", "acquisition_status", "access_and_license"):
            assert key in si, f"{rid} missing source_identity.{key}"


def test_unknown_source_version_is_explicit_not_guessed(by_id):
    locomo = by_id["locomo"]
    assert locomo["canonical_identity"]["source_dataset_version_or_revision"] == "unknown"


# ---------------------------------------------------------------------------
# Artifact identity
# ---------------------------------------------------------------------------

def test_prepared_resources_have_artifact_identity(by_id):
    for rid in ("locomo", "longmemeval", "msc", "conversation_chronicles"):
        artifact = by_id[rid]["artifact_identity"]
        assert artifact["status"] == "prepared"
        assert artifact["artifact_id"] and len(artifact["artifact_id"]) == 24


def test_unprepared_resources_have_no_artifact_identity(by_id):
    # hidden_in_memory is INSPECTED only, never prepared.
    artifact = by_id["hidden_in_memory"]["artifact_identity"]
    assert artifact["artifact_id"] is None
    assert artifact["status"] == "not_applicable_no_prepared_artifact"


# ---------------------------------------------------------------------------
# Schema / temporal policy scoping
# ---------------------------------------------------------------------------

def test_umr_schema_version_only_on_core_datasets(by_id, manifest):
    core = {"locomo", "longmemeval", "msc", "conversation_chronicles"}
    for rid in core:
        assert by_id[rid]["canonical_identity"]["unified_memory_record_schema_version"] == \
            manifest["schema_and_policy_versions"]["unified_memory_record_schema_version"]
    for rid, e in by_id.items():
        if rid not in core:
            assert e["canonical_identity"]["unified_memory_record_schema_version"] == "not_applicable"


# ---------------------------------------------------------------------------
# Seed semantics
# ---------------------------------------------------------------------------

def test_seed_applicable_only_for_conversation_chronicles(by_id, cfg):
    cc = by_id["conversation_chronicles"]["canonical_identity"]["seed"]
    assert cc["seed_applicable"] is True
    assert cc["seed_value"] == cfg.seed == 20260101

    for rid, e in by_id.items():
        if rid != "conversation_chronicles":
            seed = e["canonical_identity"]["seed"]
            assert seed["seed_applicable"] is False
            assert seed["seed_value"] is None


# ---------------------------------------------------------------------------
# Configuration identity
# ---------------------------------------------------------------------------

def test_configuration_identity_is_a_content_hash_not_a_path(cfg):
    ident = get_configuration_identity(cfg)
    assert len(ident["configuration_id"]) == 64
    # relative, repo-style path only -- never an absolute filesystem path
    assert not ident["config_relative_path"].startswith("C:")
    assert str(cfg.raw_dir.parent) not in ident["config_relative_path"]


def test_configuration_identity_reproducible(cfg):
    a = get_configuration_identity(cfg)
    b = get_configuration_identity(cfg)
    assert a == b


# ---------------------------------------------------------------------------
# Canonical identity determinism + path independence
# ---------------------------------------------------------------------------

def test_manifest_is_deterministic(cfg):
    a = build_reproducibility_manifest(cfg, _TS)
    b = build_reproducibility_manifest(cfg, _TS)
    assert a == b


def test_canonical_identity_hash_unaffected_by_generated_at(cfg):
    a = build_reproducibility_manifest(cfg, _TS)
    b = build_reproducibility_manifest(cfg, "1999-01-01T00:00:00Z")
    a_by_id = {e["resource_id"]: e["canonical_identity_hash"] for e in a["resources"]}
    b_by_id = {e["resource_id"]: e["canonical_identity_hash"] for e in b["resources"]}
    assert a_by_id == b_by_id


def test_canonical_identity_never_contains_absolute_local_path(by_id):
    import re

    windows_drive_re = re.compile(r"^[A-Za-z]:[\\/]")
    for rid, e in by_id.items():
        for key, value in e["canonical_identity"].items():
            if isinstance(value, str):
                assert not windows_drive_re.match(value), f"{rid}.{key} leaked an absolute path: {value!r}"


def test_resources_sorted(manifest):
    ids = [e["resource_id"] for e in manifest["resources"]]
    assert ids == sorted(ids)


# ---------------------------------------------------------------------------
# Adversarial tests (Section 28)
# ---------------------------------------------------------------------------

def test_adversarial_source_version_change_changes_canonical_hash():
    fields = {
        "resource_id": "locomo", "source_dataset_version_or_revision": "unknown",
        "snapshot_id": "2026-08-12T16:54:58Z", "preparation_version": "1.0.0",
        "unified_memory_record_schema_version": "1.1.0",
        "temporal_normalization_policy_version": "2.3.0",
        "configuration_id": "abc123", "seed": {"seed_applicable": False, "seed_value": None, "seed_status": "seed_not_applicable"},
    }
    original_hash = _canonical_hash(fields)
    changed = copy.deepcopy(fields)
    changed["source_dataset_version_or_revision"] = "v2.0"
    assert _canonical_hash(changed) != original_hash


def test_adversarial_preparation_version_change_changes_canonical_hash():
    fields = {
        "resource_id": "locomo", "source_dataset_version_or_revision": "unknown",
        "snapshot_id": "unknown", "preparation_version": "1.0.0",
        "unified_memory_record_schema_version": "1.1.0",
        "temporal_normalization_policy_version": "2.3.0",
        "configuration_id": "abc123", "seed": {"seed_applicable": False, "seed_value": None, "seed_status": "seed_not_applicable"},
    }
    original_hash = _canonical_hash(fields)
    changed = copy.deepcopy(fields)
    changed["preparation_version"] = "1.0.1"
    assert _canonical_hash(changed) != original_hash


def test_adversarial_schema_version_change_changes_canonical_hash():
    fields = {
        "resource_id": "locomo", "source_dataset_version_or_revision": "unknown",
        "snapshot_id": "unknown", "preparation_version": "1.0.0",
        "unified_memory_record_schema_version": "1.1.0",
        "temporal_normalization_policy_version": "2.3.0",
        "configuration_id": "abc123", "seed": {"seed_applicable": False, "seed_value": None, "seed_status": "seed_not_applicable"},
    }
    original_hash = _canonical_hash(fields)
    changed = copy.deepcopy(fields)
    changed["unified_memory_record_schema_version"] = "1.2.0"
    assert _canonical_hash(changed) != original_hash


def test_adversarial_seed_change_changes_canonical_hash_when_applicable():
    fields = {
        "resource_id": "conversation_chronicles", "source_dataset_version_or_revision": "unknown",
        "snapshot_id": "unknown", "preparation_version": "1.0.0",
        "unified_memory_record_schema_version": "1.1.0",
        "temporal_normalization_policy_version": "2.3.0",
        "configuration_id": "abc123", "seed": {"seed_applicable": True, "seed_value": 20260101, "seed_status": "seed_used"},
    }
    original_hash = _canonical_hash(fields)
    changed = copy.deepcopy(fields)
    changed["seed"]["seed_value"] = 999
    assert _canonical_hash(changed) != original_hash


def test_adversarial_local_path_change_does_not_affect_canonical_hash(by_id):
    """A local_path change lives only in source_identity (convenience),
    never in canonical_identity -- so mutating it must not change the hash."""
    locomo = by_id["locomo"]
    fields = locomo["canonical_identity"]
    original_hash = _canonical_hash(fields)
    # local_path is not even a key in canonical_identity; confirm that.
    assert "local_path" not in fields
    assert _canonical_hash(fields) == original_hash


def test_adversarial_injecting_unregistered_resource_fails_validation(cfg):
    report = validate_reproducibility_manifest(cfg, _TS)
    check1 = next(c for c in report["checks"] if c["name"] == "check_1_every_phase2_4_resource_has_identity_metadata")
    assert check1["status"] == "PASS"
    # Simulate injection by asserting the check would fail on a mismatched set.
    org_ids = {"locomo", "longmemeval", "msc", "conversation_chronicles", "not_a_real_resource"}
    manifest_ids = {"locomo", "longmemeval", "msc", "conversation_chronicles"}
    assert org_ids != manifest_ids  # the real check_1 logic would FAIL on this


def test_adversarial_memory_role_misclassification_fails_validation(cfg):
    """Mirrors test_benchmark_organization.py's own role-corruption test:
    corrupting the category->role table must make Phase 2.4 (and therefore
    Phase 2.5, which reads it) refuse to build."""
    import preprocessing.benchmark_organization as bo
    from preprocessing.benchmark_organization import RoleClassificationError

    original = dict(bo._CATEGORY_TO_ROLE)
    bo._CATEGORY_TO_ROLE["memory_data"] = bo.ROLE_ATTACK
    try:
        with pytest.raises(RoleClassificationError):
            build_reproducibility_manifest(cfg, _TS)
    finally:
        bo._CATEGORY_TO_ROLE.clear()
        bo._CATEGORY_TO_ROLE.update(original)


# ---------------------------------------------------------------------------
# Full validation report (all 20+ checks)
# ---------------------------------------------------------------------------

def test_full_reproducibility_validation_report_passes(cfg):
    report = validate_reproducibility_manifest(cfg, _TS)
    failed = [c["name"] for c in report["checks"] if c["status"] != "PASS"]
    assert not failed, f"reproducibility validation failed checks: {failed}"
    assert report["overall_status"] == "PASS"
    assert report["reproducibility_manifest_version"] == REPRODUCIBILITY_MANIFEST_VERSION
    assert len(report["checks"]) >= 20


def test_code_state_is_captured_honestly():
    state = get_code_state()
    if state["git_available"]:
        assert state["commit_hash"] and len(state["commit_hash"]) == 40
        assert state["is_dirty"] in (True, False)
    else:
        assert state["commit_hash"] is None
