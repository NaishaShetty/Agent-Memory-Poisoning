"""Fit B15's content threshold — DEV DATA ONLY (round 6).

Same training population as B14 (`train_b14.training_data`): the designated dev pool,
external-DEV, and AgentDojo's dev benign half. Two features only (deberta prompt-injection
probability, GPT-2 perplexity), both local, so this runs in seconds with no model swapping.

Thresholds from GROUP-held-out out-of-fold scores at 0.5% and 2% FPR on dev negatives, the
protocol B12 and B14 both used.

ALSO FIXED HERE: the false-positive cost that tripped B13's own pre-registered failure
condition. B13 excluded 17/1515 (1.1%) of LoCoMo's own benign derived memories because their
supporting turn was not among the 5 most similar retrieved, so a genuinely grounded memory
looked unsupported. B14 "fixed" that by requiring a second signal before excluding, which cost
17 points of evasion recall (28/47 -> 11/47) — treating the symptom. `tune_support_retrieval()`
measures the actual cause: how many of those 17 are retrieval misses that a wider search
finds. The widened setting is applied in `b13_live.support_scores` for every config that uses
it, so the fix helps B13 and B15 alike rather than being bolted onto one.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import numpy as np

from phase17.judge_scores import recall_at_fpr

MODEL_PATH = Path(__file__).parent / "data" / "b15_model.json"
REPORT = Path(__file__).parent / "data" / "b15_training_report.json"
SUPPORT_REPORT = Path(__file__).parent / "data" / "b15_support_retrieval.json"
C = 1.0


def fit(fprs=(0.005, 0.02)) -> dict:
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GroupKFold

    from phase17.b15_live import FEATURES, content_features
    from phase17.train_b14 import training_data

    texts, y, groups = training_data()
    print(f"training on {len(texts)} dev items ({sum(y)} attacks), {len(set(groups))} groups", flush=True)
    X, y, g = content_features(texts), np.asarray(y), np.asarray(groups)
    oof = np.zeros(len(y))
    for tr, te in GroupKFold(8).split(X, y, g):
        oof[te] = LogisticRegression(C=C, max_iter=5000, class_weight="balanced").fit(
            X[tr], y[tr]).predict_proba(X[te])[:, 1]
    p, n = list(oof[y == 1]), list(oof[y == 0])
    thr = {f: recall_at_fpr(p, n, f)["threshold"] for f in fprs}
    oof_recall = {f: recall_at_fpr(p, n, f)["recall"] for f in fprs}
    clf = LogisticRegression(C=C, max_iter=5000, class_weight="balanced").fit(X, y)
    model = {"features": list(FEATURES), "coef": clf.coef_[0].tolist(),
             "intercept": float(clf.intercept_[0]), "thr": {str(k): v for k, v in thr.items()},
             "oof_recall": {str(k): v for k, v in oof_recall.items()}, "c": C, "n_train": len(y)}
    MODEL_PATH.write_text(json.dumps(model, indent=1), encoding="utf-8")
    report = {"model": model, "coefficients": dict(zip(FEATURES, clf.coef_[0].round(4).tolist())),
              "oof_recall_at_fpr": {str(k): v for k, v in oof_recall.items()}}
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def tune_support_retrieval(top_ks=(5, 10, 20, 40)) -> dict:
    """DEV ONLY. Is B13's 1.1% benign-exclusion cost a retrieval miss rather than a real
    disagreement? For LoCoMo's own benign observation memories (which ARE grounded in the
    conversation by construction) and the dev fabrications (which are not), measure how
    support changes as the evidence search widens."""
    from phase17 import b13_live
    from phase17.provenance_sets import DEV_SAMPLES, fabrications, observations, owner_turns

    fabs = [f for f in fabrications("dev")]
    out: Dict[str, dict] = {}
    for k in top_ks:
        orig = b13_live.SUPPORT_TOP_K if hasattr(b13_live, "SUPPORT_TOP_K") else 5
        b13_live.SUPPORT_TOP_K = k
        obs_unsupported = obs_n = fab_unsupported = fab_n = 0
        for s in DEV_SAMPLES:
            ev = [t["text"] for t in owner_turns(s)]
            obs = [o["text"] for o in observations(s)]
            sc = b13_live.support_scores(obs, ev)
            obs_unsupported += int((sc < b13_live.SUPPORT_EXCLUDE).sum())
            obs_n += len(obs)
            ft = [f["text"] for f in fabs if f["sample"] == s]
            if ft:
                sf = b13_live.support_scores(ft, ev)
                fab_unsupported += int((sf < b13_live.SUPPORT_EXCLUDE).sum())
                fab_n += len(ft)
        out[f"top_k={k}"] = {"benign_observations_judged_unsupported": f"{obs_unsupported}/{obs_n}",
                            "benign_rate": round(obs_unsupported / max(obs_n, 1), 4),
                            "fabrications_judged_unsupported": f"{fab_unsupported}/{fab_n}",
                            "attack_rate": round(fab_unsupported / max(fab_n, 1), 4)}
        print(f"  top_k={k}: benign unsupported {obs_unsupported}/{obs_n}, "
              f"fabrications unsupported {fab_unsupported}/{fab_n}", flush=True)
        b13_live.SUPPORT_TOP_K = orig
    SUPPORT_REPORT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    import sys

    if "--support" in sys.argv:
        print(json.dumps(tune_support_retrieval(), indent=1))
    else:
        r = fit()
        print(json.dumps(r["coefficients"], indent=1))
        print("OOF recall at FPR:", r["oof_recall_at_fpr"])
    print("DONE")
