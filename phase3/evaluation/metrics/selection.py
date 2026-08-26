"""Selection count/cardinality and Strict TSR.

Evaluator-side only: functions here take plain ID lists (the shape an evaluator would
read from `AgentExecutionResult.selected_memory_ids` and
`EvaluatorReference.gold_evidence_ids`), never an `AgentVisibleContext`-shaped object.

Pure functions: no filesystem/network/LLM/embeddings access, no randomness, no global
state.
"""

from __future__ import annotations

from statistics import mean, median
from typing import Sequence

from .types import (
    MetricResult,
    STATUS_OK,
    STATUS_UNDEFINED_EMPTY_SEQUENCE,
)

# ---------------------------------------------------------------------------
# Selection count / cardinality
# ---------------------------------------------------------------------------


def selection_count(selected_ids: Sequence[str]) -> MetricResult:
    """Cardinality of the selected memory set for one task.

    Duplicate behavior (explicit default, per the 3.2-C task brief): `selected_ids` is
    treated as a SET -- duplicate ids count ONCE. Rationale: `selected_memory_ids` is
    conceptually "which distinct memories did evidence selection choose to pass to
    reasoning" (CLEAN_AGENT_INTERFACES.md section 1); a memory selected "twice" (e.g. by
    an implementation bug, or because two different selection passes both chose it) still
    represents one piece of evidence occupying the reasoning context once. `detail` still
    reports `raw_count` (list length, duplicates included) alongside `distinct_count`
    (the returned `value`), so a caller who wants the raw/list-length interpretation can
    read it without recomputing.

    Never undefined: an empty list is a valid count of 0, not an edge case requiring a
    sentinel (unlike precision/recall, cardinality of the empty set is unambiguously 0).
    """
    raw_count = len(selected_ids)
    distinct_count = len(set(selected_ids))
    return MetricResult(
        metric_name="SELECTION_COUNT",
        value=float(distinct_count),
        status=STATUS_OK,
        detail={"distinct_count": distinct_count, "raw_count": raw_count},
        note=(
            "value is the distinct (set) cardinality; duplicates count once by default. "
            "See detail['raw_count'] for the duplicate-inclusive list length."
        ),
    )


def selection_count_aggregate(selected_id_lists: Sequence[Sequence[str]]) -> MetricResult:
    """Mean/median/min/max selection count across a list of runs (one list per task/run).

    Edge case: an empty list of runs is undefined (no runs to aggregate over) -- returns
    ``value=None``, ``status=STATUS_UNDEFINED_EMPTY_SEQUENCE``, rather than silently
    reporting 0.
    """
    if len(selected_id_lists) == 0:
        return MetricResult(
            metric_name="SELECTION_COUNT_AGGREGATE",
            value=None,
            status=STATUS_UNDEFINED_EMPTY_SEQUENCE,
            detail={"num_runs": 0},
            note="No runs provided; aggregate selection count is undefined.",
        )

    per_run_counts = [selection_count(ids).value for ids in selected_id_lists]
    return MetricResult(
        metric_name="SELECTION_COUNT_AGGREGATE",
        value=mean(per_run_counts),
        status=STATUS_OK,
        detail={
            "num_runs": len(per_run_counts),
            "mean": mean(per_run_counts),
            "median": median(per_run_counts),
            "min": min(per_run_counts),
            "max": max(per_run_counts),
        },
        note="value == detail['mean']; median/min/max provided for debugging/reporting.",
    )


# ---------------------------------------------------------------------------
# Strict TSR
# ---------------------------------------------------------------------------


def strict_tsr(selected_or_used_ids: Sequence[str], gold_evidence_ids: Sequence[str]) -> MetricResult:
    """STRICT_TSR: literal gold-evidence-ID membership diagnostic, for ONE task.

    Definition (frozen formula per EVALUATION_CONTRACT.md section 3, historically computed
    in `phase3_reference/clean_agent_v1/src/reference_agent.py` as
    ``set(used_memory_ids) & set(evidence_memory_ids)``):

        STRICT_TSR = 1 if len(set(selected_or_used_ids) & set(gold_evidence_ids)) > 0 else 0

    IMPORTANT -- what this metric is NOT (per EVALUATION_CONTRACT.md sections 1 and 3,
    and PHASE3_CLEAN_AGENT_FOUNDATION_SPEC.md's historical-lessons section 3):

    - STRICT_TSR IS NOT agent task success.
    - STRICT_TSR IS NOT QA/reasoning/answer accuracy.
    - STRICT_TSR IS NOT a complete measure of "did the agent do its job."

    It is purely an identity-overlap diagnostic: did the selected/used memory set contain
    at least one memory whose ID is literally, exactly one of the benchmark's gold evidence
    IDs? A selected memory that is semantically equivalent to, or a content-duplicate of,
    gold evidence but carries a DIFFERENT memory_id still scores as a STRICT_TSR failure --
    that is the evidence-equivalent-success diagnostic's job (EVALUATION_CONTRACT.md section
    4), explicitly out of scope for Phase 3.2-C (see this package's README).

    This function is evaluator-side: it consumes `EvaluatorReference.gold_evidence_ids` and
    `AgentExecutionResult.selected_memory_ids` (or `used_memory_ids`, in historical naming)
    as plain lists -- it is NEVER derived from `AgentVisibleContext` (agent-visible data
    never carries `gold_evidence_ids` at all, per LEAKAGE_AND_VISIBILITY_CONTRACT.md).

    Edge cases:
    - Both empty, or gold empty, selected empty: intersection is empty either way, so the
      result is well-defined as 0 -- there is no ambiguous case here (unlike
      precision/recall, "no overlap because nothing to overlap" is a real, meaningful 0,
      not a divide-by-zero). `detail["gold_empty"]` / `detail["selected_empty"]` flag this
      so a caller can distinguish "0 because nothing matched" from "0 because there was
      nothing to match," without treating either as undefined.

    Range: always in {0, 1} (never any other value), i.e. `value in (0.0, 1.0)`.
    """
    intersection = set(selected_or_used_ids) & set(gold_evidence_ids)
    hit = len(intersection) > 0
    return MetricResult(
        metric_name="STRICT_TSR",
        value=1.0 if hit else 0.0,
        status=STATUS_OK,
        detail={
            "intersection": sorted(intersection),
            "gold_empty": len(gold_evidence_ids) == 0,
            "selected_empty": len(selected_or_used_ids) == 0,
        },
        note=(
            "STRICT_TSR is a literal-identity diagnostic only -- NOT agent task success, "
            "NOT answer correctness. See module docstring."
        ),
    )
