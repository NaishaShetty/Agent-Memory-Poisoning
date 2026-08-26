"""Phase 3.2-C tests for the core memory metrics package (`phase3/evaluation/metrics/`).

Scope note: this suite tests METRIC COMPUTATION only -- Recall@K, MRR, Strict TSR,
selection count, selection-capacity diagnostics, evidence precision/recall/coverage,
irrelevant-memory rate, and identity-duplication redundancy. It does not modify, re-run, or
depend on `test_evaluation_contracts.py` (the 62 Phase 3.2-B schema/fixture/boundary
tests), which must remain green, unmodified, alongside this file.

Fixtures used here are tiny, hand-authored, deterministic literal Python data (not JSON
files, and NOT real dataset samples) embedded directly in this test module, per the 3.2-C
task brief's "embed as literal Python data in the test file" option.

This module deliberately never imports anything from `phase3_reference/` (historical-only,
per PHASE3_RESTART_BOUNDARY.md) -- the historical-TSR-compatibility test below proves
mathematical equivalence to the historical formula by re-deriving it inline as a literal
one-line expression, not by importing or executing any phase3_reference/ code.
"""

from __future__ import annotations

import inspect
import math

import pytest

from phase3.evaluation.metrics import (
    MetricResult,
    recall_at_k,
    reciprocal_rank,
    mean_reciprocal_rank,
    classify_gold_id_capacity,
    selection_capacity_report,
    CLASSIFICATION_HIT,
    CLASSIFICATION_SELECTION_MISS,
    CLASSIFICATION_RETRIEVAL_MISS,
    selection_count,
    selection_count_aggregate,
    strict_tsr,
    evidence_precision,
    evidence_recall,
    evidence_coverage,
    irrelevant_memory_rate,
    redundancy,
)
from phase3.evaluation.metrics import retrieval as retrieval_mod
from phase3.evaluation.metrics import selection as selection_mod
from phase3.evaluation.metrics import evidence as evidence_mod
from phase3.evaluation.metrics.types import (
    STATUS_OK,
    STATUS_NO_HIT,
    STATUS_UNDEFINED_EMPTY_GOLD,
    STATUS_UNDEFINED_EMPTY_SELECTED,
    STATUS_UNDEFINED_EMPTY_SEQUENCE,
    STATUS_UNDEFINED_EMPTY_TASK_SET,
    STATUS_UNDEFINED_K_NON_POSITIVE,
)


# ---------------------------------------------------------------------------
# Synthetic fixtures -- the ten required cases from the 3.2-C task brief
# ---------------------------------------------------------------------------

# 1. Perfect retrieval: gold appears first.
PERFECT_RETRIEVAL = {"retrieved": ["A", "B", "C"], "gold": ["A"]}

# 2. Retrieval miss: gold never appears in retrieved at all.
RETRIEVAL_MISS_CASE = {"retrieved": ["X", "Y", "Z"], "gold": ["A"]}

# 3. Retrieved-but-not-selected (selection failure).
SELECTION_FAILURE_CASE = {
    "retrieved": ["A", "B", "C"],
    "selected": ["B", "C"],
    "gold": ["A"],
}

# 4. Rank sensitivity: Recall@1=0, Recall@2=0, Recall@3=1, MRR=1/3.
RANK_SENSITIVITY_CASE = {"retrieved": ["B", "C", "A"], "gold": ["A"]}

# 5. Multiple gold evidence.
MULTI_GOLD_CASE = {
    "retrieved": ["A", "B", "C", "D"],
    "selected": ["A", "C"],
    "gold": ["A", "D"],
}

# 6. Irrelevant selections (selected entirely disjoint from gold).
IRRELEVANT_SELECTIONS_CASE = {"selected": ["X", "Y"], "gold": ["A", "B"]}

# 7. Duplicate IDs (in both retrieved and selected).
DUPLICATE_IDS_CASE = {
    "retrieved": ["A", "A", "B"],
    "selected": ["A", "A"],
    "gold": ["A"],
}

# 8. Empty retrieval.
EMPTY_RETRIEVAL_CASE = {"retrieved": [], "gold": ["A"]}

# 9. K exceeds retrieval length.
K_EXCEEDS_LENGTH_CASE = {"retrieved": ["A", "B"], "gold": ["A"]}

# 10. Selection capacity: retrieval hit + selection miss together in one task.
SELECTION_CAPACITY_CASE = {
    "retrieved": ["A", "B", "C"],
    "selected": ["B"],
    "gold": ["A", "B", "Z"],  # A: selection_miss, B: hit, Z: retrieval_miss
}


# ---------------------------------------------------------------------------
# Recall@K
# ---------------------------------------------------------------------------


def test_recall_at_k_perfect_retrieval():
    r = recall_at_k(PERFECT_RETRIEVAL["retrieved"], PERFECT_RETRIEVAL["gold"], 1)
    assert r.status == STATUS_OK
    assert r.value == 1.0


def test_recall_at_k_retrieval_miss():
    r = recall_at_k(RETRIEVAL_MISS_CASE["retrieved"], RETRIEVAL_MISS_CASE["gold"], 3)
    assert r.status == STATUS_OK
    assert r.value == 0.0


def test_recall_at_k_rank_sensitivity():
    retrieved, gold = RANK_SENSITIVITY_CASE["retrieved"], RANK_SENSITIVITY_CASE["gold"]
    assert recall_at_k(retrieved, gold, 1).value == 0.0
    assert recall_at_k(retrieved, gold, 2).value == 0.0
    assert recall_at_k(retrieved, gold, 3).value == 1.0


def test_recall_at_k_empty_retrieval_is_defined_zero_when_gold_nonempty():
    r = recall_at_k(EMPTY_RETRIEVAL_CASE["retrieved"], EMPTY_RETRIEVAL_CASE["gold"], 5)
    assert r.status == STATUS_OK
    assert r.value == 0.0


def test_recall_at_k_zero_k_is_undefined():
    r = recall_at_k(["A", "B"], ["A"], 0)
    assert r.value is None
    assert r.status == STATUS_UNDEFINED_K_NON_POSITIVE


def test_recall_at_k_negative_k_is_undefined():
    r = recall_at_k(["A", "B"], ["A"], -3)
    assert r.value is None
    assert r.status == STATUS_UNDEFINED_K_NON_POSITIVE


def test_recall_at_k_exceeds_retrieval_length_is_defined():
    retrieved, gold = K_EXCEEDS_LENGTH_CASE["retrieved"], K_EXCEEDS_LENGTH_CASE["gold"]
    r = recall_at_k(retrieved, gold, 10)
    assert r.status == STATUS_OK
    assert r.value == 1.0
    assert r.detail["k_effective"] == len(retrieved)
    assert "exceeds retrieved length" in r.note


def test_recall_at_k_empty_gold_is_undefined():
    r = recall_at_k(["A", "B"], [], 2)
    assert r.value is None
    assert r.status == STATUS_UNDEFINED_EMPTY_GOLD


def test_recall_at_k_duplicate_retrieved_ids_not_deduplicated():
    # Duplicates preserved in the prefix; a hit still registers correctly.
    r = recall_at_k(["A", "A", "B"], ["B"], 2)
    assert r.value == 0.0  # B is at index 2, outside first-2 prefix ["A","A"]
    r2 = recall_at_k(["A", "A", "B"], ["B"], 3)
    assert r2.value == 1.0


@pytest.mark.parametrize(
    "retrieved,gold",
    [
        (["B", "C", "A"], ["A"]),
        (["X", "Y", "Z"], ["A"]),
        (["A", "B", "C", "D"], ["D"]),
        (["A", "A", "A"], ["A"]),
    ],
)
def test_recall_at_k_monotonic_non_decreasing(retrieved, gold):
    values = []
    for k in range(1, len(retrieved) + 2):
        result = recall_at_k(retrieved, gold, k)
        values.append(result.value)
    for earlier, later in zip(values, values[1:]):
        assert later >= earlier, f"Recall@K not monotonic: {values}"


# ---------------------------------------------------------------------------
# MRR
# ---------------------------------------------------------------------------


def test_reciprocal_rank_rank_sensitivity_case():
    r = reciprocal_rank(RANK_SENSITIVITY_CASE["retrieved"], RANK_SENSITIVITY_CASE["gold"])
    assert r.status == STATUS_OK
    assert math.isclose(r.value, 1.0 / 3.0)


def test_reciprocal_rank_no_hit():
    r = reciprocal_rank(["X", "Y"], ["A"])
    assert r.status == STATUS_NO_HIT
    assert r.value == 0.0


def test_reciprocal_rank_empty_retrieved():
    r = reciprocal_rank([], ["A"])
    assert r.status == STATUS_NO_HIT
    assert r.value == 0.0


def test_reciprocal_rank_empty_gold_is_undefined():
    r = reciprocal_rank(["A", "B"], [])
    assert r.value is None
    assert r.status == STATUS_UNDEFINED_EMPTY_GOLD


def test_reciprocal_rank_duplicate_gold_hit_uses_first_occurrence():
    r = reciprocal_rank(["X", "A", "A", "B"], ["A"])
    assert r.detail["first_hit_rank"] == 2
    assert math.isclose(r.value, 1.0 / 2.0)


def test_mean_reciprocal_rank_matches_rank_sensitivity_example():
    result = mean_reciprocal_rank(
        [RANK_SENSITIVITY_CASE["retrieved"]], [RANK_SENSITIVITY_CASE["gold"]]
    )
    assert result.status == STATUS_OK
    assert math.isclose(result.value, 1.0 / 3.0)


def test_mean_reciprocal_rank_empty_task_set_is_undefined_not_zero():
    result = mean_reciprocal_rank([], [])
    assert result.value is None
    assert result.status == STATUS_UNDEFINED_EMPTY_TASK_SET


def test_mean_reciprocal_rank_all_empty_gold_is_undefined():
    result = mean_reciprocal_rank([["A", "B"]], [[]])
    assert result.value is None
    assert result.status == STATUS_UNDEFINED_EMPTY_GOLD


def test_mean_reciprocal_rank_mismatched_lengths_raises():
    with pytest.raises(ValueError):
        mean_reciprocal_rank([["A"]], [["A"], ["B"]])


def test_mean_reciprocal_rank_mixed_tasks_excludes_empty_gold_tasks():
    # Task 1: hit at rank 1 -> RR=1.0. Task 2: empty gold -> excluded.
    result = mean_reciprocal_rank([["A"], ["B"]], [["A"], []])
    assert result.status == STATUS_OK
    assert result.value == 1.0
    assert result.detail["excluded_empty_gold_tasks"] == 1
    assert result.detail["num_scored_tasks"] == 1


@pytest.mark.parametrize(
    "retrieved,gold",
    [
        (["A"], ["A"]),
        (["X", "Y"], ["A"]),
        (["B", "C", "A"], ["A"]),
    ],
)
def test_mrr_single_task_in_zero_one_range(retrieved, gold):
    result = mean_reciprocal_rank([retrieved], [gold])
    assert 0.0 <= result.value <= 1.0


# ---------------------------------------------------------------------------
# Strict TSR
# ---------------------------------------------------------------------------


def test_strict_tsr_hit():
    r = strict_tsr(["A", "B"], ["B", "Z"])
    assert r.value == 1.0
    assert r.status == STATUS_OK


def test_strict_tsr_no_hit():
    r = strict_tsr(IRRELEVANT_SELECTIONS_CASE["selected"], IRRELEVANT_SELECTIONS_CASE["gold"])
    assert r.value == 0.0


def test_strict_tsr_empty_selected():
    r = strict_tsr([], ["A"])
    assert r.value == 0.0
    assert r.detail["selected_empty"] is True


def test_strict_tsr_empty_gold():
    r = strict_tsr(["A"], [])
    assert r.value == 0.0
    assert r.detail["gold_empty"] is True


def test_strict_tsr_both_empty():
    r = strict_tsr([], [])
    assert r.value == 0.0


def test_strict_tsr_value_always_zero_or_one():
    for selected, gold in [
        (["A"], ["A"]),
        (["A"], ["B"]),
        ([], []),
        (["A", "B", "C"], ["C"]),
    ]:
        r = strict_tsr(selected, gold)
        assert r.value in (0.0, 1.0)


def test_strict_tsr_is_not_labeled_as_task_success():
    # Documentation/labeling check: the note must disclaim task-success equivalence.
    r = strict_tsr(["A"], ["A"])
    assert "NOT agent task success" in r.note
    assert r.metric_name == "STRICT_TSR"


def test_historical_strict_tsr_compatibility():
    """Prove STRICT_TSR matches the historical formula
    `used_memory_ids ∩ evidence_memory_ids != ∅` via synthetic cases, WITHOUT importing or
    executing any phase3_reference/ code (per the 3.2-C task brief -- this is a
    self-contained mathematical re-derivation, not an import of historical code)."""
    synthetic_cases = [
        (["mem-1", "mem-2"], ["mem-2", "mem-9"]),  # hit
        (["mem-1"], ["mem-9"]),  # miss
        ([], ["mem-9"]),  # miss, empty used
        (["mem-1", "mem-1", "mem-2"], ["mem-1"]),  # hit with duplicates in used
        ([], []),  # miss, both empty
    ]
    for used_memory_ids, evidence_memory_ids in synthetic_cases:
        historical_formula_result = (
            1.0 if set(used_memory_ids) & set(evidence_memory_ids) else 0.0
        )
        new_result = strict_tsr(used_memory_ids, evidence_memory_ids)
        assert new_result.value == historical_formula_result, (
            f"STRICT_TSR diverges from historical formula for "
            f"used={used_memory_ids!r}, evidence={evidence_memory_ids!r}"
        )


# ---------------------------------------------------------------------------
# Selection count
# ---------------------------------------------------------------------------


def test_selection_count_basic():
    r = selection_count(["A", "B", "C"])
    assert r.value == 3.0
    assert r.detail["raw_count"] == 3


def test_selection_count_duplicates_count_once():
    r = selection_count(DUPLICATE_IDS_CASE["selected"])  # ["A", "A"]
    assert r.value == 1.0
    assert r.detail["raw_count"] == 2
    assert r.detail["distinct_count"] == 1


def test_selection_count_empty_is_well_defined_zero():
    r = selection_count([])
    assert r.value == 0.0
    assert r.status == STATUS_OK


def test_selection_count_value_never_negative():
    for ids in [[], ["A"], ["A", "A", "B"]]:
        r = selection_count(ids)
        assert r.value >= 0.0


def test_selection_count_aggregate_basic():
    r = selection_count_aggregate([["A"], ["A", "B"], ["A", "B", "C"]])
    assert r.status == STATUS_OK
    assert r.detail["mean"] == 2.0
    assert r.detail["median"] == 2.0
    assert r.detail["min"] == 1.0
    assert r.detail["max"] == 3.0


def test_selection_count_aggregate_empty_runs_is_undefined():
    r = selection_count_aggregate([])
    assert r.value is None
    assert r.status == STATUS_UNDEFINED_EMPTY_SEQUENCE


# ---------------------------------------------------------------------------
# Selection-capacity diagnostics
# ---------------------------------------------------------------------------


def test_classify_gold_id_capacity_hit():
    assert (
        classify_gold_id_capacity(["A", "B"], ["A"], "A") == CLASSIFICATION_HIT
    )


def test_classify_gold_id_capacity_selection_miss():
    assert (
        classify_gold_id_capacity(["A", "B"], ["B"], "A") == CLASSIFICATION_SELECTION_MISS
    )


def test_classify_gold_id_capacity_retrieval_miss():
    assert (
        classify_gold_id_capacity(["B", "C"], ["B"], "A") == CLASSIFICATION_RETRIEVAL_MISS
    )


def test_selection_capacity_report_does_not_collapse_categories():
    case = SELECTION_CAPACITY_CASE
    r = selection_capacity_report(case["retrieved"], case["selected"], case["gold"])
    assert r.status == STATUS_OK
    assert r.detail["per_gold"]["A"] == CLASSIFICATION_SELECTION_MISS
    assert r.detail["per_gold"]["B"] == CLASSIFICATION_HIT
    assert r.detail["per_gold"]["Z"] == CLASSIFICATION_RETRIEVAL_MISS
    assert r.detail["counts"][CLASSIFICATION_HIT] == 1
    assert r.detail["counts"][CLASSIFICATION_SELECTION_MISS] == 1
    assert r.detail["counts"][CLASSIFICATION_RETRIEVAL_MISS] == 1
    assert math.isclose(r.value, 1.0 / 3.0)


def test_selection_capacity_report_retrieved_but_not_selected_case():
    case = SELECTION_FAILURE_CASE
    r = selection_capacity_report(case["retrieved"], case["selected"], case["gold"])
    assert r.detail["per_gold"]["A"] == CLASSIFICATION_SELECTION_MISS
    assert r.value == 0.0


def test_selection_capacity_report_empty_gold_is_undefined():
    r = selection_capacity_report(["A"], ["A"], [])
    assert r.value is None
    assert r.status == STATUS_UNDEFINED_EMPTY_GOLD


# ---------------------------------------------------------------------------
# Evidence precision / recall / coverage / irrelevant-memory-rate / redundancy
# ---------------------------------------------------------------------------


def test_evidence_precision_and_recall_distinguishable_from_recall_at_k():
    """The exact worked example from the 3.2-C task brief."""
    retrieved = MULTI_GOLD_CASE["retrieved"]  # [A,B,C,D]
    selected = MULTI_GOLD_CASE["selected"]  # [A,C]
    gold = MULTI_GOLD_CASE["gold"]  # [A,D]

    recall_4 = recall_at_k(retrieved, gold, 4)
    assert recall_4.value == 1.0  # A appears in first 4 retrieved

    ev_recall = evidence_recall(selected, gold)
    assert math.isclose(ev_recall.value, 0.5)  # |{A,C}∩{A,D}| / |{A,D}| = 1/2

    assert recall_4.value != ev_recall.value


def test_evidence_precision_basic():
    r = evidence_precision(MULTI_GOLD_CASE["selected"], MULTI_GOLD_CASE["gold"])
    assert math.isclose(r.value, 0.5)  # |{A,C}∩{A,D}| / |{A,C}| = 1/2


def test_evidence_precision_empty_selected_undefined():
    r = evidence_precision([], ["A"])
    assert r.value is None
    assert r.status == STATUS_UNDEFINED_EMPTY_SELECTED


def test_evidence_recall_empty_gold_undefined():
    r = evidence_recall(["A"], [])
    assert r.value is None
    assert r.status == STATUS_UNDEFINED_EMPTY_GOLD


def test_evidence_precision_recall_irrelevant_selections():
    case = IRRELEVANT_SELECTIONS_CASE
    p = evidence_precision(case["selected"], case["gold"])
    r = evidence_recall(case["selected"], case["gold"])
    assert p.value == 0.0
    assert r.value == 0.0


@pytest.mark.parametrize(
    "selected,gold",
    [
        (["A"], ["A"]),
        (["A", "B"], ["A"]),
        (["A", "B"], ["C", "D"]),
        (["A", "A"], ["A"]),
    ],
)
def test_evidence_precision_recall_in_zero_one_range_when_defined(selected, gold):
    p = evidence_precision(selected, gold)
    r = evidence_recall(selected, gold)
    if p.value is not None:
        assert 0.0 <= p.value <= 1.0
    if r.value is not None:
        assert 0.0 <= r.value <= 1.0


def test_evidence_coverage_is_distinct_from_recall_at_k_and_evidence_recall():
    all_candidates = ["A", "B", "C", "D", "E"]  # union of several retrieval passes
    gold = ["A", "Z"]  # Z never appears anywhere in the candidate pool
    coverage = evidence_coverage(all_candidates, gold)
    assert coverage.status == STATUS_OK
    assert math.isclose(coverage.value, 0.5)  # only A of {A,Z} covered
    assert "PROVISIONAL" in coverage.note


def test_evidence_coverage_empty_gold_undefined():
    r = evidence_coverage(["A", "B"], [])
    assert r.value is None
    assert r.status == STATUS_UNDEFINED_EMPTY_GOLD


def test_irrelevant_memory_rate_basic():
    r = irrelevant_memory_rate(IRRELEVANT_SELECTIONS_CASE["selected"], IRRELEVANT_SELECTIONS_CASE["gold"])
    assert r.value == 1.0  # both selected ids are irrelevant


def test_irrelevant_memory_rate_empty_selected_undefined():
    r = irrelevant_memory_rate([], ["A"])
    assert r.value is None
    assert r.status == STATUS_UNDEFINED_EMPTY_SELECTED


@pytest.mark.parametrize(
    "selected,gold",
    [
        (["A", "B"], ["A"]),
        (["A", "B", "C"], ["A", "B"]),
        (["X", "Y"], ["A", "B"]),
        (["A"], ["A"]),
    ],
)
def test_irrelevant_memory_rate_is_exact_complement_of_precision(selected, gold):
    precision = evidence_precision(selected, gold)
    irrelevant = irrelevant_memory_rate(selected, gold)
    assert precision.value is not None and irrelevant.value is not None
    assert math.isclose(precision.value + irrelevant.value, 1.0)


def test_redundancy_duplicate_ids_case():
    r = redundancy(DUPLICATE_IDS_CASE["retrieved"])  # ["A","A","B"]
    assert r.status == STATUS_OK
    assert r.detail["duplicate_count"] == 1
    assert math.isclose(r.value, 1.0 / 3.0)


def test_redundancy_no_duplicates():
    r = redundancy(["A", "B", "C"])
    assert r.value == 0.0


def test_redundancy_empty_sequence_undefined():
    r = redundancy([])
    assert r.value is None
    assert r.status == STATUS_UNDEFINED_EMPTY_SEQUENCE
    assert r.detail["duplicate_count"] == 0


def test_redundancy_is_identity_only_not_semantic():
    # Two distinct ids that would be "semantically" the same content still count as
    # non-redundant under this identity-only definition -- there is no content field here
    # at all, only ids, which is itself the point: this function cannot see semantics.
    r = redundancy(["mem-1", "mem-2"])
    assert r.value == 0.0
    assert "NOT semantic equivalence" in r.note


# ---------------------------------------------------------------------------
# Selected count >= 0 invariant (property-style, across all fixtures)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ids",
    [[], ["A"], ["A", "A"], ["A", "B", "C"], DUPLICATE_IDS_CASE["selected"]],
)
def test_selection_count_invariant_non_negative(ids):
    assert selection_count(ids).value >= 0.0


# ---------------------------------------------------------------------------
# Architectural property: no metric function derives gold from agent-visible data
# ---------------------------------------------------------------------------

_ALL_METRIC_FUNCTIONS = [
    recall_at_k,
    reciprocal_rank,
    mean_reciprocal_rank,
    classify_gold_id_capacity,
    selection_capacity_report,
    selection_count,
    selection_count_aggregate,
    strict_tsr,
    evidence_precision,
    evidence_recall,
    evidence_coverage,
    irrelevant_memory_rate,
    redundancy,
]


@pytest.mark.parametrize("func", _ALL_METRIC_FUNCTIONS, ids=lambda f: f.__name__)
def test_no_metric_function_takes_agent_visible_context(func):
    """No metric function may accept a parameter shaped like/named after
    AgentVisibleContext. Gold-bearing metrics are evaluator-side and must source gold data
    only from EvaluatorReference-shaped inputs (or plain IDs/lists), never from
    agent-visible data, per LEAKAGE_AND_VISIBILITY_CONTRACT.md."""
    sig = inspect.signature(func)
    param_names = [p.lower() for p in sig.parameters]
    for name in param_names:
        assert "agent_visible" not in name, (
            f"{func.__name__} has a parameter suggestive of AgentVisibleContext: {name}"
        )
        assert "agentvisible" not in name.replace("_", "")


def test_metrics_module_never_imports_agent_visible_context_type():
    """Static check: no metrics module contains an `import` line referencing
    AgentVisibleContext (as a type/module), and no function is annotated with it.
    Reinforces that these are evaluator-side-only functions that never read agent-visible
    data to obtain gold labels. (Only actual code lines are checked -- prose in docstrings
    that merely *discusses* AgentVisibleContext, e.g. to explain what these functions do
    NOT take, is not itself a violation.)"""
    for module in (retrieval_mod, selection_mod, evidence_mod):
        for line in inspect.getsource(module).splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")) or ": AgentVisibleContext" in line:
                assert "AgentVisibleContext" not in stripped, (
                    f"{module.__name__} has a live code reference to AgentVisibleContext: {stripped!r}"
                )
        for _, func in inspect.getmembers(module, inspect.isfunction):
            for param in inspect.signature(func).parameters.values():
                assert param.annotation != "AgentVisibleContext"


def test_metrics_package_never_imports_phase3_reference():
    """Static check: no metrics module contains an `import`/`from` line referencing
    phase3_reference/ (historical-only per PHASE3_RESTART_BOUNDARY.md). Docstring prose
    that cites the historical formula for context (e.g. in strict_tsr's docstring) is not
    itself an import and is not what this check targets."""
    for module in (retrieval_mod, selection_mod, evidence_mod):
        for line in inspect.getsource(module).splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")):
                assert "phase3_reference" not in stripped, (
                    f"{module.__name__} has a live import referencing phase3_reference: {stripped!r}"
                )


# ---------------------------------------------------------------------------
# MetricResult structural sanity
# ---------------------------------------------------------------------------


def test_metric_result_is_shared_dataclass_type_across_modules():
    results = [
        recall_at_k(["A"], ["A"], 1),
        reciprocal_rank(["A"], ["A"]),
        strict_tsr(["A"], ["A"]),
        selection_count(["A"]),
        evidence_precision(["A"], ["A"]),
        evidence_recall(["A"], ["A"]),
        evidence_coverage(["A"], ["A"]),
        irrelevant_memory_rate(["A"], ["A"]),
        redundancy(["A"]),
        selection_capacity_report(["A"], ["A"], ["A"]),
    ]
    for r in results:
        assert isinstance(r, MetricResult)
        assert isinstance(r.detail, dict)
        assert isinstance(r.metric_name, str) and r.metric_name
        assert isinstance(r.status, str) and r.status
