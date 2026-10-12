"""Hold-out 8 anomaly and union results with thresholds that never see hold-out 8's evaluation data
(review issues M7 / D7 / P0-6 / P1-2; Gap 3, sleeper).

THE DEFECT. `eval_holdout8.py` fitted the anomaly signal's KMeans clusters on one half of hold-out 8's
benign notes, then set the threshold at a percentile of the OTHER half's outlier scores and reported the
false-positive rate on that same half. A threshold at the 90th percentile of a set flags ~10% of that set
by construction, so the reported benign FPR (9/85 for the sleeper arm, 8/85 for the union) is not a
measurement, and recall is measured at a threshold derived from the hold-out. The operating point (90th /
99th percentile) was fixed before scoring (commit 0a8805d8 precedes the freeze 76cd4600), so this is
transductive calibration, not selection on results -- but it is not a held-out estimate either.

WHAT THIS MODULE DOES. Nothing frozen is modified; the original artifact stays as the historical record.
Three arms are computed from the same frozen texts, the same embedding model and the same B13 per-item
decisions already stored in `eval_holdout8.json`:

  ORIGINAL (reproduction):  clusters on HO8 benign[0::2], threshold = percentile of HO8 benign[1::2],
                            FPR on benign[1::2]  -- must reproduce the published numbers exactly.
  DEV-FITTED (primary):     clusters AND threshold fitted on the development benign train split exactly as
                            `union_defense_dev.py` did (RandomState(17) split, KMeans(8, n_init=10,
                            random_state=17), 90th / 99th percentile of dev-train benign scores); applied
                            unchanged to all 160 HO8 attacks and all 171 HO8 benign notes.
  OWNER-ADAPTIVE, LEAK-FREE: clusters AND threshold fitted on HO8 benign[0::2] only (a deployment that fits
                            on the owner's own earlier benign notes); FPR measured on benign[1::2], which
                            neither the clusters nor the threshold saw.

The supervised member of union3 (`EmbeddingDetector`, trained on development data only) is unchanged; it
never saw hold-out 8.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import numpy as np

DATA = Path(__file__).resolve().parents[1] / "data"
OUT = DATA / "remediation" / "ho8_anomaly_devfit.json"
ORIGINAL = DATA / "eval_holdout8.json"


def _dev_fit():
    """Clusters and the dev-train benign score distribution, exactly as union_defense_dev.run()."""
    from sklearn.cluster import KMeans

    from phase17.epistemic_quarantine import _dev_sets
    from phase17.query_trigger_signal import benign_cluster_outlier_scores
    from phase17.semantic_detector import _embed

    recs, _, btexts, _, _ = _dev_sets()
    rng = np.random.RandomState(17)
    _atk_tr = rng.rand(len(recs)) < 0.5          # drawn first, as in union_defense_dev, to keep the stream aligned
    ben_tr = rng.rand(len(btexts)) < 0.5
    EB = _embed(btexts)
    km = KMeans(n_clusters=8, n_init=10, random_state=17).fit(EB[ben_tr])
    ob = benign_cluster_outlier_scores(btexts, km.cluster_centers_)
    return km, ob[ben_tr], int(ben_tr.sum())


def _arm(oa: np.ndarray, ob_eval: np.ndarray, thr: float, b13a, b13b_eval, sem_a, sem_b_eval, fam) -> Dict:
    from phase17.stats import exact_mcnemar_p, rate_with_ci

    an_a, an_b = oa >= thr, ob_eval >= thr
    u2a, u2b = b13a | an_a, b13b_eval | an_b
    u3a, u3b = u2a | sem_a, u2b | sem_b_eval
    n, nb = len(oa), len(ob_eval)
    by_fam = {f: {"anomaly": f"{int(an_a[fam == f].sum())}/{int((fam == f).sum())}",
                  "union2": f"{int(u2a[fam == f].sum())}/{int((fam == f).sum())}",
                  "B13": f"{int(b13a[fam == f].sum())}/{int((fam == f).sum())}"} for f in sorted(set(fam))}
    return {"threshold": round(float(thr), 6),
            "anomaly": {"recall": rate_with_ci(int(an_a.sum()), n), "benign_fpr": rate_with_ci(int(an_b.sum()), nb)},
            "union2_B13_or_anomaly": {"recall": rate_with_ci(int(u2a.sum()), n),
                                      "benign_fpr": rate_with_ci(int(u2b.sum()), nb)},
            "union3_plus_supervised": {"recall": rate_with_ci(int(u3a.sum()), n),
                                       "benign_fpr": rate_with_ci(int(u3b.sum()), nb)},
            "B13_alone": {"recall": rate_with_ci(int(b13a.sum()), n), "benign_fpr": rate_with_ci(int(b13b_eval.sum()), nb)},
            "union2_vs_B13_paired": {"only_union2": int((u2a & ~b13a).sum()), "only_B13": int((b13a & ~u2a).sum()),
                                     "p_exact": exact_mcnemar_p(int((u2a & ~b13a).sum()), int((b13a & ~u2a).sum()))},
            "union2_minus_B13_fpr_points": round(100 * (u2b.mean() - b13b_eval.mean()), 2),
            "by_family": by_fam}


def run() -> Dict:
    from sklearn.cluster import KMeans

    from phase17.epistemic_quarantine import _dev_sets
    from phase17.holdout8_corpus import attack_records, benign_texts, verify_frozen
    from phase17.query_trigger_signal import benign_cluster_outlier_scores as oc
    from phase17.semantic_detector import EmbeddingDetector, _embed

    assert verify_frozen(), "hold-out 8 does not match its frozen digest"
    orig = json.loads(ORIGINAL.read_text(encoding="utf-8"))
    recs, b8 = attack_records(), benign_texts()
    atk = [r.text for r in recs]
    fam = np.array([r.family for r in recs])
    b13a = np.array(orig["raw"]["attack"]["B13"], dtype=bool)
    b13b = np.array(orig["raw"]["benign"]["B13"], dtype=bool)          # untrusted channel, with evidence
    assert len(b13a) == len(recs) and len(b13b) == len(b8)

    # supervised member, trained on DEV only (unchanged from eval_holdout8)
    dr, _, db, _, _ = _dev_sets()
    det = EmbeddingDetector(c=1.0)
    det.fit([r.text for r in dr], list(db))
    sem_a = np.array(det.flags(atk), dtype=bool)
    sem_b = np.array(det.flags(b8), dtype=bool)

    out: Dict = {"issue": "M7 / D7 / P1-2 (independent review 2026-10-12)", "n_attacks": len(recs),
                 "n_benign": len(b8), "b13_source": "eval_holdout8.json raw (stored per-item decisions)",
                 "arms": {}}

    # ORIGINAL reproduction
    fit, ev = b8[0::2], b8[1::2]
    km_o = KMeans(n_clusters=8, n_init=10, random_state=17).fit(_embed(fit))
    oa_o, ob_eval_o = oc(atk, km_o.cluster_centers_), oc(ev, km_o.cluster_centers_)
    ev_idx = list(range(1, len(b8), 2))
    out["arms"]["original_transductive"] = {
        "description": "threshold = percentile of the SAME benign half the FPR is reported on (historical)",
        "p90": _arm(oa_o, ob_eval_o, float(np.percentile(ob_eval_o, 90)), b13a, b13b[ev_idx], sem_a, sem_b[ev_idx], fam),
        "p99": _arm(oa_o, ob_eval_o, float(np.percentile(ob_eval_o, 99)), b13a, b13b[ev_idx], sem_a, sem_b[ev_idx], fam)}
    pub = orig["sleeper"]["activation_anomaly"]["cluster_outlier"]
    rep = out["arms"]["original_transductive"]["p90"]["anomaly"]
    out["reproduces_published"] = {
        "sleeper_p90_recall": [rep["recall"]["k"], pub["attack_recall"]["k"]],
        "sleeper_p90_fpr": [rep["benign_fpr"]["k"], pub["benign_fpr"]["k"]],
        "union2_p99_recall": [out["arms"]["original_transductive"]["p99"]["union2_B13_or_anomaly"]["recall"]["k"],
                              orig["union_defense"]["union2_B13_or_anomaly"]["recall"]["k"]],
        "union2_p99_fpr": [out["arms"]["original_transductive"]["p99"]["union2_B13_or_anomaly"]["benign_fpr"]["k"],
                           orig["union_defense"]["union2_B13_or_anomaly"]["benign_fpr_eval_half"]["k"]]}
    out["reproduction_ok"] = all(a == b for a, b in out["reproduces_published"].values())

    # DEV-FITTED (primary): clusters and threshold from development benign only; all 171 HO8 benign scored
    km_d, ob_devtr, n_devtr = _dev_fit()
    oa_d, ob_d = oc(atk, km_d.cluster_centers_), oc(b8, km_d.cluster_centers_)
    out["arms"]["dev_fitted"] = {
        "description": f"KMeans and threshold fitted on {n_devtr} development benign texts (union_defense_dev split); "
                       "applied unchanged to all HO8 attacks and all 171 HO8 benign notes",
        "p90": _arm(oa_d, ob_d, float(np.percentile(ob_devtr, 90)), b13a, b13b, sem_a, sem_b, fam),
        "p99": _arm(oa_d, ob_d, float(np.percentile(ob_devtr, 99)), b13a, b13b, sem_a, sem_b, fam)}

    # OWNER-ADAPTIVE, LEAK-FREE: fit AND threshold on benign[0::2]; evaluate on benign[1::2]
    ob_fit_o = oc(fit, km_o.cluster_centers_)
    out["arms"]["owner_adaptive_leakfree"] = {
        "description": "KMeans AND threshold fitted on HO8 benign[0::2]; FPR on benign[1::2], unseen by both",
        "p90": _arm(oa_o, ob_eval_o, float(np.percentile(ob_fit_o, 90)), b13a, b13b[ev_idx], sem_a, sem_b[ev_idx], fam),
        "p99": _arm(oa_o, ob_eval_o, float(np.percentile(ob_fit_o, 99)), b13a, b13b[ev_idx], sem_a, sem_b[ev_idx], fam)}
    # SHIPPED: the committed centroids + threshold the live phase6 signal loads
    # (phase6/defense/sleeper/activation_anomaly_centroids.json, fitted on ALL development benign by
    # build_sleeper_anomaly_centroids.py). This is what evaluate_sleeper_admission_augmented would do.
    shipped = json.loads((DATA.parents[1] / "phase6" / "defense" / "sleeper" / "activation_anomaly_centroids.json")
                         .read_text(encoding="utf-8"))
    C = np.asarray(shipped["centroids"], dtype=float)
    oa_s, ob_s = oc(atk, C), oc(b8, C)
    out["arms"]["shipped_committed_centroids"] = {
        "description": "the committed live signal (activation_anomaly_centroids.json, dev-fitted); all 171 HO8 benign",
        "p90": _arm(oa_s, ob_s, float(shipped["threshold"]), b13a, b13b, sem_a, sem_b, fam)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    print("reproduction ok:", r["reproduction_ok"], r["reproduces_published"])
    for arm, v in r["arms"].items():
        for p in [q for q in ("p90", "p99") if q in v]:
            a = v[p]
            print(f"{arm:26s} {p}: anomaly {a['anomaly']['recall']['k']}/160 fpr {a['anomaly']['benign_fpr']['k']}/"
                  f"{a['anomaly']['benign_fpr']['n']} | union2 {a['union2_B13_or_anomaly']['recall']['k']} "
                  f"fpr {a['union2_B13_or_anomaly']['benign_fpr']['k']}/{a['union2_B13_or_anomaly']['benign_fpr']['n']}"
                  f" | B13 {a['B13_alone']['recall']['k']} fpr {a['B13_alone']['benign_fpr']['k']}"
                  f" | p(u2 vs B13) {a['union2_vs_B13_paired']['p_exact']:.2g}")
