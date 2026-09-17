"""Phase 10.2 -- tests for the RiskEstimate -> MGP action decision surface.

Also documents, via `test_needs_verification_is_not_a_new_action`, the real
reconciliation this stage made against the Phase 10 plan's original proposal
(see `risk_action.py`'s module docstring): `REQUIRE_VALIDATION`, not a new
`NEEDS_VERIFICATION` action, is what MODERATE/ELEVATED risk routes to.
"""

from __future__ import annotations

import pytest

from phase6.defense.policy.states import (
    ALLOW,
    ALLOWED_TRANSITIONS,
    BLOCKED,
    IllegalTransitionError,
    QUARANTINE,
    QUARANTINED,
    REQUIRE_VALIDATION,
    SUSPICIOUS,
    TRUSTED,
    UNASSESSED,
)
from phase6.defense.risk.risk_action import action_for_risk_band, action_for_risk_estimate
from phase6.defense.risk.risk_score import ELEVATED, HIGH, LOW, MODERATE, RiskEstimate


def _estimate(risk_band: str, score: float = 0.5) -> RiskEstimate:
    return RiskEstimate(
        memory_id="MEM-1", risk_score=score, contributing_signals={"lineage_taint_score": score},
        risk_band=risk_band, rationale=("test",),
    )


# ---------------------------------------------------------------------------
# The reconciliation itself: no new action was added.
# ---------------------------------------------------------------------------


def test_needs_verification_is_not_a_new_action():
    """No `NEEDS_VERIFICATION` symbol exists anywhere in the policy vocabulary
    -- the plan's proposed new action was reconciled away in favor of the
    already-existing `REQUIRE_VALIDATION` (see risk_action.py docstring)."""
    import phase6.defense.policy.states as states

    assert not hasattr(states, "NEEDS_VERIFICATION")
    assert "NEEDS_VERIFICATION" not in states.ACTIONS


# ---------------------------------------------------------------------------
# The band -> action mapping.
# ---------------------------------------------------------------------------


def test_low_maps_to_allow():
    assert action_for_risk_band(LOW) == ALLOW


def test_moderate_and_elevated_both_map_to_require_validation():
    assert action_for_risk_band(MODERATE) == REQUIRE_VALIDATION
    assert action_for_risk_band(ELEVATED) == REQUIRE_VALIDATION


def test_high_maps_to_quarantine_never_block():
    assert action_for_risk_band(HIGH) == QUARANTINE
    assert action_for_risk_band(HIGH) != "BLOCK"


def test_unknown_band_is_refused():
    with pytest.raises(ValueError):
        action_for_risk_band("NOT_A_REAL_BAND")


# ---------------------------------------------------------------------------
# action_for_risk_estimate(): transition legality is enforced, matching
# every other Phase 6 guard's own "validate_transition before returning"
# discipline.
# ---------------------------------------------------------------------------


def test_legal_transitions_from_unassessed_succeed_for_every_band():
    # UNASSESSED -> {TRUSTED, SUSPICIOUS, QUARANTINED} are all legal first
    # assessments (states.py's own table), so every band's action is legal
    # starting from UNASSESSED.
    for band in (LOW, MODERATE, ELEVATED, HIGH):
        action = action_for_risk_estimate(_estimate(band), current_security_state=UNASSESSED)
        assert action == action_for_risk_band(band)


def test_illegal_transition_raises():
    """BLOCKED is terminal for v1 -- no risk-driven action can move a
    currently-BLOCKED memory anywhere else, and this must raise loudly, not
    silently no-op or silently succeed."""
    with pytest.raises(IllegalTransitionError):
        action_for_risk_estimate(_estimate(HIGH), current_security_state=BLOCKED)


def test_trusted_to_quarantined_via_high_band_is_legal():
    # (TRUSTED, QUARANTINED) is an allowed edge -- later evidence can raise
    # concern on an already-trusted memory.
    action = action_for_risk_estimate(_estimate(HIGH), current_security_state=TRUSTED)
    assert action == QUARANTINE


def test_moderate_band_on_trusted_memory_is_legal_require_validation():
    action = action_for_risk_estimate(_estimate(MODERATE), current_security_state=TRUSTED)
    assert action == REQUIRE_VALIDATION


def test_every_mapped_action_is_a_legal_edge_from_every_non_terminal_state():
    """Structural check across the whole table: for every (band, from_state)
    pair where states.py defines ANY legal edge to that action's resulting
    state, action_for_risk_estimate() must succeed -- and where it does not,
    it must raise, never something silently wrong in between."""
    from phase6.defense.policy.states import ACTION_RESULTING_STATE, SECURITY_STATES

    for band in (LOW, MODERATE, ELEVATED, HIGH):
        action = action_for_risk_band(band)
        resulting = ACTION_RESULTING_STATE[action]
        for from_state in SECURITY_STATES:
            legal = (from_state, resulting) in ALLOWED_TRANSITIONS
            if legal:
                assert (
                    action_for_risk_estimate(_estimate(band), current_security_state=from_state) == action
                )
            else:
                with pytest.raises(IllegalTransitionError):
                    action_for_risk_estimate(_estimate(band), current_security_state=from_state)


# ---------------------------------------------------------------------------
# Explicit scope boundary: not wired into any live pipeline or Phase 3.
# ---------------------------------------------------------------------------


def test_risk_action_module_does_not_import_phase3_or_orchestration_pipeline():
    """Structural guarantee mirroring Phase 10 plan Section 4.2's disclosed
    scope boundary: this module must not reach into Phase 3's generation-time
    modules, nor call into the live orchestration pipeline -- both are named,
    deliberately deferred follow-on items, not silently done here."""
    import phase6.defense.risk.risk_action as mod

    source = open(mod.__file__, encoding="utf-8").read()
    assert "phase3." not in source
    assert "phase6.defense.orchestration" not in source
