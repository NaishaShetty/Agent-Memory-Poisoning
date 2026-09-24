"""Phase 15 -- folding B9 (and, at corpus level only, B10) into Phase 12's
own per-(dataset, defense-configuration) security matrix shape
(`phase12/evaluation_matrix.py::MatrixCell`), rather than rebuilding a
second, separate reporting pipeline (see `docs/phase15/PHASE15_PLAN.md`
Section 3's "stitch together, don't rebuild" recommendation).

B9: A REAL, NEW PER-DATASET RESHAPE
--------------------------------------------------------------------------------
B9 is a deterministic, rule-based composition (`compute_memory_risk_score`,
`GROUPED_GATED`) -- the SAME kind of per-memory computation B0-B8 already
run per dataset via `evaluate_pool()`. `run_b9_risk_composed()`
(`phase6/evaluation/ablations/run_b0_b7.py`) already returns the exact same
`(ConfigurationMetrics, exclusions)` shape `compute_metrics()` gives B0-B8 --
it was only ever CALLED against the frozen 75-scenario corpus
(`all_pools()`). This module's own `pools` parameter (added this session,
additive, backward-compatible -- see that function's own Update note) lets
it be called against Phase 12's own real per-dataset `DatasetCorpus.pools`
instead, producing REAL, NEW per-dataset B9 cells this project has never
computed before, using the exact same mechanism B9's own historically-
reported numbers use -- not a re-derivation of anything already reported.

B10: A DELIBERATE, DISCLOSED SCOPE DECISION -- CORPUS-LEVEL ONLY
--------------------------------------------------------------------------------
B10 (the GNN+GLN learned hybrid) is fundamentally different: its real
numbers (`phase11/gnn/real_attack_corpus_detector.py`) come from a trained
detector evaluated via a real train/held-out seed methodology (seeds 11-20),
not a stateless per-memory rule. Decomposing it per-dataset would require
re-training/re-evaluating the detector against dataset-specific splits --
real, substantial new ML work, out of scope for a reshape. Per
`docs/phase15/PHASE15_PLAN.md` Section 6, Question 3's own resolution: B10's
real, already-reported, already-trusted number (99.6% mean detection, 9.1%
FPR -- `docs/phase11/PHASE11_FINAL_GAP_CLOSURE_REPORT.md`) is reused
verbatim, reported ONCE at the corpus level, not decomposed into per-dataset
cells it was never designed to produce.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence

from phase6.defense.orchestration.pipeline import ConfigurationMetrics
from phase6.defense.risk.risk_score import GROUPED_GATED_RETRIEVAL_CORROBORATED
from phase6.evaluation.ablations.run_b0_b7 import run_b9_risk_composed
from phase12.eval_corpus import DatasetCorpus, per_dataset_eval_corpora
from phase12.evaluation_matrix import MatrixCell

CONFIG_NAME_B9 = "B9"

# Real, already-reported, corpus-level-only B10 number (not decomposed per
# dataset -- see module docstring). Cited, not recomputed.
B10_MEAN_DETECTION = 0.996
B10_FALSE_POSITIVE_RATE = 0.091
B10_SOURCE = "docs/phase11/PHASE11_FINAL_GAP_CLOSURE_REPORT.md (real_attack_corpus_detector.py, seeds 11-20)"


def b9_matrix_cells(
    corpora: Dict[str, DatasetCorpus] = None, *, rule: str = GROUPED_GATED_RETRIEVAL_CORROBORATED,
) -> List[MatrixCell]:
    """One real `MatrixCell` per real dataset for B9, computed the SAME real
    way `run_security_matrix()` computes B0-B8's cells -- reusing
    `run_b9_risk_composed()`'s own real mechanism against each dataset's own
    real pools, never re-implemented.

    `rule` defaults to `GROUPED_GATED_RETRIEVAL_CORROBORATED` (2026-09-23,
    same-day follow-on, explicitly authorized) -- the real, root-caused fix
    for the 50% real LongMemEval false-positive rate `GROUPED_GATED` itself
    produces here (see `risk_score.py`'s own module note for the full real
    cause and validation). Pass `rule=GROUPED_GATED` explicitly to reproduce
    the original, unfixed numbers for comparison -- both are exercised by
    `test_security_matrix_extension.py`."""
    corpora = corpora or per_dataset_eval_corpora()
    cells: List[MatrixCell] = []
    for dataset_name, corpus in corpora.items():
        metrics, exclusions = run_b9_risk_composed(pools=corpus.pools, rule=rule)
        if exclusions:
            raise RuntimeError(
                f"B9 real IllegalTransitionError exclusion(s) on dataset {dataset_name!r}: {exclusions!r} -- "
                "not silently absorbed; see run_b9_risk_composed()'s own exclusion discipline."
            )
        cells.append(MatrixCell(dataset_name, CONFIG_NAME_B9, metrics))
    return cells


@dataclass(frozen=True)
class B10CorpusLevelResult:
    config_name: str
    mean_detection: float
    false_positive_rate: float
    source: str
    scope_note: str = (
        "Corpus-level only, not decomposed per dataset -- B10 is a trained "
        "detector evaluated via a real train/held-out seed methodology, not "
        "a stateless per-memory rule; see security_matrix_extension.py's "
        "own module docstring for the full, disclosed reasoning."
    )


def b10_corpus_level_result() -> B10CorpusLevelResult:
    return B10CorpusLevelResult(
        config_name="B10", mean_detection=B10_MEAN_DETECTION,
        false_positive_rate=B10_FALSE_POSITIVE_RATE, source=B10_SOURCE,
    )


__all__ = [
    "CONFIG_NAME_B9", "B10_MEAN_DETECTION", "B10_FALSE_POSITIVE_RATE", "B10_SOURCE",
    "b9_matrix_cells", "B10CorpusLevelResult", "b10_corpus_level_result",
]
