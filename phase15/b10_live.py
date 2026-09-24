"""Phase 15 follow-on (2026-09-23, explicitly authorized) -- a LIVE, per-task
B10 decision, so B10 can be measured on Phase 14's utility axis like every
other config (previously disclosed as "no live-path analog").

HOW: one ensemble of the real trained GNNs (seeds 11-20, trained ONCE on
`split.all_dev_pools()`, never real dataset content) scores each task's own
candidate pool via the SAME `build_dataset`/`combined_untrained_score`/
`blended_score` chain `b10_per_dataset.py` uses. One GLOBAL decision
threshold is fit ONCE (tie-aware, target `LIVE_TARGET_FPR`) on the pooled
benign records of all four of Phase 12's real per-dataset corpora -- content
disjoint from Phase 14's own Track A/B task pools (real QA declaratives / real
poison scenarios), so calibration never sees the tasks it is later applied to.
A candidate is EXCLUDED (action QUARANTINE) iff it is CORROBORATED (real
non-retrieval evidence fired, `b10_corroboration.py`) AND its ensemble blend >=
threshold, Phase 14's own `HARD_MITIGATION_ACTIONS` convention. UPDATE: the
corroboration gate was added after the first, ungated version was measured
(protected 0/9 isolated poison, excluded ~5% of benign Track A candidates --
retrieval-only evidence, the same B9/LongMemEval root cause). DISCLOSED: no
Phase 12 benign record is corroborated, so the calibrated score threshold is
-inf and the decision reduces to the corroboration gate itself.

DISCLOSED LIMITS: a single global threshold cannot adapt per dataset the way
`b10_per_dataset.py`'s per-dataset calibration does, and B10 has no real
signal on LongMemEval-style content (AUROC 0.481) -- both are expected to
show up as real utility/protection results, not hidden.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Dict, Sequence, Tuple

from dataclasses import replace

import torch

from phase11.data import split
from phase11.gnn.blend_pooled_family import build_dataset
from phase11.gnn.combined_untrained_score import blended_score, combined_untrained_score, grouped_raw_tensor
from phase11.gnn.train import train_model
from phase11.gnn.features import GNN_FEATURE_KEYS
from phase12.eval_corpus import per_dataset_eval_corpora
from phase15.b10_corroboration import RETRIEVAL_FEATURE_KEYS, corroborated_grouped_scores
from phase15.b10_per_dataset import W, WEIGHT_DECAY, _gated_threshold
from phase6.defense.orchestration.pipeline import MemoryScenario, ScenarioPool

SEEDS = tuple(range(11, 21))
LIVE_TARGET_FPR = 0.02


@lru_cache(maxsize=1)
def _ensemble():
    train_pools = split.all_dev_pools()
    train_ds = build_dataset(train_pools)
    train_grouped = grouped_raw_tensor(train_pools, train_ds.node_ids)
    models = []
    for seed in SEEDS:
        model = train_model(train_ds, seed=seed, weight_decay=WEIGHT_DECAY)
        fitted = model.predict_proba(train_ds.features, train_ds.mean_adj)
        models.append((model, fitted.mean().item(), fitted.std(unbiased=False).item()))
    return train_ds, train_grouped, models


def _score_pools(pools: Sequence[ScenarioPool]) -> Tuple[Dict[str, float], Dict[str, bool]]:
    """Ensemble blend per node PLUS whether it is corroborated (real
    non-retrieval evidence fired) -- the same corroboration gate
    `b10_per_dataset.py` applies (see `b10_corroboration.py`): retrieval
    features of uncorroborated nodes are zeroed before scoring."""
    train_ds, train_grouped, models = _ensemble()
    ds = build_dataset(tuple(pools))
    gscores, corr = corroborated_grouped_scores(pools)
    grouped = torch.tensor([gscores[nid] for nid in ds.node_ids], dtype=torch.float32)
    retr_cols = [i for i, k in enumerate(GNN_FEATURE_KEYS) if k in RETRIEVAL_FEATURE_KEYS]
    feats = ds.features.clone()
    for row, nid in enumerate(ds.node_ids):
        if not corr[nid]:
            feats[row, retr_cols] = 0.0
    ds = replace(ds, features=feats)
    untrained = combined_untrained_score(train_ds.features, train_grouped, ds.features, grouped)
    total = None
    for model, fit_mean, fit_std in models:
        fitted = model.predict_proba(ds.features, ds.mean_adj)
        blend = blended_score(fitted, untrained, w_fit=W, fit_mean=fit_mean, fit_std=fit_std)
        total = blend if total is None else total + blend
    return dict(zip(ds.node_ids, (total / len(models)).tolist())), {nid: corr[nid] for nid in ds.node_ids}


@lru_cache(maxsize=1)
def live_threshold() -> float:
    pools = [p for c in per_dataset_eval_corpora().values() for p in c.benign_pools]
    scores, corr = _score_pools(pools)
    return _gated_threshold([scores[n] for n in scores if corr[n]])


def b10_actions(items: Sequence[Tuple[str, str]]) -> Dict[str, str]:
    pool = ScenarioPool("phase15-b10-live", tuple(MemoryScenario(mid, text) for mid, text in items))
    threshold = live_threshold()
    scores, corr = _score_pools([pool])
    return {
        mid: ("QUARANTINE" if corr[mid] and scores[mid] >= threshold else "ALLOW") for mid, _ in items
    }


__all__ = ["b10_actions", "live_threshold", "LIVE_TARGET_FPR"]
