"""Phase 3.3-DATASET -- an ADDITIVE, non-replacing correctness metric.

`outcomes.py::evaluate_answer_correctness()` (Phase 3.2-E, frozen) is deliberately
strict exact-match after only `.strip()` -- by explicit design, not a bug (see that
function's own docstring). Running it against the real 120x2 dataset produced a
near-zero `ANSWER_CORRECT` rate even for substantively right answers (e.g. gold
`"Extreme sports"` vs real model output `"extreme sports [evidence-slot-1]"`) --
traced directly to the grader, not the agent (`PHASE3_3_DATASET_FULL_120x2_COMPLETION_REPORT.md`
section 3).

This module does NOT change or replace that frozen grader. It adds a SEPARATE,
clearly-named metric answering a different, narrower question: "does the answer
contain the gold answer as a normalized substring" -- still fully deterministic, no
LLM/embedding involved, same "no case-folding beyond what's declared" discipline
`evaluate_answer_correctness()` itself established, just with normalization actually
declared and case-folding + light punctuation-stripping applied. Both metrics are
meant to be reported side by side, never one silently substituted for the other.
"""

from __future__ import annotations

import re
import string
from typing import Optional

from phase3.evaluation.agent.outcomes import (
    EXECUTION_STATUS_SUCCESS,
    SUCCESS_ANSWER_CORRECT,
    SUCCESS_ANSWER_INCORRECT,
    SUCCESS_EVALUATION_UNDEFINED,
    SUCCESS_EXECUTION_FAILURE,
    AgentExecutionResult,
)
from phase3.evaluation.metrics.types import MetricResult

METRIC_NAME = "ANSWER_CORRECTNESS_NORMALIZED"

_PUNCT_TABLE = str.maketrans("", "", string.punctuation)


def _normalize(text: str) -> str:
    """Declared, deterministic normalization: lowercase, strip surrounding
    whitespace, strip ASCII punctuation, collapse internal whitespace runs. No
    stemming, no synonym matching, no fuzzy edit distance -- still a purely
    structural transform, just a more permissive one than `.strip()` alone."""
    lowered = text.lower().translate(_PUNCT_TABLE)
    return re.sub(r"\s+", " ", lowered).strip()


def evaluate_answer_correctness_normalized(
    execution_result: AgentExecutionResult, expected_answer: Optional[str]
) -> MetricResult:
    """`ANSWER_CORRECT` (normalized) iff the normalized expected answer appears as a
    substring of the normalized actual answer, OR vice versa (handles both
    "answer is a superstring with citation/framing added" -- the `"extreme sports
    [evidence-slot-1]"` case -- and "answer is a terser paraphrase of a longer gold
    string"). Same undefined/execution-failure precedence as
    `evaluate_answer_correctness()`, reused verbatim in spirit (not imported, to
    keep this module's own dependency surface minimal -- it only needs
    `AgentExecutionResult`'s fields, not the frozen function's internals).
    """
    if execution_result.execution_status != EXECUTION_STATUS_SUCCESS:
        return MetricResult(
            metric_name=METRIC_NAME, value=None, status=SUCCESS_EXECUTION_FAILURE,
            detail={"task_id": execution_result.task_id, "execution_status": execution_result.execution_status},
            note="execution_status != SUCCESS; there is no answer to judge for correctness.",
        )
    if expected_answer is None:
        return MetricResult(
            metric_name=METRIC_NAME, value=None, status=SUCCESS_EVALUATION_UNDEFINED,
            detail={"task_id": execution_result.task_id},
            note="No evaluator-supplied expected_answer was provided; correctness is undefined.",
        )
    if execution_result.answer is None:
        return MetricResult(
            metric_name=METRIC_NAME, value=None, status=SUCCESS_EVALUATION_UNDEFINED,
            detail={"task_id": execution_result.task_id},
            note="execution_status is SUCCESS but answer is None -- defensive, shouldn't normally happen.",
        )

    norm_expected = _normalize(expected_answer)
    norm_actual = _normalize(execution_result.answer)
    # KNOWN BUG, discovered 2026-09-08 (Phase 3.3-RESEARCH Round 12): an empty
    # `norm_actual` is a substring of every string, so a genuinely empty/truncated
    # answer was previously auto-credited as ANSWER_CORRECT via `norm_actual in
    # norm_expected`. Never surfaced with Qwen3-8B (which essentially never returned a
    # truly empty answer); surfaced immediately when a reasoning model exhausted its
    # token budget mid-thinking and returned "". Guarding `bool(norm_actual)`
    # explicitly -- an empty answer can never be correct, regardless of gold content.
    is_correct = bool(norm_expected) and bool(norm_actual) and (norm_expected in norm_actual or norm_actual in norm_expected)

    return MetricResult(
        metric_name=METRIC_NAME,
        value=1.0 if is_correct else 0.0,
        status=SUCCESS_ANSWER_CORRECT if is_correct else SUCCESS_ANSWER_INCORRECT,
        detail={
            "task_id": execution_result.task_id,
            "normalized_expected": norm_expected, "normalized_actual": norm_actual,
        },
        note=(
            "Normalized bidirectional-substring match -- lowercase, punctuation-stripped, "
            "whitespace-collapsed, NOT the frozen exact-match ANSWER_CORRECTNESS metric. "
            "Report both side by side; never substitute one for the other."
        ),
    )


__all__ = ["METRIC_NAME", "evaluate_answer_correctness_normalized"]
