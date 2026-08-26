"""Phase 3.2-C: core memory metrics.

Implements exactly the ten metric families scoped for Phase 3.2-C (see
`phase3/evaluation/metrics/README.md` for full definitions, edge cases, and the
distinctions this package treats as load-bearing):

1. Recall@K                         -- retrieval.recall_at_k
2. MRR                              -- retrieval.reciprocal_rank, retrieval.mean_reciprocal_rank
3. Strict TSR                       -- selection.strict_tsr
4. Selection count                  -- selection.selection_count, selection.selection_count_aggregate
5. Selection-capacity diagnostics   -- retrieval.classify_gold_id_capacity, retrieval.selection_capacity_report
6. Evidence precision               -- evidence.evidence_precision
7. Evidence recall                  -- evidence.evidence_recall
8. Evidence coverage (PROVISIONAL)  -- evidence.evidence_coverage
9. Irrelevant-memory rate           -- evidence.irrelevant_memory_rate
10. Redundancy (identity-dup only)  -- evidence.redundancy

Explicitly NOT implemented here (see README.md "Out of scope" section and
PHASE3_CLEAN_AGENT_FOUNDATION_SPEC.md / EVALUATION_CONTRACT.md for where they belong):
evidence-equivalent/semantic scoring, provenance/lineage/lifecycle metrics, memory
contribution / gold-memory-ceiling / retrieval-utilization, agent answer correctness,
task success beyond strict TSR, leakage detection, determinism/reproducibility harnesses,
dataset adapters, Qwen/agent/retrieval/reranking/selection implementation, or any memory
creation/storage code.

Design principles (enforced across every function in this package):
- Pure functions: input -> `MetricResult`. No filesystem, network, LLM, embeddings, or
  randomness access, and no global/mutable state.
- Deterministic given the same inputs.
- No metric function accepts, requires, imports, or is typed against an
  `AgentVisibleContext`-shaped object -- gold-bearing inputs always arrive as plain IDs or
  `EvaluatorReference`-shaped data. This is checked automatically in
  `phase3/evaluation/tests/test_core_memory_metrics.py`.
- Every function returns a `MetricResult` (see `types.py`) with an explicit `status` field
  -- no metric silently converts an undefined case (empty gold, empty selection, k<=0,
  empty task set, etc.) to a numeric 0.
"""

from __future__ import annotations

from .types import MetricResult
from .retrieval import (
    recall_at_k,
    reciprocal_rank,
    mean_reciprocal_rank,
    classify_gold_id_capacity,
    selection_capacity_report,
    CLASSIFICATION_HIT,
    CLASSIFICATION_SELECTION_MISS,
    CLASSIFICATION_RETRIEVAL_MISS,
)
from .selection import (
    selection_count,
    selection_count_aggregate,
    strict_tsr,
)
from .evidence import (
    evidence_precision,
    evidence_recall,
    evidence_coverage,
    irrelevant_memory_rate,
    redundancy,
)
from .equivalence import (
    extract_equivalence_edges,
    validate_equivalence_edges,
    equivalence_classes,
    equivalence_group_size,
    FINDING_OK,
    FINDING_UNKNOWN_MEMORY_REFERENCE,
    FINDING_SELF_EQUIVALENCE_DECLARED,
    FINDING_ASYMMETRIC_DECLARATION,
)
from .provenance import (
    validate_parent_edges,
    orphan_parent_count,
    detect_cycles,
    ancestors,
    descendants,
    root_origins,
    shared_origin_report,
    lineage_depth,
    validate_provenance,
    provenance_completeness_report,
    independence_report,
    PROVENANCE_COMPLETE,
    PROVENANCE_INCOMPLETE,
    PROVENANCE_INVALID,
    CLASS_LINEAGE_INDEPENDENT,
    CLASS_SHARED_LINEAGE_ORIGIN,
    CLASS_DIRECT_ANCESTOR_DESCENDANT,
    CLASS_EQUIVALENT_INFORMATION,
    CLASS_MULTI_ORIGIN_DERIVED,
    CLASS_UNKNOWN,
)

__all__ = [
    "MetricResult",
    "recall_at_k",
    "reciprocal_rank",
    "mean_reciprocal_rank",
    "classify_gold_id_capacity",
    "selection_capacity_report",
    "CLASSIFICATION_HIT",
    "CLASSIFICATION_SELECTION_MISS",
    "CLASSIFICATION_RETRIEVAL_MISS",
    "selection_count",
    "selection_count_aggregate",
    "strict_tsr",
    "evidence_precision",
    "evidence_recall",
    "evidence_coverage",
    "irrelevant_memory_rate",
    "redundancy",
    "extract_equivalence_edges",
    "validate_equivalence_edges",
    "equivalence_classes",
    "equivalence_group_size",
    "FINDING_OK",
    "FINDING_UNKNOWN_MEMORY_REFERENCE",
    "FINDING_SELF_EQUIVALENCE_DECLARED",
    "FINDING_ASYMMETRIC_DECLARATION",
    "validate_parent_edges",
    "orphan_parent_count",
    "detect_cycles",
    "ancestors",
    "descendants",
    "root_origins",
    "shared_origin_report",
    "lineage_depth",
    "validate_provenance",
    "provenance_completeness_report",
    "independence_report",
    "PROVENANCE_COMPLETE",
    "PROVENANCE_INCOMPLETE",
    "PROVENANCE_INVALID",
    "CLASS_LINEAGE_INDEPENDENT",
    "CLASS_SHARED_LINEAGE_ORIGIN",
    "CLASS_DIRECT_ANCESTOR_DESCENDANT",
    "CLASS_EQUIVALENT_INFORMATION",
    "CLASS_MULTI_ORIGIN_DERIVED",
    "CLASS_UNKNOWN",
]
