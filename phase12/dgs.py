"""Phase 12 -- DGS: Defense Generalization Score.

Extends Phase 11's own already-validated train/eval separation discipline
(`phase11/gnn/lofo.py`, `phase11/gnn/real_attack_corpus_detector.py`) from
the GNN specifically to EVERY rule-based configuration this project has
(B0-B8) -- same discipline, wider scope, per Plan Section 4/5 (confirmed).

Non-circular: `tuned_pools` (`phase6.evaluation.ablations.corpus.all_pools()`,
the SAME corpus B0-B8 report their real numbers against) is read-only here,
never modified. `new_pools` (`phase12.eval_corpus`) is real content this
project has never evaluated any B0-B8 configuration against before.

SCOPE OF THIS PASS: B0-B8 only (rule-based configurations). B9/B10 (the
risk-composed and GNN/GLN-hybrid configurations) require retraining a
learned model per corpus and are out of scope for this pass -- an explicit,
disclosed scope limit, not a silent omission (Plan Section 5: "no fabricated
ground truth... a negative or mixed result is a complete, acceptable, and
expected finding").
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

from phase6.defense.orchestration.pipeline import DefenseConfiguration, compute_metrics, evaluate_pool
from phase6.evaluation.ablations.corpus import all_pools as tuned_corpus_pools

from phase12.eval_corpus import combined_new_corpus_pools


@dataclass(frozen=True)
class DGSResult:
    config_name: str
    tuned_detection_rate: float
    new_corpus_detection_rate: float
    tuned_fpr: float
    new_corpus_fpr: float
    detection_gap: float  # new_corpus - tuned; negative == degradation on unseen data
    fpr_gap: float  # new_corpus - tuned; positive == more false positives on unseen data
    n_poison_tuned: int
    n_poison_new: int
    n_benign_tuned: int
    n_benign_new: int
    generalization_ratio: float  # new_corpus_detection_rate / tuned_detection_rate; 1.0 == perfect generalization


def _run_config(pools, config: DefenseConfiguration, run_id: str):
    outcomes = []
    for pool in pools:
        outcomes.extend(evaluate_pool(pool, config, run_id=run_id))
    return compute_metrics(outcomes, config.name)


def compute_dgs(configs: Sequence[DefenseConfiguration]) -> List[DGSResult]:
    tuned_pools = tuned_corpus_pools()  # read-only; the reported B0-B8 corpus, untouched
    new_pools = combined_new_corpus_pools()  # real, never previously evaluated against these configs

    results: List[DGSResult] = []
    for config in configs:
        tuned = _run_config(tuned_pools, config, run_id=f"phase12-dgs-tuned-{config.name}")
        new = _run_config(new_pools, config, run_id=f"phase12-dgs-new-{config.name}")
        results.append(
            DGSResult(
                config_name=config.name,
                tuned_detection_rate=tuned.poison_detection_rate,
                new_corpus_detection_rate=new.poison_detection_rate,
                tuned_fpr=tuned.benign_false_positive_rate,
                new_corpus_fpr=new.benign_false_positive_rate,
                detection_gap=new.poison_detection_rate - tuned.poison_detection_rate,
                fpr_gap=new.benign_false_positive_rate - tuned.benign_false_positive_rate,
                n_poison_tuned=tuned.n_poison,
                n_poison_new=new.n_poison,
                n_benign_tuned=tuned.n_benign,
                n_benign_new=new.n_benign,
                generalization_ratio=(
                    new.poison_detection_rate / tuned.poison_detection_rate if tuned.poison_detection_rate else 0.0
                ),
            )
        )
    return results
