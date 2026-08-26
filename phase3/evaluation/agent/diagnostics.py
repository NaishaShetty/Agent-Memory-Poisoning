"""Gold-evidence ceiling, retrieval utilization, evidence-available/agent-failed, and
observed-failure-stage classification diagnostics.

Phase 3.2-E scope note: every classification in this module is explicitly DIAGNOSTIC
ONLY, never a causal claim. In particular, `classify_observed_failure_stage()` uses
"OBSERVED_FAILURE_STAGE" framing throughout -- it reports WHICH stage's evidence-handling
outcome was observed alongside an incorrect/failed answer, never that the stage CAUSED
the failure. A retrieval miss observed alongside an incorrect answer does not prove
retrieval is why the answer was wrong (the reasoning layer might have gotten it wrong
regardless); this module reports only the observed co-occurrence.

Reuses `phase3/evaluation/metrics/retrieval.py::classify_gold_id_capacity()` for the
per-gold-id RETRIEVAL_MISS/SELECTION_MISS/HIT classification rather than reimplementing
that logic, per the 3.2-E task brief's explicit instruction.

Pure functions: no filesystem/network/LLM/embeddings access, no randomness, no global
state.
"""

from __future__ import annotations

from statistics import mean
from typing import Mapping, Optional, Sequence

from phase3.evaluation.metrics.retrieval import (
    classify_gold_id_capacity,
    CLASSIFICATION_RETRIEVAL_MISS,
    CLASSIFICATION_SELECTION_MISS,
)
from phase3.evaluation.metrics.types import MetricResult

from .conditions import CONDITION_GOLD_EVIDENCE, CONDITION_NO_MEMORY
from .outcomes import (
    AgentExecutionResult,
    SUCCESS_ANSWER_CORRECT,
    SUCCESS_ANSWER_INCORRECT,
    SUCCESS_EVALUATION_UNDEFINED,
    SUCCESS_EXECUTION_FAILURE,
    classify_agent_success,
)

# ---------------------------------------------------------------------------
# Gold-evidence ceiling (OBSERVED, empirical -- NOT a theoretical ceiling)
# ---------------------------------------------------------------------------

STATUS_OBSERVED_GOLD_EVIDENCE_CEILING = "OBSERVED_GOLD_EVIDENCE_CEILING"
STATUS_UNDEFINED_NO_GOLD_EVIDENCE_RESULTS = "UNDEFINED_NO_GOLD_EVIDENCE_RESULTS"


def observed_gold_evidence_ceiling(
    gold_evidence_results: Sequence[AgentExecutionResult],
    expected_answers: Mapping[str, str],
) -> MetricResult:
    """DIAGNOSTIC ONLY. The observed ANSWER_CORRECT rate across a set of
    GOLD_EVIDENCE-condition (Condition B) execution results, for THIS fixture/task set,
    under THIS reasoning behavior only.

    Definition
    ----------
    ``value = count(ANSWER_CORRECT) / count(results with a defined success classification)``

    Every result in `gold_evidence_results` MUST have `condition == CONDITION_GOLD_EVIDENCE`
    -- this function raises `ValueError` otherwise, since the ceiling diagnostic is
    scoped, by definition, to Condition B only (mixing in other conditions would silently
    change what the number means).

    ================================================================================
    NOT A THEORETICAL CEILING. `OBSERVED_GOLD_EVIDENCE_CEILING` reports what this
    specific reasoning behavior, over this specific (synthetic, small) task set, achieved
    when handed gold evidence directly. It is NOT a claim about the best possible
    achievable accuracy under any reasoning model or any task set in general -- a
    different reasoning behavior, a larger task set, or a different gold-evidence
    presentation could observe a different number. Per EVALUATION_CONTRACT.md section 5,
    Condition B exists so Condition C (RETRIEVED_MEMORY) can be characterized RELATIVE TO
    it, not so this number can be reported as an abstract upper bound on agent capability.
    ================================================================================

    Results whose success classification is `EVALUATION_UNDEFINED` or
    `EXECUTION_FAILURE` are excluded from both numerator and denominator (their exclusion
    count is reported in `detail["excluded_count"]`), mirroring
    `retrieval.py::mean_reciprocal_rank()`'s pattern of never silently folding an
    undefined per-item result into the aggregate.

    Edge cases: empty `gold_evidence_results`, or every result excluded -> undefined
    (`status=STATUS_UNDEFINED_NO_GOLD_EVIDENCE_RESULTS`).
    """
    for result in gold_evidence_results:
        if result.condition != CONDITION_GOLD_EVIDENCE:
            raise ValueError(
                "observed_gold_evidence_ceiling is scoped to GOLD_EVIDENCE-condition "
                f"results only; got condition={result.condition!r} for task_id="
                f"{result.task_id!r}."
            )

    scored = []
    excluded = 0
    for result in gold_evidence_results:
        expected = expected_answers.get(result.task_id)
        classification = classify_agent_success(result, expected)
        if classification.status in (SUCCESS_EVALUATION_UNDEFINED, SUCCESS_EXECUTION_FAILURE):
            excluded += 1
            continue
        scored.append(1.0 if classification.status == SUCCESS_ANSWER_CORRECT else 0.0)

    if not scored:
        return MetricResult(
            metric_name="GOLD_EVIDENCE_CEILING",
            value=None,
            status=STATUS_UNDEFINED_NO_GOLD_EVIDENCE_RESULTS,
            detail={"num_results": len(gold_evidence_results), "excluded_count": excluded},
            note="No GOLD_EVIDENCE result with a defined success classification was supplied.",
        )

    return MetricResult(
        metric_name="GOLD_EVIDENCE_CEILING",
        value=mean(scored),
        status=STATUS_OBSERVED_GOLD_EVIDENCE_CEILING,
        detail={
            "num_results": len(gold_evidence_results),
            "num_scored": len(scored),
            "excluded_count": excluded,
        },
        note=(
            "OBSERVED, empirical diagnostic over THIS task set/behavior only -- NOT a "
            "theoretical ceiling on achievable accuracy. See module docstring."
        ),
    )


# ---------------------------------------------------------------------------
# Retrieval utilization
# ---------------------------------------------------------------------------

UTILIZATION_NO_SELECTED_EVIDENCE = "NO_SELECTED_EVIDENCE"
UTILIZATION_SELECTED_BUT_NOT_USED = "SELECTED_BUT_NOT_USED"
UTILIZATION_SELECTED_AND_USED = "SELECTED_AND_USED"
STATUS_UNDEFINED_USAGE_NOT_OBSERVABLE = "UNDEFINED_USAGE_NOT_OBSERVABLE"


def classify_retrieval_utilization(execution_result: AgentExecutionResult) -> MetricResult:
    """NO_SELECTED_EVIDENCE / SELECTED_BUT_NOT_USED / SELECTED_AND_USED, comparing
    `execution_result.selected_memory_ids` against `execution_result.used_memory_ids`.

    Definition
    ----------
    - `execution_result.used_memory_ids is None` (distinct from an empty tuple): usage
      was not exposed/observable by this execution's trace -> undefined
      (`status=STATUS_UNDEFINED_USAGE_NOT_OBSERVABLE`). This is explicitly NOT treated as
      "not used" -- "we don't know" and "we know it wasn't used" are different findings.
    - `selected_memory_ids` empty -> `NO_SELECTED_EVIDENCE` (nothing was selected, so
      utilization is trivially/vacuously "no selected evidence," not "not used" --
      distinguishable from the case below by construction).
    - `selected_memory_ids` non-empty and disjoint from `used_memory_ids` ->
      `SELECTED_BUT_NOT_USED`.
    - `selected_memory_ids` non-empty and intersects `used_memory_ids` ->
      `SELECTED_AND_USED`.
    """
    if execution_result.used_memory_ids is None:
        return MetricResult(
            metric_name="RETRIEVAL_UTILIZATION",
            value=None,
            status=STATUS_UNDEFINED_USAGE_NOT_OBSERVABLE,
            detail={"task_id": execution_result.task_id},
            note="used_memory_ids is None; usage was not observable from this execution's trace.",
        )

    selected = set(execution_result.selected_memory_ids)
    used = set(execution_result.used_memory_ids)

    if not selected:
        classification = UTILIZATION_NO_SELECTED_EVIDENCE
    elif selected & used:
        classification = UTILIZATION_SELECTED_AND_USED
    else:
        classification = UTILIZATION_SELECTED_BUT_NOT_USED

    return MetricResult(
        metric_name="RETRIEVAL_UTILIZATION",
        value=None,
        status=classification,
        detail={
            "task_id": execution_result.task_id,
            "selected_memory_ids": sorted(selected),
            "used_memory_ids": sorted(used),
            "intersection": sorted(selected & used),
        },
        note="value is intentionally None -- this is a categorical classification, not a scalar metric.",
    )


# ---------------------------------------------------------------------------
# Evidence-available / agent-failed diagnostic
# ---------------------------------------------------------------------------

STATUS_AGENT_FAILURE_WITH_EVIDENCE = "AGENT_FAILURE_WITH_EVIDENCE"
STATUS_NOT_APPLICABLE_EVIDENCE_UNAVAILABLE = "NOT_APPLICABLE_EVIDENCE_UNAVAILABLE"
STATUS_NOT_APPLICABLE_ANSWER_NOT_INCORRECT = "NOT_APPLICABLE_ANSWER_NOT_INCORRECT"


def evidence_available_agent_failed(
    execution_result: AgentExecutionResult,
    expected_answer: Optional[str],
    gold_evidence_available: bool,
) -> MetricResult:
    """DIAGNOSTIC ONLY. Gold evidence was available to the agent (per `gold_evidence_
    available`, an evaluator-side determination the CALLER supplies -- e.g. from
    `classify_observed_failure_stage`'s own retrieval/selection-capacity check, or
    simply "this was a GOLD_EVIDENCE-condition run") AND the agent's answer was incorrect
    -> `AGENT_FAILURE_WITH_EVIDENCE`.

    This function does NOT itself determine evidence availability from retrieval/
    selection capacity (that is `classify_observed_failure_stage`'s job, which calls
    this after determining the gold-hit/selection-miss/retrieval-miss classification
    itself) -- it takes `gold_evidence_available` as an already-known boolean so this
    diagnostic's OWN logic stays a single, simple, testable statement: "evidence present
    + wrong answer -> agent-side failure," with no retrieval/selection reasoning
    duplicated here.

    ★ Must not claim retrieval/selection caused anything when evidence was unavailable.
    If `gold_evidence_available` is False, this function returns
    `STATUS_NOT_APPLICABLE_EVIDENCE_UNAVAILABLE` -- it never reports
    `AGENT_FAILURE_WITH_EVIDENCE` in that case, and never implies retrieval/selection is
    "innocent" either; it simply declines to apply this diagnostic when its precondition
    (evidence availability) does not hold.
    """
    if not gold_evidence_available:
        return MetricResult(
            metric_name="EVIDENCE_AVAILABLE_AGENT_FAILED",
            value=None,
            status=STATUS_NOT_APPLICABLE_EVIDENCE_UNAVAILABLE,
            detail={"task_id": execution_result.task_id},
            note="Gold evidence was not available to the agent; this diagnostic does not apply.",
        )

    classification = classify_agent_success(execution_result, expected_answer)
    if classification.status != SUCCESS_ANSWER_INCORRECT:
        return MetricResult(
            metric_name="EVIDENCE_AVAILABLE_AGENT_FAILED",
            value=None,
            status=STATUS_NOT_APPLICABLE_ANSWER_NOT_INCORRECT,
            detail={
                "task_id": execution_result.task_id,
                "success_classification": classification.status,
            },
            note="Answer was not classified ANSWER_INCORRECT; this diagnostic does not apply.",
        )

    return MetricResult(
        metric_name="EVIDENCE_AVAILABLE_AGENT_FAILED",
        value=1.0,
        status=STATUS_AGENT_FAILURE_WITH_EVIDENCE,
        detail={"task_id": execution_result.task_id},
        note=(
            "Gold evidence was available and the answer was incorrect. This does NOT claim "
            "retrieval or selection is exonerated or implicated -- it is an observed "
            "co-occurrence, reported for the OBSERVED_FAILURE_STAGE classification."
        ),
    )


# ---------------------------------------------------------------------------
# Observed failure-stage classification
# ---------------------------------------------------------------------------

STAGE_RETRIEVAL_FAILURE = "RETRIEVAL_FAILURE"
STAGE_SELECTION_FAILURE = "SELECTION_FAILURE"
STAGE_EVIDENCE_UNAVAILABLE = "EVIDENCE_UNAVAILABLE"
STAGE_AGENT_FAILURE_WITH_EVIDENCE = "AGENT_FAILURE_WITH_EVIDENCE"
STAGE_AGENT_EXECUTION_FAILURE = "AGENT_EXECUTION_FAILURE"
STAGE_SUCCESS = "SUCCESS"
STAGE_UNDEFINED = "UNDEFINED_EVALUATION"

FAILURE_STAGES: tuple = (
    STAGE_RETRIEVAL_FAILURE,
    STAGE_SELECTION_FAILURE,
    STAGE_EVIDENCE_UNAVAILABLE,
    STAGE_AGENT_FAILURE_WITH_EVIDENCE,
    STAGE_AGENT_EXECUTION_FAILURE,
    STAGE_SUCCESS,
)


def classify_observed_failure_stage(
    execution_result: AgentExecutionResult,
    expected_answer: Optional[str],
    gold_evidence_ids: Sequence[str],
    retrieved_memory_ids: Sequence[str] = (),
) -> MetricResult:
    """OBSERVED_FAILURE_STAGE classification: RETRIEVAL_FAILURE / SELECTION_FAILURE /
    EVIDENCE_UNAVAILABLE / AGENT_FAILURE_WITH_EVIDENCE / AGENT_EXECUTION_FAILURE / SUCCESS.

    ================================================================================
    "OBSERVED_FAILURE_STAGE" framing, never a causal claim. This function reports WHICH
    stage's evidence-handling state was observed to co-occur with an incorrect/failed
    outcome -- it never asserts that stage CAUSED the outcome. A RETRIEVAL_FAILURE
    classification means "gold evidence was absent from what was retrieved, and the
    answer was wrong or undefined" -- it does not prove the wrong answer happened
    BECAUSE retrieval missed the evidence (the reasoning layer might have answered
    incorrectly regardless, even with perfect retrieval).
    ================================================================================

    Precedence (checked in this order; the first matching case wins -- exactly one
    stage is ever returned):
    1. `execution_result.execution_status != SUCCESS` -> `AGENT_EXECUTION_FAILURE`.
    2. `classify_agent_success(...).status == SUCCESS_ANSWER_CORRECT` -> `SUCCESS`.
    3. `classify_agent_success(...).status == SUCCESS_EVALUATION_UNDEFINED` ->
       `STAGE_UNDEFINED` (cannot classify a failure stage without knowing whether the
       answer was even wrong).
    4. `execution_result.condition == CONDITION_NO_MEMORY` -> `EVIDENCE_UNAVAILABLE`
       (by construction, no memory was ever made available under this condition -- this
       is never conflated with a retrieval/selection problem, since there was no
       retrieval/selection layer engaged at all).
    5. `gold_evidence_ids` is empty -> `STAGE_UNDEFINED` (nothing to classify retrieval/
       selection capacity against).
    6. `execution_result.condition == CONDITION_GOLD_EVIDENCE` -> `AGENT_FAILURE_WITH_
       EVIDENCE` directly (Condition B hands gold evidence CONTENT directly with no
       retrieval/selection layer in between, per EVALUATION_CONTRACT.md section 5 and
       CLEAN_AGENT_INTERFACES.md section 1 -- there is no retrieval/selection stage to
       blame or exonerate here by construction).
    7. Otherwise, classify EVERY gold id via
       `retrieval.classify_gold_id_capacity(retrieved_memory_ids,
       execution_result.selected_memory_ids, gold_id)` (reused verbatim, not
       reimplemented): if ANY gold id is `RETRIEVAL_MISS` -> `RETRIEVAL_FAILURE`; else if
       ANY is `SELECTION_MISS` -> `SELECTION_FAILURE`; else (all `HIT`) ->
       `AGENT_FAILURE_WITH_EVIDENCE`. This ordering is an explicit DECISION: a retrieval
       miss on ANY gold id is reported as the (observed, not causal) bottleneck ahead of
       a selection miss, and a selection miss ahead of "evidence was fully available" --
       mirroring the historical root-cause ordering (candidate-generation failures are
       the dominant, most severe category per PHASE3_CLEAN_AGENT_FOUNDATION_SPEC.md
       section 3) without claiming this ordering proves causal severity for any specific
       task.
    """
    if execution_result.execution_status != "SUCCESS":
        return MetricResult(
            metric_name="OBSERVED_FAILURE_STAGE",
            value=None,
            status=STAGE_AGENT_EXECUTION_FAILURE,
            detail={"task_id": execution_result.task_id},
            note="Execution did not complete; no answer/evidence handling stage can be observed.",
        )

    success = classify_agent_success(execution_result, expected_answer)

    if success.status == SUCCESS_ANSWER_CORRECT:
        return MetricResult(
            metric_name="OBSERVED_FAILURE_STAGE",
            value=None,
            status=STAGE_SUCCESS,
            detail={"task_id": execution_result.task_id},
            note="Answer was correct; no failure stage to observe.",
        )

    if success.status == SUCCESS_EVALUATION_UNDEFINED:
        return MetricResult(
            metric_name="OBSERVED_FAILURE_STAGE",
            value=None,
            status=STAGE_UNDEFINED,
            detail={"task_id": execution_result.task_id},
            note="Agent success is undefined (no expected_answer); failure stage cannot be classified.",
        )

    # success.status == SUCCESS_ANSWER_INCORRECT from here on.

    if execution_result.condition == CONDITION_NO_MEMORY:
        return MetricResult(
            metric_name="OBSERVED_FAILURE_STAGE",
            value=None,
            status=STAGE_EVIDENCE_UNAVAILABLE,
            detail={"task_id": execution_result.task_id, "condition": execution_result.condition},
            note="NO_MEMORY condition; no memory was made available by construction.",
        )

    if len(gold_evidence_ids) == 0:
        return MetricResult(
            metric_name="OBSERVED_FAILURE_STAGE",
            value=None,
            status=STAGE_UNDEFINED,
            detail={"task_id": execution_result.task_id},
            note="gold_evidence_ids is empty; failure stage cannot be classified against no gold.",
        )

    if execution_result.condition == CONDITION_GOLD_EVIDENCE:
        return MetricResult(
            metric_name="OBSERVED_FAILURE_STAGE",
            value=None,
            status=STAGE_AGENT_FAILURE_WITH_EVIDENCE,
            detail={"task_id": execution_result.task_id, "condition": execution_result.condition},
            note=(
                "GOLD_EVIDENCE condition hands evidence content directly with no retrieval/"
                "selection layer between memory and reasoning; answer was incorrect despite "
                "evidence being directly available."
            ),
        )

    per_gold = {
        gid: classify_gold_id_capacity(
            retrieved_memory_ids, execution_result.selected_memory_ids, gid
        )
        for gid in gold_evidence_ids
    }

    if any(v == CLASSIFICATION_RETRIEVAL_MISS for v in per_gold.values()):
        stage = STAGE_RETRIEVAL_FAILURE
    elif any(v == CLASSIFICATION_SELECTION_MISS for v in per_gold.values()):
        stage = STAGE_SELECTION_FAILURE
    else:
        stage = STAGE_AGENT_FAILURE_WITH_EVIDENCE

    return MetricResult(
        metric_name="OBSERVED_FAILURE_STAGE",
        value=None,
        status=stage,
        detail={
            "task_id": execution_result.task_id,
            "condition": execution_result.condition,
            "per_gold": per_gold,
        },
        note=(
            "OBSERVED_FAILURE_STAGE -- describes what co-occurred with the incorrect answer, "
            "never a causal claim that this stage caused the failure. See module docstring."
        ),
    )
