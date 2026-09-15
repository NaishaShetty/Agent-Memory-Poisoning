"""Phase 6.19 -- tests for the reproducibility manifest and the real JSON
Schema for MGPDecisionRecord.
"""

from __future__ import annotations

import json
import os

import jsonschema
import pytest

from phase6.defense.policy.records import build_decision
from phase6.evaluation.reproducibility.manifest import (
    MANIFEST_SCHEMA_VERSION,
    Phase6ReproducibilityManifest,
    build_shipped_defense_manifest,
    environment_snapshot,
)

_SCHEMA_PATH = os.path.join(
    os.path.dirname(__file__), "..", "schemas", "mgp_decision_record.schema.json"
)


def _load_schema():
    with open(_SCHEMA_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _decision_to_dict(decision):
    return {
        "decision_id": decision.decision_id,
        "candidate_memory_id": decision.candidate_memory_id,
        "policy_version": decision.policy_version,
        "signals_used": dict(decision.signals_used),
        "action": decision.action,
        "resulting_state": decision.resulting_state,
        "reason": decision.reason,
        "run_id": decision.run_id,
        "episode_id": decision.episode_id,
        "timestamp": decision.timestamp,
        "evidence_refs": list(decision.evidence_refs),
    }


# ---------------------------------------------------------------------------
# JSON Schema validates real MGPDecisionRecord instances
# ---------------------------------------------------------------------------


def test_real_allow_decision_validates_against_schema():
    decision = build_decision(
        candidate_memory_id="MEM-1", signals_used={"self_reference_score": 0.5}, action="ALLOW",
        reason="test reason grounded in signals", run_id="run-1", episode_id="episode-1",
        timestamp="2026-09-14T00:00:00Z", evidence_refs=("EVT-1",),
    )
    jsonschema.validate(_decision_to_dict(decision), _load_schema())


def test_real_block_decision_with_null_episode_validates():
    decision = build_decision(
        candidate_memory_id="MEM-2", signals_used={"perfection_claim_score": 1.0}, action="BLOCK",
        reason="test reason", run_id="run-1", episode_id=None,
        timestamp="2026-09-14T00:00:00Z", evidence_refs=("EVT-2", "EVT-3"),
    )
    jsonschema.validate(_decision_to_dict(decision), _load_schema())


def test_all_seven_actions_produce_schema_valid_decisions():
    for action in ("ALLOW", "ALLOW_WITH_RESTRICTION", "REQUIRE_VALIDATION", "QUARANTINE", "BLOCK", "RELEASE", "DOWNRANK"):
        decision = build_decision(
            candidate_memory_id="MEM-X", signals_used={"x": 1.0}, action=action,
            reason="reason", run_id="run-1", episode_id="e1",
            timestamp="2026-09-14T00:00:00Z", evidence_refs=("EVT-1",),
        )
        jsonschema.validate(_decision_to_dict(decision), _load_schema())


def test_schema_rejects_missing_evidence_refs():
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            {
                "decision_id": "MGPDEC-" + "a" * 64, "candidate_memory_id": "M", "policy_version": "mgp-1.0.0",
                "signals_used": {}, "action": "ALLOW", "resulting_state": "TRUSTED", "reason": "r",
                "run_id": "run-1", "timestamp": "2026-09-14T00:00:00Z", "evidence_refs": [],
            },
            _load_schema(),
        )


def test_schema_rejects_unknown_action():
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            {
                "decision_id": "MGPDEC-" + "a" * 64, "candidate_memory_id": "M", "policy_version": "mgp-1.0.0",
                "signals_used": {}, "action": "NOT_A_REAL_ACTION", "resulting_state": None, "reason": "r",
                "run_id": "run-1", "timestamp": "2026-09-14T00:00:00Z", "evidence_refs": ["E1"],
            },
            _load_schema(),
        )


def test_schema_rejects_additional_properties():
    d = _decision_to_dict(
        build_decision(
            candidate_memory_id="MEM-1", signals_used={"x": 1.0}, action="ALLOW",
            reason="r", run_id="run-1", episode_id="e1",
            timestamp="2026-09-14T00:00:00Z", evidence_refs=("E1",),
        )
    )
    d["unexpected_extra_field"] = "should not be allowed"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(d, _load_schema())


# ---------------------------------------------------------------------------
# Reproducibility manifest
# ---------------------------------------------------------------------------


def test_build_shipped_defense_manifest_reads_real_thresholds():
    """The manifest's thresholds must come from the actual shipped module
    constants, not be retyped by hand -- checked by cross-referencing one
    real constant directly."""
    from phase6.defense.retrieval.consensus_guard import THRESHOLD_DOWNRANK

    manifest = build_shipped_defense_manifest(campaign_id="c1", run_id="r1")
    assert manifest.configuration["retrieval"]["threshold_downrank"] == THRESHOLD_DOWNRANK


def test_manifest_rejects_empty_campaign_or_run_id():
    with pytest.raises(ValueError):
        Phase6ReproducibilityManifest(
            manifest_schema_version=MANIFEST_SCHEMA_VERSION, campaign_id="", run_id="r1",
            episode_id=None, defense_component_versions={}, policy_version="mgp-1.0.0",
            configuration={}, model_versions={}, seeds={}, attack_version=None,
            task_sample_description=None, memory_foundation=None,
        )


def test_canonical_identity_is_deterministic():
    m1 = build_shipped_defense_manifest(campaign_id="c1", run_id="r1")
    m2 = build_shipped_defense_manifest(campaign_id="c1", run_id="r1")
    assert m1.canonical_identity() == m2.canonical_identity()


def test_canonical_identity_excludes_environment():
    """Two manifests differing only in a machine-local environment field
    (simulated here) must produce the SAME canonical identity -- environment
    facts should not change whether two runs are considered the same
    configuration."""
    m1 = build_shipped_defense_manifest(campaign_id="c1", run_id="r1")
    # Construct a second manifest with a different (fake) environment but
    # identical everything else.
    m2 = Phase6ReproducibilityManifest(
        manifest_schema_version=m1.manifest_schema_version, campaign_id=m1.campaign_id,
        run_id=m1.run_id, episode_id=m1.episode_id,
        defense_component_versions=m1.defense_component_versions, policy_version=m1.policy_version,
        configuration=m1.configuration, model_versions=m1.model_versions, seeds=m1.seeds,
        attack_version=m1.attack_version, task_sample_description=m1.task_sample_description,
        memory_foundation=m1.memory_foundation,
        environment={"python_version": "some-other-fake-version", "platform": "fake", "dependency_versions": {}},
    )
    assert m1.canonical_identity() == m2.canonical_identity()


def test_canonical_identity_changes_with_real_configuration_difference():
    m1 = build_shipped_defense_manifest(campaign_id="c1", run_id="r1")
    m2 = Phase6ReproducibilityManifest(
        manifest_schema_version=m1.manifest_schema_version, campaign_id=m1.campaign_id,
        run_id=m1.run_id, episode_id=m1.episode_id,
        defense_component_versions=m1.defense_component_versions, policy_version=m1.policy_version,
        configuration={**m1.configuration, "extra_key": "different"},
        model_versions=m1.model_versions, seeds=m1.seeds, attack_version=m1.attack_version,
        task_sample_description=m1.task_sample_description, memory_foundation=m1.memory_foundation,
    )
    assert m1.canonical_identity() != m2.canonical_identity()


def test_environment_snapshot_reports_real_dependency_versions_not_fabricated():
    snapshot = environment_snapshot()
    assert snapshot["dependency_versions"]["scipy"] is not None
    assert "python_version" in snapshot
    assert "platform" in snapshot


def test_environment_snapshot_reports_none_for_a_package_not_installed():
    from phase6.evaluation.reproducibility import manifest as manifest_module

    original = manifest_module._TRACKED_PACKAGES
    manifest_module._TRACKED_PACKAGES = ("definitely-not-a-real-package-xyz",)
    try:
        snapshot = environment_snapshot()
        assert snapshot["dependency_versions"]["definitely-not-a-real-package-xyz"] is None
    finally:
        manifest_module._TRACKED_PACKAGES = original


def test_to_dict_includes_canonical_identity():
    manifest = build_shipped_defense_manifest(campaign_id="c1", run_id="r1")
    d = manifest.to_dict()
    assert d["canonical_identity"] == manifest.canonical_identity()
