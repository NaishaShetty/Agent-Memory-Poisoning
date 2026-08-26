"""Paired-condition comparison harness and the memory-contribution diagnostic.

Phase 3.2-E scope note: this module deliberately uses "PAIRED CONDITION COMPARISON"
terminology throughout, never "counterfactual." A counterfactual claim ("had memory been
absent, the answer would have been X") requires holding everything else about a SINGLE
execution fixed while hypothetically varying one input -- this module does no such
thing. It compares two SEPARATE, already-executed `AgentExecutionResult`s (one under
NO_MEMORY, one under a WITH_MEMORY condition) for the SAME task/expected-answer identity,
and reports what was OBSERVED in each, never what would have happened. This is a much
weaker and more honest claim than "counterfactual," and the naming makes that explicit.

The memory-contribution classification produced here (`POSITIVE_MEMORY_CONTRIBUTION` /
`NO_OBSERVED_MEMORY_CONTRIBUTION` / `NEGATIVE_MEMORY_EFFECT`) is DIAGNOSTIC ONLY and
explicitly non-causal: it reports an observed PAIRED outcome difference, never a proof
that memory access caused the difference (a different reasoning-layer run under the same
two conditions, or a different task, could observe a different pairing outcome). See
`phase3/evaluation/agent/README.md`'s CANONICAL/PROVISIONAL/DIAGNOSTIC-ONLY table.

Pure functions: no filesystem/network/LLM/embeddings access, no randomness, no global
state.
"""

from __future__ import annotations

from typing import Mapping, Optional, Sequence

from phase3.evaluation.metrics.types import MetricResult

from .conditions import CONDITION_NO_MEMORY, WITH_MEMORY_CONDITIONS
from .outcomes import (
    AgentExecutionResult,
    SUCCESS_ANSWER_CORRECT,
    SUCCESS_ANSWER_INCORRECT,
    SUCCESS_EVALUATION_UNDEFINED,
    SUCCESS_EXECUTION_FAILURE,
    classify_agent_success,
)


class PairedComparisonIdentityError(ValueError):
    """Raised when a paired-condition comparison is attempted across two execution
    results that do not share the same task identity (task_id and/or expected_answer).
    A PAIRED_CONDITION_COMPARISON is only meaningful when both sides answer the SAME
    task against the SAME expected answer -- comparing across different tasks would
    silently manufacture a meaningless contribution signal.
    """


# ---------------------------------------------------------------------------
# Paired-condition comparison
# ---------------------------------------------------------------------------


def paired_condition_comparison(
    no_memory_result: AgentExecutionResult,
    with_memory_result: AgentExecutionResult,
    expected_answer_no_memory: Optional[str],
    expected_answer_with_memory: Optional[str],
) -> MetricResult:
    """PAIRED_CONDITION_COMPARISON (never "counterfactual") between a NO_MEMORY-condition
    execution result and a WITH_MEMORY-condition (any of `WITH_MEMORY_CONDITIONS`)
    execution result for what must be the SAME underlying task.

    Identity enforcement (required by the 3.2-E task brief)
    --------------------------------------------------------
    Raises `PairedComparisonIdentityError` if:
    - `no_memory_result.task_id != with_memory_result.task_id`, or
    - `expected_answer_no_memory != expected_answer_with_memory` (the evaluator-supplied
      expected answer must be identical across both sides of the pair -- a mismatch would
      mean the two runs are not actually evaluating the same question), or
    - `no_memory_result.condition != CONDITION_NO_MEMORY`, or
    - `with_memory_result.condition not in WITH_MEMORY_CONDITIONS`.

    Returns
    -------
    A `MetricResult` (`metric_name="PAIRED_CONDITION_COMPARISON"`) whose `detail` carries
    both sides' success classifications (`no_memory_classification`,
    `with_memory_classification`) and `value=None` (this function reports the paired
    observation, not a scalar -- the scalar contribution classification is
    `classify_memory_contribution()`'s job, which calls this function first).
    """
    if no_memory_result.condition != CONDITION_NO_MEMORY:
        raise PairedComparisonIdentityError(
            f"no_memory_result.condition must be {CONDITION_NO_MEMORY!r}, got "
            f"{no_memory_result.condition!r}."
        )
    if with_memory_result.condition not in WITH_MEMORY_CONDITIONS:
        raise PairedComparisonIdentityError(
            f"with_memory_result.condition must be one of {WITH_MEMORY_CONDITIONS!r}, got "
            f"{with_memory_result.condition!r}."
        )
    if no_memory_result.task_id != with_memory_result.task_id:
        raise PairedComparisonIdentityError(
            "PAIRED_CONDITION_COMPARISON requires the same task_id on both sides; got "
            f"{no_memory_result.task_id!r} vs. {with_memory_result.task_id!r}."
        )
    if expected_answer_no_memory != expected_answer_with_memory:
        raise PairedComparisonIdentityError(
            "PAIRED_CONDITION_COMPARISON requires the same expected_answer on both sides; "
            f"got {expected_answer_no_memory!r} vs. {expected_answer_with_memory!r}."
        )

    no_memory_classification = classify_agent_success(no_memory_result, expected_answer_no_memory)
    with_memory_classification = classify_agent_success(with_memory_result, expected_answer_with_memory)

    return MetricResult(
        metric_name="PAIRED_CONDITION_COMPARISON",
        value=None,
        status="PAIRED_CONDITION_COMPARISON",
        detail={
            "task_id": no_memory_result.task_id,
            "no_memory_condition": no_memory_result.condition,
            "with_memory_condition": with_memory_result.condition,
            "no_memory_classification": no_memory_classification.status,
            "with_memory_classification": with_memory_classification.status,
        },
        note=(
            "PAIRED observation only -- NOT a counterfactual claim. See module docstring."
        ),
    )


# ---------------------------------------------------------------------------
# Memory contribution diagnostic (DIAGNOSTIC ONLY / PROVISIONAL, non-causal)
# ---------------------------------------------------------------------------

CONTRIBUTION_POSITIVE = "POSITIVE_MEMORY_CONTRIBUTION"
CONTRIBUTION_NONE = "NO_OBSERVED_MEMORY_CONTRIBUTION"
CONTRIBUTION_NEGATIVE = "NEGATIVE_MEMORY_EFFECT"
CONTRIBUTION_UNDEFINED = "UNDEFINED_MEMORY_CONTRIBUTION"


def classify_memory_contribution(
    no_memory_result: AgentExecutionResult,
    with_memory_result: AgentExecutionResult,
    expected_answer_no_memory: Optional[str],
    expected_answer_with_memory: Optional[str],
) -> MetricResult:
    """DIAGNOSTIC ONLY, PROVISIONAL, explicitly NON-CAUSAL. Classifies a single paired
    (NO_MEMORY, WITH_MEMORY) task-level comparison into exactly one of four cases:

    ```
    NO_MEMORY incorrect, WITH_MEMORY correct   -> POSITIVE_MEMORY_CONTRIBUTION
    NO_MEMORY correct,   WITH_MEMORY correct   -> NO_OBSERVED_MEMORY_CONTRIBUTION
                                                   (memory unnecessary: already succeeded)
    NO_MEMORY incorrect, WITH_MEMORY incorrect -> NO_OBSERVED_MEMORY_CONTRIBUTION
                                                   (memory did not help; both failed)
    NO_MEMORY correct,   WITH_MEMORY incorrect -> NEGATIVE_MEMORY_EFFECT
    ```

    If either side's success classification is `EXECUTION_FAILURE` or
    `EVALUATION_UNDEFINED`, the pair's contribution is `CONTRIBUTION_UNDEFINED` --
    contribution cannot be assessed when one side's correctness itself is unknown.

    This function first calls `paired_condition_comparison()`, so the same task/
    expected-answer identity enforcement (raising `PairedComparisonIdentityError` on a
    mismatch) applies here too.

    ================================================================================
    NON-CAUSAL, DIAGNOSTIC ONLY. `POSITIVE_MEMORY_CONTRIBUTION` reports an OBSERVED
    paired outcome difference for ONE task under ONE reasoning behavior -- it is not
    proof that memory access CAUSED the difference in any deeper sense (e.g. the
    NO_MEMORY-condition run's incorrect answer could have been due to an unrelated
    reasoning slip that happened to not recur on the WITH_MEMORY-condition run). No
    aggregate formula beyond a simple per-pair tally (see
    `memory_contribution_tally()`) is frozen by this module -- there is no invented
    single combined "memory contribution score."
    ================================================================================
    """
    comparison = paired_condition_comparison(
        no_memory_result,
        with_memory_result,
        expected_answer_no_memory,
        expected_answer_with_memory,
    )
    no_mem_status = comparison.detail["no_memory_classification"]
    with_mem_status = comparison.detail["with_memory_classification"]

    undefined_statuses = (SUCCESS_EXECUTION_FAILURE, SUCCESS_EVALUATION_UNDEFINED)
    if no_mem_status in undefined_statuses or with_mem_status in undefined_statuses:
        classification = CONTRIBUTION_UNDEFINED
    elif no_mem_status == SUCCESS_ANSWER_INCORRECT and with_mem_status == SUCCESS_ANSWER_CORRECT:
        classification = CONTRIBUTION_POSITIVE
    elif no_mem_status == SUCCESS_ANSWER_CORRECT and with_mem_status == SUCCESS_ANSWER_INCORRECT:
        classification = CONTRIBUTION_NEGATIVE
    else:
        # Both correct, or both incorrect.
        classification = CONTRIBUTION_NONE

    return MetricResult(
        metric_name="MEMORY_CONTRIBUTION",
        value=None,
        status=classification,
        detail={
            "task_id": no_memory_result.task_id,
            "no_memory_classification": no_mem_status,
            "with_memory_classification": with_mem_status,
            "with_memory_condition": with_memory_result.condition,
        },
        note=(
            "DIAGNOSTIC ONLY, PROVISIONAL, non-causal. Reports an observed paired-outcome "
            "difference for one task, never a causal claim about why. See module docstring."
        ),
    )


def memory_contribution_tally(
    pairs: Sequence[MetricResult],
) -> MetricResult:
    """Convenience per-classification TALLY (count) across a set of
    `classify_memory_contribution()` results -- NOT a single frozen combined score,
    per the 3.2-E task brief's explicit prohibition on inventing one. Mirrors the
    tally-only aggregation pattern already used by
    `provenance.py::provenance_completeness_report()`'s `counts` dict.

    Edge case: empty `pairs` -> undefined (`value=None`,
    `status="UNDEFINED_EMPTY_SEQUENCE"`), never silently reported as all-zero.
    """
    if len(pairs) == 0:
        return MetricResult(
            metric_name="MEMORY_CONTRIBUTION_TALLY",
            value=None,
            status="UNDEFINED_EMPTY_SEQUENCE",
            detail={"counts": {}},
            note="No paired comparisons supplied; tally is undefined.",
        )

    counts = {
        CONTRIBUTION_POSITIVE: 0,
        CONTRIBUTION_NONE: 0,
        CONTRIBUTION_NEGATIVE: 0,
        CONTRIBUTION_UNDEFINED: 0,
    }
    for pair in pairs:
        counts[pair.status] += 1

    return MetricResult(
        metric_name="MEMORY_CONTRIBUTION_TALLY",
        value=float(counts[CONTRIBUTION_POSITIVE]) / len(pairs),
        status="OK",
        detail={"counts": counts, "num_pairs": len(pairs)},
        note=(
            "value is the POSITIVE_MEMORY_CONTRIBUTION fraction, a convenience scalar only -- "
            "detail['counts'] carries the full, never-merged four-way tally. This is NOT a "
            "combined memory-contribution score; no such score is defined anywhere in this "
            "package."
        ),
    )
