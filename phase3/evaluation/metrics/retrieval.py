"""Recall@K, MRR, and retrieval/selection-capacity diagnostics.

Evaluator-side only: every function here takes plain, already-extracted ID lists (the
shape an evaluator would pull from `AgentExecutionResult.retrieved_memory_ids` /
`selected_memory_ids` and `EvaluatorReference.gold_evidence_ids`), never an
`AgentVisibleContext`-shaped object and never a parameter literally named/typed as such.
Gold labels must always arrive via an evaluator-only source. See
`phase3/evaluation/tests/test_core_memory_metrics.py::test_no_metric_function_takes_agent_visible_context`
for the automated check of this property.

Pure functions: no filesystem/network/LLM/embeddings access, no randomness, no global
state. Deterministic given the same inputs.
"""

from __future__ import annotations

from statistics import mean, median
from typing import Sequence

from .types import (
    MetricResult,
    STATUS_NO_HIT,
    STATUS_OK,
    STATUS_UNDEFINED_EMPTY_GOLD,
    STATUS_UNDEFINED_EMPTY_TASK_SET,
    STATUS_UNDEFINED_K_NON_POSITIVE,
)

# ---------------------------------------------------------------------------
# Recall@K
# ---------------------------------------------------------------------------


def recall_at_k(
    retrieved_ranked_ids: Sequence[str], gold_ids: Sequence[str], k: int
) -> MetricResult:
    """Recall@K for a single task: 1 if any gold id appears in the first K retrieved ids
    (order-preserving prefix, NOT deduplicated), else 0.

    Definition
    ----------
    ``recall_at_k = 1 if set(retrieved_ranked_ids[:k]) & set(gold_ids) else 0``

    Edge cases (explicit, never silently coerced):
    - ``k <= 0``: undefined. Returns ``value=None``,
      ``status=STATUS_UNDEFINED_K_NON_POSITIVE``. Recall@K is only meaningful for a
      positive cutoff.
    - ``gold_ids`` empty: undefined (there is no gold id that could ever be "found").
      Returns ``value=None``, ``status=STATUS_UNDEFINED_EMPTY_GOLD``. This is a
      conservative choice -- it would be equally possible to call this "vacuously 1" (no
      gold to miss) or "vacuously 0" (nothing was found); this module refuses to guess and
      instead reports the case explicitly rather than picking a convention silently.
    - ``retrieved_ranked_ids`` empty (and gold non-empty): well-defined, value 0.0 --
      nothing was retrieved, so no gold id can have been found.
    - ``k > len(retrieved_ranked_ids)``: well-defined. The prefix is simply the entire
      (shorter) list; `detail["k_requested"]` and `detail["k_effective"]` record both so a
      caller can see the cutoff was clamped, and `note` states this explicitly.
    - Duplicate ids in `retrieved_ranked_ids`: NOT deduplicated before taking the prefix --
      the first K raw entries (including repeats) are examined, per the task brief ("not
      deduplicating unless contract says so" -- no contract document specifies dedup
      behavior for Recall@K, so the literal prefix is used).

    Monotonicity: for fixed `retrieved_ranked_ids` and `gold_ids`, `recall_at_k(..., k)` is
    non-decreasing as `k` increases, since the prefix only grows (see the invariant test in
    test_core_memory_metrics.py).
    """
    if k <= 0:
        return MetricResult(
            metric_name="RECALL_AT_K",
            value=None,
            status=STATUS_UNDEFINED_K_NON_POSITIVE,
            detail={"k_requested": k},
            note="k must be a positive integer; Recall@K is undefined for k <= 0.",
        )

    if len(gold_ids) == 0:
        return MetricResult(
            metric_name="RECALL_AT_K",
            value=None,
            status=STATUS_UNDEFINED_EMPTY_GOLD,
            detail={"k_requested": k, "num_retrieved": len(retrieved_ranked_ids)},
            note="gold_ids is empty; Recall@K is undefined (neither vacuously 0 nor 1).",
        )

    k_effective = min(k, len(retrieved_ranked_ids))
    prefix = list(retrieved_ranked_ids[:k_effective])
    gold_set = set(gold_ids)
    hit = any(rid in gold_set for rid in prefix)

    note = ""
    if k > len(retrieved_ranked_ids):
        note = (
            f"k={k} exceeds retrieved length {len(retrieved_ranked_ids)}; evaluated over "
            f"all {len(retrieved_ranked_ids)} available retrieved ids."
        )

    return MetricResult(
        metric_name="RECALL_AT_K",
        value=1.0 if hit else 0.0,
        status=STATUS_OK,
        detail={
            "k_requested": k,
            "k_effective": k_effective,
            "num_retrieved": len(retrieved_ranked_ids),
            "num_gold": len(gold_ids),
            "hit": hit,
        },
        note=note,
    )


# ---------------------------------------------------------------------------
# MRR
# ---------------------------------------------------------------------------


def reciprocal_rank(retrieved_ranked_ids: Sequence[str], gold_ids: Sequence[str]) -> MetricResult:
    """Reciprocal rank of the first valid gold hit for a single task.

    Rank is 1-indexed. If the first gold id encountered while scanning
    `retrieved_ranked_ids` in order is at position ``r`` (1-indexed), the reciprocal rank is
    ``1/r``. If no gold id ever appears, the reciprocal rank is 0.0 (status STATUS_NO_HIT,
    not undefined -- "never found" is a well-defined, meaningful outcome for MRR, unlike an
    empty gold set).

    Edge cases:
    - ``gold_ids`` empty: undefined, mirrors `recall_at_k` -- returns
      ``value=None``, ``status=STATUS_UNDEFINED_EMPTY_GOLD``.
    - ``retrieved_ranked_ids`` empty (gold non-empty): well-defined, value 0.0, status
      STATUS_NO_HIT (nothing to rank).
    - Duplicate ids: the first occurrence (lowest index) of a gold id determines rank;
      later duplicate occurrences are irrelevant since only the first hit matters.
    """
    if len(gold_ids) == 0:
        return MetricResult(
            metric_name="RECIPROCAL_RANK",
            value=None,
            status=STATUS_UNDEFINED_EMPTY_GOLD,
            detail={"num_retrieved": len(retrieved_ranked_ids)},
            note="gold_ids is empty; reciprocal rank is undefined.",
        )

    gold_set = set(gold_ids)
    for index, rid in enumerate(retrieved_ranked_ids):
        if rid in gold_set:
            rank = index + 1  # 1-indexed
            return MetricResult(
                metric_name="RECIPROCAL_RANK",
                value=1.0 / rank,
                status=STATUS_OK,
                detail={"first_hit_rank": rank, "num_retrieved": len(retrieved_ranked_ids)},
            )

    return MetricResult(
        metric_name="RECIPROCAL_RANK",
        value=0.0,
        status=STATUS_NO_HIT,
        detail={"first_hit_rank": None, "num_retrieved": len(retrieved_ranked_ids)},
        note="No gold id found anywhere in retrieved_ranked_ids.",
    )


def mean_reciprocal_rank(
    task_retrievals: Sequence[Sequence[str]], task_golds: Sequence[Sequence[str]]
) -> MetricResult:
    """Mean Reciprocal Rank across a task set.

    Parameters
    ----------
    task_retrievals:
        One ranked retrieved-id list per task.
    task_golds:
        One gold-id list per task, same length/order as `task_retrievals`.

    Edge cases:
    - Empty task set (`len(task_retrievals) == 0`): undefined. Returns ``value=None``,
      ``status=STATUS_UNDEFINED_EMPTY_TASK_SET`` -- this is deliberately NOT silently
      treated as 0/0 -> 0, per the task brief's explicit instruction.
    - Mismatched lengths between `task_retrievals` and `task_golds`: raises `ValueError`
      (a caller-side contract violation, not a metric-definition ambiguity).
    - Per-task tasks with empty gold_ids are excluded from the mean and counted separately
      in `detail["excluded_empty_gold_tasks"]`, since `reciprocal_rank` reports them as
      undefined rather than 0 -- including an undefined per-task value in an average would
      silently manufacture a number the definition does not support.
    - If ALL tasks have empty gold_ids (so nothing is left to average), this is also
      undefined: returns ``value=None``, ``status=STATUS_UNDEFINED_EMPTY_GOLD``.

    Range: the returned value, when defined, is always in [0, 1].
    """
    if len(task_retrievals) != len(task_golds):
        raise ValueError(
            f"task_retrievals (len={len(task_retrievals)}) and task_golds "
            f"(len={len(task_golds)}) must be the same length"
        )

    if len(task_retrievals) == 0:
        return MetricResult(
            metric_name="MRR",
            value=None,
            status=STATUS_UNDEFINED_EMPTY_TASK_SET,
            detail={"num_tasks": 0},
            note="Task set is empty; MRR is undefined (not silently 0).",
        )

    per_task_rr = []
    excluded = 0
    for retrieved, gold in zip(task_retrievals, task_golds):
        result = reciprocal_rank(retrieved, gold)
        if result.status == STATUS_UNDEFINED_EMPTY_GOLD:
            excluded += 1
            continue
        per_task_rr.append(result.value)

    if not per_task_rr:
        return MetricResult(
            metric_name="MRR",
            value=None,
            status=STATUS_UNDEFINED_EMPTY_GOLD,
            detail={"num_tasks": len(task_retrievals), "excluded_empty_gold_tasks": excluded},
            note="Every task in the set had empty gold_ids; MRR is undefined.",
        )

    return MetricResult(
        metric_name="MRR",
        value=mean(per_task_rr),
        status=STATUS_OK,
        detail={
            "num_tasks": len(task_retrievals),
            "num_scored_tasks": len(per_task_rr),
            "excluded_empty_gold_tasks": excluded,
        },
    )


# ---------------------------------------------------------------------------
# Selection-capacity diagnostics (retrieval-miss vs. selection-miss vs. hit)
# ---------------------------------------------------------------------------

CLASSIFICATION_HIT = "HIT"
CLASSIFICATION_SELECTION_MISS = "SELECTION_MISS"
CLASSIFICATION_RETRIEVAL_MISS = "RETRIEVAL_MISS"


def classify_gold_id_capacity(
    retrieved_ids: Sequence[str], selected_ids: Sequence[str], gold_id: str
) -> str:
    """Classify a single gold id into exactly one of three mutually exclusive buckets.

    - RETRIEVAL_MISS: `gold_id` is absent from `retrieved_ids` -- candidate discovery never
      surfaced it, so selection never had the chance to choose it.
    - SELECTION_MISS: `gold_id` is present in `retrieved_ids` but absent from
      `selected_ids` -- candidate discovery found it, but evidence selection did not carry
      it forward. This is the historically-important distinct failure mode (see
      EVALUATION_CONTRACT.md section 2 / AUDIT.md's ~72.4%/14.8% split) that this function
      refuses to collapse into RETRIEVAL_MISS.
    - HIT: present in `selected_ids` (implies present in `retrieved_ids` under the normal
      pipeline invariant that selection operates over retrieved candidates; this function
      does not assume that invariant and classifies HIT directly from `selected_ids`
      regardless).

    These three categories are mutually exclusive and collectively exhaustive for any
    `gold_id` string -- exactly one is returned.
    """
    if gold_id in selected_ids:
        return CLASSIFICATION_HIT
    if gold_id in retrieved_ids:
        return CLASSIFICATION_SELECTION_MISS
    return CLASSIFICATION_RETRIEVAL_MISS


def selection_capacity_report(
    retrieved_ids: Sequence[str], selected_ids: Sequence[str], gold_ids: Sequence[str]
) -> MetricResult:
    """Per-gold-id RETRIEVAL_MISS / SELECTION_MISS / HIT classification for one task.

    Consumes `retrieved_memory_ids` AND `selected_memory_ids` from `AgentExecutionResult`
    plus `gold_evidence_ids` from `EvaluatorReference` (as plain lists here).

    `value` is the HIT rate over gold ids (``count(HIT) / len(gold_ids)``) when
    `gold_ids` is non-empty; this is a convenience scalar, but the full per-gold-id
    breakdown (the load-bearing output of this function) is always in `detail["per_gold"]`
    and `detail["counts"]`, which keep RETRIEVAL_MISS and SELECTION_MISS as two separate
    counters, never merged into one "not selected" bucket.

    Edge case: `gold_ids` empty -> undefined (`value=None`,
    `status=STATUS_UNDEFINED_EMPTY_GOLD`), `detail["per_gold"]` is an empty dict.
    """
    if len(gold_ids) == 0:
        return MetricResult(
            metric_name="SELECTION_CAPACITY",
            value=None,
            status=STATUS_UNDEFINED_EMPTY_GOLD,
            detail={"per_gold": {}, "counts": {}},
            note="gold_ids is empty; selection-capacity classification is undefined.",
        )

    per_gold = {
        gold_id: classify_gold_id_capacity(retrieved_ids, selected_ids, gold_id)
        for gold_id in gold_ids
    }
    counts = {
        CLASSIFICATION_HIT: sum(1 for v in per_gold.values() if v == CLASSIFICATION_HIT),
        CLASSIFICATION_SELECTION_MISS: sum(
            1 for v in per_gold.values() if v == CLASSIFICATION_SELECTION_MISS
        ),
        CLASSIFICATION_RETRIEVAL_MISS: sum(
            1 for v in per_gold.values() if v == CLASSIFICATION_RETRIEVAL_MISS
        ),
    }

    return MetricResult(
        metric_name="SELECTION_CAPACITY",
        value=counts[CLASSIFICATION_HIT] / len(gold_ids),
        status=STATUS_OK,
        detail={"per_gold": per_gold, "counts": counts, "num_gold": len(gold_ids)},
    )
