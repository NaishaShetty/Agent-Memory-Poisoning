"""Phase 11 -- re-sweeping `WEIGHT_DECAY` against the LOFO (family-
generalization) objective specifically, per the user's own direct question
("I want the GNN to work properly") and the recommendation that closed
`docs/phase11/PHASE11_LOFO_BASELINE_C_REPORT.md`.

WHY THIS IS A GENUINELY DIFFERENT TEST THAN THE ORIGINAL SWEEP
--------------------------------------------------------------------------------
`phase11/gnn/train.py`'s own module docstring already discloses a
weight-decay sweep (0.0, 0.001, 0.005, 0.01, 0.02, 0.05) that found every
nonzero value made the real held-out result WORSE -- but that sweep was
measured against the POOLED-family held-out metric (`held_out_pools()`,
trained on all 4 families together). The LOFO investigation's own real
finding (`PHASE11_LOFO_REPORT.md`) was that BOTH the GNN and a from-scratch
linear model (`PHASE11_LOFO_BASELINE_C_REPORT.md`) overfit specifically to
the FAMILIES present during training -- a different failure mode than
"overfits to the training examples in general," which is what weight decay
is classically for. This sweep asks whether regularization, untested
against this specific objective before now, changes the LOFO result --
using the SAME leakage-safe fold construction `phase11/gnn/lofo.py` already
built and audited (`PHASE11_LOFO_AUDIT.md`), with ONE additive parameter
(`weight_decay`, threaded through `train_model()`/`run_lofo_fold()` with a
`None`-default that preserves every pre-existing call site's behavior
byte-for-byte -- verified by `test_gnn_lofo.py`/`test_gnn_train.py` still
passing unmodified).

WHAT THIS DOES NOT DO
--------------------------------------------------------------------------------
Does not change `MinimalGNN`'s architecture, the feature contract, or
`held_out_pools()`. Does not retune anything else while sweeping
`weight_decay` (single-factor sweep, per this project's own "one real
lever at a time" discipline). Does not silently keep searching once a
result is in -- the values swept are fixed here, before any result is
seen: 0.0 (the current shipped default, for a same-run comparison point),
0.001, 0.005, 0.01, 0.02, 0.05 (the EXACT SAME 6 values the original,
different-objective sweep already used, for direct comparability -- not a
new, wider search invented to go fishing for a better number).
"""

from __future__ import annotations

import statistics
from typing import Dict, List

from phase11.gnn.lofo import SEEDS, _discover_families, per_family_summary, run_lofo_fold
from phase11.data import split

WEIGHT_DECAY_VALUES = (0.0, 0.001, 0.005, 0.01, 0.02, 0.05)  # identical to train.py's own original sweep


def run_weight_decay_sweep(*, weight_decay_values=WEIGHT_DECAY_VALUES, seeds=SEEDS) -> Dict[float, Dict[str, dict]]:
    families = _discover_families(split.all_dev_pools())
    results: Dict[float, Dict[str, dict]] = {}
    for wd in weight_decay_values:
        results[wd] = {}
        for family in families:
            fold_results = run_lofo_fold(family, seeds=seeds, weight_decay=wd)
            results[wd][family] = per_family_summary(fold_results)
    return results


def macro_auroc_by_weight_decay(sweep_results: Dict[float, Dict[str, dict]]) -> Dict[float, float]:
    """Unweighted mean of the 4 per-family AUROC means, per weight_decay --
    the same macro-summary statistic `pooled_out_of_fold_summary()` already
    reports, applied across the sweep so a decrease/increase is visible at
    a glance. Reported as a SECONDARY, descriptive statistic (per Audit
    Section 8) -- the per-family table is the primary result."""
    return {
        wd: statistics.mean(family_summary["auroc_mean"] for family_summary in per_family.values())
        for wd, per_family in sweep_results.items()
    }


if __name__ == "__main__":
    import json

    sweep = run_weight_decay_sweep()
    for wd, per_family in sweep.items():
        print(f"\n=== weight_decay={wd} ===")
        for family, summary in per_family.items():
            print(f"  {family}: n={summary['n_family_poison_held_out']} "
                  f"auroc_mean={summary['auroc_mean']:.4f} "
                  f"[{summary['auroc_min']:.4f}, {summary['auroc_max']:.4f}] "
                  f"detection_mean={summary['detection_rate_mean']:.4f} "
                  f"fpr_mean={summary['false_positive_rate_mean']:.4f}")

    print("\n=== Macro AUROC (unweighted mean across families) by weight_decay ===")
    print(json.dumps(macro_auroc_by_weight_decay(sweep), indent=2))
