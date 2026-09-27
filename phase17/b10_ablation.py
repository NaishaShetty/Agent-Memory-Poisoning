"""Phase 17 -- B10 learned-part ablation (`PHASE17_PLAN.md` A4).

Phase 16's open finding: after Phase 15's corroboration gate, no benign
record is corroborated, so the score threshold is -inf and the gate alone
decides -- the learned blend cannot matter. This module tests that directly
and ALSO measures what happens without the gate (where the blend can decide):

  variants = {gate on/off} x {blend (W=0.25, shipped), untrained-only (W=0),
                              GNN-only (W=1)}

Score boundary for UNGATED variants is calibrated on Phase 12's benign
pools (tie-aware, target 0.02); FPR there is reported HELD-OUT via the same
2-fold pool-parity scheme Phase 15 uses (never the in-sample number). The
gated variants use the shipped `_gated_threshold` over corroborated benign
(there are none -> -inf).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Dict, List, Sequence, Tuple

import torch

from phase11.gnn.blend_pooled_family import build_dataset
from phase11.gnn.combined_untrained_score import blended_score, combined_untrained_score
from phase11.gnn.features import GNN_FEATURE_KEYS
from phase15.b10_corroboration import RETRIEVAL_FEATURE_KEYS, corroborated_grouped_scores
from phase15.b10_live import _ensemble
from phase15.b10_per_dataset import _gated_threshold, _tie_aware_threshold_for_target_fpr
from phase6.defense.orchestration.pipeline import ScenarioPool

VARIANTS = {
    "blend(W=0.25,shipped)": 0.25,
    "untrained-only(W=0)": 0.0,
    "GNN-only(W=1)": 1.0,
}


def score(pools: Sequence[ScenarioPool], w_fit: float, gate: bool) -> Tuple[Dict[str, float], Dict[str, bool]]:
    train_ds, train_grouped, models = _ensemble()
    ds = build_dataset(tuple(pools))
    gscores, corr = corroborated_grouped_scores(pools)
    # ancestor records (frozen corpus lineage pools) are graph nodes without their own scored evidence
    grouped = torch.tensor([gscores.get(n, 0.0) for n in ds.node_ids], dtype=torch.float32)
    if gate:
        cols = [i for i, k in enumerate(GNN_FEATURE_KEYS) if k in RETRIEVAL_FEATURE_KEYS]
        feats = ds.features.clone()
        for row, nid in enumerate(ds.node_ids):
            if not corr.get(nid, False):
                feats[row, cols] = 0.0
        ds = replace(ds, features=feats)
    else:
        from phase11.gnn.combined_untrained_score import grouped_raw_tensor

        grouped = grouped_raw_tensor(tuple(pools), ds.node_ids)
    untrained = combined_untrained_score(train_ds.features, train_grouped, ds.features, grouped)
    total = None
    for model, mu, sd in models:
        fitted = model.predict_proba(ds.features, ds.mean_adj)
        b = blended_score(fitted, untrained, w_fit=w_fit, fit_mean=mu, fit_std=sd)
        total = b if total is None else total + b
    return dict(zip(ds.node_ids, (total / len(models)).tolist())), {n: corr.get(n, False) for n in ds.node_ids}


def calibrate_ungated(benign_pools: Sequence[ScenarioPool], w_fit: float):
    """(scores, per-fold thresholds, pool->fold) for held-out FPR reporting."""
    scores, _ = score(benign_pools, w_fit, gate=False)
    fold = {m.scenario_id: i % 2 for i, p in enumerate(benign_pools) for m in p.memories}
    thr = []
    for f in (0, 1):
        cal = [s for n, s in scores.items() if fold[n] != f]
        thr.append(_tie_aware_threshold_for_target_fpr(cal, [0.0] * len(cal), 0.02))
    return scores, thr, fold


def decisions(pools: Sequence[ScenarioPool], w_fit: float, gate: bool, thr: float) -> Dict[str, bool]:
    s, c = score(pools, w_fit, gate)
    return {n: ((c[n] if gate else True) and s[n] >= thr) for n in s}


__all__ = ["VARIANTS", "score", "calibrate_ungated", "decisions"]
