"""Phase 3.3-V5 -- an EIGHTH, additive answer-correctness metric: multi-reference
gold matching, per the "multi-reference gold answers" suggestion (SQuAD-style: 2-4
acceptable phrasings per question, curated per-instance rather than a global
synonym dictionary applied blindly across the dataset).

WHAT THIS ACTUALLY IS -- AND ISN'T
--------------------------------------------------------------------------------
This reuses the EXACT SAME bidirectional-substring comparison
`normalized_correctness.py` already uses -- this metric adds no new comparison
algorithm. What it adds is MORE REFERENCE TEXTS to compare against: the original
gold answer, PLUS every hand-reviewed alias phrasing for that specific question.
An answer is credited correct if it normalized-matches ANY one of them. Any
improvement over plain normalized_correctness therefore comes entirely from having
more correct target phrasings to hit, never from a looser matching rule -- the
exact SQuAD "answer equivalence via multiple references" idea, not a semantic
fuzzy-match.

PROVENANCE -- WHAT "VERIFIED" MEANS HERE, STATED PLAINLY
--------------------------------------------------------------------------------
The alias set this metric is built to consume (`multiref_gold_aliases_VERIFIED_
110.json`) was LLM-generated, then hand-reviewed by Claude across two passes (a
full read of all 120 candidate sets, plus a targeted second pass re-checking every
negation/yes-no/numeric/date entry for subtle meaning drift) -- ZERO factual
errors found in the 110 kept entries; 10 of the original 120 were excluded because
every candidate in those cases rephrased the QUESTION instead of the ANSWER (a
real, systematic failure mode for short, single-entity gold answers, confirmed by
hand, not a hunch). This is real, disclosed, non-trivial review -- but it is AI
review, not independent human verification, and is reported as such every time
this metric's provenance is described. Never call this "human-verified gold."

COVERAGE IS PARTIAL, BY CONSTRUCTION, NEVER PAPERED OVER
--------------------------------------------------------------------------------
Only 110 of 120 real LoCoMo tasks have verified aliases. For the other 10 (and for
any task_id this metric is asked about that has no alias entry at all), this
metric falls back to comparing against ONLY the original gold answer -- identical
behavior to `normalized_correctness.py` for those tasks, never guessing at
aliases that were never generated or were excluded for cause. The `used_aliases`
field in the returned detail always discloses whether alias matching was actually
available for a given call.

DOES NOT MODIFY OR REPLACE ANY EXISTING METRIC
--------------------------------------------------------------------------------
All seven prior metrics are untouched. This is reported side by side, never
substituted for `normalized_correctness.py` -- a genuinely fair before/after
comparison of "does multi-reference actually help" requires both numbers,
side by side, on the same answers.
"""

from __future__ import annotations

import re
import string
from typing import Mapping, Optional, Sequence

from phase3.evaluation.agent.outcomes import (
    EXECUTION_STATUS_SUCCESS,
    SUCCESS_ANSWER_CORRECT,
    SUCCESS_ANSWER_INCORRECT,
    SUCCESS_EVALUATION_UNDEFINED,
    SUCCESS_EXECUTION_FAILURE,
    AgentExecutionResult,
)
from phase3.evaluation.metrics.types import MetricResult

METRIC_NAME = "ANSWER_CORRECTNESS_MULTI_REFERENCE"

_PUNCT_TABLE = str.maketrans("", "", string.punctuation)


def _normalize(text: str) -> str:
    """Identical declared transform to normalized_correctness.py::_normalize() --
    reused in spirit (not imported) to keep this module's dependency surface
    minimal, same discipline every other additive metric in this package follows."""
    lowered = text.lower().translate(_PUNCT_TABLE)
    return re.sub(r"\s+", " ", lowered).strip()


def _bidirectional_match(reference: str, answer_norm: str) -> bool:
    ref_norm = _normalize(reference)
    return bool(ref_norm) and bool(answer_norm) and (ref_norm in answer_norm or answer_norm in ref_norm)


def load_verified_aliases(path: str) -> Mapping[str, Sequence[str]]:
    """Loads a multiref_gold_aliases_VERIFIED_*.json file into a plain
    {task_id: [alias, ...]} lookup -- the shape evaluate_answer_correctness_multi_
    reference() expects for its `aliases` parameter. Pure I/O helper, not called
    internally by the metric function itself, so the metric stays testable without
    ever touching a filesystem path in its own signature.
    """
    import json

    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {tid: entry.get("candidate_aliases", []) for tid, entry in data.items()}


def evaluate_answer_correctness_multi_reference(
    execution_result: AgentExecutionResult,
    expected_answer: Optional[str],
    aliases: Optional[Sequence[str]] = None,
) -> MetricResult:
    """`aliases` is the caller-supplied list of verified alternate phrasings for
    THIS specific task (typically looked up by task_id from `load_verified_
    aliases()`'s output) -- never fetched internally, so a caller always knows
    exactly which references were actually used, and a task with no verified
    aliases at all simply passes `None` or `[]`, falling back to gold-only
    comparison, identical to `normalized_correctness.py`.
    """
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

    answer_norm = _normalize(str(execution_result.answer))
    references = [str(expected_answer)] + list(aliases or [])

    matched_reference = None
    for ref in references:
        if _bidirectional_match(ref, answer_norm):
            matched_reference = ref
            break

    is_correct = matched_reference is not None
    return MetricResult(
        metric_name=METRIC_NAME,
        value=1.0 if is_correct else 0.0,
        status=SUCCESS_ANSWER_CORRECT if is_correct else SUCCESS_ANSWER_INCORRECT,
        detail={
            "task_id": execution_result.task_id,
            "matched_reference": matched_reference,
            "matched_via_alias": matched_reference is not None and matched_reference != str(expected_answer),
            "used_aliases": bool(aliases),
            "num_references_checked": len(references),
        },
        note=(
            "Bidirectional-substring match against gold PLUS hand-reviewed (AI-"
            "reviewed, not independently human-verified) alias phrasings, when "
            "available for this task_id -- see module docstring for exactly what "
            "'reviewed' means and which 110/120 tasks have aliases. Report "
            "alongside, never in place of, normalized_correctness or the other six "
            "correctness metrics."
        ),
    )


__all__ = [
    "METRIC_NAME",
    "load_verified_aliases",
    "evaluate_answer_correctness_multi_reference",
]
