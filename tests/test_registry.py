from __future__ import annotations

from preprocessing.config import load_config
from preprocessing.registry import build_registry, build_registry_report

_REQUIRED_FIELDS = {
    "resource_id", "name", "category", "research_purpose", "phase1_action",
    "phase1_status", "acquisition_status", "preprocessing_status",
    "version_or_revision", "access_and_license", "local_path",
    "source_reference", "reproducibility", "limitations", "intended_later_phase",
}

_VALID_STATUSES = {
    "PROCESSED", "PREPARED", "INSPECTED", "OPTIONAL_PENDING_ACCESS",
    "INACCESSIBLE", "NOT_SUITABLE", "DEFERRED_WITH_JUSTIFICATION",
}

_VALID_CATEGORIES = {"memory_data", "task_workload", "sleeper", "attack", "security_benchmark"}


def test_registry_covers_all_planned_resources():
    cfg = load_config()
    entries = build_registry(cfg)
    ids = [e.resource_id for e in entries]
    assert len(ids) == len(set(ids)), "duplicate resource_id in registry"
    # at minimum, all 4 memory datasets + the named attack/security resources
    expected_present = {
        "locomo", "longmemeval", "msc", "conversation_chronicles",
        "agentpoison", "minja", "dsrm", "memorygraft", "farma", "mpbench",
        "memsecbench", "memsad", "memaudit", "a_memguard", "asb", "agentdojo", "injecagent",
        "hidden_in_memory", "sleeper_dataset_generator",
        "api_bank", "toolbench", "strategyqa", "webshop", "swebench_verified",
        "tau_bench", "tau2_bench", "ehragent", "mimic_eicu",
    }
    assert expected_present.issubset(set(ids))


def test_registry_entries_have_all_required_fields():
    cfg = load_config()
    for e in build_registry(cfg):
        d = e.to_dict()
        assert _REQUIRED_FIELDS.issubset(d.keys()), f"{e.resource_id} missing fields"


def test_registry_statuses_and_categories_are_from_known_vocabulary():
    cfg = load_config()
    for e in build_registry(cfg):
        assert e.phase1_status in _VALID_STATUSES, f"{e.resource_id}: unknown status {e.phase1_status}"
        assert e.category in _VALID_CATEGORIES, f"{e.resource_id}: unknown category {e.category}"


def test_no_resource_claims_implemented_without_local_evidence():
    """Section 3: never mark something PROCESSED unless it actually has
    local data, and never claim CODE AVAILABLE == cloned/implemented."""
    cfg = load_config()
    for e in build_registry(cfg):
        if e.phase1_status == "PROCESSED":
            assert e.local_path is not None, f"{e.resource_id} claims PROCESSED but has no local_path"
        if e.category == "attack":
            # attack resources must never claim a local copy was made in Phase 1
            assert e.local_path is None, f"{e.resource_id}: attack resource must not have a local copy in Phase 1"


def test_dsrm_identity_resolved_but_implementation_not_overclaimed():
    """Phase 2.1-R resolved DSRM's identity against a supplied paper
    (Jing et al. 2026, Engineering Applications of AI). Its phase1_status
    moved from INACCESSIBLE to INSPECTED -- paper verified, but no public
    implementation exists, and the entry must not claim otherwise."""
    cfg = load_config()
    by_id = {e.resource_id: e for e in build_registry(cfg)}
    dsrm = by_id["dsrm"]
    assert dsrm.phase1_status == "INSPECTED"
    assert dsrm.local_path is None, "no implementation was cloned or found"
    assert "113968" in dsrm.version_or_revision
    assert "PAPER VERIFIED" in dsrm.acquisition_status
    assert "IMPLEMENTATION_AVAILABILITY" in dsrm.acquisition_status


def test_optional_resource_not_marked_mandatory():
    cfg = load_config()
    by_id = {e.resource_id: e for e in build_registry(cfg)}
    assert by_id["mimic_eicu"].phase1_status == "OPTIONAL_PENDING_ACCESS"
    assert by_id["mimic_eicu"].local_path is None


def test_registry_report_counts_are_internally_consistent():
    cfg = load_config()
    report = build_registry_report(cfg)
    assert report["total_resources"] == len(report["resources"])
    assert sum(report["resources_by_category"].values()) == report["total_resources"]
    assert sum(report["resources_by_phase1_status"].values()) == report["total_resources"]
