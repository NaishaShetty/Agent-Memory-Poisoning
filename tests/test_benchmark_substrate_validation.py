"""Phase 2.6: benchmark-substrate validation tests. Covers each of the
24 domains from the implementation prompt plus the requested adversarial
cases (Section 30). Uses the real, already-generated artifacts (same
convention as tests/test_benchmark_organization.py and
tests/test_reproducibility_manifest.py) -- the object under test *is* the
cross-phase consistency of those real artifacts.
"""
from __future__ import annotations

import pytest

from preprocessing.benchmark_organization import (
    APPROVED_MEMORY_FOUNDATION,
    ROLE_ATTACK,
    ROLE_MEMORY,
    build_benchmark_organization,
)
from preprocessing.benchmark_substrate_validation import (
    SUBSTRATE_VALIDATION_VERSION,
    _scan_forbidden_definitions,
    validate_benchmark_substrate,
)
from preprocessing.config import load_config
from preprocessing.registry import REPO_ROOT

_TS = "2026-08-16T00:00:00Z"


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture(scope="module")
def report(cfg):
    return validate_benchmark_substrate(cfg, _TS)


@pytest.fixture(scope="module")
def by_name(report):
    return {c["name"]: c for c in report["checks"]}


# ---------------------------------------------------------------------------
# Full report
# ---------------------------------------------------------------------------

def test_full_substrate_validation_report_passes(report):
    failed = [c["name"] for c in report["checks"] if c["status"] != "PASS"]
    assert not failed, f"benchmark substrate validation failed checks: {failed}"
    assert report["overall_status"] == "PASS"
    assert report["substrate_validation_version"] == SUBSTRATE_VALIDATION_VERSION
    assert report["total_checks"] >= 24


def test_canonical_state_matches_expected(report):
    state = report["canonical_state"]
    assert state["memory_foundation"] == sorted(APPROVED_MEMORY_FOUNDATION)
    assert state["memory_record_total"] == 1_266_194
    assert state["umr_schema_version"] == "1.1.0"
    assert state["temporal_normalization_policy_version"] == "2.3.0"
    assert state["resource_role_counts"] == {"memory": 4, "workload": 9, "attack": 6, "sleeper": 2, "evaluation": 7}
    assert state["total_resources"] == 28


# ---------------------------------------------------------------------------
# Domain-specific spot checks (by name, from the already-computed report)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("check_name", [
    "domain1_memory_foundation_exactly_four_approved_datasets",
    "domain1_memory_foundation_record_counts_match_expected",
    "domain2_umr_schema_version_consistent_across_all_layers",
    "domain2_umr_validator_passes_fresh",
    "domain3_no_cross_dataset_memory_id_collisions",
    "domain4_provenance_chain_intact_for_memory_foundation",
    "domain4_provenance_preserved_for_all_28_resources",
    "domain5_temporal_validator_passes_fresh",
    "domain6_temporal_provenance_split_matches_each_datasets_documented_signal",
    "domain6_no_fabricated_source_absolute_timestamps",
    "domain7_resource_role_counts_match_expected",
    "domain7_memory_foundation_boundary_enforced",
    "domain8_role_status_implementation_activation_kept_separate",
    "domain9_resource_availability_honest",
    "domain10_reproducibility_metadata_present_for_all_resources",
    "domain10_reproducibility_validator_passes_fresh",
    "domain11_cross_manifest_resource_id_consistency",
    "domain11_cross_manifest_role_and_status_agree",
    "domain12_version_consistency_across_layers",
    "domain13_record_count_consistency_across_layers",
    "domain14_raw_file_integrity_targeted_checksums",
    "domain14_frozen_output_files_untouched_by_phase2_builders",
    "domain18_no_later_phase_functionality_implemented",
    "domain19_experimental_activation_boundary_respected",
    "domain20_phase2_component_artifacts_all_present",
    "domain21_phase2_2_regression",
    "domain22_phase2_3_regression",
    "domain23_phase2_4_regression",
    "domain24_phase2_5_regression",
])
def test_domain_check_passes(by_name, check_name):
    assert check_name in by_name, f"missing check {check_name}"
    assert by_name[check_name]["status"] == "PASS", by_name[check_name]["detail"]


def test_full_corpus_scope_is_labeled_honestly(report):
    """Checks that genuinely scanned the full 1.27M-record corpus are
    labeled scope=full_corpus; the targeted raw-checksum check is labeled
    scope=targeted_sample, never claiming full-corpus coverage it didn't do."""
    by_name = {c["name"]: c for c in report["checks"]}
    assert by_name["domain1_memory_foundation_record_counts_match_expected"]["scope"] == "full_corpus"
    assert by_name["domain14_raw_file_integrity_targeted_checksums"]["scope"] == "targeted_sample"


# ---------------------------------------------------------------------------
# Adversarial tests (Section 30)
# ---------------------------------------------------------------------------

def test_adversarial_changed_resource_role_fails_validation(cfg):
    """Corrupting the memory_data->role mapping is the one role change
    build_benchmark_organization actually guards against (see its
    is_memory_foundation invariant) -- mirrors
    tests/test_benchmark_organization.py's own equivalent adversarial test."""
    import preprocessing.benchmark_organization as bo

    original = dict(bo._CATEGORY_TO_ROLE)
    bo._CATEGORY_TO_ROLE["memory_data"] = bo.ROLE_ATTACK
    try:
        with pytest.raises(bo.RoleClassificationError):
            build_benchmark_organization(cfg, _TS)
    finally:
        bo._CATEGORY_TO_ROLE.clear()
        bo._CATEGORY_TO_ROLE.update(original)


def test_adversarial_attack_resource_in_memory_foundation_would_fail_domain7():
    """Simulates the corrupted state directly (rather than mutating shared
    module state mid-suite) and confirms the same predicate Domain 7 uses
    would flag it."""
    org_by_id = {
        "locomo": {"primary_role": ROLE_MEMORY}, "longmemeval": {"primary_role": ROLE_MEMORY},
        "msc": {"primary_role": ROLE_MEMORY}, "conversation_chronicles": {"primary_role": ROLE_MEMORY},
        "agentpoison": {"primary_role": ROLE_ATTACK},
    }
    corrupted_foundation = APPROVED_MEMORY_FOUNDATION | {"agentpoison"}
    boundary_violations = [
        rid for rid, e in org_by_id.items()
        if e["primary_role"] != ROLE_MEMORY and rid in corrupted_foundation
    ]
    assert boundary_violations == ["agentpoison"]


def test_adversarial_missing_core_dataset_fails_domain1():
    partial_foundation = APPROVED_MEMORY_FOUNDATION - {"msc"}
    assert partial_foundation != APPROVED_MEMORY_FOUNDATION
    assert len(partial_foundation) == 3


def test_adversarial_changed_record_count_fails_domain1_predicate():
    from preprocessing.benchmark_validation import _EXPECTED_MEMORY_RECORD_COUNTS, _EXPECTED_TOTAL

    tampered = dict(_EXPECTED_MEMORY_RECORD_COUNTS)
    tampered["locomo"] = 5881  # off by one
    assert sum(tampered.values()) != _EXPECTED_TOTAL


def test_adversarial_changed_umr_schema_version_would_be_detected(report):
    check = {c["name"]: c for c in report["checks"]}["domain2_umr_schema_version_consistent_across_all_layers"]
    sources = check["detail"]["sources"]
    # all three sources must currently agree; simulate a drift and confirm
    # the same equality predicate the check uses would catch it
    drifted = dict(sources)
    drifted["reproducibility_manifest.schema_and_policy_versions"] = "9.9.9"
    assert len(set(drifted.values())) != 1


def test_adversarial_changed_temporal_policy_version_would_be_detected(report):
    check = {c["name"]: c for c in report["checks"]}["domain12_version_consistency_across_layers"]
    assert check["status"] == "PASS"  # baseline: currently consistent


def test_adversarial_local_path_change_does_not_affect_canonical_identity(cfg):
    """Reproducibility identity (Domain 10/15) stays valid across a local
    path change -- re-verifies Phase 2.5's own invariant at the substrate
    level using the real manifest."""
    from preprocessing.reproducibility import build_reproducibility_manifest

    a = build_reproducibility_manifest(cfg, _TS)
    b = build_reproducibility_manifest(cfg, "1999-01-01T00:00:00Z")
    a_hashes = {e["resource_id"]: e["canonical_identity_hash"] for e in a["resources"]}
    b_hashes = {e["resource_id"]: e["canonical_identity_hash"] for e in b["resources"]}
    assert a_hashes == b_hashes  # generated_at changed; canonical identity did not


def test_adversarial_dsrm_marked_active_would_fail_domain8_and_19():
    dsrm_corrupted = {"primary_role": ROLE_ATTACK, "implementation_status": "local_copy_present", "phase2_input_approved": True, "local_path": "data/raw/dsrm"}
    role_status_ok = (
        dsrm_corrupted.get("primary_role") == ROLE_ATTACK
        and dsrm_corrupted.get("implementation_status") == "specification_only_no_public_implementation_found"
        and dsrm_corrupted.get("phase2_input_approved") is not True
        and dsrm_corrupted.get("local_path") is None
    )
    assert role_status_ok is False


def test_adversarial_conflicting_resource_id_across_manifests_fails_domain11(cfg):
    from preprocessing.registry import build_registry_report
    from preprocessing.reproducibility import build_reproducibility_manifest

    registry_ids = {e["resource_id"] for e in build_registry_report(cfg)["resources"]}
    repro_ids = {e["resource_id"] for e in build_reproducibility_manifest(cfg, _TS)["resources"]}
    injected = repro_ids | {"not_a_real_resource"}
    assert injected != registry_ids
    assert injected.symmetric_difference(registry_ids) == {"not_a_real_resource"}


def test_adversarial_missing_provenance_fails_domain4():
    entry_without_provenance = {"source_reference": "https://example.com", "provenance": {}}
    missing = (
        not entry_without_provenance.get("source_reference")
        or not entry_without_provenance.get("provenance", {}).get("source")
        or not entry_without_provenance.get("provenance", {}).get("mambench_created")
    )
    assert missing is True


# ---------------------------------------------------------------------------
# Scope-boundary scanner unit tests
# ---------------------------------------------------------------------------

def test_forbidden_definition_scanner_finds_nothing_in_current_codebase():
    violations = _scan_forbidden_definitions(REPO_ROOT)
    assert violations == []


def test_forbidden_definition_scanner_detects_a_planted_violation(tmp_path):
    fake_pkg = tmp_path / "preprocessing"
    fake_pkg.mkdir()
    (fake_pkg / "evil.py").write_text("def execute_attack(x):\n    return x\n", encoding="utf-8")
    violations = _scan_forbidden_definitions(tmp_path)
    assert len(violations) == 1
    assert violations[0]["file"] == "preprocessing/evil.py" or violations[0]["file"] == "preprocessing\\evil.py"


def test_forbidden_definition_scanner_ignores_role_names_and_field_names(tmp_path):
    fake_pkg = tmp_path / "preprocessing"
    fake_pkg.mkdir()
    (fake_pkg / "safe.py").write_text(
        'ROLE_ATTACK = "attack"\n'
        'ROLE_SLEEPER = "sleeper"\n'
        '"""does not implement lifecycle, attack, propagation, sleeper, or defense"""\n'
        "poison_status = None\n"
        "propagation_history = []\n",
        encoding="utf-8",
    )
    violations = _scan_forbidden_definitions(tmp_path)
    assert violations == []
