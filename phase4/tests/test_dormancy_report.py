"""Unit tests for `phase4.shared.dormancy_report` (Phase 4.11 gap-closing
shared observability helper)."""

from __future__ import annotations

import unittest

from phase3.evaluation.agent.conditions import CONDITION_RETRIEVED_MEMORY
from phase3.evaluation.agent.outcomes import EXECUTION_STATUS_SUCCESS, AgentExecutionResult
from phase3.evaluation.agent_runtime.runner import AgentRunOutcome

from phase4.shared.dormancy_report import (
    STATE_IN_CANDIDATE_POOL,
    STATE_NOT_RETRIEVED,
    STATE_SELECTED_TOP_K,
    describe_dormancy,
)


def _outcome(retrieved, selected) -> AgentRunOutcome:
    exec_result = AgentExecutionResult(
        task_id="t", condition=CONDITION_RETRIEVED_MEMORY, answer="a",
        execution_status=EXECUTION_STATUS_SUCCESS, selected_memory_ids=tuple(selected),
        used_memory_ids=None, execution_metadata={},
    )
    return AgentRunOutcome(
        task_id="t", condition=CONDITION_RETRIEVED_MEMORY, memory_available=True,
        retrieved_memory_ids=tuple(retrieved), selected_memory_ids=tuple(selected),
        exposed_memory_ids=tuple(selected), agent_visible_context={}, execution_result=exec_result,
        attempts=(), generation_config_fingerprint="fp", model_metadata={}, total_latency_sec=0.0,
        foundation_identity={"foundation_id": "mem0"},
    )


class DescribeDormancyTests(unittest.TestCase):
    def test_selected_id_is_selected_top_k(self) -> None:
        outcome = _outcome(retrieved=["a", "b"], selected=["a"])
        states = describe_dormancy(outcome, ["a"])
        self.assertEqual(states["a"].state, STATE_SELECTED_TOP_K)

    def test_retrieved_but_not_selected_is_in_candidate_pool(self) -> None:
        outcome = _outcome(retrieved=["a", "b"], selected=["b"])
        states = describe_dormancy(outcome, ["a"])
        self.assertEqual(states["a"].state, STATE_IN_CANDIDATE_POOL)

    def test_absent_entirely_is_not_retrieved(self) -> None:
        outcome = _outcome(retrieved=["b"], selected=["b"])
        states = describe_dormancy(outcome, ["a"])
        self.assertEqual(states["a"].state, STATE_NOT_RETRIEVED)

    def test_multiple_ids_classified_independently(self) -> None:
        outcome = _outcome(retrieved=["a", "b"], selected=["a"])
        states = describe_dormancy(outcome, ["a", "b", "c"])
        self.assertEqual(states["a"].state, STATE_SELECTED_TOP_K)
        self.assertEqual(states["b"].state, STATE_IN_CANDIDATE_POOL)
        self.assertEqual(states["c"].state, STATE_NOT_RETRIEVED)


if __name__ == "__main__":
    unittest.main()
