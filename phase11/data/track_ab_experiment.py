"""Phase 11.x Track A/B -- the controlled model experiment comparing:

  A. Existing Phase 11 training data (Option 1's own frozen config)
  B. + Track A clean expansion (LongMemEval/MSC/ConversationChronicles, 30
     real pools, 367 real records)
  C. + Track B poison regeneration (7 new real attack instances, 9 memories)

against the SAME frozen, non-circular evaluation set Option 1/2 already
established (`dev_pools() + real_poison_scenarios()`) -- never touching
`held_out_pools()`. Reuses `phase11/gnn/self_supervised.py`'s existing,
UNMODIFIED training/scoring functions -- no new architecture, per the
governing instructions' "do not immediately introduce additional
architectural complexity."

Run directly: `python -m phase11.data.track_ab_experiment`
"""

from __future__ import annotations

import statistics

from phase11.data import split
from phase11.data.clean_expansion import clean_expansion_pools
from phase11.data.poison_regeneration import regenerate_poison_batch
from phase11.data.real_corpus import real_benign_scenarios, real_poison_scenarios
from phase11.gnn.self_supervised import (
    ae_anomaly_scores,
    auroc,
    build_relation_dataset,
    svdd_anomaly_scores,
    train_autoencoder,
    train_svdd_encoder,
)

SEEDS = tuple(range(11, 21))


def _eval_pools():
    return split.dev_pools() + (real_poison_scenarios(),)


def _repr_pools_for_config(config: str):
    base = split.train_pools() + real_benign_scenarios()
    if config == "A":
        return base
    if config == "B":
        clean_pools, _ = clean_expansion_pools()
        return base + clean_pools
    if config == "C":
        clean_pools, _ = clean_expansion_pools()
        regen_pool, _ = regenerate_poison_batch()
        return base + clean_pools + (regen_pool,)
    raise ValueError(config)


def run_config(config: str) -> dict:
    repr_pools = _repr_pools_for_config(config)
    eval_pools = _eval_pools()
    repr_ds = build_relation_dataset(repr_pools)
    eval_ds = build_relation_dataset(eval_pools)

    benign_mask = repr_ds.labels == 0.0
    centroid = repr_ds.features[benign_mask].mean(dim=0)
    raw_scores = ((eval_ds.features - centroid) ** 2).sum(dim=1).sqrt()
    raw_auroc = auroc(raw_scores, eval_ds.labels)

    svdd_aurocs, ae_aurocs = [], []
    for seed in SEEDS:
        encoder, center = train_svdd_encoder(repr_ds, seed=seed)
        svdd_aurocs.append(auroc(svdd_anomaly_scores(encoder, center, eval_ds), eval_ds.labels))
        enc2, dec2 = train_autoencoder(repr_ds, seed=seed)
        ae_aurocs.append(auroc(ae_anomaly_scores(enc2, dec2, eval_ds), eval_ds.labels))

    return {
        "config": config,
        "n_repr": len(repr_ds.labels), "n_repr_benign": int((repr_ds.labels == 0).sum()),
        "n_repr_poison": int(repr_ds.labels.sum()),
        "n_eval": len(eval_ds.labels), "n_eval_poison": int(eval_ds.labels.sum()),
        "n_eval_benign": int((eval_ds.labels == 0).sum()),
        "raw_centroid_auroc": raw_auroc,
        "svdd_auroc_mean": statistics.mean(svdd_aurocs), "svdd_auroc_range": (min(svdd_aurocs), max(svdd_aurocs)),
        "ae_auroc_mean": statistics.mean(ae_aurocs), "ae_auroc_range": (min(ae_aurocs), max(ae_aurocs)),
    }


def run_all() -> dict:
    return {c: run_config(c) for c in ("A", "B", "C")}


if __name__ == "__main__":
    results = run_all()
    for config, r in results.items():
        print(f"config {config}: n_repr={r['n_repr']} (benign={r['n_repr_benign']}, poison={r['n_repr_poison']}) "
              f"n_eval={r['n_eval']} (poison={r['n_eval_poison']}, benign={r['n_eval_benign']})")
        print(f"  raw_centroid_auroc={r['raw_centroid_auroc']:.3f}")
        print(f"  svdd_auroc_mean={r['svdd_auroc_mean']:.3f} range={r['svdd_auroc_range']}")
        print(f"  ae_auroc_mean={r['ae_auroc_mean']:.3f} range={r['ae_auroc_range']}")
