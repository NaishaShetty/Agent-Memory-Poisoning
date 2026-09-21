"""Phase 11.4 -- the hybrid hook, and the Section 8 acceptance criterion: a
single-signal-only `RiskEstimate` contribution from either learned component
still cannot alone justify a BLOCK-equivalent band, verified directly."""

from __future__ import annotations

from phase6.defense.risk.risk_score import GROUPED_GATED, HIGH
from phase11.hybrid import compose_hybrid_risk_estimate


def test_hybrid_composes_a_real_risk_estimate_from_rule_and_learned_signals():
    estimate = compose_hybrid_risk_estimate(
        "MEM-1", {"self_reference_score": 0.8}, gnn_risk_score=0.9, gln_risk_score=0.9,
    )
    assert 0.0 <= estimate.risk_score <= 1.0
    assert "gnn_risk_score" in estimate.contributing_signals
    assert "gln_risk_score" in estimate.contributing_signals


def test_single_learned_signal_alone_cannot_reach_high_band():
    """gnn_risk_score=1.0 with nothing else present -- exactly the
    single-nonzero-signal case `compute_memory_risk_score()` already caps
    below HIGH, verified here for the two NEW Phase 11 keys specifically
    (the flat weight on one signal alone keeps the raw score well under the
    HIGH threshold too, so this also indirectly confirms the cap is never
    even reached, not merely that the post-hoc downgrade rule fires)."""
    estimate = compose_hybrid_risk_estimate("MEM-2", {}, gnn_risk_score=1.0)
    assert estimate.risk_band != HIGH


def test_single_gln_signal_alone_cannot_reach_high_band():
    estimate = compose_hybrid_risk_estimate("MEM-3", {}, gln_risk_score=1.0)
    assert estimate.risk_band != HIGH


def test_single_learned_signal_alone_cannot_reach_high_band_under_grouped_gated():
    """The follow-on `learned_group` (risk_score.py, 2026-09-17) must respect
    the same single-signal cap as every other group."""
    estimate = compose_hybrid_risk_estimate("MEM-3b", {}, gnn_risk_score=1.0, rule=GROUPED_GATED)
    assert estimate.risk_band != HIGH


def test_omitted_learned_signal_is_not_fabricated_as_zero():
    """No gnn_risk_score/gln_risk_score passed -- absence of evidence, not a
    confirmed-safe 0.0 claim -- so neither key appears in contributing_signals
    at all."""
    estimate = compose_hybrid_risk_estimate("MEM-4", {"self_reference_score": 0.5})
    assert "gnn_risk_score" not in estimate.contributing_signals
    assert "gln_risk_score" not in estimate.contributing_signals
