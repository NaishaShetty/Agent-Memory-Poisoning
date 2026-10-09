"""The generalized defense, measured on DEVELOPMENT data: the UNION of the specialized detectors vs a
learned attack-type ROUTER. Design fixed 2026-10-09 before the run.

Each specialized defense is strong on its own attack type and weak elsewhere: provenance/corroboration
(B13) on planted-claim / standing-instruction poisoning, the embedding cluster-outlier anomaly on
engineered/planted memory (incl. dormant sleepers). The honest generalized defense is to run them all
and take the UNION -- no attack-type classification, no added failure mode. A ROUTER (predict the
attack type, apply only that type's detector) can only help if it reaches the union's recall at a
materially lower false-positive rate. This measures both.

Dev set: own attacks (with family) + ordinary benign (epistemic_quarantine._dev_sets), with B13's
per-item decision. Anomaly = cluster-outlier distance to benign KMeans centroids (the attack's own
off-cluster objective), fit on a train split, thresholded to a 10% benign FPR. The router is a
logistic-regression group classifier on the text embedding, trained on the train split only; it is
reported with its own confusion so misrouting is visible. 50/50 split by a fixed seed.

Pre-registered: U-1 the union's attack recall exceeds either detector alone. U-2 the router matches the
union's recall within 3 points AND at a lower benign FPR (only then does routing earn its place);
otherwise the honest conclusion is 'run the union'. Reported whichever way they go.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

DATA = Path(__file__).parent / "data"
OUT = DATA / "union_defense_dev.json"
SLEEPER = {"sleeper_memory_poisoning", "conditional_backdoor", "Sleeper", "write_directive"}
PROPAGATION = {"memory_worm", "minja", "propagated", "MemoryGraft-style-volume"}


def _group(family: str) -> str:
    if family in SLEEPER:
        return "sleeper"
    if family in PROPAGATION:
        return "propagation"
    return "provenance"


def run() -> dict:
    from sklearn.cluster import KMeans
    from sklearn.linear_model import LogisticRegression

    from phase17.epistemic_quarantine import _dev_sets, _excluded
    from phase17.query_trigger_signal import benign_cluster_outlier_scores
    from phase17.semantic_detector import _embed
    from phase17.stats import rate_with_ci

    recs, ca, btexts, cb, _ = _dev_sets()
    atk_text = [r.text for r in recs]
    atk_group = [_group(getattr(r, "family", "provenance")) for r in recs]
    b13_atk = np.array([_excluded(c) for c in ca])
    b13_ben = np.array([_excluded(c) for c in cb])

    rng = np.random.RandomState(17)
    atk_tr = rng.rand(len(recs)) < 0.5
    ben_tr = rng.rand(len(btexts)) < 0.5

    EA, EB = _embed(atk_text), _embed(btexts)
    # anomaly: fit clusters + threshold on TRAIN benign only
    km = KMeans(n_clusters=8, n_init=10, random_state=17).fit(EB[ben_tr])
    oa = benign_cluster_outlier_scores(atk_text, km.cluster_centers_)
    ob = benign_cluster_outlier_scores(btexts, km.cluster_centers_)
    othr = float(np.percentile(ob[ben_tr], 90))
    anom_atk, anom_ben = oa >= othr, ob >= othr

    # router: LR on embeddings, 4 classes (3 attack groups + benign), TRAIN split only
    Xtr = np.vstack([EA[atk_tr], EB[ben_tr]])
    ytr = [g for g, t in zip(atk_group, atk_tr) if t] + ["benign"] * int(ben_tr.sum())
    clf = LogisticRegression(max_iter=1000, C=1.0).fit(Xtr, ytr)
    pred_atk = clf.predict(EA)
    pred_ben = clf.predict(EB)

    def detector_fires(group, b13, anom):
        if group == "provenance":
            return b13
        if group in ("sleeper", "propagation"):
            return anom
        return False                       # predicted benign -> allow

    te_a, te_b = ~atk_tr, ~ben_tr
    na, nb = int(te_a.sum()), int(te_b.sum())

    def rates(flag_a, flag_b):
        return {"recall": rate_with_ci(int(flag_a[te_a].sum()), na),
                "fpr": rate_with_ci(int(flag_b[te_b].sum()), nb)}

    out = {"n_attacks_test": na, "n_benign_test": nb, "anomaly_threshold": round(othr, 4),
           "groups": {"sleeper": sorted(SLEEPER), "propagation": sorted(PROPAGATION), "provenance": "rest"},
           "detectors": {
               "B13_provenance": rates(b13_atk, b13_ben),
               "anomaly_cluster_outlier": rates(anom_atk, anom_ben),
               "union_B13_or_anomaly": rates(b13_atk | anom_atk, b13_ben | anom_ben)}}

    router_a = np.array([detector_fires(pred_atk[i], b13_atk[i], anom_atk[i]) for i in range(len(recs))])
    router_b = np.array([detector_fires(pred_ben[i], b13_ben[i], anom_ben[i]) for i in range(len(btexts))])
    out["detectors"]["router"] = rates(router_a, router_b)
    # router classification quality on the test split
    out["router_group_accuracy_test"] = round(float(np.mean(pred_atk[te_a] == np.array(atk_group)[te_a])), 3)
    out["router_benign_correct_test"] = round(float(np.mean(pred_ben[te_b] == "benign")), 3)

    # per-group recall (test), union vs router
    out["by_group_recall_test"] = {}
    ag = np.array(atk_group)
    for g in ("provenance", "sleeper", "propagation"):
        m = te_a & (ag == g)
        if m.sum():
            out["by_group_recall_test"][g] = {
                "n": int(m.sum()),
                "B13": rate_with_ci(int(b13_atk[m].sum()), int(m.sum())),
                "anomaly": rate_with_ci(int(anom_atk[m].sum()), int(m.sum())),
                "union": rate_with_ci(int((b13_atk | anom_atk)[m].sum()), int(m.sum())),
                "router": rate_with_ci(int(router_a[m].sum()), int(m.sum()))}

    # ---- FPR reduction + propagation lift: a supervised detector as a 3rd member, and a threshold sweep.
    from phase17.semantic_detector import EmbeddingDetector

    det = EmbeddingDetector(c=1.0)
    det.fit([atk_text[i] for i in np.where(atk_tr)[0]], [btexts[i] for i in np.where(ben_tr)[0]])
    sem_a = np.array(det.flags(atk_text))
    sem_b = np.array(det.flags(btexts))
    out["detectors"]["semantic_supervised"] = rates(sem_a, sem_b)
    out["detectors"]["union3_B13_anomaly_semantic"] = rates(b13_atk | anom_atk | sem_a,
                                                            b13_ben | anom_ben | sem_b)

    # Sweep the anomaly percentile to trade FPR against recall; report per-group (propagation focus).
    ag = np.array(atk_group)
    sweep = []
    for pct in (90, 95, 97.5, 99):
        thr = float(np.percentile(ob[ben_tr], pct))
        aa, ab = oa >= thr, ob >= thr
        ua, ub = b13_atk | aa, b13_ben | ab           # union2 at this anomaly FPR
        u3a, u3b = ua | sem_a, ub | sem_b             # union3 adds the supervised detector
        row = {"anomaly_pct": pct,
               "union2": {"recall": rate_with_ci(int(ua[te_a].sum()), na), "fpr": rate_with_ci(int(ub[te_b].sum()), nb),
                          "propagation_recall": rate_with_ci(int(ua[te_a & (ag == "propagation")].sum()),
                                                             int((te_a & (ag == "propagation")).sum()))},
               "union3": {"recall": rate_with_ci(int(u3a[te_a].sum()), na), "fpr": rate_with_ci(int(u3b[te_b].sum()), nb),
                          "propagation_recall": rate_with_ci(int(u3a[te_a & (ag == "propagation")].sum()),
                                                             int((te_a & (ag == "propagation")).sum()))}}
        sweep.append(row)
    out["sweep"] = sweep

    u = out["detectors"]["union_B13_or_anomaly"]
    r = out["detectors"]["router"]
    b = out["detectors"]["B13_provenance"]
    a = out["detectors"]["anomaly_cluster_outlier"]
    out["U-1_union_beats_singles"] = u["recall"]["rate"] > max(b["recall"]["rate"], a["recall"]["rate"])
    out["U-2_router_earns_place"] = (r["recall"]["rate"] >= u["recall"]["rate"] - 0.03
                                     and r["fpr"]["rate"] < u["fpr"]["rate"])
    out["verdict"] = ("the router earns its place (union recall at lower FPR)"
                      if out["U-2_router_earns_place"] else
                      "the union is the generalized defense; the router does not beat it -- run the union")
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    for n, v in r["detectors"].items():
        print(f"  {n:26s} recall {v['recall']['k']}/{r['n_attacks_test']} ({v['recall']['rate']:.0%})  "
              f"FPR {v['fpr']['rate']:.1%}")
    print(f"router group acc {r['router_group_accuracy_test']}, benign-correct {r['router_benign_correct_test']}")
    print("U-1", r["U-1_union_beats_singles"], "| U-2", r["U-2_router_earns_place"])
    print(r["verdict"])
