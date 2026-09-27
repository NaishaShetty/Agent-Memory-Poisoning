"""Fix round 4 -- STACKED detector: logistic regression over [bge-small embedding, zero-shot
judge logit], trained on the enlarged diverse dev pool (37 attack groups, hard negatives, real
even-pool benign) with thresholds set from GROUP-held-out out-of-fold scores (leave-mechanism-out,
leave-benign-pool-out) at 0.5% (exclude) and 2% (flag) FPR. Script routing: the embedding model is
English-only, so text that is mostly CJK falls back to the judge logit alone with its own dev threshold.
Why stacking: the judge knows WHAT an attack does but only 40% of unseen mechanisms clear its
threshold; the embedding carries topical/lexical cues the judge misses; each alone fails, together
they reach ~60% recall at 0.5% FPR under leave-mechanism-out (`stacked_lomo.json`)."""

from __future__ import annotations

import re
from typing import Dict, List, Sequence

import numpy as np

from phase17.judge_scores import ScoreJudge, recall_at_fpr

_CJK = re.compile(r"[\u4e00-\u9fff]")


def is_cjk(t: str) -> bool:
    return len(_CJK.findall(t)) / max(len(t), 1) >= 0.3


class StackedDetector:
    def __init__(self, c: float = 10.0):
        self.c, self.judge = c, ScoreJudge("concept")

    def _features(self, texts: Sequence[str]) -> np.ndarray:
        from phase17.semantic_detector import _embed

        z = np.array([self.judge.score(t) for t in texts])[:, None] / 10.0
        return np.hstack([_embed(list(texts)), z])

    def fit(self, texts: Sequence[str], y: Sequence[int], groups: Sequence[str], fprs=(0.005, 0.02)) -> dict:
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import GroupKFold

        X, y, g = self._features(texts), np.array(y), np.array(groups)
        oof = np.zeros(len(y))
        for tr, te in GroupKFold(8).split(X, y, g):
            oof[te] = LogisticRegression(C=self.c, max_iter=3000, class_weight="balanced").fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
        p, n = list(oof[y == 1]), list(oof[y == 0])
        self.thr = {f: recall_at_fpr(p, n, f)["threshold"] for f in fprs}
        self.oof_recall = {f: recall_at_fpr(p, n, f)["recall"] for f in fprs}
        zj = X[:, -1] * 10.0   # judge-only fallback thresholds (CJK route), from the same dev negatives
        self.judge_thr = {f: recall_at_fpr(list(zj[y == 1]), list(zj[y == 0]), f)["threshold"] for f in fprs}
        self.clf = LogisticRegression(C=self.c, max_iter=3000, class_weight="balanced").fit(X, y)
        self.judge.save()
        return {"thr": self.thr, "oof_recall": self.oof_recall, "judge_thr": self.judge_thr}

    # -- persistence (the shipped model is a handful of numbers, no pickle) --------------------------
    def save(self, path) -> None:
        import json

        json.dump({"c": self.c, "coef": self.clf.coef_[0].tolist(), "intercept": float(self.clf.intercept_[0]),
                   "thr": {str(k): v for k, v in self.thr.items()}, "judge_thr": {str(k): v for k, v in self.judge_thr.items()},
                   "oof_recall": {str(k): v for k, v in self.oof_recall.items()}}, open(path, "w"), indent=1)

    @classmethod
    def load(cls, path):
        import json

        d = json.load(open(path))
        o = cls(d["c"])
        o.thr = {float(k): v for k, v in d["thr"].items()}
        o.judge_thr = {float(k): v for k, v in d["judge_thr"].items()}
        o.oof_recall = {float(k): v for k, v in d["oof_recall"].items()}
        o._w, o._b = np.array(d["coef"]), d["intercept"]
        o.clf = None
        return o

    def _proba(self, X: np.ndarray) -> np.ndarray:
        if self.clf is not None:
            return self.clf.predict_proba(X)[:, 1]
        return 1.0 / (1.0 + np.exp(-(X @ self._w + self._b)))

    def decide(self, texts: Sequence[str], fpr: float, route: str = "translate") -> List[bool]:
        """route="translate" (default): CJK text is translated to English first and scored by the same
        detector; route="judge_only": CJK text uses the judge logit alone (previous behaviour)."""
        if route == "translate":
            from phase17.translate_route import save as _save, to_english

            texts = [to_english(t) if is_cjk(t) else t for t in texts]
            _save()
        X = self._features(texts)
        s = self._proba(X)
        out = []
        for t, si, xi in zip(texts, s, X):
            out.append(bool(xi[-1] * 10.0 >= self.judge_thr[fpr]) if (route == 'judge_only' and is_cjk(t)) else bool(si >= self.thr[fpr]))
        self.judge.save()
        return out


__all__ = ["StackedDetector", "is_cjk"]
