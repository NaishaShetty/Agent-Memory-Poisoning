"""Phase 6.18 -- the F1-F14 failure-cause taxonomy (brief-specified), plus one
disclosed, clearly-labeled proposed extension this stage's own synthesis work
found necessary.

WHY AN EXTENSION WAS NEEDED, DISCLOSED HERE RATHER THAN FORCE-FITTING
--------------------------------------------------------------------------------
Stage 6.10/6.15's AgentPoison finding does not fit any of F1-F14 cleanly: F2
("poison hidden from admission detector") implies a detector EXISTS and
failed to catch something; AgentPoison's real attack surface (a query-side
embedding trigger) has NO Phase 6 mechanism examining it AT ALL -- there is
nothing to have failed. Rather than mislabel this as F2 (which would imply a
detection attempt was made and missed), this module adds F15 as an explicit,
disclosed, clearly-marked-as-NOT-part-of-the-original-brief extension. Every
other case in the catalog uses only the original F1-F14.
"""

from __future__ import annotations

from enum import Enum


class FailureCause(str, Enum):
    F1_POISON_ADMITTED = "F1_POISON_ADMITTED"
    F2_POISON_HIDDEN_FROM_ADMISSION_DETECTOR = "F2_POISON_HIDDEN_FROM_ADMISSION_DETECTOR"
    F3_POISON_RETRIEVED = "F3_POISON_RETRIEVED"
    F4_POISON_SELECTED = "F4_POISON_SELECTED"
    F5_POISON_EXPOSED = "F5_POISON_EXPOSED"
    F6_POISON_PROPAGATED = "F6_POISON_PROPAGATED"
    F7_POISON_INFLUENCED_RESPONSE = "F7_POISON_INFLUENCED_RESPONSE"
    F8_SLEEPER_ACTIVATED = "F8_SLEEPER_ACTIVATED"
    F9_BENIGN_MEMORY_INCORRECTLY_CLASSIFIED = "F9_BENIGN_MEMORY_INCORRECTLY_CLASSIFIED"
    F10_ATTACKER_ADAPTED = "F10_ATTACKER_ADAPTED"
    F11_DEFENSE_EVIDENCE_UNAVAILABLE = "F11_DEFENSE_EVIDENCE_UNAVAILABLE"
    F12_DEFENSE_POLICY_CONFLICT = "F12_DEFENSE_POLICY_CONFLICT"
    F13_DEFENSE_CAUSED_UTILITY_REGRESSION = "F13_DEFENSE_CAUSED_UTILITY_REGRESSION"
    F14_ENVIRONMENT_INFRASTRUCTURE_FAILURE = "F14_ENVIRONMENT_INFRASTRUCTURE_FAILURE"
    # DISCLOSED EXTENSION -- not in the original brief's F1-F14. See module
    # docstring for why F2 does not honestly cover this case.
    F15_NO_APPLICABLE_MECHANISM_PROPOSED_EXTENSION = "F15_NO_APPLICABLE_MECHANISM_PROPOSED_EXTENSION"


ORIGINAL_BRIEF_CAUSES = frozenset(FailureCause) - {FailureCause.F15_NO_APPLICABLE_MECHANISM_PROPOSED_EXTENSION}
