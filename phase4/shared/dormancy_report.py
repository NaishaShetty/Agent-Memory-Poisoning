"""Phase 4.11 gap-closing -- a shared, reusable ground-truth-state reporter.

Built to close two disclosed gaps from PHASE4_4_11_PHASE4_REPRODUCIBILITY.md
Section 7: (1) six pre-Sleeper campaign scripts only ever printed
`selected_memory_ids`, never `retrieved_memory_ids`, so their own real runs
could not distinguish POISON_IN_CANDIDATE_POOL from POISON_SELECTED_TOP_K
the way PHASE4_4_9_ATTACK_GROUND_TRUTH.md's registry needs; (2) no shared
orchestration piece existed for this specific, genuinely reusable
observation (as opposed to full campaign orchestration, which 4.7
deliberately did NOT unify across attacks, since `generate()`/`inject()`
are real attack-specific mechanisms -- ground-truth-STATE REPORTING for an
already-produced `AgentRunOutcome`, by contrast, is identical logic for
every attack, exactly like `retrieve_select_generate()` itself was found to
be in Phase 4.7).

Reads ONLY `AgentRunOutcome.retrieved_memory_ids`/`selected_memory_ids` --
both already returned by `phase4.shared.campaign_runner.retrieve_select_generate()`
for every attack, confirmed by direct inspection, not new data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from phase3.evaluation.agent_runtime.runner import AgentRunOutcome
from phase4.shared.ground_truth import (
    STATE_POISON_IN_CANDIDATE_POOL,
    STATE_POISON_SELECTED_TOP_K,
)

STATE_NOT_RETRIEVED = "NOT_RETRIEVED"  # not even in the raw candidate pool -- pre-vocabulary, not one of the nine canonical states (there is no admitted-but-unretrieved state in PHASE4_4_9_ATTACK_GROUND_TRUTH.md)
# The two canonical names below are re-exported here (not re-declared) so this
# module's three-way split stays a single source of truth with
# `phase4.shared.ground_truth`'s nine-state vocabulary -- see that module's
# docstring for the P0 fix this closes.
STATE_IN_CANDIDATE_POOL = STATE_POISON_IN_CANDIDATE_POOL
STATE_SELECTED_TOP_K = STATE_POISON_SELECTED_TOP_K


@dataclass(frozen=True)
class DormancyState:
    memory_id: str
    state: str


def describe_dormancy(outcome: AgentRunOutcome, memory_ids: Sequence[str]) -> Mapping[str, DormancyState]:
    """For each id in `memory_ids`, classify its ground-truth retrieval
    state for this one `AgentRunOutcome` -- the exact three-way split
    PHASE4_4_2_COMMON_ATTACK_CONTRACT.md Section 7a's vocabulary
    distinguishes (assumes the id was already ADMITTED; that stage is
    attack-specific and reported separately by each attack's own
    injector)."""
    result = {}
    for mid in memory_ids:
        if mid in outcome.selected_memory_ids:
            state = STATE_SELECTED_TOP_K
        elif mid in outcome.retrieved_memory_ids:
            state = STATE_IN_CANDIDATE_POOL
        else:
            state = STATE_NOT_RETRIEVED
        result[mid] = DormancyState(memory_id=mid, state=state)
    return result


def print_dormancy_report(label: str, outcome: AgentRunOutcome, memory_ids: Sequence[str]) -> None:
    """Convenience wrapper matching the print-style every real campaign
    script in this project already uses -- one line per artifact id."""
    states = describe_dormancy(outcome, memory_ids)
    for mid, ds in states.items():
        print(f"[{label}] {mid}: {ds.state}")


__all__ = [
    "STATE_NOT_RETRIEVED",
    "STATE_IN_CANDIDATE_POOL",
    "STATE_SELECTED_TOP_K",
    "DormancyState",
    "describe_dormancy",
    "print_dormancy_report",
]
