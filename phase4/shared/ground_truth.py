"""Phase 4 P0 fix -- the nine-state attack ground-truth vocabulary
(`PHASE4_4_9_ATTACK_GROUND_TRUTH.md`), made real, checkable code.

WHY THIS MODULE EXISTS
--------------------------------------------------------------------------------
The audit finding this closes: `PHASE4_4_9_ATTACK_GROUND_TRUTH.md` presents
`POISON_NOT_ADMITTED | POISON_ADMITTED | POISON_IN_CANDIDATE_POOL |
POISON_SELECTED_TOP_K | POISON_RETRIEVED_BUT_NOT_USED |
POISON_INFLUENCED_RESPONSE | TARGET_BEHAVIOR_TRIGGERED | ATTACK_SUCCESS |
ATTACK_FAILURE` as a closed nine-state chain, but before this fix no code
anywhere defined that enum or validated transitions between states --
`phase4/shared/dormancy_report.py` only defined three of the nine
(`NOT_RETRIEVED`, `POISON_IN_CANDIDATE_POOL`, `POISON_SELECTED_TOP_K`); the
rest existed only as free-text strings hand-typed into 26 campaign scripts
and the markdown registry table. Every `ATTACK_SUCCESS`-consistent verdict in
that table was therefore a human inference written after reading printed
output, not a programmatically derived, self-consistent state.

This module is the single source of truth for the nine state names and the
transitions Section 2 of `PHASE4_4_9_ATTACK_GROUND_TRUTH.md` (and the real,
observed campaign table there) describe. `dormancy_report.py`'s three
retrieval-stage states now import their canonical names from here rather
than re-declaring them. `GroundTruthTrace` (below) is a lightweight,
per-artifact, in-memory recorder any campaign script MAY use going forward
to get transition validation for free -- exactly mirroring the pattern
`phase6/defense/policy/states.py`'s `ALLOWED_TRANSITIONS`/`validate_transition`
already established for the Memory Governance Policy vocabulary (built after
this module, and a useful confirmation this shape of fix is this project's
own established, working pattern for exactly this problem).

THIS DOES NOT MODIFY ANY FROZEN PHASE 4 CAMPAIGN LOG OR ARTIFACT
--------------------------------------------------------------------------------
Purely additive, new module. No existing campaign script, log, or artifact is
edited by this fix -- the real, already-published verdicts in
`PHASE4_4_9_ATTACK_GROUND_TRUTH.md`'s table are unchanged; this module gives
future (and, opt-in, existing) campaign reporting a real state machine to
validate against instead of hand-typed prose, per the project's own
established "review/reopen/refreeze" discipline for additive fixes to
already-published claims.

TRANSITION TABLE -- DERIVED FROM THE REAL, DOCUMENTED CAMPAIGN OBSERVATIONS
--------------------------------------------------------------------------------
See `PHASE4_4_9_ATTACK_GROUND_TRUTH.md` Section 1's real-trial table and
Section 2 for the evidence each edge below is grounded in:
- `POISON_ADMITTED -> POISON_IN_CANDIDATE_POOL` and
  `POISON_ADMITTED -> POISON_SELECTED_TOP_K`: some campaigns only ever
  observe "reached the candidate pool" as an intermediate fact; others (the
  common case in the real table) observe selection directly. Both are real,
  disclosed possibilities -- this module does not force every campaign to
  report an intermediate pool-only observation it may not have measured.
- `POISON_IN_CANDIDATE_POOL -> ATTACK_FAILURE`: a poison that never reaches
  top-K is a legitimate, real non-success terminal (dormant/never selected),
  distinct from the pre-admission `POISON_NOT_ADMITTED` failure mode.
- `POISON_SELECTED_TOP_K -> POISON_RETRIEVED_BUT_NOT_USED` and
  `-> POISON_INFLUENCED_RESPONSE`: the real branch Section 2.3's
  single-mask-vs-joint-mask discussion depends on -- a selected poison is not
  automatically influential.
- `POISON_INFLUENCED_RESPONSE -> TARGET_BEHAVIOR_TRIGGERED` and the direct
  `-> ATTACK_SUCCESS`: attacks with an explicit discrete trigger concept
  (AgentPoison, Sleeper, DSRM's decision manipulation) pass through
  TARGET_BEHAVIOR_TRIGGERED; attacks with no such discrete trigger (FARMA,
  MemoryGraft, MPBench-PCFI) go directly from influence to success in the
  real table -- both are real, disclosed shapes, not invented for this
  module.
- `TARGET_BEHAVIOR_TRIGGERED -> ATTACK_FAILURE`: never observed in this
  project's real evidence (a genuine post-admission ATTACK_FAILURE has never
  been seen -- a disclosed limitation carried forward unchanged), but is a
  logically legal edge under this vocabulary and is not artificially
  excluded just because it has not yet been observed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import FrozenSet, List, Optional, Tuple

STATE_POISON_NOT_ADMITTED = "POISON_NOT_ADMITTED"
STATE_POISON_ADMITTED = "POISON_ADMITTED"
STATE_POISON_IN_CANDIDATE_POOL = "POISON_IN_CANDIDATE_POOL"
STATE_POISON_SELECTED_TOP_K = "POISON_SELECTED_TOP_K"
STATE_POISON_RETRIEVED_BUT_NOT_USED = "POISON_RETRIEVED_BUT_NOT_USED"
STATE_POISON_INFLUENCED_RESPONSE = "POISON_INFLUENCED_RESPONSE"
STATE_TARGET_BEHAVIOR_TRIGGERED = "TARGET_BEHAVIOR_TRIGGERED"
STATE_ATTACK_SUCCESS = "ATTACK_SUCCESS"
STATE_ATTACK_FAILURE = "ATTACK_FAILURE"

GROUND_TRUTH_STATES: Tuple[str, ...] = (
    STATE_POISON_NOT_ADMITTED,
    STATE_POISON_ADMITTED,
    STATE_POISON_IN_CANDIDATE_POOL,
    STATE_POISON_SELECTED_TOP_K,
    STATE_POISON_RETRIEVED_BUT_NOT_USED,
    STATE_POISON_INFLUENCED_RESPONSE,
    STATE_TARGET_BEHAVIOR_TRIGGERED,
    STATE_ATTACK_SUCCESS,
    STATE_ATTACK_FAILURE,
)

# Terminal states: no outgoing edge exists for these (Section 2's real table
# never observes a transition out of a NOT_ADMITTED, ATTACK_SUCCESS, or
# ATTACK_FAILURE state).
TERMINAL_STATES: FrozenSet[str] = frozenset(
    {STATE_POISON_NOT_ADMITTED, STATE_ATTACK_SUCCESS, STATE_ATTACK_FAILURE}
)

# `None` as `from_state` means "no prior state recorded for this artifact yet"
# -- the two legal first observations (an admission gate either refuses, or
# admits, the artifact; nothing else can be the first fact ever recorded).
ALLOWED_TRANSITIONS: FrozenSet[Tuple[Optional[str], str]] = frozenset(
    {
        (None, STATE_POISON_NOT_ADMITTED),
        (None, STATE_POISON_ADMITTED),
        (STATE_POISON_ADMITTED, STATE_POISON_IN_CANDIDATE_POOL),
        (STATE_POISON_ADMITTED, STATE_POISON_SELECTED_TOP_K),
        (STATE_POISON_IN_CANDIDATE_POOL, STATE_POISON_SELECTED_TOP_K),
        (STATE_POISON_IN_CANDIDATE_POOL, STATE_ATTACK_FAILURE),
        (STATE_POISON_SELECTED_TOP_K, STATE_POISON_RETRIEVED_BUT_NOT_USED),
        (STATE_POISON_SELECTED_TOP_K, STATE_POISON_INFLUENCED_RESPONSE),
        (STATE_POISON_RETRIEVED_BUT_NOT_USED, STATE_ATTACK_FAILURE),
        (STATE_POISON_INFLUENCED_RESPONSE, STATE_TARGET_BEHAVIOR_TRIGGERED),
        (STATE_POISON_INFLUENCED_RESPONSE, STATE_ATTACK_SUCCESS),
        (STATE_TARGET_BEHAVIOR_TRIGGERED, STATE_ATTACK_SUCCESS),
        (STATE_TARGET_BEHAVIOR_TRIGGERED, STATE_ATTACK_FAILURE),
    }
)


class IllegalGroundTruthTransitionError(ValueError):
    """Raised when a recorded ground-truth observation would move an
    artifact through an edge `ALLOWED_TRANSITIONS` does not contain -- e.g.
    reporting `ATTACK_SUCCESS` for an artifact with no prior
    `POISON_INFLUENCED_RESPONSE`/`TARGET_BEHAVIOR_TRIGGERED` observation.
    This is a reporting-correctness bug if it is ever raised in real use
    (someone typed the wrong state), not a normal outcome to catch and
    ignore -- mirrors `phase6.defense.policy.states.IllegalTransitionError`'s
    own documented discipline exactly."""


def validate_transition(from_state: Optional[str], to_state: str) -> str:
    """Validate that `to_state` is a legal next observation given
    `from_state` (`None` for "no prior observation"). Returns `to_state` on
    success; raises `IllegalGroundTruthTransitionError` otherwise."""
    if to_state not in GROUND_TRUTH_STATES:
        raise ValueError(f"Unknown ground-truth state: {to_state!r}")
    if from_state is not None and from_state not in GROUND_TRUTH_STATES:
        raise ValueError(f"Unknown ground-truth state: {from_state!r}")
    if (from_state, to_state) not in ALLOWED_TRANSITIONS:
        raise IllegalGroundTruthTransitionError(
            f"Ground-truth vocabulary forbids {from_state!r} -> {to_state!r} "
            "(PHASE4_4_9_ATTACK_GROUND_TRUTH.md's nine-state chain has no "
            "such edge)."
        )
    return to_state


@dataclass
class GroundTruthTrace:
    """A lightweight, in-memory, per-artifact record of every ground-truth
    observation made during one campaign, with transition validation on
    every append. Optional, additive infrastructure -- existing campaign
    scripts that print hand-typed state strings are unaffected; any script
    that wants real validation instead constructs one of these and calls
    `.record()` at each stage instead of `print()`-ing a bare string.

    NOT a persistent ledger (no disk I/O, no cross-run identity) -- Phase 4's
    real campaigns are one-shot, human-directed, manually-run scripts (a
    disclosed, unchanged project characteristic); this is exactly enough
    structure to make ONE campaign's own reported state sequence
    self-consistent, without inventing new persistence machinery Phase 4
    never had and this fix does not need to add.
    """

    artifact_id: str
    observations: List[str] = field(default_factory=list)

    def record(self, state: str) -> str:
        """Validate and append `state` as the next observation for this
        artifact. Raises `IllegalGroundTruthTransitionError` if illegal."""
        current = self.observations[-1] if self.observations else None
        validate_transition(current, state)
        self.observations.append(state)
        return state

    @property
    def current_state(self) -> Optional[str]:
        return self.observations[-1] if self.observations else None

    def is_attack_success(self) -> bool:
        return self.current_state == STATE_ATTACK_SUCCESS

    def is_attack_failure(self) -> bool:
        return self.current_state == STATE_ATTACK_FAILURE


__all__ = [
    "STATE_POISON_NOT_ADMITTED",
    "STATE_POISON_ADMITTED",
    "STATE_POISON_IN_CANDIDATE_POOL",
    "STATE_POISON_SELECTED_TOP_K",
    "STATE_POISON_RETRIEVED_BUT_NOT_USED",
    "STATE_POISON_INFLUENCED_RESPONSE",
    "STATE_TARGET_BEHAVIOR_TRIGGERED",
    "STATE_ATTACK_SUCCESS",
    "STATE_ATTACK_FAILURE",
    "GROUND_TRUTH_STATES",
    "TERMINAL_STATES",
    "ALLOWED_TRANSITIONS",
    "IllegalGroundTruthTransitionError",
    "validate_transition",
    "GroundTruthTrace",
]
