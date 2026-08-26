"""Evidence precision, evidence recall, evidence coverage, irrelevant-memory rate, and
identity-duplication redundancy.

Evaluator-side only: functions here take plain ID lists/sequences (the shape an evaluator
would read from `AgentExecutionResult.selected_memory_ids` /
`AgentExecutionResult.retrieved_memory_ids` and `EvaluatorReference.gold_evidence_ids`),
never an `AgentVisibleContext`-shaped object.

Pure functions: no filesystem/network/LLM/embeddings access, no randomness, no global
state.

Provisional/ambiguous definition flagged up front: **evidence coverage**. Neither
`EVALUATION_CONTRACT.md` nor `PHASE3_CLEAN_AGENT_FOUNDATION_SPEC.md` gives evidence
coverage a precise mathematical formula -- both simply list it by name alongside evidence
precision/recall (EVALUATION_CONTRACT.md section 2). `phase3/evaluation/AUDIT.md` section 3
confirms "no historical implementation located anywhere." This module does NOT equate
coverage with Recall@K or with evidence recall (both of which ARE precisely defined
elsewhere in this package) -- see `evidence_coverage()`'s docstring for the specific,
explicitly-labeled-provisional interpretation implemented here, and
`phase3/evaluation/metrics/README.md` for the full ambiguity write-up.
"""

from __future__ import annotations

from typing import Sequence

from .types import (
    MetricResult,
    STATUS_OK,
    STATUS_UNDEFINED_EMPTY_GOLD,
    STATUS_UNDEFINED_EMPTY_SELECTED,
    STATUS_UNDEFINED_EMPTY_SEQUENCE,
)

# ---------------------------------------------------------------------------
# Evidence precision / recall
# ---------------------------------------------------------------------------


def evidence_precision(selected_ids: Sequence[str], gold_ids: Sequence[str]) -> MetricResult:
    """Evidence precision for one task: |selected ∩ gold| / |selected|.

    Edge case: `selected_ids` empty -> undefined (division by zero has no principled
    answer: "no evidence was selected" is neither "all of it was relevant" (1.0) nor "none
    of it was relevant" (0.0) -- there is no evidence to judge). Returns ``value=None``,
    ``status=STATUS_UNDEFINED_EMPTY_SELECTED``.

    Range when defined: always in [0, 1].

    Distinct from Recall@K: precision asks "of what was selected, how much was gold?";
    Recall@K asks "did any gold appear in the top-K *retrieved* (not selected) prefix?".
    They operate on different sets (selected vs. retrieved-prefix) and different
    denominators.
    """
    if len(selected_ids) == 0:
        return MetricResult(
            metric_name="EVIDENCE_PRECISION",
            value=None,
            status=STATUS_UNDEFINED_EMPTY_SELECTED,
            detail={"num_gold": len(gold_ids)},
            note="selected_ids is empty; evidence precision is undefined (no evidence to judge).",
        )

    intersection = set(selected_ids) & set(gold_ids)
    return MetricResult(
        metric_name="EVIDENCE_PRECISION",
        value=len(intersection) / len(set(selected_ids)),
        status=STATUS_OK,
        detail={
            "intersection_size": len(intersection),
            "distinct_selected_count": len(set(selected_ids)),
            "num_gold": len(gold_ids),
        },
    )


def evidence_recall(selected_ids: Sequence[str], gold_ids: Sequence[str]) -> MetricResult:
    """Evidence recall for one task: |selected ∩ gold| / |gold|.

    Edge case: `gold_ids` empty -> undefined (no gold to recover, so "fraction of gold
    recovered" has no denominator). Returns ``value=None``,
    ``status=STATUS_UNDEFINED_EMPTY_GOLD``.

    Range when defined: always in [0, 1].

    Distinguishable from Recall@K by construction (worked example from the 3.2-C task
    brief, also encoded as a test in test_core_memory_metrics.py):
    retrieved=[A,B,C,D], selected=[A,C], gold=[A,D]
        -> Recall@4 = 1 (A appears in the first 4 retrieved)
        -> evidence_recall = |{A,C} ∩ {A,D}| / |{A,D}| = 1/2
    Recall@K measures the retrieval/candidate-discovery layer against a rank cutoff;
    evidence_recall measures the FINAL selected set against the full gold set, independent
    of any rank or cutoff.
    """
    if len(gold_ids) == 0:
        return MetricResult(
            metric_name="EVIDENCE_RECALL",
            value=None,
            status=STATUS_UNDEFINED_EMPTY_GOLD,
            detail={"num_selected": len(selected_ids)},
            note="gold_ids is empty; evidence recall is undefined (nothing to recover).",
        )

    intersection = set(selected_ids) & set(gold_ids)
    return MetricResult(
        metric_name="EVIDENCE_RECALL",
        value=len(intersection) / len(set(gold_ids)),
        status=STATUS_OK,
        detail={
            "intersection_size": len(intersection),
            "distinct_gold_count": len(set(gold_ids)),
            "num_selected": len(selected_ids),
        },
    )


# ---------------------------------------------------------------------------
# Evidence coverage (PROVISIONAL -- see module docstring)
# ---------------------------------------------------------------------------


def evidence_coverage(
    all_candidate_ids_across_run: Sequence[str], gold_ids: Sequence[str]
) -> MetricResult:
    """PROVISIONAL metric. Fraction of distinct gold ids that appear ANYWHERE in the full
    retrieved-candidate pool for a run (across all retrieval attempts/passes for that task,
    not just the final selected set and not truncated to any rank cutoff K).

        evidence_coverage = |distinct(all_candidate_ids_across_run) ∩ distinct(gold_ids)| / |distinct(gold_ids)|

    Why this is flagged provisional: neither `EVALUATION_CONTRACT.md` nor any other
    contract document gives evidence coverage a precise formula (confirmed by
    `phase3/evaluation/AUDIT.md` section 3 and section 10: "Evidence coverage: No
    implementation found anywhere"). This module does not invent a formula out of nothing
    -- it implements the single most conservative, clearly-labeled reading consistent with
    the name "coverage" and with the metric's placement in EVALUATION_CONTRACT.md section 2
    directly alongside (not merged with) evidence precision/recall: precision/recall
    operate on the FINAL SELECTED set; this interpretation of coverage instead asks "was
    the gold evidence ever *findable* at all, anywhere in the candidate pool the run
    produced" -- a superset-level question distinct from both Recall@K (which is
    rank-cutoff-bound and per-task-single-hit, evaluated over ONE ranked list) and evidence
    recall (which is selected-set-bound).

    This is NOT silently equated with Recall@K or evidence recall -- it is a distinct
    computation with a distinct denominator context (the full candidate pool, no rank
    cutoff, aggregated across however many candidate ids the caller supplies). A future
    Phase 3 stage may redefine this metric once a contract document fixes its formula;
    until then, treat this implementation as a documented placeholder, not a frozen
    definition.

    Edge case: `gold_ids` empty -> undefined, ``status=STATUS_UNDEFINED_EMPTY_GOLD``.
    """
    if len(gold_ids) == 0:
        return MetricResult(
            metric_name="EVIDENCE_COVERAGE",
            value=None,
            status=STATUS_UNDEFINED_EMPTY_GOLD,
            detail={"num_candidates": len(all_candidate_ids_across_run)},
            note=(
                "gold_ids is empty; evidence coverage is undefined. "
                "PROVISIONAL METRIC -- see module docstring."
            ),
        )

    candidate_set = set(all_candidate_ids_across_run)
    gold_set = set(gold_ids)
    covered = candidate_set & gold_set
    return MetricResult(
        metric_name="EVIDENCE_COVERAGE",
        value=len(covered) / len(gold_set),
        status=STATUS_OK,
        detail={
            "covered_gold_ids": sorted(covered),
            "distinct_gold_count": len(gold_set),
            "distinct_candidate_count": len(candidate_set),
        },
        note=(
            "PROVISIONAL definition (no contract-fixed formula exists as of Phase 3.2-C): "
            "fraction of distinct gold ids present anywhere in the full candidate pool "
            "supplied, independent of rank cutoff or final selection. Distinct from "
            "Recall@K (rank-cutoff-bound, single ranked list) and evidence_recall "
            "(selected-set-bound). See phase3/evaluation/metrics/README.md."
        ),
    )


# ---------------------------------------------------------------------------
# Irrelevant-memory rate
# ---------------------------------------------------------------------------


def irrelevant_memory_rate(selected_ids: Sequence[str], gold_ids: Sequence[str]) -> MetricResult:
    """Irrelevant-memory rate for one task: |selected - gold| / |selected|.

    Edge case: `selected_ids` empty -> undefined, mirroring `evidence_precision` (no
    selection to judge as relevant or irrelevant). Returns ``value=None``,
    ``status=STATUS_UNDEFINED_EMPTY_SELECTED``.

    Relationship to evidence precision (stated explicitly, not silently duplicated):
    under this module's shared "relevant == member of gold_ids" definition and the same
    non-empty-selected denominator, ``irrelevant_memory_rate == 1 - evidence_precision``
    for every input where both are defined. This is proven directly (not merely asserted)
    by `test_irrelevant_memory_rate_is_exact_complement_of_precision` in
    test_core_memory_metrics.py. This function still computes its result independently
    (via set difference) rather than calling `evidence_precision` and subtracting, so each
    function remains independently readable and testable -- but the mathematical identity
    is documented here rather than left as an unstated coincidence.
    """
    if len(selected_ids) == 0:
        return MetricResult(
            metric_name="IRRELEVANT_MEMORY_RATE",
            value=None,
            status=STATUS_UNDEFINED_EMPTY_SELECTED,
            detail={"num_gold": len(gold_ids)},
            note="selected_ids is empty; irrelevant-memory rate is undefined.",
        )

    distinct_selected = set(selected_ids)
    irrelevant = distinct_selected - set(gold_ids)
    return MetricResult(
        metric_name="IRRELEVANT_MEMORY_RATE",
        value=len(irrelevant) / len(distinct_selected),
        status=STATUS_OK,
        detail={
            "irrelevant_ids": sorted(irrelevant),
            "distinct_selected_count": len(distinct_selected),
            "num_gold": len(gold_ids),
        },
        note="Exact complement of evidence_precision (1 - precision) under the shared relevance definition.",
    )


# ---------------------------------------------------------------------------
# Redundancy (identity-duplication ONLY -- NOT semantic equivalence)
# ---------------------------------------------------------------------------


def redundancy(id_sequence: Sequence[str]) -> MetricResult:
    """Identity-duplication count/rate within a retrieved-OR-selected id sequence.

    IMPORTANT SCOPE NOTE: this measures EXACT memory_id duplication only -- the same
    memory_id string appearing more than once in the sequence (e.g. a retrieval or
    selection pass that (re-)surfaces the same memory twice). It does NOT measure semantic
    equivalence (two DIFFERENT memory_ids whose content means the same thing, e.g. an
    `equivalent_to` relationship per `memory_schema.md` section 3.3) or content-duplicate
    detection. Semantic/evidence-equivalence scoring is explicitly out of scope for Phase
    3.2-C (see EVALUATION_CONTRACT.md section 4's "evidence-equivalent success" and this
    package's README) -- that is Phase 3.2-D.

        duplicate_count = len(id_sequence) - len(set(id_sequence))
        redundancy_rate = duplicate_count / len(id_sequence)   (when id_sequence non-empty)

    Edge case: empty `id_sequence` -> undefined redundancy rate (0/0 has no principled
    reading -- there is no sequence to be redundant or non-redundant). Returns
    ``value=None``, ``status=STATUS_UNDEFINED_EMPTY_SEQUENCE``. `detail["duplicate_count"]`
    is still reported as 0 in this case since a count (unlike a rate) is well-defined even
    for an empty sequence.
    """
    n = len(id_sequence)
    duplicate_count = n - len(set(id_sequence))

    if n == 0:
        return MetricResult(
            metric_name="REDUNDANCY",
            value=None,
            status=STATUS_UNDEFINED_EMPTY_SEQUENCE,
            detail={"duplicate_count": 0, "sequence_length": 0},
            note="id_sequence is empty; redundancy rate is undefined (count is 0).",
        )

    return MetricResult(
        metric_name="REDUNDANCY",
        value=duplicate_count / n,
        status=STATUS_OK,
        detail={
            "duplicate_count": duplicate_count,
            "sequence_length": n,
            "distinct_count": len(set(id_sequence)),
        },
        note="Identity-duplication only (exact memory_id repeats) -- NOT semantic equivalence.",
    )
