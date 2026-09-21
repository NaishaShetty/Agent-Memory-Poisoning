"""Phase 11.x Option 2 -- the controlled experiment itself.

Reuses the EXACT same non-circular real data split the Option-1
investigation already established and disclosed:

  repr (representation-training) pools = `train_pools()` + `real_benign_scenarios()`
  eval (dev-time evaluation) pools     = `dev_pools()` + `real_poison_scenarios()`

`held_out_pools()` is never imported or referenced anywhere in this module.

Run directly: `python -m phase11.expanded_features.experiment`
"""

from __future__ import annotations

import statistics

from phase11.data import split
from phase11.data.real_corpus import real_benign_scenarios, real_poison_scenarios
from phase11.expanded_features.anomaly import (
    ae_anomaly_scores,
    auroc,
    raw_centroid_scores,
    svdd_anomaly_scores,
    train_autoencoder,
    train_svdd_encoder,
)
from phase11.expanded_features.dataset import build_expanded_dataset, fit_semantic_pca_on_training_pools

SEEDS = tuple(range(11, 21))


def _repr_and_eval_pools():
    repr_pools = split.train_pools() + real_benign_scenarios()
    eval_pools = split.dev_pools() + (real_poison_scenarios(),)
    return repr_pools, eval_pools


def run_config(config: str, fitted_pca=None) -> dict:
    repr_pools, eval_pools = _repr_and_eval_pools()
    repr_ds = build_expanded_dataset(repr_pools, config, fitted_pca=fitted_pca)
    eval_ds = build_expanded_dataset(eval_pools, config, fitted_pca=fitted_pca)

    raw_scores = raw_centroid_scores(repr_ds, eval_ds)
    raw_auroc = auroc(raw_scores, eval_ds.labels)

    svdd_aurocs = []
    ae_aurocs = []
    memorygraft_svdd_scores = []
    memorygraft_index = None
    if "REAL-MEMORYGRAFT-0" in eval_ds.node_ids:
        memorygraft_index = eval_ds.node_ids.index("REAL-MEMORYGRAFT-0")

    for seed in SEEDS:
        encoder, center = train_svdd_encoder(repr_ds, seed=seed)
        scores = svdd_anomaly_scores(encoder, center, eval_ds)
        svdd_aurocs.append(auroc(scores, eval_ds.labels))
        if memorygraft_index is not None:
            memorygraft_svdd_scores.append(float(scores[memorygraft_index]))

        enc2, dec2 = train_autoencoder(repr_ds, seed=seed)
        ae_scores = ae_anomaly_scores(enc2, dec2, eval_ds)
        ae_aurocs.append(auroc(ae_scores, eval_ds.labels))

    return {
        "config": config,
        "feature_dim": repr_ds.features.shape[1],
        "feature_keys": repr_ds.feature_keys,
        "n_repr": len(repr_ds.labels),
        "n_repr_benign": int((repr_ds.labels == 0).sum()),
        "n_eval": len(eval_ds.labels),
        "n_eval_poison": int(eval_ds.labels.sum()),
        "n_eval_benign": int((eval_ds.labels == 0).sum()),
        "raw_centroid_auroc": raw_auroc,
        "svdd_auroc_mean": statistics.mean(svdd_aurocs),
        "svdd_auroc_range": (min(svdd_aurocs), max(svdd_aurocs)),
        "ae_auroc_mean": statistics.mean(ae_aurocs),
        "ae_auroc_range": (min(ae_aurocs), max(ae_aurocs)),
        "memorygraft_svdd_score_mean": (
            statistics.mean(memorygraft_svdd_scores) if memorygraft_svdd_scores else None
        ),
    }


def run_all() -> dict:
    repr_pools, _ = _repr_and_eval_pools()
    fitted_pca = fit_semantic_pca_on_training_pools(repr_pools)

    results = {}
    for config in ("A", "B", "S", "C", "M", "D"):
        pca_arg = fitted_pca if config in ("C", "D", "M") else None
        results[config] = run_config(config, fitted_pca=pca_arg)
    results["_pca"] = {
        "n_components": fitted_pca.n_components,
        "n_training_examples": fitted_pca.n_training_examples,
        "explained_variance_ratio_sum": sum(fitted_pca.explained_variance_ratio),
    }
    return results


if __name__ == "__main__":
    results = run_all()
    pca_info = results.pop("_pca")
    print(f"PCA: {pca_info['n_components']} components fit on {pca_info['n_training_examples']} "
          f"real training embeddings, cumulative explained variance = "
          f"{pca_info['explained_variance_ratio_sum']:.3f}")
    print()
    header = f"{'cfg':4s} {'dim':4s} {'n_eval(p/b)':12s} {'raw':>8s} {'svdd_mean':>10s} {'svdd_range':>16s} {'ae_mean':>8s} {'ae_range':>16s} {'mg_svdd':>8s}"
    print(header)
    for config, r in results.items():
        mg = f"{r['memorygraft_svdd_score_mean']:.3f}" if r["memorygraft_svdd_score_mean"] is not None else "n/a"
        print(
            f"{config:4s} {r['feature_dim']:4d} "
            f"{r['n_eval_poison']}/{r['n_eval_benign']:<9d} "
            f"{r['raw_centroid_auroc']:8.3f} "
            f"{r['svdd_auroc_mean']:10.3f} "
            f"[{r['svdd_auroc_range'][0]:.2f},{r['svdd_auroc_range'][1]:.2f}]      "
            f"{r['ae_auroc_mean']:8.3f} "
            f"[{r['ae_auroc_range'][0]:.2f},{r['ae_auroc_range'][1]:.2f}]      "
            f"{mg:>8s}"
        )
