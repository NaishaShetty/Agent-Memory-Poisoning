"""Phase 15 follow-on (2026-09-23, explicitly authorized) -- unit tests for
`GROUPED_GATED_RETRIEVAL_CORROBORATED`, the real, scoped fix for B9's real
50% false-positive rate on LongMemEval (root-caused to uncorroborated
retrieval-only evidence -- see `risk_score.py`'s own module note and
`docs/phase15/PHASE15_CROSS_CUTTING_REPORT.md` Section 3.3). Fast (no LLM
calls, pure signal-level tests)."""

from __future__ import annotations

from phase6.defense.risk.risk_score import (
    GROUPED_GATED,
    GROUPED_GATED_RETRIEVAL_CORROBORATED,
    compute_memory_risk_score,
)
from phase6.defense.risk.risk_action import action_for_risk_estimate
from phase6.defense.policy.states import ALLOW, UNASSESSED


def test_retrieval_only_evidence_is_suppressed_under_the_new_rule():
    """The exact real signal shape found on LongMemEval's own real benign
    pools: high semantic divergence, nothing else corroborating."""
    signals = {"semantic_consensus_divergence_score": 0.65, "dormancy_activation_score": 1.0}
    unfixed = compute_memory_risk_score("MEM-1", signals, rule=GROUPED_GATED)
    fixed = compute_memory_risk_score("MEM-1", signals, rule=GROUPED_GATED_RETRIEVAL_CORROBORATED)
    assert action_for_risk_estimate(unfixed, current_security_state=UNASSESSED) != ALLOW
    assert action_for_risk_estimate(fixed, current_security_state=UNASSESSED) == ALLOW
    assert fixed.risk_score == 0.0


def test_retrieval_evidence_corroborated_by_admission_is_not_suppressed():
    """Real, deliberate non-regression: when retrieval divergence is
    corroborated by a genuine admission-side signal, the new rule must NOT
    suppress it -- only truly uncorroborated retrieval-only evidence is
    dampened."""
    signals = {
        "semantic_consensus_divergence_score": 0.65,
        "self_reference_score": 1.0,
        "dormancy_activation_score": 1.0,
    }
    fixed = compute_memory_risk_score("MEM-2", signals, rule=GROUPED_GATED_RETRIEVAL_CORROBORATED)
    unfixed = compute_memory_risk_score("MEM-2", signals, rule=GROUPED_GATED)
    assert fixed.risk_score == unfixed.risk_score
    assert fixed.risk_score > 0.0


def test_lexical_retrieval_only_evidence_is_also_suppressed():
    signals = {"consensus_divergence_score": 0.9, "dormancy_activation_score": 1.0}
    fixed = compute_memory_risk_score("MEM-3", signals, rule=GROUPED_GATED_RETRIEVAL_CORROBORATED)
    assert fixed.risk_score == 0.0


def test_admission_only_evidence_is_unaffected_by_the_new_rule():
    """The new rule targets retrieval_group specifically -- admission-only
    real evidence (no retrieval signal at all) must behave identically under
    both rules."""
    signals = {"self_reference_score": 1.0, "decision_log_vocabulary_score": 1.0}
    fixed = compute_memory_risk_score("MEM-4", signals, rule=GROUPED_GATED_RETRIEVAL_CORROBORATED)
    unfixed = compute_memory_risk_score("MEM-4", signals, rule=GROUPED_GATED)
    assert fixed.risk_score == unfixed.risk_score
