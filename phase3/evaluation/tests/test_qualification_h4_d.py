"""Phase 3.3-H.4-D (Foundation Qualification Gate) contract tests.

Covers every invariant in mission section 8 and every adversarial case in section 9 of
PHASE3_3_H4_D_MISSION.md. Exercised ONLY against mock adapters
(`foundations/mocks/mock_*.py`) -- no real qualification run against Mem0/A-MEM/Graphiti/
Letta is performed anywhere in this file (see the implementation report's explicit
real-vs-mock statement).
"""

from __future__ import annotations

import json

import pytest

from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase3.evaluation.foundations.memory_versioning import SupersessionLedger
from phase3.evaluation.foundations.mocks.mock_amem import MockAMemAdapter
from phase3.evaluation.foundations.mocks.mock_mem0 import ADAPTER_VERSION, MockMem0Adapter
from phase3.evaluation.foundations.run_config import RunConfigLedger, RunConfigRecord, compute_config_fingerprint
from phase3.evaluation.foundations_real.conformance_record import (
    ENVIRONMENT_LIMITATION,
    REAL_FOUNDATION_CONFORMANCE,
)
from phase3.evaluation.foundations_real.qualification_fixtures import (
    FILE_COUNT,
    FIXTURE_SET_VERSION,
    FixtureManifestError,
    compute_fixture_manifest,
    load_all_fixture_bundles,
    load_frozen_manifest,
    load_lineage_fixture,
    load_multi_file_fixture,
    verify_fixture_manifest,
)
from phase3.evaluation.foundations_real.qualification_harness import (
    ReplayError,
    compare_graphs,
    compute_expected_graph,
    reconstruct_graph,
    replay_fixture,
    run_qualification_fixture,
)
from phase3.evaluation.foundations_real.qualification_record import (
    VERDICT_NOT_QUALIFIED,
    VERDICT_QUALIFIED,
    CurrencyCheckResult,
    FoundationQualificationRecord,
    QualificationCollisionError,
    QualificationLedger,
    QualificationValidationError,
    check_qualification_currency,
    run_foundation_qualification,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fresh_ledgers(tmp_path, name="sys"):
    memory_ledger = CanonicalMemoryLedger(tmp_path / name / "memory")
    event_ledger = CanonicalEventLedger(tmp_path / name / "events", memory_ledger)
    supersession_ledger = SupersessionLedger(tmp_path / name / "supersessions")
    return memory_ledger, event_ledger, supersession_ledger


def _mock_foundation():
    foundation = MockMem0Adapter()
    foundation.initialize({})
    return foundation


def _config_record():
    fp = compute_config_fingerprint(
        embedding_model="text-embedding-3-large", embedding_model_revision="v1",
        retrieval_k=10, retrieval_mechanism="dense_knn", selection_mechanism="rerank_topk",
        adapter_revision="mem0-adapter@abc123",
    )
    return RunConfigRecord(
        config_fingerprint=fp, embedding_model="text-embedding-3-large", embedding_model_revision="v1",
        retrieval_k=10, retrieval_mechanism="dense_knn", selection_mechanism="rerank_topk",
        adapter_revision="mem0-adapter@abc123", created_at="2026-01-01T00:00:00Z",
    )


_ALL_BUNDLE_NAMES = [
    "conflicting_memory", "equivalent_memory", "derived_memory",
    "lineage/01_independent.json", "lineage/02_direct_derivation.json", "lineage/03_chain.json",
    "lineage/04_branching.json", "lineage/05_multi_parent.json", "lineage/06_equivalence_pair.json",
    "lineage/07_equivalence_component.json", "lineage/08_equivalence_and_lineage.json",
    "lineage/09_orphan_reference.json", "lineage/10_cycle.json",
    "lineage/11_equivalent_selected_evidence.json", "lineage/12_shared_origin_selected.json",
]


# ---------------------------------------------------------------------------
# Section 8, item 1: fixture_set_version stability / content-addressability
# ---------------------------------------------------------------------------


def test_fixture_manifest_is_stable_and_content_addressable():
    m1 = compute_fixture_manifest()
    m2 = compute_fixture_manifest()
    assert m1["fixture_set_hash"] == m2["fixture_set_hash"]
    assert m1["file_count"] == FILE_COUNT == 22


def test_frozen_manifest_matches_current_fixtures_on_disk():
    matches, detail = verify_fixture_manifest()
    assert matches, detail


def test_frozen_manifest_file_exists_and_is_versioned():
    manifest = load_frozen_manifest()
    assert manifest["fixture_set_version"] == FIXTURE_SET_VERSION == "qualification_fixtures_v1"
    assert manifest["file_count"] == 22


def test_verify_fixture_manifest_detects_modified_file(tmp_path):
    frozen = load_frozen_manifest()
    tampered_path = tmp_path / "tampered_manifest.json"
    tampered = dict(frozen)
    tampered["files"] = dict(frozen["files"])
    a_key = next(iter(tampered["files"]))
    tampered["files"][a_key] = "0" * 64
    tampered_path.write_text(json.dumps(tampered), encoding="utf-8")
    matches, detail = verify_fixture_manifest(tampered_path)
    assert not matches
    assert a_key in detail["modified_files"]


def test_verify_fixture_manifest_detects_a_file_frozen_no_longer_lists(tmp_path):
    """Frozen manifest missing a key that genuinely exists on disk -> reported as ADDED
    (a real file the frozen manifest never declared)."""
    frozen = load_frozen_manifest()
    tampered_path = tmp_path / "tampered_manifest.json"
    tampered = dict(frozen)
    tampered["files"] = dict(frozen["files"])
    missing_key = next(iter(tampered["files"]))
    del tampered["files"][missing_key]
    tampered["fixture_set_hash"] = "irrelevant-for-this-check"
    tampered_path.write_text(json.dumps(tampered), encoding="utf-8")
    matches, detail = verify_fixture_manifest(tampered_path)
    assert not matches
    assert missing_key in detail["added_files"]


def test_verify_fixture_manifest_detects_a_file_frozen_lists_that_no_longer_exists(tmp_path):
    """Frozen manifest lists a file that does not exist on disk -> reported as REMOVED."""
    frozen = load_frozen_manifest()
    tampered_path = tmp_path / "tampered_manifest.json"
    tampered = dict(frozen)
    tampered["files"] = dict(frozen["files"])
    tampered["files"]["lineage/99_never_existed.json"] = "0" * 64
    tampered["fixture_set_hash"] = "irrelevant-for-this-check"
    tampered_path.write_text(json.dumps(tampered), encoding="utf-8")
    matches, detail = verify_fixture_manifest(tampered_path)
    assert not matches
    assert "lineage/99_never_existed.json" in detail["removed_files"]


# ---------------------------------------------------------------------------
# Section 8, item 2: harness determinism
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bundle_name", _ALL_BUNDLE_NAMES)
def test_harness_is_deterministic_across_two_runs(tmp_path, bundle_name):
    bundle = load_all_fixture_bundles()[bundle_name]
    results = []
    for i in range(2):
        ml, el, sl = _fresh_ledgers(tmp_path, f"run{i}-{bundle_name.replace('/', '_')}")
        foundation = _mock_foundation()
        result = run_qualification_fixture(
            bundle, foundation=foundation, foundation_name="mem0",
            memory_ledger=ml, event_ledger=el, supersession_ledger=sl,
        )
        results.append(result)
    assert results[0].passed == results[1].passed
    assert results[0].mismatches == results[1].mismatches


# ---------------------------------------------------------------------------
# Every frozen fixture actually passes against a mock adapter (the harness's own
# correctness, independent of whether a real qualification run was ever performed).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bundle_name", _ALL_BUNDLE_NAMES)
def test_every_frozen_fixture_passes_against_mock_mem0(tmp_path, bundle_name):
    bundle = load_all_fixture_bundles()[bundle_name]
    ml, el, sl = _fresh_ledgers(tmp_path, bundle_name.replace("/", "_"))
    foundation = _mock_foundation()
    result = run_qualification_fixture(
        bundle, foundation=foundation, foundation_name="mem0",
        memory_ledger=ml, event_ledger=el, supersession_ledger=sl,
    )
    assert result.passed, result.mismatches
    assert result.all_writes_succeeded


@pytest.mark.parametrize("bundle_name", _ALL_BUNDLE_NAMES)
def test_every_frozen_fixture_passes_against_mock_amem(tmp_path, bundle_name):
    """Harness correctness is not tied to one specific mock -- a second, structurally
    different mock adapter (A-MEM) round-trips every fixture identically."""
    bundle = load_all_fixture_bundles()[bundle_name]
    ml, el, sl = _fresh_ledgers(tmp_path, "amem-" + bundle_name.replace("/", "_"))
    foundation = MockAMemAdapter()
    foundation.initialize({})
    result = run_qualification_fixture(
        bundle, foundation=foundation, foundation_name="amem",
        memory_ledger=ml, event_ledger=el, supersession_ledger=sl,
    )
    assert result.passed, result.mismatches


# ---------------------------------------------------------------------------
# Section 8, item 3: overall_verdict==QUALIFIED structurally requires
# REAL_FOUNDATION_CONFORMANCE and all fixtures passed
# ---------------------------------------------------------------------------


def _qualification_kwargs(**overrides):
    base = dict(
        foundation_id="MOCK",
        adapter_revision="rev-1",
        fixture_set_version=FIXTURE_SET_VERSION,
        config_fingerprint="CFG-abc",
        per_fixture_results={"conflicting_memory": {"passed": True}},
        conformance_tag=REAL_FOUNDATION_CONFORMANCE,
        overall_verdict=VERDICT_QUALIFIED,
        qualified_at="2026-01-01T00:00:00Z",
    )
    base.update(overrides)
    return base


def test_qualified_requires_real_foundation_conformance():
    with pytest.raises(QualificationValidationError, match="REAL_FOUNDATION_CONFORMANCE"):
        FoundationQualificationRecord(**_qualification_kwargs(conformance_tag=ENVIRONMENT_LIMITATION))


def test_qualified_requires_every_fixture_passed():
    with pytest.raises(QualificationValidationError, match="every fixture"):
        FoundationQualificationRecord(
            **_qualification_kwargs(per_fixture_results={"conflicting_memory": {"passed": False}})
        )


def test_qualified_allowed_when_both_conditions_hold():
    record = FoundationQualificationRecord(**_qualification_kwargs())
    assert record.overall_verdict == VERDICT_QUALIFIED


def test_not_qualified_never_rejected_regardless_of_fixture_outcomes():
    record = FoundationQualificationRecord(
        **_qualification_kwargs(conformance_tag=ENVIRONMENT_LIMITATION, overall_verdict=VERDICT_NOT_QUALIFIED)
    )
    assert record.overall_verdict == VERDICT_NOT_QUALIFIED


# ---------------------------------------------------------------------------
# Section 8, item 4: QualificationLedger is append-only
# ---------------------------------------------------------------------------


def test_qualification_ledger_has_no_update_or_delete_api(tmp_path):
    ledger = QualificationLedger(tmp_path / "qual")
    assert not hasattr(ledger, "update")
    assert not hasattr(ledger, "delete")
    assert not hasattr(ledger, "update_record")
    assert not hasattr(ledger, "delete_record")


# ---------------------------------------------------------------------------
# Section 8, item 5: config_fingerprint resolves against a real RunConfigLedger entry
# ---------------------------------------------------------------------------


def test_run_foundation_qualification_rejects_unresolvable_config_fingerprint(tmp_path):
    config_ledger = RunConfigLedger(tmp_path / "cfg")
    foundation = _mock_foundation()
    with pytest.raises(QualificationValidationError, match="config_fingerprint"):
        run_foundation_qualification(
            foundation_id="MEM0", foundation=foundation, foundation_name="mem0",
            adapter_revision=ADAPTER_VERSION, conformance_tag=REAL_FOUNDATION_CONFORMANCE,
            config_fingerprint="CFG-does-not-exist", qualified_at="2026-01-01T00:00:00Z",
            storage_dir=tmp_path / "q", config_ledger=config_ledger,
        )


def test_run_foundation_qualification_accepts_resolvable_config_fingerprint(tmp_path):
    config_ledger = RunConfigLedger(tmp_path / "cfg")
    config = _config_record()
    config_ledger.append(config)
    foundation = _mock_foundation()
    record = run_foundation_qualification(
        foundation_id="MEM0", foundation=foundation, foundation_name="mem0",
        adapter_revision=ADAPTER_VERSION, conformance_tag=REAL_FOUNDATION_CONFORMANCE,
        config_fingerprint=config.config_fingerprint, qualified_at="2026-01-01T00:00:00Z",
        storage_dir=tmp_path / "q", config_ledger=config_ledger,
    )
    assert record.overall_verdict == VERDICT_QUALIFIED


# ---------------------------------------------------------------------------
# Section 8, item 6: vendor IDs never appear in a qualification record's persisted fields
# ---------------------------------------------------------------------------


def test_qualification_record_never_contains_vendor_ids(tmp_path):
    foundation = _mock_foundation()
    record = run_foundation_qualification(
        foundation_id="MEM0", foundation=foundation, foundation_name="mem0",
        adapter_revision=ADAPTER_VERSION, conformance_tag=REAL_FOUNDATION_CONFORMANCE,
        config_fingerprint="CFG-test", qualified_at="2026-01-01T00:00:00Z",
        storage_dir=tmp_path / "q",
    )
    serialized = json.dumps(record.to_dict())
    # MockMem0Adapter honors the caller's own memory_id as its vendor id (see
    # canonical_write.py test precedent), so this checks the STRUCTURAL claim (no separate
    # "foundation_memory_id"/"vendor_id" field anywhere in the persisted shape), not string
    # absence, which would be vacuous here.
    assert "foundation_memory_id" not in record.to_dict()
    assert "vendor_id" not in record.to_dict()
    assert set(record.to_dict().keys()) == {
        "foundation_id", "adapter_revision", "fixture_set_version", "config_fingerprint",
        "per_fixture_results", "conformance_tag", "overall_verdict", "qualified_at", "note",
    }


# ---------------------------------------------------------------------------
# Section 9, item 1: ENVIRONMENT_LIMITATION conformance -> NOT_QUALIFIED even if every
# fixture structurally passes
# ---------------------------------------------------------------------------


def test_environment_limitation_conformance_is_never_qualified_even_if_fixtures_pass(tmp_path):
    foundation = _mock_foundation()  # structurally passes every fixture
    record = run_foundation_qualification(
        foundation_id="LETTA", foundation=foundation, foundation_name="letta",
        adapter_revision="letta-rev", conformance_tag=ENVIRONMENT_LIMITATION,
        config_fingerprint="CFG-test", qualified_at="2026-01-01T00:00:00Z",
        storage_dir=tmp_path / "q",
    )
    assert all(v["passed"] for v in record.per_fixture_results.values())
    assert record.overall_verdict == VERDICT_NOT_QUALIFIED


# ---------------------------------------------------------------------------
# Section 9, item 2: a disagreeing fixture is reported with the specific edge named
# ---------------------------------------------------------------------------


def test_disagreeing_graphs_report_the_specific_edge_not_a_bare_boolean():
    expected = {"conflict_pairs": [("mem-a", "mem-b")], "ancestors": {"mem-a": []}}
    reconstructed = {"conflict_pairs": [], "ancestors": {"mem-a": []}}
    passed, mismatches = compare_graphs(expected, reconstructed)
    assert not passed
    assert len(mismatches) == 1
    assert "conflict_pairs" in mismatches[0]
    assert "mem-a" in mismatches[0] and "mem-b" in mismatches[0]


def test_fixture_result_reports_mismatch_when_reconstruction_is_tampered(tmp_path, monkeypatch):
    """Simulates a foundation that silently drops a conflicts_with relationship during
    round-tripping: patch reconstruct_graph to omit it, and confirm the fixture is reported
    FAILED with the specific pair named, not silently passed."""
    import phase3.evaluation.foundations_real.qualification_harness as harness_module

    bundle = load_multi_file_fixture("conflicting_memory")
    ml, el, sl = _fresh_ledgers(tmp_path, "tamper")
    foundation = _mock_foundation()

    real_reconstruct = harness_module.reconstruct_graph

    def _tampered_reconstruct(*args, **kwargs):
        graph = real_reconstruct(*args, **kwargs)
        graph["conflict_pairs"] = []  # simulate a dropped conflicts_with edge
        return graph

    monkeypatch.setattr(harness_module, "reconstruct_graph", _tampered_reconstruct)
    result = harness_module.run_qualification_fixture(
        bundle, foundation=foundation, foundation_name="mem0",
        memory_ledger=ml, event_ledger=el, supersession_ledger=sl,
    )
    assert not result.passed
    assert any("conflict_pairs" in m for m in result.mismatches)


# ---------------------------------------------------------------------------
# Section 9, item 3: two qualification runs, different adapter_revision, both retained;
# get_latest() returns the most recent
# ---------------------------------------------------------------------------


def test_multiple_qualification_runs_are_retained_and_get_latest_is_most_recent(tmp_path):
    ledger = QualificationLedger(tmp_path / "qual")
    older = FoundationQualificationRecord(**_qualification_kwargs(adapter_revision="rev-1", qualified_at="2026-01-01T00:00:00Z"))
    newer = FoundationQualificationRecord(**_qualification_kwargs(adapter_revision="rev-2", qualified_at="2026-06-01T00:00:00Z"))
    ledger.append(older)
    ledger.append(newer)
    assert len(ledger.all_for_foundation("MOCK")) == 2
    assert ledger.get_latest("MOCK").adapter_revision == "rev-2"


# ---------------------------------------------------------------------------
# Section 9, item 4: qualification attempt against an undeclared/drifted fixture set is
# rejected before the harness runs
# ---------------------------------------------------------------------------


def test_run_foundation_qualification_rejects_drifted_fixture_set(tmp_path, monkeypatch):
    import phase3.evaluation.foundations_real.qualification_record as record_module

    def _mismatched_verify(*args, **kwargs):
        return False, {"modified_files": ["conflicting_memory/memory_a.json"]}

    monkeypatch.setattr(
        "phase3.evaluation.foundations_real.qualification_fixtures.verify_fixture_manifest", _mismatched_verify
    )
    foundation = _mock_foundation()
    with pytest.raises(FixtureManifestError):
        run_foundation_qualification(
            foundation_id="MEM0", foundation=foundation, foundation_name="mem0",
            adapter_revision=ADAPTER_VERSION, conformance_tag=REAL_FOUNDATION_CONFORMANCE,
            config_fingerprint="CFG-test", qualified_at="2026-01-01T00:00:00Z",
            storage_dir=tmp_path / "q",
        )


# ---------------------------------------------------------------------------
# check_qualification_currency() -- the gate (mission section 7)
# ---------------------------------------------------------------------------


def test_currency_check_flags_missing_qualification(tmp_path):
    ledger = QualificationLedger(tmp_path / "qual")
    result = check_qualification_currency({"foundation_id": "MEM0", "fixture_set_version": FIXTURE_SET_VERSION}, ledger)
    assert not result.is_current
    assert any("no qualification record" in r for r in result.reasons)


def test_currency_check_flags_not_qualified_verdict(tmp_path):
    ledger = QualificationLedger(tmp_path / "qual")
    ledger.append(FoundationQualificationRecord(
        **_qualification_kwargs(conformance_tag=ENVIRONMENT_LIMITATION, overall_verdict=VERDICT_NOT_QUALIFIED)
    ))
    result = check_qualification_currency({"foundation_id": "MOCK", "fixture_set_version": FIXTURE_SET_VERSION}, ledger)
    assert not result.is_current
    assert any("NOT_QUALIFIED" in r for r in result.reasons)


def test_currency_check_flags_stale_adapter_revision(tmp_path):
    ledger = QualificationLedger(tmp_path / "qual")
    ledger.append(FoundationQualificationRecord(**_qualification_kwargs(adapter_revision="rev-1")))
    result = check_qualification_currency(
        {"foundation_id": "MOCK", "fixture_set_version": FIXTURE_SET_VERSION}, ledger, current_adapter_revision="rev-2"
    )
    assert not result.is_current
    assert any("no longer matches" in r for r in result.reasons)


def test_currency_check_flags_mismatched_fixture_set_version(tmp_path):
    ledger = QualificationLedger(tmp_path / "qual")
    ledger.append(FoundationQualificationRecord(**_qualification_kwargs(fixture_set_version="qualification_fixtures_v1")))
    result = check_qualification_currency(
        {"foundation_id": "MOCK", "fixture_set_version": "qualification_fixtures_v2"}, ledger
    )
    assert not result.is_current
    assert any("fixture_set_version" in r for r in result.reasons)


def test_currency_check_passes_when_everything_matches(tmp_path):
    ledger = QualificationLedger(tmp_path / "qual")
    ledger.append(FoundationQualificationRecord(**_qualification_kwargs(adapter_revision="rev-1")))
    result = check_qualification_currency(
        {"foundation_id": "MOCK", "fixture_set_version": FIXTURE_SET_VERSION}, ledger, current_adapter_revision="rev-1"
    )
    assert result.is_current
    assert result.reasons == ()


# ---------------------------------------------------------------------------
# Serialization round trip / persistence
# ---------------------------------------------------------------------------


def test_qualification_record_persists_and_reloads(tmp_path):
    ledger = QualificationLedger(tmp_path / "qual")
    record = FoundationQualificationRecord(**_qualification_kwargs())
    ledger.append(record)
    reloaded = QualificationLedger(tmp_path / "qual")
    assert reloaded.get_latest("MOCK") == record


def test_duplicate_identical_qualification_record_is_idempotent(tmp_path):
    ledger = QualificationLedger(tmp_path / "qual")
    record = FoundationQualificationRecord(**_qualification_kwargs())
    ledger.append(record)
    ledger.append(record)
    assert len(ledger.all_for_foundation("MOCK")) == 1


def test_qualification_record_collision_on_differing_payload(tmp_path):
    ledger = QualificationLedger(tmp_path / "qual")
    record = FoundationQualificationRecord(**_qualification_kwargs())
    ledger.append(record)
    colliding = FoundationQualificationRecord(**_qualification_kwargs(note="a different note"))
    with pytest.raises(QualificationCollisionError):
        ledger.append(colliding)


# ---------------------------------------------------------------------------
# Adversarial: orphan-reference and cycle fixtures must not crash replay
# ---------------------------------------------------------------------------


def test_orphan_reference_fixture_is_handled_not_crashed(tmp_path):
    bundle = load_lineage_fixture("09_orphan_reference.json")
    ml, el, sl = _fresh_ledgers(tmp_path, "orphan")
    foundation = _mock_foundation()
    replay = replay_fixture(
        bundle, foundation=foundation, foundation_name="mem0",
        memory_ledger=ml, event_ledger=el, supersession_ledger=sl,
    )
    assert any(e.memory_id == "mem-lin-A" for e in replay.errors)
    expected = compute_expected_graph(bundle)
    assert expected["orphan_children"] == ["mem-lin-A"]


def test_cycle_fixture_is_handled_not_crashed(tmp_path):
    bundle = load_lineage_fixture("10_cycle.json")
    ml, el, sl = _fresh_ledgers(tmp_path, "cycle")
    foundation = _mock_foundation()
    result = run_qualification_fixture(
        bundle, foundation=foundation, foundation_name="mem0",
        memory_ledger=ml, event_ledger=el, supersession_ledger=sl,
    )
    assert result.passed, result.mismatches
    expected = compute_expected_graph(bundle)
    assert len(expected["cycles"]) == 1
