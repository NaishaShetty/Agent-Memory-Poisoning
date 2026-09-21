"""Phase 12 -- the security evaluation matrix: attack-family x dataset x
defense-configuration, workload axis dropped (Plan Section 8.2, confirmed).

Combines `phase12.eval_corpus` (the new, real, separate corpus) with
`phase6.defense.orchestration.pipeline`'s real `evaluate_pool()`/
`compute_metrics()` -- no new decision logic. Scope: B0-B8 (rule-based
configurations); B9/B10 excluded this pass (see `phase12.dgs` docstring).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from phase6.defense.orchestration.pipeline import (
    B0_TO_B7,
    B8_ALL_FOUR,
    ConfigurationMetrics,
    DefenseConfiguration,
    compute_metrics,
    evaluate_pool,
)

from phase12.eval_corpus import DatasetCorpus, per_dataset_eval_corpora

ALL_RULE_BASED_CONFIGS: Tuple[DefenseConfiguration, ...] = B0_TO_B7 + (B8_ALL_FOUR,)


@dataclass(frozen=True)
class MatrixCell:
    dataset_name: str
    config_name: str
    metrics: ConfigurationMetrics


def run_security_matrix(
    configs: Sequence[DefenseConfiguration] = ALL_RULE_BASED_CONFIGS,
    corpora: Dict[str, DatasetCorpus] = None,
) -> List[MatrixCell]:
    """One real `ConfigurationMetrics` per (dataset, defense-configuration)
    cell. `per_attack_family_detection` on each cell's metrics already
    gives the attack-family axis (Plan Section 7's 3rd, real dimension)
    without a separate loop -- `compute_metrics()` groups by
    `attack_family_ground_truth` internally."""
    corpora = corpora or per_dataset_eval_corpora()
    cells: List[MatrixCell] = []
    for dataset_name, corpus in corpora.items():
        for config in configs:
            outcomes = []
            for pool in corpus.pools:
                outcomes.extend(evaluate_pool(pool, config, run_id=f"phase12-matrix-{dataset_name}-{config.name}"))
            metrics = compute_metrics(outcomes, config.name)
            cells.append(MatrixCell(dataset_name, config.name, metrics))
    return cells


def cells_by_dataset(cells: Sequence[MatrixCell]) -> Dict[str, List[MatrixCell]]:
    grouped: Dict[str, List[MatrixCell]] = {}
    for cell in cells:
        grouped.setdefault(cell.dataset_name, []).append(cell)
    return grouped
