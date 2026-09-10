"""Phase 3.3-RESEARCH -- a THIRD, additive answer-correctness metric, built in direct
response to a real, quantified finding: classifying all 120 real Condition-B (gold
evidence) MEM0 answers against their real gold answers (see
`phase3/experiments/research_variant/PHASE3_RESEARCH_IMPROVEMENT_PLAN.md`) found that
~20% of the 120 tasks are cases where the answer is substantively correct but fails
`evaluate_answer_correctness_normalized()`'s strict bidirectional-substring check purely
because the gold phrasing isn't echoed verbatim (e.g. gold `"Transgender woman"`, answer
`"Caroline's identity is transgender."`).

DOES NOT MODIFY OR REPLACE EITHER EXISTING METRIC
--------------------------------------------------------------------------------
`evaluate_answer_correctness()` (frozen, Phase 3.2-E, exact-match) and
`evaluate_answer_correctness_normalized()` (Phase 3.3-DATASET, bidirectional-substring)
are both untouched, imported nowhere near being altered. This module adds a THIRD,
separately-named metric, reported side by side with the other two, never substituted
for either -- same discipline the normalized metric's own docstring already
established for itself relative to the frozen exact-match metric.

METRIC DEFINITION -- GOLD CONTENT-WORD RECALL
--------------------------------------------------------------------------------
Deterministic, no LLM, no embeddings. Tokenize gold and answer (lowercase, strip
punctuation), remove a small fixed stopword list, and compute what fraction of gold's
remaining CONTENT words appear anywhere in the answer's content words. `ANSWER_CORRECT`
iff that recall is >= `CONTENT_RECALL_THRESHOLD` AND gold has at least one content word
(a gold answer that is ALL stopwords, e.g. "the," has undefined recall by construction
and is never silently marked correct).

THRESHOLD FIXED IN ADVANCE, NOT TUNED ON RESULTS
--------------------------------------------------------------------------------
`CONTENT_RECALL_THRESHOLD = 0.8` was chosen and fixed BEFORE re-scoring the 120-task
Condition-B corpus, precisely so that this metric's own reported effect size cannot be
accused of being tuned to produce a favorable number after the fact. See the
`content_recall_rescoring_report.json` artifact this metric produced for the full
before/after picture at this fixed threshold.

KNOWN, DISCLOSED LIMITATION -- NO NEGATION GUARD
--------------------------------------------------------------------------------
This metric has no semantic understanding and cannot detect a negated or contradicted
answer that happens to share most of gold's content words (e.g. gold "she agreed" vs.
answer "she did not agree" would score a high recall despite being the opposite claim).
This is a real, acknowledged gap, not a silent one -- a genuine semantic-equivalence
check would need either a much larger fixed rule set or an LLM judge (out of scope for
this deterministic metric, and not built here).
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

METRIC_NAME = "ANSWER_CORRECTNESS_CONTENT_RECALL"
CONTENT_RECALL_THRESHOLD = 0.8  # fixed in advance -- see module docstring

_PUNCT_TABLE = str.maketrans("", "", string.punctuation)
_WORD_RE = re.compile(r"[a-z0-9']+")

# Small, fixed, disclosed stopword list -- articles, pronouns, and the most common
# copulas/prepositions/conjunctions. Deliberately conservative (short list) so it never
# strips a genuine content word by overreaching.
_STOPWORDS = frozenset({
    "a", "an", "the", "of", "to", "in", "on", "at", "is", "was", "were", "be", "been",
    "being", "that", "this", "these", "those", "and", "or", "but", "for", "with", "as",
    "by", "it", "its", "their", "his", "her", "hers", "they", "he", "she", "i", "you",
    "we", "us", "them", "him", "my", "your", "our", "from", "into", "about", "than",
    "then", "so", "if", "not", "no", "do", "does", "did", "has", "have", "had", "will",
    "would", "can", "could", "should", "may", "might", "am", "are",
})


def _content_words(text: str) -> frozenset:
    lowered = str(text).lower().translate(_PUNCT_TABLE)
    tokens = _WORD_RE.findall(lowered)
    return frozenset(t for t in tokens if t not in _STOPWORDS)


def content_recall(expected_answer: str, actual_answer: str) -> Optional[float]:
    """Returns the fraction of `expected_answer`'s content words present in
    `actual_answer`'s content words, or None if `expected_answer` has zero content
    words (recall is undefined, never silently treated as 0.0 or 1.0)."""
    gold_words = _content_words(expected_answer)
    if not gold_words:
        return None
    answer_words = _content_words(actual_answer)
    return len(gold_words & answer_words) / len(gold_words)


def evaluate_answer_correctness_content_recall(
    execution_result: AgentExecutionResult, expected_answer: Optional[str]
) -> MetricResult:
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

    recall = content_recall(expected_answer, execution_result.answer)
    if recall is None:
        return MetricResult(
            metric_name=METRIC_NAME, value=None, status=SUCCESS_EVALUATION_UNDEFINED,
            detail={"task_id": execution_result.task_id},
            note="Gold answer has zero content words after stopword removal; recall is undefined.",
        )

    is_correct = recall >= CONTENT_RECALL_THRESHOLD
    return MetricResult(
        metric_name=METRIC_NAME,
        value=1.0 if is_correct else 0.0,
        status=SUCCESS_ANSWER_CORRECT if is_correct else SUCCESS_ANSWER_INCORRECT,
        detail={"task_id": execution_result.task_id, "content_recall": recall, "threshold": CONTENT_RECALL_THRESHOLD},
        note=(
            "Gold content-word recall (stopwords removed) >= threshold, fixed in "
            "advance at 0.8. NOT a semantic-equivalence check -- no negation guard "
            "(see module docstring). Report alongside, never in place of, the exact-match "
            "and bidirectional-substring metrics."
        ),
    )


__all__ = [
    "METRIC_NAME",
    "CONTENT_RECALL_THRESHOLD",
    "content_recall",
    "evaluate_answer_correctness_content_recall",
]
