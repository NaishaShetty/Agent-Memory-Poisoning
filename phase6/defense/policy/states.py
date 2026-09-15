"""Phase 6.3 -- the Memory Governance Policy (MGP) state and action vocabulary.

See `docs/phase6/MEMORY_GOVERNANCE_POLICY.md` for the full justification of every
state, every action, and every transition below -- this module is the vocabulary
made real code, not a place to re-derive that reasoning.

THIS IS A SEPARATE VOCABULARY FROM PHASE 3's LIFECYCLE STATUS
--------------------------------------------------------------------------------
Phase 3's `memory_versioning.py` defines `active` / `superseded` / `retired` --
a completely different question ("which version of this memory identity is
current") from what this module answers ("should this memory be trusted"). This
module never imports from `phase3.evaluation.foundations.memory_versioning`, never
reuses its vocabulary, and is never imported by it. A memory can be
`lifecycle_status=active` (Phase 3) and `security_state=QUARANTINED` (Phase 6)
simultaneously; neither phase's code needs to know the other's vocabulary exists.

THIS IS ALSO A SEPARATE VOCABULARY FROM THE NINE-STATE ATTACK GROUND TRUTH
--------------------------------------------------------------------------------
`POISON_NOT_ADMITTED` .. `ATTACK_FAILURE` (Phase 4/5) is evaluator-only ground
truth about what an attack actually achieved. `SecurityState` is what a deployed
defense, using only legitimately-available signals, concluded. A real defense may
reach `TRUSTED` on a memory whose evaluator-only ground truth is
`POISON_INFLUENCED_RESPONSE` -- that is a defense FAILURE, not a contradiction in
the vocabulary, and Stage 6.18's failure analysis depends on being able to state
exactly that without the two vocabularies being conflated into one.
"""

from __future__ import annotations

from typing import Dict, FrozenSet, Optional, Tuple

# ---------------------------------------------------------------------------
# Security states (Policy document Section 2.1 -- all six of the brief's
# proposed states, individually justified there, none added or dropped).
# ---------------------------------------------------------------------------

UNASSESSED = "UNASSESSED"
TRUSTED = "TRUSTED"
SUSPICIOUS = "SUSPICIOUS"
QUARANTINED = "QUARANTINED"
BLOCKED = "BLOCKED"
RELEASED = "RELEASED"

SECURITY_STATES: Tuple[str, ...] = (
    UNASSESSED,
    TRUSTED,
    SUSPICIOUS,
    QUARANTINED,
    BLOCKED,
    RELEASED,
)

# ---------------------------------------------------------------------------
# Actions (Policy document Section 3 -- the brief's six plus the one disclosed,
# necessary addition, RELEASE, without which QUARANTINED -> RELEASED is
# unreachable).
# ---------------------------------------------------------------------------

ALLOW = "ALLOW"
ALLOW_WITH_RESTRICTION = "ALLOW_WITH_RESTRICTION"
REQUIRE_VALIDATION = "REQUIRE_VALIDATION"
QUARANTINE = "QUARANTINE"
BLOCK = "BLOCK"
RELEASE = "RELEASE"
DOWNRANK = "DOWNRANK"  # query-local only -- see PERSISTENT_ACTIONS below

ACTIONS: Tuple[str, ...] = (
    ALLOW,
    ALLOW_WITH_RESTRICTION,
    REQUIRE_VALIDATION,
    QUARANTINE,
    BLOCK,
    RELEASE,
    DOWNRANK,
)

# DOWNRANK is the only action that never writes a state transition (Policy
# document Section 3's D3-local / persistent split). Every other action is
# persistent and MUST have an entry in ACTION_RESULTING_STATE.
PERSISTENT_ACTIONS: FrozenSet[str] = frozenset(ACTIONS) - {DOWNRANK}

# The resulting state an action produces is independent of which specific
# `from_state` it was applied to (Policy document Section 3's table) -- what
# actually gates legality is ALLOWED_TRANSITIONS below, keyed by (from_state,
# to_state), not by action name, since several actions can produce the same
# resulting state from different starting states.
ACTION_RESULTING_STATE: Dict[str, Optional[str]] = {
    ALLOW: TRUSTED,
    ALLOW_WITH_RESTRICTION: SUSPICIOUS,
    REQUIRE_VALIDATION: SUSPICIOUS,
    QUARANTINE: QUARANTINED,
    BLOCK: BLOCKED,
    RELEASE: RELEASED,
    DOWNRANK: None,
}

# ---------------------------------------------------------------------------
# Transition legality (Policy document Section 2.2's table, made real).
# A no-op (from_state == to_state) is always legal for every state except the
# absorbing states BLOCKED (terminal for v1) and the sentinel UNASSESSED
# (nothing legitimately "re-assesses to still unassessed").
# ---------------------------------------------------------------------------

ALLOWED_TRANSITIONS: FrozenSet[Tuple[str, str]] = frozenset(
    {
        # From UNASSESSED: any first assessment is legal.
        (UNASSESSED, TRUSTED),
        (UNASSESSED, SUSPICIOUS),
        (UNASSESSED, QUARANTINED),
        (UNASSESSED, BLOCKED),
        # From TRUSTED: later evidence can raise concern, but never straight to
        # BLOCKED (Policy document Section 2.2's rationale: every BLOCK must
        # have an intermediate SUSPICIOUS/QUARANTINED record in its history).
        (TRUSTED, SUSPICIOUS),
        (TRUSTED, QUARANTINED),
        (TRUSTED, TRUSTED),  # no-op: re-confirmed trusted
        # From SUSPICIOUS: can clear or escalate.
        (SUSPICIOUS, TRUSTED),
        (SUSPICIOUS, QUARANTINED),
        (SUSPICIOUS, SUSPICIOUS),  # no-op: re-confirmed suspicious
        # From QUARANTINED: resolves via RELEASE or BLOCK only -- never
        # directly back to TRUSTED (Section 2.2's rationale for keeping
        # RELEASED distinct and non-collapsible).
        (QUARANTINED, RELEASED),
        (QUARANTINED, BLOCKED),
        (QUARANTINED, QUARANTINED),  # no-op: still under review
        # From RELEASED: can be re-flagged by new evidence, in either
        # direction, but not straight to BLOCKED (same rationale as TRUSTED).
        (RELEASED, SUSPICIOUS),
        (RELEASED, QUARANTINED),
        (RELEASED, RELEASED),  # no-op: re-confirmed released
        # BLOCKED is terminal for v1 -- only a no-op is legal.
        (BLOCKED, BLOCKED),
    }
)


class IllegalTransitionError(ValueError):
    """Raised when a decision would move a memory through an undefined edge.

    This is a defense-correctness bug if it is ever raised in real use (it means
    a caller is trying to apply an action inconsistent with Section 2.2's frozen
    table), not a normal outcome to catch-and-ignore.
    """


def resulting_state_for(action: str) -> Optional[str]:
    """The state an action produces, or `None` for a query-local action (DOWNRANK)."""
    if action not in ACTIONS:
        raise ValueError(f"Unknown MGP action: {action!r}")
    return ACTION_RESULTING_STATE[action]


def validate_transition(from_state: str, action: str) -> Optional[str]:
    """Validate `action` applied to a memory currently in `from_state`.

    Returns the resulting state (or `None` for DOWNRANK, which changes no
    persisted state). Raises `IllegalTransitionError` if the resulting edge is
    not in `ALLOWED_TRANSITIONS`.
    """
    if from_state not in SECURITY_STATES:
        raise ValueError(f"Unknown MGP security state: {from_state!r}")
    to_state = resulting_state_for(action)
    if to_state is None:
        return None  # DOWNRANK: no persisted-state edge to validate
    if (from_state, to_state) not in ALLOWED_TRANSITIONS:
        raise IllegalTransitionError(
            f"MGP policy forbids {from_state!r} -> {to_state!r} via action {action!r}"
        )
    return to_state
