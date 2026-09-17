"""Phase 10.2 -- the RiskEstimate -> MGP action decision surface.

RECONCILIATION, DISCLOSED (Phase 10 plan Section 1's own standing discipline:
"any change forced by implementation reality is reconciled here explicitly,
not silently")
--------------------------------------------------------------------------------
`docs/phase10/PHASE10_PLAN.md` Section 4.2, written before this stage's
implementation, proposed a NEW action, `NEEDS_VERIFICATION`, reasoning that
the six-then-seven-action vocabulary in `phase6/defense/policy/states.py` had
no genuine middle ground between ALLOW and QUARANTINE.

That reasoning was written without first checking `states.py` itself.
`REQUIRE_VALIDATION` already exists there (added at Stage 6.7 for the
propagation containment guard, `phase6/defense/propagation/containment_guard.py`),
already resolves to `SUSPICIOUS`, and already carries the exact "genuine
middle ground, not ALLOW, not QUARANTINE" semantics the plan asked for.
Shipping `NEEDS_VERIFICATION` alongside it would have created two actions
with identical resulting-state semantics and no real behavioral difference --
a duplicate vocabulary entry this project's own "one obvious way" discipline
(e.g. `build_signal_context()`'s own module docstring) exists specifically to
avoid.

Stage 10.2's real, remaining job is therefore narrower than the plan
originally scoped it: not a new action, but the missing DECISION SURFACE that
routes a `RiskEstimate` (Stage 10.1) to `REQUIRE_VALIDATION` (or `ALLOW` /
`QUARANTINE`) in the first place -- today `REQUIRE_VALIDATION` is reachable
ONLY through the propagation guard's own lineage-taint score; no signal
composed across guards can reach it. This module is that missing wiring, and
nothing else.

EXPLICITLY OUT OF SCOPE (Phase 10 plan Section 4.2's own boundary, unchanged
by the reconciliation above): this module defines the mapping and its
transition-legality check ONLY. It is NOT wired into any live governance
pipeline (`phase6/defense/orchestration/pipeline.py`'s `evaluate_pool()` does
not call it) and NOT wired into Phase 3's real Verify/Revise generation-time
modules -- both are named, deliberately deferred follow-on items, the same
"Stage 6.10 live-ledger wiring" deferral pattern this project already uses
elsewhere.
"""

from __future__ import annotations

from typing import Dict

from phase6.defense.policy.states import ALLOW, QUARANTINE, REQUIRE_VALIDATION, validate_transition
from phase6.defense.risk.risk_score import ELEVATED, HIGH, LOW, MODERATE, RiskEstimate

RISK_ACTION_VERSION = "risk-action-10.2.0"

# Uncalibrated v1 starting default (disclosed, versioned, like every other
# Phase 6/10 threshold -- Phase 10 plan Section 5's calibration-only-against-
# dev-data constraint applies here identically). LOW never escalates past
# ALLOW; MODERATE and ELEVATED both route to the SAME genuine middle ground
# (REQUIRE_VALIDATION) rather than inventing a second, finer-grained action
# to distinguish them, mirroring the reconciliation above -- a distinction
# between two ALREADY-non-ALLOW, non-QUARANTINE bands is not, on its own,
# evidence that they need two different ACTIONS as well as two different
# BANDS; HIGH routes to QUARANTINE, never BLOCK (Phase 10 plan Section 5's
# inherited "no BLOCK from a single uncorroborated signal" constraint --
# RiskEstimate.risk_band already structurally caps at ELEVATED for any
# single-signal estimate, per Stage 10.1's own guarantee, so nothing built
# purely from `compute_memory_risk_score()` can even present as HIGH without
# real, multi-signal corroboration; QUARANTINE, not BLOCK, is still the
# ceiling here because a composed risk estimate -- however corroborated -- is
# not the same class of evidence as a guard's own direct, targeted decision).
ACTION_FOR_RISK_BAND: Dict[str, str] = {
    LOW: ALLOW,
    MODERATE: REQUIRE_VALIDATION,
    ELEVATED: REQUIRE_VALIDATION,
    HIGH: QUARANTINE,
}


def action_for_risk_band(risk_band: str) -> str:
    """The ONLY place a risk_band maps to an MGP action -- never re-derived
    inline elsewhere, mirroring `risk_score.risk_band_for_score()`'s own
    "one lookup function" discipline."""
    if risk_band not in ACTION_FOR_RISK_BAND:
        raise ValueError(f"Unknown risk_band: {risk_band!r}")
    return ACTION_FOR_RISK_BAND[risk_band]


def action_for_risk_estimate(estimate: RiskEstimate, *, current_security_state: str) -> str:
    """The real decision-surface entry point: given a `RiskEstimate` and the
    memory's current MGP security state, return the action `states.py`'s own
    transition table confirms is LEGAL from that state -- raising
    `IllegalTransitionError` otherwise, exactly as every other Phase 6 guard
    (`evaluate_admission`, `evaluate_sleeper_retrieval_risk`,
    `evaluate_propagation_containment`) already does before returning. This
    function does not write to any ledger, does not read `current_security_state`
    from anywhere itself, and is not called from any live pipeline -- see
    module docstring's explicit scope boundary.
    """
    action = action_for_risk_band(estimate.risk_band)
    validate_transition(current_security_state, action)
    return action
