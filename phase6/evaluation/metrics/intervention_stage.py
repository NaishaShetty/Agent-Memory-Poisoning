"""Phase 6.12 -- the Intervention Stage taxonomy: the single mechanism every
other metric in this module builds on to avoid collapsing "the defense
worked" into one ambiguous category.

WHY THIS EXISTS (Section 35 of the Phase 6 brief, made real)
--------------------------------------------------------------------------------
"A system may have high detection but low prevention, or low detection but
strong retrieval containment. These are scientifically different outcomes."
Every metric in `defense_metrics.py`/`security_metrics.py` that reports a
single "success" number is REQUIRED to also report the distribution across
this taxonomy -- never a bare rate with no breakdown.

MUTUAL EXCLUSIVITY AND PRIORITY ORDER
--------------------------------------------------------------------------------
Exactly one stage applies to a given memory/attack instance, decided by a
fixed priority order (earliest lifecycle intervention wins, since an item
blocked at admission never reaches retrieval and so on): admission -> retrieval
-> propagation -> sleeper -> (whatever happened after exposure, which requires
REAL counterfactual evidence, never inferred from exposure alone -- Charter
Section 6 / Attribution's own "exposed != used != influenced" discipline,
enforced here identically).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from phase6.defense.policy.states import BLOCK, DOWNRANK, QUARANTINE


class InterventionStage(str, Enum):
    """Closed vocabulary. `str` base lets these serialize as plain strings
    (JSONL-friendly, matching every other ledger in this project)."""

    PREVENTED_AT_ADMISSION = "PREVENTED_AT_ADMISSION"
    PREVENTED_AT_RETRIEVAL = "PREVENTED_AT_RETRIEVAL"
    CONTAINED_AT_PROPAGATION = "CONTAINED_AT_PROPAGATION"
    DETECTED_SLEEPER_PRE_ACTIVATION = "DETECTED_SLEEPER_PRE_ACTIVATION"
    INFLUENCE_STATUS_UNKNOWN = "INFLUENCE_STATUS_UNKNOWN"
    CONFIRMED_NO_INFLUENCE = "CONFIRMED_NO_INFLUENCE"
    CONFIRMED_INFLUENCED_UNMITIGATED = "CONFIRMED_INFLUENCED_UNMITIGATED"
    CONFIRMED_INFLUENCED_THEN_RECOVERED = "CONFIRMED_INFLUENCED_THEN_RECOVERED"


# Stages that count as the defense having "prevented or neutralized" an
# attack attempt, for Defense Success Rate (defense_metrics.py) -- the ONLY
# place this grouping is used; every other report must show the full,
# ungrouped stage breakdown too (Section 35's own instruction).
NEUTRALIZED_STAGES = frozenset(
    {
        InterventionStage.PREVENTED_AT_ADMISSION,
        InterventionStage.PREVENTED_AT_RETRIEVAL,
        InterventionStage.CONTAINED_AT_PROPAGATION,
        InterventionStage.DETECTED_SLEEPER_PRE_ACTIVATION,
        InterventionStage.CONFIRMED_NO_INFLUENCE,
        InterventionStage.CONFIRMED_INFLUENCED_THEN_RECOVERED,
    }
)


@dataclass(frozen=True)
class InterventionEvidence:
    """Everything needed to classify one memory/attack instance's outcome.

    `counterfactual_influence` and `later_quarantined` are EVALUATOR-ONLY /
    ATTRIBUTION-DERIVED fields, legitimate for METRICS computation (this
    module), never for a runtime defense decision (Charter Section 6) -- the
    same allow-for-metrics/forbid-for-decisions split Stage 6.9's
    `compute_metrics()` already established.
    """

    admission_action: Optional[str] = None
    retrieval_eligible: Optional[bool] = None  # False = excluded from the candidate pool this call
    retrieval_action: Optional[str] = None
    propagation_action: Optional[str] = None
    sleeper_action: Optional[str] = None
    # None = no counterfactual test was ever run (Attribution's own honest
    # "not established" case) -- never defaulted to False.
    counterfactual_influence: Optional[bool] = None
    # Only meaningful when counterfactual_influence is True: was this same
    # memory/source later found QUARANTINED/BLOCKED in a subsequent
    # decision (real recovery), as opposed to influence with no later
    # containment ever observed.
    later_quarantined: Optional[bool] = None


def classify_intervention_stage(evidence: InterventionEvidence) -> InterventionStage:
    """The one function every metric in this package routes through.
    Priority order matches the real lifecycle: an item stopped at admission
    never reaches retrieval, etc. -- see module docstring.
    """
    if evidence.admission_action == BLOCK:
        return InterventionStage.PREVENTED_AT_ADMISSION
    if evidence.admission_action == QUARANTINE:
        return InterventionStage.PREVENTED_AT_ADMISSION

    if evidence.retrieval_eligible is False:
        return InterventionStage.PREVENTED_AT_RETRIEVAL
    if evidence.retrieval_action in (QUARANTINE, DOWNRANK):
        return InterventionStage.PREVENTED_AT_RETRIEVAL

    if evidence.propagation_action == QUARANTINE:
        return InterventionStage.CONTAINED_AT_PROPAGATION

    if evidence.sleeper_action == QUARANTINE:
        return InterventionStage.DETECTED_SLEEPER_PRE_ACTIVATION

    # Nothing intervened before exposure -- what happens next is governed
    # STRICTLY by real counterfactual evidence, never inferred.
    if evidence.counterfactual_influence is None:
        return InterventionStage.INFLUENCE_STATUS_UNKNOWN
    if evidence.counterfactual_influence is False:
        return InterventionStage.CONFIRMED_NO_INFLUENCE
    # counterfactual_influence is True from here on.
    if evidence.later_quarantined is True:
        return InterventionStage.CONFIRMED_INFLUENCED_THEN_RECOVERED
    return InterventionStage.CONFIRMED_INFLUENCED_UNMITIGATED
