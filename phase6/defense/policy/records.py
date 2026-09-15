"""Phase 6.3 -- `MGPDecisionRecord`: the evidence-grounded, append-only unit of
every Memory Governance Policy decision.

See `docs/phase6/MEMORY_GOVERNANCE_POLICY.md` Section 4 for the field-by-field
rationale. This module also owns the evaluator-only leakage guard (Section 7 of
that document) -- construction-time enforcement, not a hope that callers remember.

WHY A GUARD LIVES HERE, NOT ONLY IN 6.4/6.5's SIGNAL FUNCTIONS
--------------------------------------------------------------------------------
Stage 6.4 (Defense Signal & Trust Contract) and Stages 6.5-6.7 (the actual
admission/retrieval/propagation components) are responsible for never COMPUTING a
signal from an evaluator-only field in the first place. This module's guard is a
second, independent backstop at the point every decision is finally recorded: even
if a future component's signal-computation logic had a bug, a decision carrying a
recognizably evaluator-only key in `signals_used` is refused here, loudly, rather
than silently persisted as if it were legitimate evidence. Defense in depth, not a
substitute for getting 6.4/6.5 right.

This denylist is a documented, extensible STARTING set (Rule 20: document
uncertainty rather than claim completeness) -- it catches the specific fields this
project has already named as evaluator-only (Phase 6 brief; Charter Section 6), not
every conceivable future leakage vector. A differently-named future evaluator-only
field would not automatically be caught by this list; 6.4's own signal-function
design discipline remains the primary line of defense.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence, Tuple

from phase3.evaluation.security.reproducibility import fingerprint
from phase6.defense.policy.states import (
    ACTIONS,
    SECURITY_STATES,
    resulting_state_for,
)

# ---------------------------------------------------------------------------
# Policy version -- single source-of-truth constant (Policy document Section 5).
# Any change to states.py's vocabulary/transitions, or to a signal threshold
# anywhere in Phase 6, requires bumping this.
# ---------------------------------------------------------------------------

CURRENT_POLICY_VERSION = "mgp-1.0.0"

# ---------------------------------------------------------------------------
# Evaluator-only leakage denylist (Policy document Section 7).
# ---------------------------------------------------------------------------

FORBIDDEN_SIGNAL_KEYS: frozenset = frozenset(
    {
        "attack_id",
        "attacker_originated",
        # Ground-truth vocabulary (Phase 4/5) -- the LABEL, not a raw observable
        # event, is forbidden. A defense may see "this memory was admitted"; it
        # may never see "this memory is POISON_ADMITTED".
        "poison_not_admitted",
        "poison_admitted",
        "poison_in_candidate_pool",
        "poison_selected_top_k",
        "poison_retrieved_but_not_used",
        "poison_influenced_response",
        "target_behavior_triggered",
        "attack_success",
        "attack_failure",
        "ground_truth_state",
        "ground_truth_label",
        # Post-hoc, same-query-timing-violating evidence (Charter Section 6).
        "counterfactually_influential",
        "counterfactual_influence",
        "counterfactual_influence_established",
        # Sleeper Memory Poisoning's own trigger label (Stage 6.8's explicit rule).
        "sleeper_trigger",
        "known_trigger_phrase",
        "is_sleeper_trigger",
        # Attribution outputs used as a RUNTIME defense input (Charter Section 6:
        # Attribution is a read-only, post-hoc analytical consumer; Stage 6.13
        # may consume its output for analysis, a live D1-D4 decision may not).
        "attribution_result",
        "attribution_origin",
        "attribution_influence",
    }
)


class EvaluatorOnlyLeakageError(ValueError):
    """Raised when `signals_used` (or `evidence_refs`) names a recognized
    evaluator-only field. See module docstring: this is a backstop, not the
    primary enforcement point."""


def _check_no_leakage(signals_used: Mapping[str, Any]) -> None:
    offending = sorted(set(signals_used.keys()) & FORBIDDEN_SIGNAL_KEYS)
    if offending:
        raise EvaluatorOnlyLeakageError(
            "MGP decision refused: signals_used contains evaluator-only field(s) "
            f"{offending!r}. A deployed defense may never condition on these -- "
            "see docs/phase6/MEMORY_GOVERNANCE_POLICY.md Section 7 and "
            "docs/phase6/DEFENSE_SIGNAL_CONTRACT.md."
        )


@dataclass(frozen=True)
class MGPDecisionRecord:
    """One immutable Memory Governance Policy decision.

    `decision_id` is content-derived (never `uuid4()`) -- see `mint_decision_id()`
    below, mirroring Phase 1's memory-record identity discipline and Phase 5's
    `Phase5Event.event_id` discipline.
    """

    decision_id: str
    candidate_memory_id: str
    policy_version: str
    signals_used: Mapping[str, Any]
    action: str
    resulting_state: Optional[str]
    reason: str
    run_id: str
    episode_id: Optional[str]
    timestamp: str  # ISO-8601, human-audit only -- never used for ordering logic
    evidence_refs: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.action not in ACTIONS:
            raise ValueError(f"Unknown MGP action: {self.action!r}")
        expected_state = resulting_state_for(self.action)
        if self.resulting_state != expected_state:
            raise ValueError(
                f"resulting_state {self.resulting_state!r} does not match what "
                f"action {self.action!r} produces ({expected_state!r}); "
                "resulting_state must never be set independently of the action "
                "that produced it (states.py is the single source of truth)."
            )
        if self.resulting_state is not None and self.resulting_state not in SECURITY_STATES:
            raise ValueError(f"Unknown MGP security state: {self.resulting_state!r}")
        if not self.reason or not self.reason.strip():
            raise ValueError(
                "MGPDecisionRecord.reason must be a non-empty, evidence-grounded "
                "explanation -- see Policy document Section 4: never fabricated "
                "independently of signals_used."
            )
        if not self.evidence_refs:
            raise ValueError(
                "MGPDecisionRecord.evidence_refs must cite at least one real "
                "Phase 3/5 event id -- a decision with no evidence reference is "
                "a bare claim, forbidden by Policy document Section 4."
            )
        _check_no_leakage(self.signals_used)

    def identity_fields(self) -> Tuple[Any, ...]:
        """The ordered tuple `decision_id` is derived from (Policy document
        Section 6). Deliberately excludes `timestamp` and `reason` (human-audit
        text, not part of the decision's defining identity) -- mirrors
        `reproducibility.py`'s own "exclude generation timestamp" discipline.
        """
        return (
            self.candidate_memory_id,
            self.policy_version,
            tuple(sorted(self.signals_used.items())),
            self.action,
            self.run_id,
        )


def mint_decision_id(
    candidate_memory_id: str,
    policy_version: str,
    signals_used: Mapping[str, Any],
    action: str,
    run_id: str,
) -> str:
    """Deterministic decision identity -- SHA-256 over the same defining fields
    `identity_fields()` returns, via the repository's one canonical fingerprint
    primitive (never `uuid4()`, never Python's `hash()`). Two calls with
    identical arguments always produce the same id."""
    return "MGPDEC-" + fingerprint(
        (
            candidate_memory_id,
            policy_version,
            tuple(sorted(signals_used.items())),
            action,
            run_id,
        )
    )


def build_decision(
    *,
    candidate_memory_id: str,
    signals_used: Mapping[str, Any],
    action: str,
    reason: str,
    run_id: str,
    episode_id: Optional[str],
    timestamp: str,
    evidence_refs: Sequence[str],
    policy_version: str = CURRENT_POLICY_VERSION,
) -> MGPDecisionRecord:
    """Convenience constructor: mints `decision_id` and `resulting_state`
    consistently rather than requiring every caller to reimplement that
    bookkeeping. This is the intended construction path for Stages 6.5-6.7's
    components -- `MGPDecisionRecord(...)` directly is only for tests."""
    decision_id = mint_decision_id(
        candidate_memory_id, policy_version, signals_used, action, run_id
    )
    return MGPDecisionRecord(
        decision_id=decision_id,
        candidate_memory_id=candidate_memory_id,
        policy_version=policy_version,
        signals_used=dict(signals_used),
        action=action,
        resulting_state=resulting_state_for(action),
        reason=reason,
        run_id=run_id,
        episode_id=episode_id,
        timestamp=timestamp,
        evidence_refs=tuple(evidence_refs),
    )
