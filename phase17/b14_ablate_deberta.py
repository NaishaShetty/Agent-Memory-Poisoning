"""Can B14's inherited instability be fixed by refitting it without deberta? (closing item #3)

THE FINDING THIS ADDRESSES. B14's 36.6-point gap between the two first hold-outs was shown to
be substantially INHERITED: on the external corpora its decisions agree with
`deberta_pi_v2@dev` 90.1% of the time, per item it catches what deberta scores near 1.0 and
misses what it scores near 0, and it degrades worse across corpora than the component it tracks
(deberta loses 18 points where B14 loses 37). That was reported as a diagnosis and listed as
"not fixable", on the grounds that it describes what the fusion learned rather than a defect
with a repair.

That was too quick. A diagnosis that names one feature as the source of the instability implies
an experiment: refit the fusion WITHOUT that feature, on the same development data, with
everything else unchanged, and measure whether cross-corpus stability improves.

THREE OUTCOMES, and what each would mean, fixed before running:

  * the gap NARROWS and own-attack recall holds -> the instability was deberta-borne and
    removable, so the fusion should ship without it and the "not fixable" label was wrong;
  * the gap narrows but recall COLLAPSES -> deberta was carrying most of B14's external
    performance, the fusion is a thin wrapper around it, and the honest conclusion is that B14
    adds little over a single off-the-shelf pass on that distribution;
  * the gap PERSISTS -> the instability is a property of the fused weights rather than of that
    one feature, and the original "inherited" framing was itself imprecise.

Any of the three is a better result than the diagnosis alone, which is why this is worth the
compute.

DISCIPLINE. The refit uses `train_b14`'s own training data and procedure, with the feature list
as the only change, so the comparison is a true ablation. Scores are then read on the already
frozen corpora using cached features -- no new model calls -- and the two hold-outs are used
exactly as they were for B14 itself, which means this inherits B14's hold-out status and adds
no new exposure.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import numpy as np

OUT = Path(__file__).parent / "data" / "b14_ablate_deberta.json"
DROP = "deberta_pi"


def _fit(feature_names, texts, y, groups):
    """`train_b14`'s procedure with a restricted feature list."""
    from sklearn.linear_model import LogisticRegression

    from phase17.fusion_features import FEATURES, build

    X_full = build(list(texts))
    keep = [i for i, f in enumerate(FEATURES) if f in feature_names]
    X = np.asarray(X_full)[:, keep]
    clf = LogisticRegression(C=1.0, max_iter=3000, class_weight="balanced").fit(X, np.asarray(y))
    return clf, keep


def _scores(clf, keep, texts) -> np.ndarray:
    from phase17.fusion_features import build

    X = np.asarray(build(list(texts)))[:, keep]
    return clf.predict_proba(X)[:, 1]


def _thr_at(dev_neg: np.ndarray, fpr: float) -> float:
    s = np.sort(dev_neg)[::-1]
    k = int(np.floor(fpr * len(s)))
    return float(s[0]) + 1e-9 if k <= 0 else float(s[k - 1])


def run() -> dict:
    from phase17.eval_populations import benign_populations
    from phase17.eval_round6 import _attack_pops
    from phase17.external_test_corpus import test_attack_records
    from phase17.fusion_features import FEATURES
    from phase17.holdout2_corpus import records as mosscap_records
    from phase17.stats import rate_with_ci
    from phase17.train_b14 import training_data

    texts, y, groups = training_data()
    print(f"refitting on {len(texts)} training texts; ablating {DROP}", flush=True)

    variants = {"full_11_features": list(FEATURES),
                f"without_{DROP}": [f for f in FEATURES if f != DROP]}
    own = {k: [r.text for r in v] for k, v in _attack_pops().items() if k.startswith("own_")}
    h1 = [r.text for r in test_attack_records()]
    h2 = [r.text for r in mosscap_records()]
    ordinary = [t for p, v in benign_populations().items() for t in v
                if any(s in p for s in ("dataset_arena", "convomem", "perltqa"))]

    out = {"ablated_feature": DROP, "n_train": len(texts),
           "note": "train_b14's own data and procedure; the feature list is the only change. "
                   "Scores are read on the already frozen corpora from cached features, so no "
                   "new model calls and no new hold-out exposure.",
           "variants": {}}
    for name, feats in variants.items():
        clf, keep = _fit(feats, texts, y, groups)
        dev_neg = _scores(clf, keep, ordinary)
        thr = _thr_at(dev_neg, 0.005)
        own_all = [t for v in own.values() for t in v]
        e = {"n_features": len(feats),
             "coefficients": dict(zip(feats, clf.coef_[0].round(4).tolist())),
             "threshold_at_0.5pct_dev_fpr": thr,
             "own_attacks": rate_with_ci(int((_scores(clf, keep, own_all) >= thr).sum()), len(own_all)),
             "holdout1_external_test": rate_with_ci(int((_scores(clf, keep, h1) >= thr).sum()), len(h1)),
             "holdout2_mosscap": rate_with_ci(int((_scores(clf, keep, h2) >= thr).sum()), len(h2)),
             "ordinary_benign_fpr": rate_with_ci(int((dev_neg >= thr).sum()), len(dev_neg))}
        e["holdout_gap_points"] = round(
            100 * (e["holdout1_external_test"]["rate"] - e["holdout2_mosscap"]["rate"]), 1)
        out["variants"][name] = e
        print(f"  {name:22s} own {e['own_attacks']['rate']:.1%}  h1 "
              f"{e['holdout1_external_test']['rate']:.1%}  h2 "
              f"{e['holdout2_mosscap']['rate']:.1%}  gap {e['holdout_gap_points']:+.1f}  "
              f"benign {e['ordinary_benign_fpr']['k']}/{e['ordinary_benign_fpr']['n']}", flush=True)

    a, b = out["variants"]["full_11_features"], out["variants"][f"without_{DROP}"]
    gap_change = b["holdout_gap_points"] - a["holdout_gap_points"]
    own_change = 100 * (b["own_attacks"]["rate"] - a["own_attacks"]["rate"])
    h1_change = 100 * (b["holdout1_external_test"]["rate"] - a["holdout1_external_test"]["rate"])
    out["comparison"] = {"gap_change_points": round(gap_change, 1),
                         "own_attack_change_points": round(own_change, 1),
                         "holdout1_change_points": round(h1_change, 1)}
    out["verdict"] = (
        f"REMOVABLE: dropping {DROP} narrows the hold-out gap by {-gap_change:.1f} points "
        f"({a['holdout_gap_points']:+.1f} to {b['holdout_gap_points']:+.1f}) while own-attack "
        f"recall changes {own_change:+.1f}. The instability was deberta-borne and the "
        f"'not fixable' label was wrong."
        if gap_change <= -5 and own_change >= -5 else
        f"THIN WRAPPER: dropping {DROP} costs {-h1_change:.1f} points on hold-out 1, so that "
        f"feature was carrying most of the fusion's external performance and B14 adds little "
        f"over a single off-the-shelf pass on that distribution."
        if h1_change <= -10 else
        f"NOT THE FEATURE: the gap moves only {gap_change:+.1f} points, so the instability is a "
        f"property of the fused weights rather than of {DROP} alone, and the 'inherited' framing "
        f"was imprecise.")
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    print(f"\ncomparison: {r['comparison']}")
    print(f"\nVERDICT: {r['verdict']}")
    print("DONE")
