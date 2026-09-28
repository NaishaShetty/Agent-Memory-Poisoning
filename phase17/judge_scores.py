"""Phase 17 fix round 3 -- CONTINUOUS judge scores (P(YES) logit from token
logprobs) instead of one binary answer, plus a retrieval-augmented few-shot
variant whose demonstrations come ONLY from the DEV set.

Why (root cause of the exclusion tradeoff): a binary YES/NO cuts the judge's
belief at one arbitrary point per prompt, so the recall/FPR tradeoff could only
be chosen between two prompts. A continuous score lets the operating point be
set by threshold on DEV (0.x% FPR) and lets prompts be ensembled.
Scores are cached on disk by (variant, text) so runs are reproducible.
"""

from __future__ import annotations

import hashlib
import json
import math
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np

from phase17.semantic_detector import PROMPTS

CACHE = Path(__file__).parent / "data" / "judge_score_cache.json"
URL = "http://127.0.0.1:11434/api/chat"
MODEL = "qwen2.5:7b"


def _key(variant: str, text: str, salt: str = "", model: str = MODEL) -> str:
    # `model` defaults to the module constant (used everywhere in this file today), but is
    # now an explicit parameter -- see semantic_detector.py::_h's matching fix -- so a
    # future caller using a different model cannot silently collide with this one's cache.
    return hashlib.sha256(f"{model}\x00{variant}\x00{salt}\x00{text}".encode("utf-8")).hexdigest()[:24]


def _key_old(variant: str, text: str, salt: str = "") -> str:
    """The PRE-fix key (no `model` field at all -- MODEL was a constant so it was never
    part of the hash). Kept only so `ScoreJudge.score` can migrate an old entry forward on
    first lookup instead of re-querying the LLM (see `semantic_detector.py::_h_old` for the
    matching fix and why this exists -- external review round 2, 2026-09-28)."""
    return hashlib.sha256(f"{variant}\x00{salt}\x00{text}".encode("utf-8")).hexdigest()[:24]


def _logit_yes(prompt: str, seed: int = 17) -> float:
    body = json.dumps({"model": MODEL, "messages": [{"role": "user", "content": prompt}], "stream": False,
                       "logprobs": True, "top_logprobs": 10,
                       "options": {"temperature": 0.0, "seed": seed, "num_predict": 1, "num_ctx": 4096}}).encode()
    r = json.loads(urllib.request.urlopen(urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"}),
                                          timeout=180).read())
    tops = r["logprobs"][0]["top_logprobs"]
    yes = [t["logprob"] for t in tops if t["token"].strip().upper() == "YES"]
    no = [t["logprob"] for t in tops if t["token"].strip().upper() == "NO"]
    ly = max(yes) if yes else -20.0
    ln = max(no) if no else -20.0
    return float(ly - ln)


class ScoreJudge:
    def __init__(self, variant: str = "concept", demos: Optional[Sequence[dict]] = None, k: int = 6, salt: str = ""):
        self.variant, self.k, self._salt = variant, k, salt
        self.demos = list(demos) if demos else None  # dev items: {"text":..., "label":0/1}
        self._cache: Dict[str, float] = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
        self._dirty = 0
        if self.demos:
            from phase17.semantic_detector import _embed

            self._demo_vec = _embed([d["text"] for d in self.demos])

    def _prompt(self, text: str, group: Optional[str] = None) -> str:
        base = PROMPTS[self.variant].format(text=text[:1500])
        if not self.demos:
            return base
        from phase17.semantic_detector import _embed

        sims = self._demo_vec @ _embed([text])[0]
        idx = [i for i in np.argsort(-sims) if self.demos[i]["text"] != text
               and (group is None or self.demos[i].get("group") != group)]  # leave-mechanism-out when group given
        pos = [self.demos[i] for i in idx if self.demos[i]["label"] == 1][: self.k // 2]
        neg = [self.demos[i] for i in idx if self.demos[i]["label"] == 0][: self.k // 2]
        shots = sorted(pos + neg, key=lambda d: hash(d["text"]) % 97)
        ex = "\n".join(f'Note: "{d["text"][:300]}" -> {"YES" if d["label"] else "NO"}' for d in shots)
        return "Labeled examples of the same decision:\n" + ex + "\n\nNow the note to decide.\n" + base

    def score(self, text: str, group: Optional[str] = None) -> float:
        variant_key = self.variant + ("+fs%d" % self.k if self.demos else "")
        salt = ("lomo:" + group) if group else self._salt
        key = _key(variant_key, text, salt=salt)
        if key not in self._cache:
            old_key = _key_old(variant_key, text, salt=salt)
            if old_key in self._cache:
                self._cache[key] = self._cache[old_key]  # migrate forward, no re-query needed
                self._dirty += 1
                return self._cache[key]
            self._cache[key] = _logit_yes(self._prompt(text, group))
            self._dirty += 1
            if self._dirty % 100 == 0:
                self.save()
        return self._cache[key]

    def save(self) -> None:
        # merge with what other processes wrote (concurrent runs once clobbered this cache)
        disk = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
        disk.update(self._cache)
        CACHE.write_text(json.dumps(disk), encoding="utf-8")


def roc_auc(pos: Sequence[float], neg: Sequence[float]) -> float:
    from scipy.stats import mannwhitneyu

    u = mannwhitneyu(pos, neg, alternative="greater").statistic
    return float(u / (len(pos) * len(neg)))


def recall_at_fpr(pos: Sequence[float], neg: Sequence[float], fpr: float) -> Dict[str, float]:
    """Threshold = smallest value with dev FPR <= fpr; returns threshold + recall."""
    ns = sorted(neg, reverse=True)
    k = int(math.floor(fpr * len(ns)))
    thr = ns[k] + 1e-9 if k < len(ns) else min(ns)
    return {"threshold": thr, "recall": float(np.mean([p >= thr for p in pos]))}


__all__ = ["ScoreJudge", "roc_auc", "recall_at_fpr"]
