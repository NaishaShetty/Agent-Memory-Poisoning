"""Phase 3.2-H.3 -- additive, deterministic answer-correctness extensions.

WHY THIS MODULE EXISTS (gap analysis summary; full detail in
`PHASE3_2_H3_FRAMEWORK_EXTENSION_SPEC.md`, Extension 2)
--------------------------------------------------------------------------------
`phase3/evaluation/agent/outcomes.py::evaluate_answer_correctness` is frozen, CANONICAL, and
this module NEVER modifies, redefines, or reimplements it. It is imported and reused
verbatim wherever its exact behavior is needed. It has two hard-coded assumptions baked into
its signature and body that two of the three H.1 candidates genuinely violate:

1. It compares against exactly ONE `expected_answer: Optional[str]`. MemoryAgentBench's
   `answers[i]` is a LIST of acceptable answer-alias strings for a single question (e.g.
   `["France", "France", "France", "France"]` or `["10th and 11th centuries", "in the 10th
   and 11th centuries"]` -- confirmed by
   `phase3/datasets/candidates/memoryagentbench/profile/memoryagentbench_profile.json`'s
   `equivalence` dimension, and by `normalized/task_records.jsonl`'s
   `evaluator_only.gold_answers` field, e.g. `["France", "France", "France", "France"]`).
   Forcing a caller to arbitrarily pick ONE alias before calling
   `evaluate_answer_correctness` would silently discard real gold-answer information the
   source provides. This is a FRAMEWORK LIMITATION (the source genuinely supplies multiple
   acceptable strings; nothing is fabricated by accepting all of them).
2. It calls `.strip()` on `execution_result.answer` and `expected_answer`, which assumes both
   are `str`. MemoryArena's `answers[i]` is `dict` (bundled_shopping), `list`
   (group_travel_planner), or `str` (progressive_search/formal_reasoning_math/phys) --
   confirmed by full-scan in `phase3/datasets/candidates/memoryarena/normalized/
   subtasks.jsonl` and by `manifests/registry_entry.json`'s `known_limitations`. Calling
   `.strip()` on a `dict`/`list` raises `AttributeError`; there is no principled way to
   coerce a structured answer into the existing str-only function without changing what
   "exact match" means for that function. This, too, is a FRAMEWORK LIMITATION: the
   underlying source data is genuinely structured, not a string the existing function was
   ever designed to accept.

Both gaps are solved ADDITIVELY here, as NEW functions with NEW metric names, never by
editing `outcomes.py`:

- `evaluate_answer_correctness_multi_reference`: exact-match (after the SAME `.strip()`-only
  normalization as the canonical function, applied per-candidate) against a SET of
  acceptable answer strings. For the degenerate case of exactly one candidate string, this
  function is proven (by an exact-assertion test) to agree with
  `outcomes.evaluate_answer_correctness` on every shared fixture -- it is a strict
  generalization, not a redefinition.
- `evaluate_structural_answer_correctness`: deterministic, recursive, non-fuzzy equality
  (`==`) between `execution_result.answer` and `expected_answer` of ANY JSON-like type (str/
  int/float/bool/None/list/dict). For `str` inputs, this function performs the IDENTICAL
  `.strip()`-then-compare normalization as the canonical function (again proven identical by
  test on shared fixtures) -- it only EXTENDS coverage to non-str types the canonical
  function was never designed to handle, it does not change str-vs-str behavior.

Neither function is a semantic/fuzzy/LLM-based comparison. Both are PROVISIONAL (no contract
document defines multi-reference or structural answer matching) and DIAGNOSTIC in the same
sense the canonical function already is: a deterministic correctness judgment, not agent
task success considered more broadly.

Pure functions: no filesystem/network/LLM/embeddings access, no randomness, no global state.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from phase3.evaluation.agent.outcomes import (
    AgentExecutionResult,
    EXECUTION_STATUS_SUCCESS,
    SUCCESS_ANSWER_CORRECT,
    SUCCESS_ANSWER_INCORRECT,
    SUCCESS_EVALUATION_UNDEFINED,
    SUCCESS_EXECUTION_FAILURE,
)
from phase3.evaluation.metrics.types import MetricResult

# ---------------------------------------------------------------------------
# Multi-reference exact-match answer correctness
# ---------------------------------------------------------------------------


def evaluate_answer_correctness_multi_reference(
    execution_result: AgentExecutionResult, expected_answers: Optional[Sequence[str]]
) -> MetricResult:
    """PROVISIONAL, additive generalization of
    `agent.outcomes.evaluate_answer_correctness` to a SET of acceptable gold-answer
    strings (MemoryAgentBench's `answers[i]` alias-list shape).

    Definition
    ----------
    - `execution_result.execution_status != EXECUTION_STATUS_SUCCESS`: undefined, status
      `SUCCESS_EXECUTION_FAILURE` (reused constant, identical semantics to the canonical
      function).
    - `expected_answers` is `None` or empty: undefined, status
      `SUCCESS_EVALUATION_UNDEFINED` -- an empty alias set is exactly as uninformative as no
      expected answer at all; never silently treated as "no valid answer exists" (0) or
      "anything is correct" (1).
    - `execution_result.answer is None` despite `execution_status == SUCCESS`: undefined,
      same status, mirroring the canonical function's defensive handling.
    - Otherwise: `ANSWER_CORRECT` (value=1.0) iff
      `execution_result.answer.strip() == candidate.strip()` for AT LEAST ONE
      `candidate in expected_answers`; else `ANSWER_INCORRECT` (value=0.0). Each candidate
      is compared with the exact same `.strip()`-only normalization the canonical function
      uses -- no case-folding, no punctuation stripping, no fuzzy/semantic comparison.

    Non-redefinition proof: for a single-element `expected_answers`, this function's result
    is identical to `outcomes.evaluate_answer_correctness(execution_result,
    expected_answers[0])` on every shared status/value -- see
    `test_h3_answer_matching.py::test_multi_reference_agrees_with_canonical_for_single_reference`.
    """
    if execution_result.execution_status != EXECUTION_STATUS_SUCCESS:
        return MetricResult(
            metric_name="ANSWER_CORRECTNESS_MULTI_REFERENCE",
            value=None,
            status=SUCCESS_EXECUTION_FAILURE,
            detail={
                "task_id": execution_result.task_id,
                "execution_status": execution_result.execution_status,
            },
            note="execution_status != SUCCESS; there is no answer to judge for correctness.",
        )

    if not expected_answers:
        return MetricResult(
            metric_name="ANSWER_CORRECTNESS_MULTI_REFERENCE",
            value=None,
            status=SUCCESS_EVALUATION_UNDEFINED,
            detail={"task_id": execution_result.task_id, "num_candidates": 0},
            note="expected_answers is None/empty; multi-reference correctness is undefined.",
        )

    if execution_result.answer is None:
        return MetricResult(
            metric_name="ANSWER_CORRECTNESS_MULTI_REFERENCE",
            value=None,
            status=SUCCESS_EVALUATION_UNDEFINED,
            detail={"task_id": execution_result.task_id},
            note="execution_status is SUCCESS but answer is None; correctness is undefined.",
        )

    answer_stripped = execution_result.answer.strip()
    matched = [c for c in expected_answers if c is not None and answer_stripped == c.strip()]
    is_correct = len(matched) > 0

    return MetricResult(
        metric_name="ANSWER_CORRECTNESS_MULTI_REFERENCE",
        value=1.0 if is_correct else 0.0,
        status=SUCCESS_ANSWER_CORRECT if is_correct else SUCCESS_ANSWER_INCORRECT,
        detail={
            "task_id": execution_result.task_id,
            "answer": execution_result.answer,
            "num_candidates": len(expected_answers),
            "matched_candidates": matched,
        },
        note=(
            "PROVISIONAL, additive generalization of ANSWER_CORRECTNESS to a set of "
            "acceptable answer strings. Deterministic exact-match (.strip() only) against "
            "each candidate -- no fuzzy/semantic comparison."
        ),
    )


# ---------------------------------------------------------------------------
# Structural (non-str-safe) answer correctness
# ---------------------------------------------------------------------------


def _normalize_for_comparison(value: Any) -> Any:
    """`.strip()` for str, identity otherwise -- mirrors the canonical function's ONLY
    normalization step, extended (not altered) to pass non-str values through unchanged.
    """
    if isinstance(value, str):
        return value.strip()
    return value


def evaluate_structural_answer_correctness(
    execution_result: AgentExecutionResult, expected_answer: Any
) -> MetricResult:
    """PROVISIONAL, additive generalization of
    `agent.outcomes.evaluate_answer_correctness` to JSON-like structured answers (dict/list),
    for MemoryArena's `bundled_shopping` (dict answers) and `group_travel_planner` (list
    answers) configs, where the canonical function's `.strip()` call would raise
    `AttributeError`.

    Definition
    ----------
    Identical control flow (execution-failure / undefined-expected-answer / undefined-None-
    answer checks) to the canonical function. Final comparison: both sides are normalized via
    `_normalize_for_comparison` (`.strip()` for `str`, identity for everything else), then
    compared with plain recursive `==` -- Python's built-in dict/list/scalar equality, which
    is inherently structural (dict comparison ignores key order; list comparison is
    order-sensitive, which is correct here since MemoryArena's list-of-day-plan answers are
    order-meaningful). No fuzzy/semantic comparison of any kind.

    Non-redefinition proof: for `str`-typed `expected_answer`/`execution_result.answer`
    pairs, this function's result is identical to
    `outcomes.evaluate_answer_correctness(execution_result, expected_answer)` on every shared
    fixture -- see
    `test_h3_answer_matching.py::test_structural_correctness_agrees_with_canonical_for_str_answers`.
    """
    if execution_result.execution_status != EXECUTION_STATUS_SUCCESS:
        return MetricResult(
            metric_name="STRUCTURAL_ANSWER_CORRECTNESS",
            value=None,
            status=SUCCESS_EXECUTION_FAILURE,
            detail={
                "task_id": execution_result.task_id,
                "execution_status": execution_result.execution_status,
            },
            note="execution_status != SUCCESS; there is no answer to judge for correctness.",
        )

    if expected_answer is None:
        return MetricResult(
            metric_name="STRUCTURAL_ANSWER_CORRECTNESS",
            value=None,
            status=SUCCESS_EVALUATION_UNDEFINED,
            detail={"task_id": execution_result.task_id},
            note="expected_answer is None; structural correctness is undefined.",
        )

    if execution_result.answer is None:
        return MetricResult(
            metric_name="STRUCTURAL_ANSWER_CORRECTNESS",
            value=None,
            status=SUCCESS_EVALUATION_UNDEFINED,
            detail={"task_id": execution_result.task_id},
            note="execution_status is SUCCESS but answer is None; correctness is undefined.",
        )

    is_correct = _normalize_for_comparison(execution_result.answer) == _normalize_for_comparison(
        expected_answer
    )
    return MetricResult(
        metric_name="STRUCTURAL_ANSWER_CORRECTNESS",
        value=1.0 if is_correct else 0.0,
        status=SUCCESS_ANSWER_CORRECT if is_correct else SUCCESS_ANSWER_INCORRECT,
        detail={
            "task_id": execution_result.task_id,
            "answer_type": type(execution_result.answer).__name__,
            "expected_answer_type": type(expected_answer).__name__,
        },
        note=(
            "PROVISIONAL, additive generalization of ANSWER_CORRECTNESS to JSON-like "
            "structured (dict/list) answers via deterministic recursive `==` -- no fuzzy/"
            "semantic comparison."
        ),
    )
