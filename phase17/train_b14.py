"""Fit B14's fusion model — DEV DATA ONLY (external review round 5).

Training data, and why each part is legitimately dev:
  * `tune_lomo.dev_pool()` positives and negatives — the designated dev pool every B12
    threshold was already set on.
  * the 266 attacks in `external_attacks.py` — **external-DEV**. Round 4 measured B12/B13 on
    these and published per-source results, so they can never serve as held-out data again;
    using them for training is the honest consequence of that, not a new concession.
  * `agentdojo_benign_tool_outputs.json` dev half — benign text arriving through an
    untrusted channel, so the model does not learn "not a user turn ⇒ attack".

**Never touched here:** `external_test_corpus.py` (frozen, SHA-256 recorded before this file
existed), and this project's own held-out attack populations (novel_60, novel_new120,
gemini_30, evasion_47, zh_native_30, trackb), which stay evaluation-only so their published
numbers keep meaning.

Thresholds come from GROUP-held-out out-of-fold scores, grouped by attack mechanism /
external source, at 0.5% and 2% FPR on dev negatives — the same protocol B12 used.
`loso()` additionally reports leave-one-source-out: refit with one external source removed
entirely, then score only that source, which is the honest estimate for a source the model
never saw.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np

from phase17.judge_scores import recall_at_fpr

MODEL_PATH = Path(__file__).parent / "data" / "b14_model.json"
REPORT = Path(__file__).parent / "data" / "b14_training_report.json"
C = 1.0


def training_data() -> Tuple[List[str], List[int], List[str]]:
    from phase17.b13_dev_calibration import agentdojo_benign
    from phase17.external_attacks import external_records
    from phase17.tune_lomo import dev_pool

    pos, neg = dev_pool()
    texts = [x["text"] for x in pos] + [x["text"] for x in neg]
    y = [1] * len(pos) + [0] * len(neg)
    groups = [x["group"] for x in pos] + [x["group"] for x in neg]
    for r in external_records():
        texts.append(r.text)
        y.append(1)
        groups.append(f"extdev:{r.family}")
    for t in agentdojo_benign("dev"):
        texts.append(t)
        y.append(0)
        groups.append("benign:agentdojo_dev")
    return texts, y, groups


def _fit(X, y, c=C):
    from sklearn.linear_model import LogisticRegression

    return LogisticRegression(C=c, max_iter=5000, class_weight="balanced").fit(X, y)


def fit(fprs=(0.005, 0.02)) -> dict:
    from sklearn.model_selection import GroupKFold

    from phase17.fusion_features import FEATURES, build

    texts, y, groups = training_data()
    print(f"training on {len(texts)} dev items ({sum(y)} attacks, {len(y)-sum(y)} benign), "
          f"{len(set(groups))} groups", flush=True)
    X = build(texts)
    y = np.asarray(y)
    g = np.asarray(groups)
    oof = np.zeros(len(y))
    for tr, te in GroupKFold(8).split(X, y, g):
        oof[te] = _fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
    p, n = list(oof[y == 1]), list(oof[y == 0])
    thr = {f: recall_at_fpr(p, n, f)["threshold"] for f in fprs}
    oof_recall = {f: recall_at_fpr(p, n, f)["recall"] for f in fprs}
    clf = _fit(X, y)
    model = {"features": list(FEATURES), "coef": clf.coef_[0].tolist(), "intercept": float(clf.intercept_[0]),
             "thr": {str(k): v for k, v in thr.items()}, "oof_recall": {str(k): v for k, v in oof_recall.items()},
             "c": C, "n_train": len(y), "n_pos": int(y.sum())}
    MODEL_PATH.write_text(json.dumps(model, indent=1), encoding="utf-8")
    report = {"model": model, "coefficients": dict(zip(FEATURES, clf.coef_[0].round(4).tolist())),
              "oof_recall_at_fpr": {str(k): v for k, v in oof_recall.items()}}
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def loso(fpr: float = 0.005) -> dict:
    """Leave-one-source-out over the external-dev sources: refit with that source entirely
    removed, threshold on the refit model's own dev negatives, then score only that source."""
    from sklearn.model_selection import GroupKFold

    from phase17.fusion_features import build

    texts, y, groups = training_data()
    X, y, g = build(texts), np.asarray(y), np.asarray(groups)
    sources = sorted({s for s in set(groups) if s.startswith("extdev:")})
    out = {}
    for src in sources:
        hold = g == src
        Xtr, ytr, gtr = X[~hold], y[~hold], g[~hold]
        oof = np.zeros(len(ytr))
        for tr, te in GroupKFold(8).split(Xtr, ytr, gtr):
            oof[te] = _fit(Xtr[tr], ytr[tr]).predict_proba(Xtr[te])[:, 1]
        t = recall_at_fpr(list(oof[ytr == 1]), list(oof[ytr == 0]), fpr)["threshold"]
        clf = _fit(Xtr, ytr)
        s = clf.predict_proba(X[hold])[:, 1]
        out[src] = {"n": int(hold.sum()), "caught": int((s >= t).sum()), "threshold": float(t)}
        print(f"  LOSO {src:28s} {out[src]['caught']}/{out[src]['n']}", flush=True)
    (Path(__file__).parent / "data" / "b14_loso.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    import sys

    r = fit()
    print(json.dumps(r["coefficients"], indent=1))
    print("OOF recall at FPR:", r["oof_recall_at_fpr"])
    if "--loso" in sys.argv:
        loso()
    print("DONE")
