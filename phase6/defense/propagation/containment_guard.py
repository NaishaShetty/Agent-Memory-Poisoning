"""Phase 6.7 -- the Propagation Containment Guard: D4's own decision layer.

CORE DESIGN RULE: LINEAGE EVIDENCE ALONE NEVER BLOCKS
--------------------------------------------------------------------------------
The Stage 6.7 brief is explicit: "Do NOT blindly assume transitive quarantine
is always correct." This guard operationalizes that instruction as a hard cap:
no amount of ancestor taint, on its own, can produce a `BLOCK` action. The
strongest action `evaluate_propagation_containment()` can select is
`QUARANTINE` -- reversible, inspectable, never silently destructive (Policy
document Section 2.1's own justification for QUARANTINE's existence). Direct
content evidence (Stage 6.5's admission signals) remains the only path to
`BLOCK`; lineage is treated as strictly weaker evidence than direct content
inspection, which is a real, disclosed, and deliberate asymmetry, not an
oversight.

PIPELINE POSITION
--------------------------------------------------------------------------------
This guard runs at a descendant memory's OWN admission time (alongside, not
instead of, Stage 6.5's content-based Reasoning Guard) or at any later
re-assessment triggered by new lineage evidence (e.g. an ancestor's state
changes AFTER the descendant was already admitted). It never reads Phase 5's
ledgers itself -- the caller (Stage 6.10's real wiring) supplies the
descendant's own current MGP state and its real ancestor chain
(`AncestorRecord` list, built from Phase 5's actual `build_propagation_graph()`
output plus `GovernanceLedger.current_state()` lookups).
"""

from __future__ import annotations

from typing import Sequence

from phase6.defense.policy.records import MGPDecisionRecord, build_decision
from phase6.defense.policy.states import (
    ALLOW,
    ALLOW_WITH_RESTRICTION,
    QUARANTINE,
    REQUIRE_VALIDATION,
    validate_transition,
)
from phase6.defense.propagation.signals import AncestorRecord, lineage_taint_signal

GUARD_VERSION = "propagation-containment-guard-1.0.0"

# Uncalibrated v1 thresholds (same disclosure discipline as
# reasoning_guard.py / consensus_guard.py's THRESHOLD_* constants). Note the
# TOP band is QUARANTINE, not BLOCK -- see module docstring "CORE DESIGN RULE."
THRESHOLD_QUARANTINE = 0.6
THRESHOLD_REQUIRE_VALIDATION = 0.35
THRESHOLD_ALLOW_WITH_RESTRICTION = 0.15


def _action_for_score(score: float) -> str:
    if score >= THRESHOLD_QUARANTINE:
        return QUARANTINE
    if score >= THRESHOLD_REQUIRE_VALIDATION:
        return REQUIRE_VALIDATION
    if score >= THRESHOLD_ALLOW_WITH_RESTRICTION:
        return ALLOW_WITH_RESTRICTION
    return ALLOW


def _reason_for(score: float, action: str, ancestors: Sequence[AncestorRecord]) -> str:
    tainted = [a for a in ancestors if a.security_state in ("BLOCKED", "QUARANTINED", "SUSPICIOUS")]
    if not tainted:
        return f"lineage_taint_score={score:.3f} ({GUARD_VERSION}); no tainted ancestors; action={action}"
    tainted_desc = ", ".join(f"{a.memory_id}({a.security_state}, distance={a.distance})" for a in tainted)
    return (
        f"lineage_taint_score={score:.3f} ({GUARD_VERSION}); tainted ancestors: "
        f"{tainted_desc}; action={action}"
    )


def evaluate_propagation_containment(
    descendant_memory_id: str,
    descendant_content: str,
    descendant_current_state: str,
    ancestors: Sequence[AncestorRecord],
    *,
    run_id: str,
    episode_id: str,
    timestamp: str,
    evidence_refs: Sequence[str],
) -> MGPDecisionRecord:
    """Evaluate one descendant memory's lineage. Returns an `MGPDecisionRecord`
    whose action is capped at `QUARANTINE` (never `BLOCK`) regardless of how
    severe or numerous the tainted ancestors are -- see module docstring.

    `validate_transition()` is called before returning, exactly as every
    other Phase 6 decision layer does, so an illegal edge from the
    descendant's ACTUAL current state raises loudly rather than being
    silently attempted. Note one real, intentional consequence: if the
    descendant is currently QUARANTINED and this call's computed action is
    ALLOW (low taint), `validate_transition()` raises `IllegalTransitionError`
    -- Stage 6.3's table requires QUARANTINED to resolve via RELEASE, never a
    direct ALLOW. This guard is not the pathway for resolving an existing
    quarantine (that requires an explicit, separate RELEASE decision, e.g.
    from a review process this module does not perform); it only evaluates
    NEW lineage concern. Callers re-assessing an already-quarantined
    descendant with genuinely low current taint should route through a
    review/RELEASE mechanism, not this function.
    """
    signal = lineage_taint_signal(descendant_content, ancestors)
    score = signal["lineage_taint_score"]
    action = _action_for_score(score)
    reason = _reason_for(score, action, ancestors)

    # Defense-in-depth re-assertion of the module's own core design rule --
    # if a future edit to _action_for_score ever accidentally introduces a
    # BLOCK band, this raises immediately rather than silently shipping a
    # violation of the Stage 6.7 brief's explicit instruction.
    assert action != "BLOCK", "Propagation containment must never select BLOCK directly (see module docstring)."

    validate_transition(descendant_current_state, action)

    return build_decision(
        candidate_memory_id=descendant_memory_id,
        signals_used=signal,
        action=action,
        reason=reason,
        run_id=run_id,
        episode_id=episode_id,
        timestamp=timestamp,
        evidence_refs=evidence_refs,
    )
