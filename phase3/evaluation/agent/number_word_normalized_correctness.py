"""Phase 3.3-V5 -- a SIXTH, additive answer-correctness metric, built the same way
`date_normalized_correctness.py` was: a narrow, deterministic, disclosed extension
targeting one specific, previously-identified evaluator-boundary defect, not a
general loosening of grading.

THE DEFECT THIS TARGETS
--------------------------------------------------------------------------------
Hand-classifying the 26 real `SHARED_REASONING_LOSS` cases (V4 diagnosis pass)
found case #12: "How long ago was Caroline's 18th birthday?" gold `"10 years ago"`,
real answer `"Ten years ago [10:37 am on 27 June, 2023]."` -- the SAME fact,
correctly stated, scored wrong by every existing metric because none of them
normalize a cardinal number written as a word ("Ten") against the same number
written as a digit ("10"). This is structurally identical to the digit zero-
padding defect §15.1 already fixed for dates, just for plain cardinal numbers.

SCOPE IS DELIBERATELY NARROW -- REUSES `normalized_correctness.py`'s OWN LOGIC
--------------------------------------------------------------------------------
This metric does NOT reimplement bidirectional-substring matching from scratch --
it applies ONE additional, declared transform (word-form cardinal numbers 0-100,
in step-of-ten and step-of-one units only -- zero/one/two/.../twenty, then
thirty/forty/.../ninety, composed as "twenty-three" etc.) BEFORE running the exact
same normalize-and-bidirectional-substring check `evaluate_answer_correctness_
normalized()` already uses. If neither the gold nor the answer contains a
recognized number word, this metric's result is IDENTICAL to the normalized
metric's -- it only ever adds credit, and only for a number-word match, never
removes it and never invents a fuzzy match elsewhere in the text.

NEVER MODIFIES OR REPLACES `normalized_correctness.py`. Reported as a separate,
clearly-named metric, side by side with the other five, exactly like every other
additive metric in this package.
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

METRIC_NAME = "ANSWER_CORRECTNESS_NUMBER_WORD_NORMALIZED"

_PUNCT_TABLE = str.maketrans("", "", string.punctuation)

_ONES = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19,
}
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90,
}
_HUNDRED = {"hundred": 100}

_ALL_UNITS = {**_ONES, **_TENS, **_HUNDRED}
# Longest-word-first so "seventeen" isn't cut short by a shorter alternate match.
_UNIT_PATTERN = re.compile(
    r"\b(" + "|".join(sorted(_ALL_UNITS, key=len, reverse=True)) + r")\b", re.IGNORECASE
)
# "twenty-three" / "twenty three" -- a tens word directly followed by a ones word.
_COMPOUND_PATTERN = re.compile(
    r"\b(" + "|".join(_TENS) + r")[\s-]+(" + "|".join(k for k in _ONES if _ONES[k] < 10) + r")\b",
    re.IGNORECASE,
)


def _words_to_digits(text: str) -> str:
    """Replaces recognized cardinal-number words with their digit form. Compound
    tens ("twenty-three" -> "23") are resolved before single-unit words are
    replaced, so "twenty" alone in "twenty-three" isn't independently replaced
    first and left orphaned. Never touches ordinal words ("first", "third") or
    anything outside this closed vocabulary -- an unrecognized word is left as-is,
    never guessed at.
    """
    def _compound_sub(m: "re.Match") -> str:
        return str(_TENS[m.group(1).lower()] + _ONES[m.group(2).lower()])

    text = _COMPOUND_PATTERN.sub(_compound_sub, text)

    def _unit_sub(m: "re.Match") -> str:
        return str(_ALL_UNITS[m.group(1).lower()])

    return _UNIT_PATTERN.sub(_unit_sub, text)


def _normalize(text: str) -> str:
    """Identical declared transform to `normalized_correctness.py::_normalize()`,
    PLUS the word-to-digit number substitution above, applied first so punctuation
    stripping doesn't interfere with matching hyphenated compounds."""
    with_digits = _words_to_digits(text)
    lowered = with_digits.lower().translate(_PUNCT_TABLE)
    return re.sub(r"\s+", " ", lowered).strip()


def evaluate_answer_correctness_number_word_normalized(
    execution_result: AgentExecutionResult, expected_answer: Optional[str]
) -> MetricResult:
    if execution_result.execution_status != EXECUTION_STATUS_SUCCESS:
        return MetricResult(
            metric_name=METRIC_NAME, value=None, status=SUCCESS_EXECUTION_FAILURE,
            detail={"task_id": execution_result.task_id, "execution_status": execution_result.execution_status},
            note="execution_status != SUCCESS; there is no answer to judge for correctness.",
        )
    if expected_answer is None or execution_result.answer is None:
        return MetricResult(
            metric_name=METRIC_NAME, value=None, status=SUCCESS_EVALUATION_UNDEFINED,
            detail={"task_id": execution_result.task_id},
            note="Missing expected_answer or answer; correctness is undefined.",
        )

    norm_expected = _normalize(expected_answer)
    norm_actual = _normalize(execution_result.answer)
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
            "Same bidirectional-substring match as ANSWER_CORRECTNESS_NORMALIZED, "
            "plus cardinal number-word-to-digit normalization (0-100 only, closed "
            "vocabulary, never a fuzzy/guessed match). Report alongside, never in "
            "place of, the other five correctness metrics."
        ),
    )


__all__ = [
    "METRIC_NAME",
    "evaluate_answer_correctness_number_word_normalized",
]
