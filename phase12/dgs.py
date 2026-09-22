"""Phase 12 -- DGS: Defense Generalization Score.

Extends Phase 11's own already-validated train/eval separation discipline
(`phase11/gnn/lofo.py`, `phase11/gnn/real_attack_corpus_detector.py`) from
the GNN specifically to EVERY rule-based configuration this project has
(B0-B8) -- same discipline, wider scope, per Plan Section 4/5 (confirmed).

Non-circular: `tuned_pools` (`phase6.evaluation.ablations.corpus.all_pools()`,
the SAME corpus B0-B8 report their real numbers against) is read-only here,
never modified. `new_pools` (`phase12.eval_corpus`) is real content this
project has never evaluated any B0-B8 configuration against before.

SCOPE OF THIS PASS: B0-B8 only (rule-based configurations, via
`evaluate_pool()`/`DefenseConfiguration`). B9/B10 (the risk-composed and
GNN/GLN-hybrid configurations) use a DIFFERENT code path entirely
(`phase11.evaluation.run_b10`'s own bespoke risk-composed/blended scoring,
never a `DefenseConfiguration`) and cannot be plugged into `compute_dgs()`
below directly.

UPDATE (2026-09-21, Phase 12 generalization-gap follow-on, explicitly
authorized): B9/B10's OWN generalization is now real and measured, just not
via this module -- `phase11/gnn/real_attack_corpus_detector.py::
run_with_tuned_comparison()` computes the identical DGS-style tuned-vs-real
comparison for the learned GNN+grouped-raw blend, non-circularly (trained
on `all_dev_pools()` only, real content from `real_corpus.py`/
`poison_regeneration.py` never seen during training). Real result: 67.6%
tuned-corpus detection -> 98.75% mean real-corpus detection at the same
9.1% FPR (generalization ratio 1.46) -- positive generalization, the same
direction as this module's own B8 result. See
`docs/phase12/PHASE12_SECURITY_METRICS_REPORT.md` Section 2.5 for the full
writeup. This was NOT a new retraining effort -- the fix already existed in
this project's own Phase 11 work (committed before this Phase 12 follow-on
began); it had simply never been wired into Phase 12's own reporting or
compared against the SAME held-out corpus this module uses for B0-B8.
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
