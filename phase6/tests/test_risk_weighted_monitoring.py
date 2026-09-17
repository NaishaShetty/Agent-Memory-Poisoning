"""Phase 10.4 -- tests for the risk-weighted forensic-target sort key."""

from __future__ import annotations

from attribution.schema import TARGET_MEMORY
from attribution.wiring.forensics_entrypoints import forensic_targets_from_mgp_decisions
from phase6.defense.policy.records import build_decision
from phase6.defense.policy.states import ALLOW, BLOCK, QUARANTINE
from phase6.defense.risk.risk_score import RiskEstimate
from phase6.defense.risk.risk_weighted_monitoring import rank_forensic_targets_by_risk


def _estimate(memory_id: str, score: float) -> RiskEstimate:
    band = "HIGH" if score >= 0.6 else "MODERATE" if score >= 0.15 else "LOW"
    return RiskEstimate(
        memory_id=memory_id, risk_score=score, contributing_signals={"lineage_taint_score": score},
        risk_band=band, rationale=("test",),
    )


def test_orders_by_descending_risk_score():
    targets = [(TARGET_MEMORY, "MEM-LOW"), (TARGET_MEMORY, "MEM-HIGH"), (TARGET_MEMORY, "MEM-MID")]
    estimates = {
        "MEM-LOW": _estimate("MEM-LOW", 0.1),
        "MEM-HIGH": _estimate("MEM-HIGH", 0.9),
        "MEM-MID": _estimate("MEM-MID", 0.5),
    }
    ranked = rank_forensic_targets_by_risk(targets, estimates)
    assert [t[1] for t in ranked] == ["MEM-HIGH", "MEM-MID", "MEM-LOW"]


def test_targets_without_a_known_estimate_are_kept_ranked_as_zero_risk():
    targets = [(TARGET_MEMORY, "MEM-KNOWN"), (TARGET_MEMORY, "MEM-UNKNOWN")]
    estimates = {"MEM-KNOWN": _estimate("MEM-KNOWN", 0.7)}
    ranked = rank_forensic_targets_by_risk(targets, estimates)
    assert [t[1] for t in ranked] == ["MEM-KNOWN", "MEM-UNKNOWN"]
    assert len(ranked) == len(targets)  # nothing dropped


def test_no_targets_added_or_removed():
    targets = [(TARGET_MEMORY, "MEM-A"), (TARGET_MEMORY, "MEM-B"), (TARGET_MEMORY, "MEM-C")]
    ranked = rank_forensic_targets_by_risk(targets, {})
    assert set(ranked) == set(targets)
    assert len(ranked) == len(targets)


def test_stable_ordering_for_equal_or_absent_risk():
    """Targets with equal (or absent, both 0.0) risk keep their ORIGINAL
    relative order -- ties never silently reordered."""
    targets = [(TARGET_MEMORY, "MEM-A"), (TARGET_MEMORY, "MEM-B"), (TARGET_MEMORY, "MEM-C")]
    ranked = rank_forensic_targets_by_risk(targets, {})  # no estimates at all -- everything ties at 0.0
    assert ranked == tuple(targets)


def test_empty_target_list_returns_empty():
    assert rank_forensic_targets_by_risk([], {}) == ()


def test_composes_with_real_frozen_forensic_target_resolution():
    """Real, end-to-end composition: the ACTUAL `forensic_targets_from_mgp_
    decisions()` output (frozen Phase 9 wiring, untouched by this module)
    ranked by real `RiskEstimate`s. This module never modifies that function
    -- it only consumes its real return value."""
    decisions = [
        build_decision(
            candidate_memory_id="MEM-QUARANTINED-LOW-RISK", signals_used={"lineage_taint_score": 0.2},
            action=QUARANTINE, reason="r", run_id="R", episode_id="E", timestamp="2026-09-17T00:00:00Z",
            evidence_refs=("EVT-1",),
        ),
        build_decision(
            candidate_memory_id="MEM-BLOCKED-HIGH-RISK", signals_used={"lineage_taint_score": 0.9},
            action=BLOCK, reason="r", run_id="R", episode_id="E", timestamp="2026-09-17T00:00:00Z",
            evidence_refs=("EVT-2",),
        ),
        build_decision(
            candidate_memory_id="MEM-ALLOWED", signals_used={}, action=ALLOW, reason="r", run_id="R",
            episode_id="E", timestamp="2026-09-17T00:00:00Z", evidence_refs=("EVT-3",),
        ),
    ]
    targets = forensic_targets_from_mgp_decisions(decisions)
    # ALLOW is never resolved to a forensic target at all (frozen wiring's own rule).
    assert len(targets) == 2
    estimates = {
        "MEM-QUARANTINED-LOW-RISK": _estimate("MEM-QUARANTINED-LOW-RISK", 0.1),
        "MEM-BLOCKED-HIGH-RISK": _estimate("MEM-BLOCKED-HIGH-RISK", 0.9),
    }
    ranked = rank_forensic_targets_by_risk(targets, estimates)
    assert [t[1] for t in ranked] == ["MEM-BLOCKED-HIGH-RISK", "MEM-QUARANTINED-LOW-RISK"]
    assert set(ranked) == set(targets)  # same targets, just reordered


def test_module_does_not_import_frozen_attribution_wiring():
    """Structural guarantee mirroring Phase 10 plan Section 5's 'no
    modification to Attribution's/Phase 9's own core wiring' constraint --
    this module must never import forensics_entrypoints.py or
    campaign_signals.py, only operate on their real OUTPUT types."""
    import phase6.defense.risk.risk_weighted_monitoring as mod

    source = open(mod.__file__, encoding="utf-8").read()
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("from") or stripped.startswith("import"):
            assert "forensics_entrypoints" not in stripped
            assert "attribution.wiring.forensics" not in stripped
            assert "campaign_signals" not in stripped
