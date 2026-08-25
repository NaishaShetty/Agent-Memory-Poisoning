"""Phase 2.4: benchmark-level resource organization tests, numbered per
the Phase 2.4 brief's Tests 1-12. Uses the real, already-generated
registry/manifest/UMR artifacts (all cheap to read; Test 11/12 re-run the
real Phase 2.2/2.3 validators, same as
preprocessing/benchmark_validation.py does) rather than synthetic
fixtures, since the object under test *is* the join across real
artifacts.
"""
from __future__ import annotations

import pytest

from preprocessing.benchmark_organization import (
    APPROVED_MEMORY_FOUNDATION,
    ROLE_ATTACK,
    ROLE_EVALUATION,
    ROLE_MEMORY,
    ROLE_SLEEPER,
    ROLE_WORKLOAD,
    VALID_ROLES,
    RoleClassificationError,
    build_benchmark_organization,
    classify_role,
)
from preprocessing.benchmark_validation import validate_benchmark_organization
from preprocessing.config import load_config
from preprocessing.registry import build_registry_report

_TS = "2026-08-16T00:00:00Z"


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture(scope="module")
def org(cfg):
    return build_benchmark_organization(cfg, _TS)


@pytest.fixture(scope="module")
def by_id(org):
    return {e["resource_id"]: e for e in org["resources"]}


# ---------------------------------------------------------------------------
# Test 1 -- all known resources are classified
# ---------------------------------------------------------------------------

def test_all_registry_resources_have_a_primary_role(cfg, org, by_id):
    registry_ids = {e["resource_id"] for e in build_registry_report(cfg)["resources"]}
    assert registry_ids == set(by_id)
    for rid in registry_ids:
        assert by_id[rid]["primary_role"], f"{rid} has no primary_role"


# ---------------------------------------------------------------------------
# Test 2 -- no unknown role
# ---------------------------------------------------------------------------

def test_every_role_is_from_the_approved_vocabulary(by_id):
    for rid, e in by_id.items():
        assert e["primary_role"] in VALID_ROLES, f"{rid}: unknown role {e['primary_role']!r}"


def test_classify_role_rejects_unknown_category():
    with pytest.raises(RoleClassificationError):
        classify_role("not_a_real_category")


def test_classify_role_is_total_over_the_five_known_categories():
    assert classify_role("memory_data") == ROLE_MEMORY
    assert classify_role("task_workload") == ROLE_WORKLOAD
    assert classify_role("attack") == ROLE_ATTACK
    assert classify_role("sleeper") == ROLE_SLEEPER
    assert classify_role("security_benchmark") == ROLE_EVALUATION


# ---------------------------------------------------------------------------
# Test 3 -- memory foundation boundary
# ---------------------------------------------------------------------------

def test_memory_foundation_is_exactly_the_four_approved_datasets(by_id):
    memory_ids = {rid for rid, e in by_id.items() if e["primary_role"] == ROLE_MEMORY}
    assert memory_ids == {"locomo", "longmemeval", "msc", "conversation_chronicles"}
    assert memory_ids == APPROVED_MEMORY_FOUNDATION


def test_build_raises_if_a_memory_foundation_id_is_misclassified(cfg, monkeypatch):
    """Synthetically corrupt the role-mapping table to prove the invariant
    is actually enforced, not just true by coincidence of current data."""
    import preprocessing.benchmark_organization as bo

    monkeypatch.setitem(bo._CATEGORY_TO_ROLE, "memory_data", ROLE_ATTACK)
    with pytest.raises(RoleClassificationError):
        bo.build_benchmark_organization(cfg, _TS)


# ---------------------------------------------------------------------------
# Test 4 / 5 / 6 -- no attack/sleeper/workload/evaluation resource in the
# clean memory foundation
# ---------------------------------------------------------------------------

def test_no_non_memory_role_resource_is_in_the_memory_foundation(by_id):
    for role in (ROLE_ATTACK, ROLE_SLEEPER, ROLE_WORKLOAD, ROLE_EVALUATION):
        ids_with_role = {rid for rid, e in by_id.items() if e["primary_role"] == role}
        assert not (ids_with_role & APPROVED_MEMORY_FOUNDATION), f"{role} resource(s) leaked into memory foundation: {ids_with_role & APPROVED_MEMORY_FOUNDATION}"


def test_known_attack_and_sleeper_resources_correctly_classified(by_id):
    for rid in ("agentpoison", "minja", "dsrm", "memorygraft", "farma", "mpbench"):
        assert by_id[rid]["primary_role"] == ROLE_ATTACK
    for rid in ("hidden_in_memory", "sleeper_dataset_generator"):
        assert by_id[rid]["primary_role"] == ROLE_SLEEPER


# ---------------------------------------------------------------------------
# Test 7 -- provenance preservation
# ---------------------------------------------------------------------------

def test_every_resource_retains_source_provenance(by_id):
    for rid, e in by_id.items():
        assert e["source_reference"], f"{rid} lost its source_reference"
        assert e["provenance"]["source"], f"{rid} lost provenance.source"
        assert e["provenance"]["mambench_created"], f"{rid} lost provenance.mambench_created"
        assert "Phase 2.4" in e["provenance"]["mambench_created"]


def test_organization_manifest_never_claims_to_be_the_original_source(by_id):
    """provenance.source always says 'external', never claims the
    organization manifest itself IS the source."""
    for e in by_id.values():
        assert e["provenance"]["source"].startswith("external")


# ---------------------------------------------------------------------------
# Test 8 -- availability honesty
# ---------------------------------------------------------------------------

def test_role_does_not_imply_availability(by_id):
    """Attack-role resources exist (identity documented) but most have no
    local implementation -- role assignment must not silently upgrade
    their availability."""
    unimplemented_attacks = [
        rid for rid, e in by_id.items()
        if e["primary_role"] == ROLE_ATTACK and e["implementation_status"] != "local_copy_present"
    ]
    assert unimplemented_attacks, "expected at least one attack resource without a local implementation"
    for rid in unimplemented_attacks:
        assert by_id[rid]["local_path"] is None
        assert by_id[rid]["phase2_input_approved"] is not True


def test_dsrm_role_is_attack_and_status_is_reconstruction_dependent(by_id):
    """Section 4/6/19: DSRM must be identifiable as an attack resource
    whose implementation is unresolved/reconstruction-dependent -- role
    and status are two different fields, neither implying the other."""
    dsrm = by_id["dsrm"]
    assert dsrm["primary_role"] == ROLE_ATTACK
    assert dsrm["implementation_status"] == "specification_only_no_public_implementation_found"
    assert dsrm["local_path"] is None
    assert dsrm["phase2_input_approved"] is not True


def test_only_memory_foundation_is_phase2_input_approved(by_id):
    approved = {rid for rid, e in by_id.items() if e["phase2_input_approved"] is True}
    assert approved == APPROVED_MEMORY_FOUNDATION


def test_optional_pending_access_resource_not_marked_available(by_id):
    mimic = by_id["mimic_eicu"]
    assert mimic["local_path"] is None
    assert mimic["phase2_input_approved"] is not True


# ---------------------------------------------------------------------------
# Test 9 -- deterministic organization
# ---------------------------------------------------------------------------

def test_organization_is_deterministic(cfg):
    a = build_benchmark_organization(cfg, _TS)
    b = build_benchmark_organization(cfg, _TS)
    assert a == b


def test_resources_by_role_lists_are_sorted(org):
    for role, ids in org["resources_by_role"].items():
        assert ids == sorted(ids), f"{role} resource id list is not sorted"


def test_resources_list_is_sorted_by_resource_id(org):
    ids = [e["resource_id"] for e in org["resources"]]
    assert ids == sorted(ids)


# ---------------------------------------------------------------------------
# Test 10 -- no data mutation
# ---------------------------------------------------------------------------

def test_organizing_does_not_touch_frozen_phase1_output(cfg):
    """build_benchmark_organization only reads; confirm no processed
    Phase 1/2.2/2.3 file's mtime changes across a build call."""
    import os

    watched = [
        cfg.processed_dir / "locomo" / "memory_records.jsonl",
        cfg.processed_dir / "unified_memory" / "locomo" / "memory_records.jsonl",
    ]
    before = {p: (p.stat().st_mtime_ns, p.stat().st_size) for p in watched if p.exists()}
    build_benchmark_organization(cfg, _TS)
    after = {p: (p.stat().st_mtime_ns, p.stat().st_size) for p in watched if p.exists()}
    assert before == after


# ---------------------------------------------------------------------------
# Test 11 -- existing Phase 2.2 / 2.3 regression
# ---------------------------------------------------------------------------

def test_phase2_2_and_phase2_3_validators_still_pass(cfg):
    from preprocessing.temporal_validation import validate_temporal
    from preprocessing.unified_validation import validate_cross_dataset

    umr = validate_cross_dataset(cfg)
    temporal = validate_temporal(cfg)
    assert umr["overall_status"] == "PASS"
    assert temporal["overall_status"] == "PASS"


# ---------------------------------------------------------------------------
# Test 12 -- UMR integrity
# ---------------------------------------------------------------------------

def test_umr_integrity_preserved(org):
    integrity = org["umr_integrity"]
    assert integrity["umr_schema_version"] == "1.1.0"
    assert integrity["temporal_normalization_policy_version"] == "2.3.0"
    assert integrity["umr_total_records"] == 1_266_194
    assert integrity["umr_per_dataset_record_counts"] == {
        "locomo": 5882,
        "longmemeval": 210365,
        "msc": 227185,
        "conversation_chronicles": 822762,
    }
    assert integrity["umr_validation_overall_status"] == "PASS"
    assert integrity["temporal_validation_overall_status"] == "PASS"


def test_full_benchmark_validation_report_passes(cfg):
    report = validate_benchmark_organization(cfg, _TS)
    failed = [c["name"] for c in report["checks"] if c["status"] != "PASS"]
    assert not failed, f"benchmark organization validation failed checks: {failed}"
    assert report["overall_status"] == "PASS"
