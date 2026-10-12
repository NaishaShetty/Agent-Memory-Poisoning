"""Build the committed benign cluster centroids + threshold for the live sleeper activation-anomaly
signal (phase6/defense/sleeper/signals.py::activation_anomaly_signal).

The signal is the content-independent planted-memory detector validated in sleeper_activation_live.py
(dev: 88% sleeper recall at 10% benign FPR) and on hold-out 8 (145/160). A planted memory lands in an
anomalous embedding region -- far from where benign content clusters. This script fits the benign
cluster model ONCE on development benign memory and writes the centroids and a 10%-FPR threshold to a
committed JSON, which the phase6 signal loads at runtime (the same cache pattern as activation_shape_
signal). No phase17 import happens at signal runtime.

Fitted on DEVELOPMENT benign only (epistemic_quarantine._dev_sets); the threshold is the 90th percentile
of benign outlier distances (a ~10% benign false-positive, review-queue operating point).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parents[1] / "phase6" / "defense" / "sleeper" / "activation_anomaly_centroids.json"


def build(n_clusters: int = 8, fpr_pct: float = 90.0) -> dict:
    from sklearn.cluster import KMeans

    from phase17.epistemic_quarantine import _dev_sets
    from phase17.query_trigger_signal import benign_cluster_outlier_scores
    from phase17.semantic_detector import _embed

    _, _, btexts, _, _ = _dev_sets()
    E = _embed(btexts)
    km = KMeans(n_clusters=n_clusters, n_init=10, random_state=17).fit(E)
    dists = benign_cluster_outlier_scores(btexts, km.cluster_centers_)
    threshold = float(np.percentile(dists, fpr_pct))
    out = {
        "model": "sentence-transformers/all-MiniLM-L6-v2",
        "n_clusters": n_clusters,
        "fitted_on": "development benign memory (epistemic_quarantine._dev_sets)",
        "n_benign_fit": len(btexts),
        "threshold": threshold,
        "threshold_fpr_pct": fpr_pct,
        "benign_fpr_at_threshold": float((dists >= threshold).mean()),
        "centroids": km.cluster_centers_.astype(float).tolist(),
        "note": ("flag a memory as a planted-content anomaly if min distance to these benign centroids "
                 ">= threshold. Review-queue posture (~10% benign FPR). Validated: sleeper_activation_live.py "
                 "(dev 88%), eval_holdout8.py (HO8 145/160)."),
    }
    OUT.write_text(json.dumps(out), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = build()
    print(f"wrote {OUT.name}: {r['n_clusters']} centroids, threshold {r['threshold']:.4f} "
          f"(benign FPR {r['benign_fpr_at_threshold']:.1%}, n_fit {r['n_benign_fit']})")
