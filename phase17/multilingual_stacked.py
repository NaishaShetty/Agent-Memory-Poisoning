"""Phase 17 fix round 6 -- Chinese generalization via a MULTILINGUAL embedding backbone,
instead of the translate-then-score detour (`translate_route.py`). Confirmed directly
(not assumed): `paraphrase-multilingual-MiniLM-L12-v2` gives 0.86 mean cosine similarity
between 20 real English poison parents and their real Chinese translations -- the same
embedding space genuinely aligns the two languages, so a detector trained ONLY on English
dev data can be scored directly on Chinese text with no translation step at all.

This is an ADDITIVE alternative to `StackedDetector` (English-only `bge-small-en-v1.5`),
never a replacement -- `phase17.stacked_detector.StackedDetector` and `B12`'s own live
path are untouched. Trained on the SAME English dev pool `tune_lomo.py` already uses (no
Chinese text in training at all -- a genuine zero-shot cross-lingual test), evaluated on
`held_out_zh` directly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Sequence

import numpy as np

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
_MODEL = None


def _ml_embed(texts: Sequence[str]) -> np.ndarray:
    from sentence_transformers import SentenceTransformer

    global _MODEL
    if _MODEL is None:
        _MODEL = SentenceTransformer(MODEL_NAME)
    return np.asarray(_MODEL.encode(list(texts), normalize_embeddings=True, batch_size=64))


class MultilingualDetector:
    """Same shape as `StackedDetector` (embedding + judge-logit stack), but with the
    multilingual embedding backbone, so it can be scored on non-English text directly."""

    def __init__(self, c: float = 10.0):
        self.c = c
        from phase17.judge_scores import ScoreJudge

        self.judge = ScoreJudge("concept")

    def _features(self, texts: Sequence[str]) -> np.ndarray:
        z = np.array([self.judge.score(t) for t in texts])[:, None] / 10.0
        return np.hstack([_ml_embed(texts), z])

    def fit(self, texts: Sequence[str], y: Sequence[int], groups: Sequence[str], fprs=(0.005, 0.02)) -> dict:
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import GroupKFold

        from phase17.judge_scores import recall_at_fpr

        X, y, g = self._features(texts), np.array(y), np.array(groups)
        oof = np.zeros(len(y))
        for tr, te in GroupKFold(8).split(X, y, g):
            oof[te] = LogisticRegression(C=self.c, max_iter=3000, class_weight="balanced").fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
        p, n = list(oof[y == 1]), list(oof[y == 0])
        self.thr = {f: recall_at_fpr(p, n, f)["threshold"] for f in fprs}
        self.oof_recall = {f: recall_at_fpr(p, n, f)["recall"] for f in fprs}
        self.clf = LogisticRegression(C=self.c, max_iter=3000, class_weight="balanced").fit(X, y)
        self.judge.save()
        return {"thr": self.thr, "oof_recall": self.oof_recall}

    def decide(self, texts: Sequence[str], fpr: float) -> List[bool]:
        X = self._features(texts)
        s = self.clf.predict_proba(X)[:, 1]
        self.judge.save()
        return [bool(si >= self.thr[fpr]) for si in s]


if __name__ == "__main__":
    from phase17.stats import rate_with_ci
    from phase17.tune_lomo import dev_pool
    from phase17.translation import zh_records
    from phase17.arenas import dataset_arena
    from phase17.extra_datasets import convomem_pools
    from phase17.perltqa import perltqa_pools

    pos, neg = dev_pool()  # ENGLISH-only dev pool -- no Chinese text anywhere in training
    det = MultilingualDetector()
    fit = det.fit([x["text"] for x in pos + neg], [x["label"] for x in pos + neg], [x["group"] for x in pos + neg])
    print("fit:", fit)

    zh = zh_records()
    tx = [r.text for r in zh]
    excl, flag = det.decide(tx, 0.005), det.decide(tx, 0.02)
    result = {"n_zh": len(zh), "excluded": rate_with_ci(sum(excl), len(zh)), "flagged": rate_with_ci(sum(flag), len(zh))}

    te = sorted(perltqa_pools()[0], key=lambda p: p.pool_id)[1::2]
    bt = [m.content_text for p in te for m in p.memories]
    excl_b, flag_b = det.decide(bt, 0.005), det.decide(bt, 0.02)
    result["perltqa_benign"] = {"n": len(bt), "excluded": rate_with_ci(sum(excl_b), len(bt)), "flagged": rate_with_ci(sum(flag_b), len(bt))}

    print(json.dumps(result, indent=1))
    Path(__file__).parent.joinpath("data", "multilingual_stacked_results.json").write_text(json.dumps(result, indent=2))
    print("DONE")
