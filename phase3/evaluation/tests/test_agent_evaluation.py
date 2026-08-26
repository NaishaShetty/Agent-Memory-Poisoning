"""Phase 3.2-E tests for `phase3/evaluation/agent/` (agent evaluation conditions,
outcomes, paired-condition comparison, and diagnostics).

Scope note: this suite does not modify, re-run, or depend on
`test_evaluation_contracts.py` (62 tests), `test_core_memory_metrics.py` (88 tests),
`test_evidence_equivalence.py` (32 tests), or `test_provenance_lineage.py` (58 tests),
which must all remain green, unmodified, alongside this file (240 tests total baseline).

All fixtures here are small, hand-authored, deterministic Python literals/dicts embedded
directly in this module (matching `test_evidence_equivalence.py`'s convention) covering
the 10 scenarios from the 3.2-E task brief: memory enables success, memory unnecessary,
memory harms outcome via conflicting memory, agent fails despite gold evidence, retrieval
failure, selection failure, selected-but-unused, selected-and-used, execution failure,
and ambiguous/undefined evaluation.
"""

from __future__ import annotations

import copy
import inspect
from typing import Optional

import pytest

from phase3.evaluation.contracts.boundary import AgentVisibilityViolation, FORBIDDEN_KEYS

from phase3.evaluation.agent import conditions as conditions_mod
from phase3.evaluation.agent.conditions import (
    ALL_CONDITIONS,
    CANONICAL_CONDITIONS,
    PROVISIONAL_CONDITIONS,
    WITH_MEMORY_CONDITIONS,
    CONDITION_NO_MEMORY,
    CONDITION_GOLD_EVIDENCE,
    CONDITION_RETRIEVED_MEMORY,
    CONDITION_SELECTED_MEMORY_AVAILABLE,
    CONDITION_DERIVED_MEMORY_AVAILABLE,
    CONDITION_CONFLICTING_MEMORY_AVAILABLE,
    CONDITION_DEFINITIONS,
    build_agent_visible_context,
)

from phase3.evaluation.agent import outcomes as outcomes_mod
from phase3.evaluation.agent.outcomes import (
    AgentExecutionResult,
    EXECUTION_STATUS_SUCCESS,
    EXECUTION_STATUS_ERROR,
    SUCCESS_ANSWER_CORRECT,
    SUCCESS_ANSWER_INCORRECT,
    SUCCESS_EXECUTION_FAILURE,
    SUCCESS_EVALUATION_UNDEFINED,
    evaluate_answer_correctness,
    classify_agent_success,
    run_synthetic_agent,
    BEHAVIOR_CORRECT_IF_EVIDENCE_PRESENT,
    BEHAVIOR_ALWAYS_CORRECT,
    BEHAVIOR_ALWAYS_WRONG,
    BEHAVIOR_IGNORE_EVIDENCE_ALWAYS_WRONG,
    BEHAVIOR_ALWAYS_FAIL_EXECUTION,
)

from phase3.evaluation.agent import diagnostics as diagnostics_mod
from phase3.evaluation.agent.diagnostics import (
    observed_gold_evidence_ceiling,
    classify_retrieval_utilization,
    evidence_available_agent_failed,
    classify_observed_failure_stage,
    STATUS_OBSERVED_GOLD_EVIDENCE_CEILING,
    STATUS_UNDEFINED_NO_GOLD_EVIDENCE_RESULTS,
    UTILIZATION_NO_SELECTED_EVIDENCE,
    UTILIZATION_SELECTED_BUT_NOT_USED,
    UTILIZATION_SELECTED_AND_USED,
    STATUS_UNDEFINED_USAGE_NOT_OBSERVABLE,
    STATUS_AGENT_FAILURE_WITH_EVIDENCE,
    STATUS_NOT_APPLICABLE_EVIDENCE_UNAVAILABLE,
    STATUS_NOT_APPLICABLE_ANSWER_NOT_INCORRECT,
    STAGE_RETRIEVAL_FAILURE,
    STAGE_SELECTION_FAILURE,
    STAGE_EVIDENCE_UNAVAILABLE,
    STAGE_AGENT_FAILURE_WITH_EVIDENCE,
    STAGE_AGENT_EXECUTION_FAILURE,
    STAGE_SUCCESS,
    STAGE_UNDEFINED,
)

from phase3.evaluation.agent import paired as paired_mod
from phase3.evaluation.agent.paired import (
    PairedComparisonIdentityError,
    paired_condition_comparison,
    classify_memory_contribution,
    memory_contribution_tally,
    CONTRIBUTION_POSITIVE,
    CONTRIBUTION_NONE,
    CONTRIBUTION_NEGATIVE,
    CONTRIBUTION_UNDEFINED,
)

from phase3.evaluation.metrics.selection import strict_tsr


# ---------------------------------------------------------------------------
# Fixture builders for the 10 scenarios
# ---------------------------------------------------------------------------

GOLD_ANSWER = "Paris"


def _ctx(condition, task_id="task-1", prompt="What is the capital of France?", memory_items=None):
    return build_agent_visible_context(
        condition=condition, task_id=task_id, prompt=prompt, memory_items=memory_items
    )


def scenario_memory_enables_success():
    """1. Memory enables success: NO_MEMORY wrong, RETRIEVED_MEMORY correct."""
    task_id = "s1-task"
    ctx_no_mem = _ctx(CONDITION_NO_MEMORY, task_id=task_id)
    ctx_with_mem = _ctx(
        CONDITION_RETRIEVED_MEMORY,
        task_id=task_id,
        memory_items=[{"memory_id": "mem-1", "content": "Paris is the capital of France."}],
    )
    no_mem_result = run_synthetic_agent(
        task_id, CONDITION_NO_MEMORY, BEHAVIOR_CORRECT_IF_EVIDENCE_PRESENT, ctx_no_mem,
        expected_answer=GOLD_ANSWER,
    )
    with_mem_result = run_synthetic_agent(
        task_id, CONDITION_RETRIEVED_MEMORY, BEHAVIOR_CORRECT_IF_EVIDENCE_PRESENT, ctx_with_mem,
        expected_answer=GOLD_ANSWER, selected_memory_ids=["mem-1"], used_memory_ids=["mem-1"],
    )
    return ctx_no_mem, ctx_with_mem, no_mem_result, with_mem_result


def scenario_memory_unnecessary():
    """2. Memory unnecessary: NO_MEMORY correct, RETRIEVED_MEMORY correct."""
    task_id = "s2-task"
    ctx_no_mem = _ctx(CONDITION_NO_MEMORY, task_id=task_id)
    ctx_with_mem = _ctx(
        CONDITION_RETRIEVED_MEMORY,
        task_id=task_id,
        memory_items=[{"memory_id": "mem-2", "content": "Paris is the capital of France."}],
    )
    no_mem_result = run_synthetic_agent(
        task_id, CONDITION_NO_MEMORY, BEHAVIOR_ALWAYS_CORRECT, ctx_no_mem,
        expected_answer=GOLD_ANSWER,
    )
    with_mem_result = run_synthetic_agent(
        task_id, CONDITION_RETRIEVED_MEMORY, BEHAVIOR_ALWAYS_CORRECT, ctx_with_mem,
        expected_answer=GOLD_ANSWER, selected_memory_ids=["mem-2"], used_memory_ids=["mem-2"],
    )
    return ctx_no_mem, ctx_with_mem, no_mem_result, with_mem_result


def scenario_memory_harms_via_conflict():
    """3. Memory harms outcome via conflicting memory: NO_MEMORY correct,
    CONFLICTING_MEMORY_AVAILABLE incorrect."""
    task_id = "s3-task"
    ctx_no_mem = _ctx(CONDITION_NO_MEMORY, task_id=task_id)
    ctx_conflict = _ctx(
        CONDITION_CONFLICTING_MEMORY_AVAILABLE,
        task_id=task_id,
        memory_items=[
            {"memory_id": "mem-3a", "content": "Paris is the capital of France."},
            {"memory_id": "mem-3b", "content": "Lyon is the capital of France."},
        ],
    )
    no_mem_result = run_synthetic_agent(
        task_id, CONDITION_NO_MEMORY, BEHAVIOR_ALWAYS_CORRECT, ctx_no_mem,
        expected_answer=GOLD_ANSWER,
    )
    conflict_result = run_synthetic_agent(
        task_id, CONDITION_CONFLICTING_MEMORY_AVAILABLE, BEHAVIOR_IGNORE_EVIDENCE_ALWAYS_WRONG,
        ctx_conflict, expected_answer=GOLD_ANSWER,
        selected_memory_ids=["mem-3a", "mem-3b"], used_memory_ids=["mem-3b"],
    )
    return ctx_no_mem, ctx_conflict, no_mem_result, conflict_result


def scenario_agent_fails_despite_gold_evidence():
    """4. Agent fails despite gold evidence: GOLD_EVIDENCE condition, incorrect answer."""
    task_id = "s4-task"
    ctx = _ctx(
        CONDITION_GOLD_EVIDENCE, task_id=task_id,
        memory_items=[{"memory_id": "evidence-slot-1", "content": "Paris is the capital of France."}],
    )
    result = run_synthetic_agent(
        task_id, CONDITION_GOLD_EVIDENCE, BEHAVIOR_ALWAYS_WRONG, ctx,
        expected_answer=GOLD_ANSWER, selected_memory_ids=["evidence-slot-1"],
        used_memory_ids=["evidence-slot-1"],
    )
    return ctx, result


def scenario_retrieval_failure():
    """5. Retrieval failure: gold id absent from retrieved_ids."""
    task_id = "s5-task"
    ctx = _ctx(
        CONDITION_RETRIEVED_MEMORY, task_id=task_id,
        memory_items=[{"memory_id": "mem-irrelevant", "content": "Some unrelated fact."}],
    )
    result = run_synthetic_agent(
        task_id, CONDITION_RETRIEVED_MEMORY, BEHAVIOR_ALWAYS_WRONG, ctx,
        expected_answer=GOLD_ANSWER, selected_memory_ids=["mem-irrelevant"],
        used_memory_ids=["mem-irrelevant"],
    )
    gold_evidence_ids = ["gold-mem-1"]
    retrieved_memory_ids = ["mem-irrelevant", "mem-other"]  # gold-mem-1 never retrieved
    return ctx, result, gold_evidence_ids, retrieved_memory_ids


def scenario_selection_failure():
    """6. Selection failure: gold id retrieved but not selected."""
    task_id = "s6-task"
    ctx = _ctx(
        CONDITION_RETRIEVED_MEMORY, task_id=task_id,
        memory_items=[{"memory_id": "mem-other", "content": "Some other fact."}],
    )
    result = run_synthetic_agent(
        task_id, CONDITION_RETRIEVED_MEMORY, BEHAVIOR_ALWAYS_WRONG, ctx,
        expected_answer=GOLD_ANSWER, selected_memory_ids=["mem-other"],
        used_memory_ids=["mem-other"],
    )
    gold_evidence_ids = ["gold-mem-1"]
    retrieved_memory_ids = ["gold-mem-1", "mem-other"]  # retrieved, but selected only mem-other
    return ctx, result, gold_evidence_ids, retrieved_memory_ids


def scenario_selected_but_unused():
    """7. Selected-but-unused: selected non-empty, used disjoint."""
    task_id = "s7-task"
    result = AgentExecutionResult(
        task_id=task_id,
        condition=CONDITION_RETRIEVED_MEMORY,
        answer=GOLD_ANSWER,
        execution_status=EXECUTION_STATUS_SUCCESS,
        selected_memory_ids=("mem-A", "mem-B"),
        used_memory_ids=(),
    )
    return result


def scenario_selected_and_used():
    """8. Selected-and-used: intersection non-empty."""
    task_id = "s8-task"
    result = AgentExecutionResult(
        task_id=task_id,
        condition=CONDITION_RETRIEVED_MEMORY,
        answer=GOLD_ANSWER,
        execution_status=EXECUTION_STATUS_SUCCESS,
        selected_memory_ids=("mem-A", "mem-B"),
        used_memory_ids=("mem-A",),
    )
    return result


def scenario_execution_failure():
    """9. Execution failure."""
    task_id = "s9-task"
    ctx = _ctx(CONDITION_RETRIEVED_MEMORY, task_id=task_id,
               memory_items=[{"memory_id": "mem-9", "content": "Something."}])
    result = run_synthetic_agent(
        task_id, CONDITION_RETRIEVED_MEMORY, BEHAVIOR_ALWAYS_FAIL_EXECUTION, ctx,
        expected_answer=GOLD_ANSWER,
    )
    return ctx, result


def scenario_ambiguous_undefined_evaluation():
    """10. Ambiguous/undefined evaluation: no expected answer supplied."""
    task_id = "s10-task"
    ctx = _ctx(CONDITION_RETRIEVED_MEMORY, task_id=task_id,
               memory_items=[{"memory_id": "mem-10", "content": "Something."}])
    result = run_synthetic_agent(
        task_id, CONDITION_RETRIEVED_MEMORY, BEHAVIOR_CORRECT_IF_EVIDENCE_PRESENT, ctx,
        expected_answer=None,
    )
    return ctx, result


ALL_SCENARIO_CONTEXTS = []
for _fn in (
    scenario_memory_enables_success,
    scenario_memory_unnecessary,
    scenario_memory_harms_via_conflict,
):
    _ctxs = _fn()[:2]
    ALL_SCENARIO_CONTEXTS.extend(_ctxs)
ALL_SCENARIO_CONTEXTS.append(scenario_agent_fails_despite_gold_evidence()[0])
ALL_SCENARIO_CONTEXTS.append(scenario_retrieval_failure()[0])
ALL_SCENARIO_CONTEXTS.append(scenario_selection_failure()[0])
ALL_SCENARIO_CONTEXTS.append(scenario_execution_failure()[0])
ALL_SCENARIO_CONTEXTS.append(scenario_ambiguous_undefined_evaluation()[0])


# ---------------------------------------------------------------------------
# Condition vocabulary tests
# ---------------------------------------------------------------------------


def test_canonical_conditions_match_schema_enum_exactly():
    assert set(CANONICAL_CONDITIONS) == {
        CONDITION_NO_MEMORY, CONDITION_GOLD_EVIDENCE, CONDITION_RETRIEVED_MEMORY
    }


def test_provisional_conditions_are_disjoint_from_canonical():
    assert set(PROVISIONAL_CONDITIONS).isdisjoint(set(CANONICAL_CONDITIONS))
    assert set(ALL_CONDITIONS) == set(CANONICAL_CONDITIONS) | set(PROVISIONAL_CONDITIONS)


def test_every_condition_has_a_definition():
    for cond in ALL_CONDITIONS:
        assert cond in CONDITION_DEFINITIONS
        defn = CONDITION_DEFINITIONS[cond]
        assert defn.canonical == (cond in CANONICAL_CONDITIONS)


def test_with_memory_conditions_excludes_no_memory():
    assert CONDITION_NO_MEMORY not in WITH_MEMORY_CONDITIONS
    assert set(WITH_MEMORY_CONDITIONS) <= set(ALL_CONDITIONS)


# ---------------------------------------------------------------------------
# Agent-visible / evaluator-only separation
# ---------------------------------------------------------------------------


def test_no_memory_context_has_no_memory_content():
    ctx = _ctx(CONDITION_NO_MEMORY)
    assert ctx["memory_content"] == []


def test_no_memory_context_ignores_supplied_memory_items():
    ctx = build_agent_visible_context(
        CONDITION_NO_MEMORY, "t", "prompt",
        memory_items=[{"memory_id": "should-not-appear", "content": "x"}],
    )
    assert ctx["memory_content"] == []


def test_gold_evidence_context_never_carries_literal_gold_evidence_id_field():
    ctx = scenario_agent_fails_despite_gold_evidence()[0]
    assert "gold_evidence_ids" not in ctx
    assert "gold_evidence_id" not in ctx


@pytest.mark.parametrize("bad_key", sorted(FORBIDDEN_KEYS))
def test_build_agent_visible_context_rejects_every_forbidden_key(bad_key):
    with pytest.raises(AgentVisibilityViolation):
        build_agent_visible_context(
            CONDITION_RETRIEVED_MEMORY, "t", "prompt",
            memory_items=[{"memory_id": "m", "content": "c", "permitted_provenance": {bad_key: "x"}}],
        )


def test_no_forbidden_key_appears_in_any_scenario_agent_visible_context():
    """Across ALL synthetic fixtures, no AgentVisibleContext payload carries a forbidden
    evaluator-only key at any nesting depth."""
    for ctx in ALL_SCENARIO_CONTEXTS:
        # build_agent_visible_context already validated at construction time; re-validate
        # here as an explicit, independent assertion per the task brief's requirement.
        from phase3.evaluation.contracts.boundary import validate_agent_visible
        validate_agent_visible(ctx)  # must not raise


# ---------------------------------------------------------------------------
# Answer correctness
# ---------------------------------------------------------------------------


def test_answer_correctness_exact_match():
    result = AgentExecutionResult(task_id="t", condition=CONDITION_NO_MEMORY, answer="Paris",
                                   execution_status=EXECUTION_STATUS_SUCCESS)
    m = evaluate_answer_correctness(result, "Paris")
    assert m.value == 1.0
    assert m.status == SUCCESS_ANSWER_CORRECT


def test_answer_correctness_mismatch():
    result = AgentExecutionResult(task_id="t", condition=CONDITION_NO_MEMORY, answer="Lyon",
                                   execution_status=EXECUTION_STATUS_SUCCESS)
    m = evaluate_answer_correctness(result, "Paris")
    assert m.value == 0.0
    assert m.status == SUCCESS_ANSWER_INCORRECT


def test_answer_correctness_tolerates_surrounding_whitespace_only():
    result = AgentExecutionResult(task_id="t", condition=CONDITION_NO_MEMORY, answer="  Paris  ",
                                   execution_status=EXECUTION_STATUS_SUCCESS)
    m = evaluate_answer_correctness(result, "Paris")
    assert m.status == SUCCESS_ANSWER_CORRECT


def test_answer_correctness_is_case_sensitive_not_fuzzy():
    result = AgentExecutionResult(task_id="t", condition=CONDITION_NO_MEMORY, answer="paris",
                                   execution_status=EXECUTION_STATUS_SUCCESS)
    m = evaluate_answer_correctness(result, "Paris")
    assert m.status == SUCCESS_ANSWER_INCORRECT


def test_answer_correctness_undefined_on_execution_failure():
    result = AgentExecutionResult(task_id="t", condition=CONDITION_NO_MEMORY, answer=None,
                                   execution_status=EXECUTION_STATUS_ERROR)
    m = evaluate_answer_correctness(result, "Paris")
    assert m.value is None
    assert m.status == SUCCESS_EXECUTION_FAILURE


def test_answer_correctness_undefined_without_expected_answer():
    result = AgentExecutionResult(task_id="t", condition=CONDITION_NO_MEMORY, answer="Paris",
                                   execution_status=EXECUTION_STATUS_SUCCESS)
    m = evaluate_answer_correctness(result, None)
    assert m.value is None
    assert m.status == SUCCESS_EVALUATION_UNDEFINED


# ---------------------------------------------------------------------------
# Agent success classification
# ---------------------------------------------------------------------------


def test_classify_agent_success_matches_correctness():
    result = AgentExecutionResult(task_id="t", condition=CONDITION_NO_MEMORY, answer="Paris",
                                   execution_status=EXECUTION_STATUS_SUCCESS)
    m = classify_agent_success(result, "Paris")
    assert m.status == SUCCESS_ANSWER_CORRECT
    assert m.metric_name == "AGENT_SUCCESS_CLASSIFICATION"


def test_scenario_9_execution_failure_classification():
    _, result = scenario_execution_failure()
    m = classify_agent_success(result, GOLD_ANSWER)
    assert m.status == SUCCESS_EXECUTION_FAILURE


def test_scenario_10_undefined_evaluation_classification():
    _, result = scenario_ambiguous_undefined_evaluation()
    m = classify_agent_success(result, None)
    assert m.status == SUCCESS_EVALUATION_UNDEFINED


# ---------------------------------------------------------------------------
# Memory contribution (all 4 paired cases)
# ---------------------------------------------------------------------------


def test_scenario_1_positive_memory_contribution():
    _, _, no_mem, with_mem = scenario_memory_enables_success()
    m = classify_memory_contribution(no_mem, with_mem, GOLD_ANSWER, GOLD_ANSWER)
    assert m.status == CONTRIBUTION_POSITIVE


def test_scenario_2_no_observed_contribution_memory_unnecessary():
    _, _, no_mem, with_mem = scenario_memory_unnecessary()
    m = classify_memory_contribution(no_mem, with_mem, GOLD_ANSWER, GOLD_ANSWER)
    assert m.status == CONTRIBUTION_NONE


def test_no_observed_contribution_both_incorrect():
    task_id = "both-wrong"
    no_mem = AgentExecutionResult(task_id=task_id, condition=CONDITION_NO_MEMORY,
                                   answer="Lyon", execution_status=EXECUTION_STATUS_SUCCESS)
    with_mem = AgentExecutionResult(task_id=task_id, condition=CONDITION_RETRIEVED_MEMORY,
                                     answer="Lyon", execution_status=EXECUTION_STATUS_SUCCESS)
    m = classify_memory_contribution(no_mem, with_mem, GOLD_ANSWER, GOLD_ANSWER)
    assert m.status == CONTRIBUTION_NONE


def test_scenario_3_negative_memory_effect():
    _, _, no_mem, with_mem = scenario_memory_harms_via_conflict()
    m = classify_memory_contribution(no_mem, with_mem, GOLD_ANSWER, GOLD_ANSWER)
    assert m.status == CONTRIBUTION_NEGATIVE


def test_memory_contribution_undefined_on_execution_failure():
    task_id = "undef-pair"
    no_mem = AgentExecutionResult(task_id=task_id, condition=CONDITION_NO_MEMORY,
                                   answer="Lyon", execution_status=EXECUTION_STATUS_SUCCESS)
    with_mem = AgentExecutionResult(task_id=task_id, condition=CONDITION_RETRIEVED_MEMORY,
                                     answer=None, execution_status=EXECUTION_STATUS_ERROR)
    m = classify_memory_contribution(no_mem, with_mem, GOLD_ANSWER, GOLD_ANSWER)
    assert m.status == CONTRIBUTION_UNDEFINED


def test_memory_contribution_tally_counts_all_four_categories():
    pairs = [
        classify_memory_contribution(*scenario_memory_enables_success()[2:], GOLD_ANSWER, GOLD_ANSWER),
        classify_memory_contribution(*scenario_memory_unnecessary()[2:], GOLD_ANSWER, GOLD_ANSWER),
        classify_memory_contribution(*scenario_memory_harms_via_conflict()[2:], GOLD_ANSWER, GOLD_ANSWER),
    ]
    tally = memory_contribution_tally(pairs)
    assert tally.detail["counts"][CONTRIBUTION_POSITIVE] == 1
    assert tally.detail["counts"][CONTRIBUTION_NONE] == 1
    assert tally.detail["counts"][CONTRIBUTION_NEGATIVE] == 1


def test_memory_contribution_tally_undefined_on_empty_sequence():
    tally = memory_contribution_tally([])
    assert tally.value is None


# ---------------------------------------------------------------------------
# Gold-evidence ceiling
# ---------------------------------------------------------------------------


def test_gold_evidence_ceiling_observed_status():
    ctx, result = scenario_agent_fails_despite_gold_evidence()
    m = observed_gold_evidence_ceiling([result], {"s4-task": GOLD_ANSWER})
    assert m.status == STATUS_OBSERVED_GOLD_EVIDENCE_CEILING
    assert m.value == 0.0  # the one result was ANSWER_INCORRECT


def test_gold_evidence_ceiling_rejects_non_gold_evidence_condition():
    _, result = scenario_execution_failure()  # condition=RETRIEVED_MEMORY
    with pytest.raises(ValueError):
        observed_gold_evidence_ceiling([result], {result.task_id: GOLD_ANSWER})


def test_gold_evidence_ceiling_undefined_on_empty_input():
    m = observed_gold_evidence_ceiling([], {})
    assert m.value is None
    assert m.status == STATUS_UNDEFINED_NO_GOLD_EVIDENCE_RESULTS


def test_gold_evidence_ceiling_mixed_correct_and_incorrect():
    ctx1 = _ctx(CONDITION_GOLD_EVIDENCE, task_id="ge-1",
                memory_items=[{"memory_id": "e1", "content": "Paris is the capital of France."}])
    result_correct = run_synthetic_agent(
        "ge-1", CONDITION_GOLD_EVIDENCE, BEHAVIOR_ALWAYS_CORRECT, ctx1, expected_answer=GOLD_ANSWER,
    )
    ctx2 = _ctx(CONDITION_GOLD_EVIDENCE, task_id="ge-2",
                memory_items=[{"memory_id": "e2", "content": "Paris is the capital of France."}])
    result_incorrect = run_synthetic_agent(
        "ge-2", CONDITION_GOLD_EVIDENCE, BEHAVIOR_ALWAYS_WRONG, ctx2, expected_answer=GOLD_ANSWER,
    )
    m = observed_gold_evidence_ceiling(
        [result_correct, result_incorrect], {"ge-1": GOLD_ANSWER, "ge-2": GOLD_ANSWER}
    )
    assert m.value == 0.5


# ---------------------------------------------------------------------------
# Retrieval utilization (3 states + undefined)
# ---------------------------------------------------------------------------


def test_scenario_7_selected_but_not_used():
    result = scenario_selected_but_unused()
    m = classify_retrieval_utilization(result)
    assert m.status == UTILIZATION_SELECTED_BUT_NOT_USED


def test_scenario_8_selected_and_used():
    result = scenario_selected_and_used()
    m = classify_retrieval_utilization(result)
    assert m.status == UTILIZATION_SELECTED_AND_USED


def test_no_selected_evidence():
    result = AgentExecutionResult(task_id="t", condition=CONDITION_NO_MEMORY, answer="x",
                                   execution_status=EXECUTION_STATUS_SUCCESS,
                                   selected_memory_ids=(), used_memory_ids=())
    m = classify_retrieval_utilization(result)
    assert m.status == UTILIZATION_NO_SELECTED_EVIDENCE


def test_retrieval_utilization_undefined_when_usage_not_observable():
    result = AgentExecutionResult(task_id="t", condition=CONDITION_RETRIEVED_MEMORY, answer="x",
                                   execution_status=EXECUTION_STATUS_SUCCESS,
                                   selected_memory_ids=("mem-A",), used_memory_ids=None)
    m = classify_retrieval_utilization(result)
    assert m.status == STATUS_UNDEFINED_USAGE_NOT_OBSERVABLE
    assert m.value is None


# ---------------------------------------------------------------------------
# Evidence-available / agent-failed
# ---------------------------------------------------------------------------


def test_scenario_4_agent_failure_with_evidence():
    ctx, result = scenario_agent_fails_despite_gold_evidence()
    m = evidence_available_agent_failed(result, GOLD_ANSWER, gold_evidence_available=True)
    assert m.status == STATUS_AGENT_FAILURE_WITH_EVIDENCE


def test_evidence_available_agent_failed_not_applicable_when_unavailable():
    ctx, result = scenario_retrieval_failure()[:2]
    m = evidence_available_agent_failed(result, GOLD_ANSWER, gold_evidence_available=False)
    assert m.status == STATUS_NOT_APPLICABLE_EVIDENCE_UNAVAILABLE


def test_evidence_available_agent_failed_not_applicable_when_answer_correct():
    result = AgentExecutionResult(task_id="t", condition=CONDITION_GOLD_EVIDENCE, answer="Paris",
                                   execution_status=EXECUTION_STATUS_SUCCESS)
    m = evidence_available_agent_failed(result, "Paris", gold_evidence_available=True)
    assert m.status == STATUS_NOT_APPLICABLE_ANSWER_NOT_INCORRECT


# ---------------------------------------------------------------------------
# Failure-stage classification (all 6 states)
# ---------------------------------------------------------------------------


def test_scenario_5_retrieval_failure_stage():
    ctx, result, gold_ids, retrieved_ids = scenario_retrieval_failure()
    m = classify_observed_failure_stage(result, GOLD_ANSWER, gold_ids, retrieved_ids)
    assert m.status == STAGE_RETRIEVAL_FAILURE


def test_scenario_6_selection_failure_stage():
    ctx, result, gold_ids, retrieved_ids = scenario_selection_failure()
    m = classify_observed_failure_stage(result, GOLD_ANSWER, gold_ids, retrieved_ids)
    assert m.status == STAGE_SELECTION_FAILURE


def test_no_memory_condition_is_evidence_unavailable_stage():
    task_id = "no-mem-wrong"
    result = AgentExecutionResult(task_id=task_id, condition=CONDITION_NO_MEMORY, answer="Lyon",
                                   execution_status=EXECUTION_STATUS_SUCCESS)
    m = classify_observed_failure_stage(result, GOLD_ANSWER, ["gold-1"], [])
    assert m.status == STAGE_EVIDENCE_UNAVAILABLE


def test_scenario_4_gold_evidence_condition_is_agent_failure_with_evidence_stage():
    ctx, result = scenario_agent_fails_despite_gold_evidence()
    m = classify_observed_failure_stage(result, GOLD_ANSWER, ["gold-1"], [])
    assert m.status == STAGE_AGENT_FAILURE_WITH_EVIDENCE


def test_scenario_9_execution_failure_stage():
    ctx, result = scenario_execution_failure()
    m = classify_observed_failure_stage(result, GOLD_ANSWER, ["gold-1"], ["gold-1"])
    assert m.status == STAGE_AGENT_EXECUTION_FAILURE


def test_success_stage_when_answer_correct():
    task_id = "correct"
    result = AgentExecutionResult(task_id=task_id, condition=CONDITION_RETRIEVED_MEMORY,
                                   answer=GOLD_ANSWER, execution_status=EXECUTION_STATUS_SUCCESS,
                                   selected_memory_ids=("gold-1",))
    m = classify_observed_failure_stage(result, GOLD_ANSWER, ["gold-1"], ["gold-1"])
    assert m.status == STAGE_SUCCESS


def test_undefined_stage_without_expected_answer():
    task_id = "no-expected"
    result = AgentExecutionResult(task_id=task_id, condition=CONDITION_RETRIEVED_MEMORY,
                                   answer="something", execution_status=EXECUTION_STATUS_SUCCESS)
    m = classify_observed_failure_stage(result, None, ["gold-1"], ["gold-1"])
    assert m.status == STAGE_UNDEFINED


def test_retrieved_memory_all_gold_selected_is_agent_failure_with_evidence_stage():
    """All gold ids HIT (selected) but the answer is still wrong -> AGENT_FAILURE_WITH_EVIDENCE,
    distinguishing this from both RETRIEVAL_FAILURE and SELECTION_FAILURE."""
    task_id = "hit-but-wrong"
    result = AgentExecutionResult(task_id=task_id, condition=CONDITION_RETRIEVED_MEMORY,
                                   answer="Lyon", execution_status=EXECUTION_STATUS_SUCCESS,
                                   selected_memory_ids=("gold-1",))
    m = classify_observed_failure_stage(result, GOLD_ANSWER, ["gold-1"], ["gold-1"])
    assert m.status == STAGE_AGENT_FAILURE_WITH_EVIDENCE


# ---------------------------------------------------------------------------
# Paired comparisons
# ---------------------------------------------------------------------------


def test_paired_condition_comparison_reports_both_sides():
    _, _, no_mem, with_mem = scenario_memory_enables_success()
    m = paired_condition_comparison(no_mem, with_mem, GOLD_ANSWER, GOLD_ANSWER)
    assert m.detail["no_memory_classification"] == SUCCESS_ANSWER_INCORRECT
    assert m.detail["with_memory_classification"] == SUCCESS_ANSWER_CORRECT
    assert m.status == "PAIRED_CONDITION_COMPARISON"


def test_paired_comparison_rejects_mismatched_task_id():
    no_mem = AgentExecutionResult(task_id="task-A", condition=CONDITION_NO_MEMORY, answer="x",
                                   execution_status=EXECUTION_STATUS_SUCCESS)
    with_mem = AgentExecutionResult(task_id="task-B", condition=CONDITION_RETRIEVED_MEMORY,
                                     answer="x", execution_status=EXECUTION_STATUS_SUCCESS)
    with pytest.raises(PairedComparisonIdentityError):
        paired_condition_comparison(no_mem, with_mem, "x", "x")


def test_paired_comparison_rejects_mismatched_expected_answer():
    no_mem = AgentExecutionResult(task_id="t", condition=CONDITION_NO_MEMORY, answer="x",
                                   execution_status=EXECUTION_STATUS_SUCCESS)
    with_mem = AgentExecutionResult(task_id="t", condition=CONDITION_RETRIEVED_MEMORY,
                                     answer="x", execution_status=EXECUTION_STATUS_SUCCESS)
    with pytest.raises(PairedComparisonIdentityError):
        paired_condition_comparison(no_mem, with_mem, "Paris", "Lyon")


def test_paired_comparison_rejects_wrong_condition_on_either_side():
    a = AgentExecutionResult(task_id="t", condition=CONDITION_RETRIEVED_MEMORY, answer="x",
                              execution_status=EXECUTION_STATUS_SUCCESS)
    b = AgentExecutionResult(task_id="t", condition=CONDITION_GOLD_EVIDENCE, answer="x",
                              execution_status=EXECUTION_STATUS_SUCCESS)
    with pytest.raises(PairedComparisonIdentityError):
        paired_condition_comparison(a, b, "x", "x")  # neither side is NO_MEMORY


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_determinism_answer_correctness_run_twice():
    result = AgentExecutionResult(task_id="t", condition=CONDITION_NO_MEMORY, answer="Paris",
                                   execution_status=EXECUTION_STATUS_SUCCESS)
    m1 = evaluate_answer_correctness(result, "Paris")
    m2 = evaluate_answer_correctness(result, "Paris")
    assert m1.value == m2.value
    assert m1.status == m2.status


def test_determinism_failure_stage_run_twice():
    ctx, result, gold_ids, retrieved_ids = scenario_retrieval_failure()
    m1 = classify_observed_failure_stage(result, GOLD_ANSWER, gold_ids, retrieved_ids)
    m2 = classify_observed_failure_stage(result, GOLD_ANSWER, gold_ids, retrieved_ids)
    assert m1.status == m2.status
    assert m1.detail == m2.detail


def test_determinism_synthetic_agent_run_twice():
    ctx = _ctx(CONDITION_RETRIEVED_MEMORY, task_id="det-task",
               memory_items=[{"memory_id": "m", "content": "c"}])
    r1 = run_synthetic_agent("det-task", CONDITION_RETRIEVED_MEMORY,
                              BEHAVIOR_CORRECT_IF_EVIDENCE_PRESENT, ctx, expected_answer=GOLD_ANSWER)
    r2 = run_synthetic_agent("det-task", CONDITION_RETRIEVED_MEMORY,
                              BEHAVIOR_CORRECT_IF_EVIDENCE_PRESENT, ctx, expected_answer=GOLD_ANSWER)
    assert r1 == r2


# ---------------------------------------------------------------------------
# Invariant tests (task brief section 32)
# ---------------------------------------------------------------------------


def test_invariant_agent_success_does_not_imply_strict_tsr():
    """STRICT_TSR=1 (selected overlaps gold) but ANSWER_INCORRECT: agent success and
    strict TSR are independent."""
    result = AgentExecutionResult(task_id="t", condition=CONDITION_RETRIEVED_MEMORY,
                                   answer="Lyon", execution_status=EXECUTION_STATUS_SUCCESS,
                                   selected_memory_ids=("gold-1",))
    tsr = strict_tsr(result.selected_memory_ids, ["gold-1"])
    success = classify_agent_success(result, GOLD_ANSWER)
    assert tsr.value == 1.0
    assert success.status == SUCCESS_ANSWER_INCORRECT


def test_invariant_strict_tsr_does_not_imply_agent_success():
    """STRICT_TSR=0 (selected does not overlap gold) but ANSWER_CORRECT: e.g. the agent
    reasoned to the right answer via a non-gold, equivalent, or otherwise different
    memory. Agent success and strict TSR are independent in both directions."""
    result = AgentExecutionResult(task_id="t", condition=CONDITION_RETRIEVED_MEMORY,
                                   answer=GOLD_ANSWER, execution_status=EXECUTION_STATUS_SUCCESS,
                                   selected_memory_ids=("non-gold-mem",))
    tsr = strict_tsr(result.selected_memory_ids, ["gold-1"])
    success = classify_agent_success(result, GOLD_ANSWER)
    assert tsr.value == 0.0
    assert success.status == SUCCESS_ANSWER_CORRECT


def test_invariant_no_memory_has_no_memory_context():
    ctx = _ctx(CONDITION_NO_MEMORY)
    assert ctx.get("memory_content") == []


def test_invariant_selected_but_not_used_distinguishable_from_no_selected_evidence():
    unused_result = scenario_selected_but_unused()
    none_result = AgentExecutionResult(task_id="t2", condition=CONDITION_RETRIEVED_MEMORY,
                                        answer="x", execution_status=EXECUTION_STATUS_SUCCESS,
                                        selected_memory_ids=(), used_memory_ids=())
    m1 = classify_retrieval_utilization(unused_result)
    m2 = classify_retrieval_utilization(none_result)
    assert m1.status != m2.status
    assert m1.status == UTILIZATION_SELECTED_BUT_NOT_USED
    assert m2.status == UTILIZATION_NO_SELECTED_EVIDENCE


def test_invariant_retrieval_failure_distinguishable_from_selection_failure():
    _, r5, gold5, retrieved5 = scenario_retrieval_failure()
    _, r6, gold6, retrieved6 = scenario_selection_failure()
    m5 = classify_observed_failure_stage(r5, GOLD_ANSWER, gold5, retrieved5)
    m6 = classify_observed_failure_stage(r6, GOLD_ANSWER, gold6, retrieved6)
    assert m5.status == STAGE_RETRIEVAL_FAILURE
    assert m6.status == STAGE_SELECTION_FAILURE
    assert m5.status != m6.status


def test_invariant_agent_failure_with_evidence_distinguishable_from_evidence_absence():
    ctx4, result4 = scenario_agent_fails_despite_gold_evidence()
    m4 = classify_observed_failure_stage(result4, GOLD_ANSWER, ["gold-1"], [])
    no_mem_result = AgentExecutionResult(task_id="nm", condition=CONDITION_NO_MEMORY,
                                          answer="Lyon", execution_status=EXECUTION_STATUS_SUCCESS)
    m_no_mem = classify_observed_failure_stage(no_mem_result, GOLD_ANSWER, ["gold-1"], [])
    assert m4.status == STAGE_AGENT_FAILURE_WITH_EVIDENCE
    assert m_no_mem.status == STAGE_EVIDENCE_UNAVAILABLE
    assert m4.status != m_no_mem.status


def test_invariant_paired_comparison_enforces_same_task_identity():
    no_mem = AgentExecutionResult(task_id="task-A", condition=CONDITION_NO_MEMORY, answer="x",
                                   execution_status=EXECUTION_STATUS_SUCCESS)
    with_mem = AgentExecutionResult(task_id="task-B", condition=CONDITION_RETRIEVED_MEMORY,
                                     answer="x", execution_status=EXECUTION_STATUS_SUCCESS)
    with pytest.raises(PairedComparisonIdentityError):
        classify_memory_contribution(no_mem, with_mem, "x", "x")


def test_invariant_gold_evidence_ids_never_in_agent_visible_context():
    ctx, _ = scenario_agent_fails_despite_gold_evidence()
    serialized_keys = set()

    def _walk(obj):
        if isinstance(obj, dict):
            serialized_keys.update(obj.keys())
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    _walk(ctx)
    assert "gold_evidence_ids" not in serialized_keys
    assert "gold_answer" not in serialized_keys


# ---------------------------------------------------------------------------
# Architectural tests (task brief section 33)
# ---------------------------------------------------------------------------

_FORBIDDEN_IMPORTS = (
    "sentence_transformers",
    "openai",
    "torch",
    "sklearn",
    "requests",
    "urllib",
    "phase3_reference",
    "qwen",
    "transformers",
    "anthropic",
)

_AGENT_MODULES = (conditions_mod, outcomes_mod, diagnostics_mod, paired_mod)


@pytest.mark.parametrize("module", _AGENT_MODULES, ids=lambda m: m.__name__)
def test_agent_modules_never_import_forbidden_libraries(module):
    source = inspect.getsource(module)
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            for forbidden in _FORBIDDEN_IMPORTS:
                assert forbidden not in stripped.lower(), (
                    f"{module.__name__} has a forbidden import: {stripped!r}"
                )


@pytest.mark.parametrize("module", _AGENT_MODULES, ids=lambda m: m.__name__)
def test_agent_modules_make_no_network_or_random_calls(module):
    source = inspect.getsource(module)
    for forbidden_token in ("socket.", "http.client", "random.", "numpy.random", "requests."):
        assert forbidden_token not in source


def test_no_agent_module_imports_phase3_reference():
    for module in _AGENT_MODULES:
        source = inspect.getsource(module)
        assert "phase3_reference" not in source


def test_no_agent_module_does_direct_dataset_loading():
    """No agent/ module reads from data/, tests/fixtures/{locomo,longmemeval,msc,...}, or
    otherwise performs direct dataset loading -- all inputs are plain in-memory objects."""
    for module in _AGENT_MODULES:
        source = inspect.getsource(module)
        for forbidden_token in ("open(", "Path(", "pd.read_", "json.load", "pickle.load"):
            assert forbidden_token not in source


def test_diagnostics_do_not_mutate_input_execution_result():
    ctx, result, gold_ids, retrieved_ids = scenario_retrieval_failure()
    before = copy.deepcopy(result)
    classify_observed_failure_stage(result, GOLD_ANSWER, gold_ids, retrieved_ids)
    classify_retrieval_utilization(result)
    evidence_available_agent_failed(result, GOLD_ANSWER, gold_evidence_available=False)
    assert result == before


def test_diagnostics_do_not_mutate_input_gold_and_retrieved_lists():
    ctx, result, gold_ids, retrieved_ids = scenario_retrieval_failure()
    gold_before = copy.deepcopy(gold_ids)
    retrieved_before = copy.deepcopy(retrieved_ids)
    classify_observed_failure_stage(result, GOLD_ANSWER, gold_ids, retrieved_ids)
    assert gold_ids == gold_before
    assert retrieved_ids == retrieved_before


def test_conditions_module_never_accepts_evaluator_reference_param():
    for _, func in inspect.getmembers(conditions_mod, inspect.isfunction):
        sig = inspect.signature(func)
        for name in sig.parameters:
            assert "evaluator_reference" not in name.lower()
            assert "gold_answer" not in name.lower()


def test_outcomes_agent_execution_result_has_no_evaluator_only_field():
    """AgentExecutionResult must never carry a gold/evaluator-only field as one of its
    dataclass fields -- agent execution output must stay structurally separate from
    evaluator-only data."""
    import dataclasses
    field_names = {f.name for f in dataclasses.fields(AgentExecutionResult)}
    assert not (field_names & FORBIDDEN_KEYS)
    assert "expected_answer" not in field_names
    assert "gold_evidence_ids" not in field_names
