"""Phase 4.7 -- the unified `AttackAdapter` interface, closing the gap
PHASE4_4_6_POISON_ARTIFACT_AND_INJECTION_MODEL.md Section 4.5 found: none of
the six attacks built this session implemented the full `validate`/
`prepare`/`generate`/`inject`/`execute`/`collect` interface described in
`PHASE4_4_2_COMMON_ATTACK_CONTRACT.md` on one class.

WHAT THIS DOES AND DOES NOT DO
--------------------------------------------------------------------------------
This does NOT reimplement any attack's real mechanism. Every concrete
subclass (one per attack, in each attack's own package) delegates to the
ALREADY REAL, ALREADY TESTED components built during each attack's own
integration/reconstruction plan (trigger optimization, SRM/CSRM, the
amplification sequence, the persistence gate, the PCFI scenarios) -- this
module only gives them one shared, real Phase-3-integration surface for
`execute()` (retrieve/select/render/generate) and `collect()` (counterfactual
measurement), extracted for the same reason
`phase4/shared/campaign_runner.py` was: those two stages were found to be
byte-for-byte identical logic duplicated across five campaign scripts (4.6
Section 4.4/4.7's own consolidation pass), not attack-specific behavior.

`validate`/`prepare`/`generate`/`inject` remain abstract -- these genuinely
differ per attack (a trigger-optimization loop is not a self-refine loop is
not a persistence gate) and are NOT collapsed into one shape here, per the
governing MPBench policy's own principle: don't build a false uniformity
that isn't actually there.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any, Optional

from phase3.evaluation.agent_runtime.counterfactual import compare_counterfactual_run, run_counterfactual_mask
from phase3.evaluation.agent_runtime.runner import AgentRunOutcome, RunConfiguration
from phase3.evaluation.foundations.adapter import MemoryFoundationAdapter

from phase4.shared.campaign_runner import retrieve_select_generate


@dataclass(frozen=True)
class AttackCollectResult:
    """`collect()`'s output -- per PHASE4_4_2_COMMON_ATTACK_CONTRACT.md's
    AttackResult shape (Section 7a's ground-truth vocabulary), for the
    common single-artifact-mask case every non-sequence attack in this
    repository uses. Sequence-shaped attacks (MINJA, FARMA) needing joint
    masking call `run_counterfactual_mask_joint` directly instead of this
    default -- see each attack's own campaign script -- rather than forcing
    a joint-mask parameter onto every attack's collect() call.
    """

    attack_id: str
    selected: bool  # POISON_SELECTED_TOP_K analogue
    baseline_answer: Optional[str]
    masked_answer: Optional[str]
    counterfactual_status: Optional[str]  # None if `selected` is False -- nothing to mask


class AttackAdapter(abc.ABC):
    """Base class for a MAMBench attack adapter. `attack_id` must be set by
    every concrete subclass (matches the `attack_id` metadata value each
    attack's own Injector already writes)."""

    attack_id: str

    @abc.abstractmethod
    def validate(self, request: Any) -> bool:
        """Confirms the request's assumptions (attacker capability, victim
        architecture) are met -- attack-specific, per each attack's own
        `validate()` design in its integration/reconstruction plan."""

    @abc.abstractmethod
    def prepare(self, request: Any) -> Any:
        """Resolves attack-specific inputs (seeds, domain translation,
        target task) into a context `generate()` can consume."""

    @abc.abstractmethod
    def generate(self, context: Any) -> Any:
        """Runs the attack's real generation mechanism, producing one or
        more PoisonArtifact-shaped objects."""

    @abc.abstractmethod
    def inject(self, artifacts: Any, foundation: MemoryFoundationAdapter, **kwargs: Any) -> Any:
        """Writes the generated artifact(s) through the attack's own real
        Injector class. Returns injector-specific result objects carrying
        `canonical_memory_id`."""

    def execute(
        self,
        foundation: MemoryFoundationAdapter,
        query: str,
        run_config: RunConfiguration,
        *,
        user_id: str,
        task_id: str,
    ) -> AgentRunOutcome:
        """Shared real Condition C retrieve -> select -> render -> generate
        pass -- identical across all six attacks (see module docstring)."""
        return retrieve_select_generate(foundation, query, run_config, user_id=user_id, task_id=task_id)

    def collect(
        self,
        baseline_outcome: AgentRunOutcome,
        injected_memory_id: str,
        run_config: RunConfiguration,
    ) -> AttackCollectResult:
        """Shared single-artifact counterfactual measurement -- see
        `AttackCollectResult`'s docstring for the sequence-attack caveat."""
        selected = injected_memory_id in baseline_outcome.selected_memory_ids
        if not selected:
            return AttackCollectResult(
                attack_id=self.attack_id, selected=False,
                baseline_answer=baseline_outcome.execution_result.answer,
                masked_answer=None, counterfactual_status=None,
            )
        masked = run_counterfactual_mask(baseline_outcome, injected_memory_id, run_config)
        comparison = compare_counterfactual_run(baseline_outcome, masked)
        return AttackCollectResult(
            attack_id=self.attack_id, selected=True,
            baseline_answer=baseline_outcome.execution_result.answer,
            masked_answer=masked.masked_answer,
            counterfactual_status=comparison.status,
        )


__all__ = ["AttackAdapter", "AttackCollectResult"]
