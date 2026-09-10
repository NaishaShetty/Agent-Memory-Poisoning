"""Phase 3.3-RESEARCH -- a FOURTH, additive answer-correctness metric, built in direct
response to a real, manually-verified finding: reading all 21 remaining "error" bucket
Condition-B answers by hand (see PHASE3_RESEARCH_IMPROVEMENT_PLAN.md) found that several
are correct via SYNONYM or full semantic paraphrase that neither the bidirectional
substring metric nor the word-overlap-based content-recall metric can catch -- e.g. gold
`"quit"` vs. answer `"Give up."` (pure synonym, zero shared word stems), or gold `"Happy
to share"` vs. answer `"felt positive about sharing... enthusiastic... willingness to
send her the recipe"` (correct, but shares almost no literal words with gold at all).

DOES NOT MODIFY OR REPLACE ANY EXISTING METRIC
--------------------------------------------------------------------------------
`evaluate_answer_correctness()` (frozen exact-match), `evaluate_answer_correctness_normalized()`
(bidirectional substring), and `evaluate_answer_correctness_content_recall()` (gold
content-word recall) are all untouched. This is a FOURTH metric, reported alongside the
other three, never substituting for any of them.

METRIC DEFINITION -- EMBEDDING COSINE SIMILARITY
--------------------------------------------------------------------------------
Reuses `foundations.similarity.score_candidates()` -- the SAME
`sentence-transformers/all-MiniLM-L6-v2` model already loaded twice over elsewhere in
this codebase (Mem0/A-MEM's own retrieval, and the benchmark-owned reranker) -- so this
introduces NO new dependency. `ANSWER_CORRECT` iff cosine similarity between gold and
answer is >= `SEMANTIC_SIMILARITY_THRESHOLD`.

THRESHOLD FIXED IN ADVANCE, NOT TUNED ON RESULTS
--------------------------------------------------------------------------------
`SEMANTIC_SIMILARITY_THRESHOLD = 0.6` is a commonly-used default for "semantically
equivalent" in semantic-textual-similarity literature for this embedding family, chosen
and fixed BEFORE re-scoring any real data with it -- not calibrated against this
project's own gold-evidence corpus (there is no independent, separately-labeled
calibration set available the way `selection_policy.py`'s threshold was calibrated
against real gold-evidence retrieval scores). This is a materially weaker calibration
basis than the other project thresholds, and is disclosed as such, not presented as
equally rigorous.

KNOWN, DISCLOSED LIMITATIONS
--------------------------------------------------------------------------------
- Same negation blindness as content-recall: a small sentence embedder frequently
  scores "X happened" and "X did not happen" as highly similar (near-duplicate topic,
  opposite truth value) -- this metric CANNOT be trusted alone to rule out a negated/
  contradicted answer, exactly the same disclosed gap as the content-recall metric.
- The 0.6 threshold is a literature default, not project-calibrated -- report this
  metric's numbers with that caveat attached, not as equally authoritative as the
  content-recall metric's threshold (which at least follows the same fixed-in-advance
  discipline, even without an independent calibration set).
- Requires `sentence-transformers` to be importable (same requirement `similarity.py`
  already documents) -- raises `SimilarityModelUnavailableError` from that module if
  not, never silently degrades to a fake score.
"""

from __future__ import annotations

from typing import Optional

from phase3.evaluation.agent.outcomes import (
    EXECUTION_STATUS_SUCCESS,
    SUCCESS_ANSWER_CORRECT,
    SUCCESS_ANSWER_INCORRECT,
    SUCCESS_EVALUATION_UNDEFINED,
    SUCCESS_EXECUTION_FAILURE,
    AgentExecutionResult,
)
from phase3.evaluation.foundations.similarity import score_candidates
from phase3.evaluation.metrics.types import MetricResult

METRIC_NAME = "ANSWER_CORRECTNESS_SEMANTIC_SIMILARITY"
SEMANTIC_SIMILARITY_THRESHOLD = 0.6  # literature default, fixed in advance -- see module docstring


def semantic_similarity(expected_answer: str, actual_answer: str) -> float:
    scored = score_candidates(expected_answer, [("actual", actual_answer)])
    return scored[0].score


def evaluate_answer_correctness_semantic_similarity(
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

    sim = semantic_similarity(expected_answer, execution_result.answer)
    is_correct = sim >= SEMANTIC_SIMILARITY_THRESHOLD
    return MetricResult(
        metric_name=METRIC_NAME,
        value=1.0 if is_correct else 0.0,
        status=SUCCESS_ANSWER_CORRECT if is_correct else SUCCESS_ANSWER_INCORRECT,
        detail={"task_id": execution_result.task_id, "cosine_similarity": sim, "threshold": SEMANTIC_SIMILARITY_THRESHOLD},
        note=(
            "Embedding cosine similarity (sentence-transformers/all-MiniLM-L6-v2) >= "
            "threshold, a LITERATURE DEFAULT not project-calibrated (weaker basis than "
            "the other metrics' thresholds -- see module docstring). No negation guard. "
            "Report alongside, never in place of, the other three correctness metrics."
        ),
    )


__all__ = [
    "METRIC_NAME",
    "SEMANTIC_SIMILARITY_THRESHOLD",
    "semantic_similarity",
    "evaluate_answer_correctness_semantic_similarity",
]
