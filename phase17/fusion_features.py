"""Per-memory content features for B14 (external review round 5).

DESIGN RATIONALE, from the round-5 diagnosis rather than from taste:

B12 is a logistic regression over [bge-small embedding (384 dims), zero-shot judge logit].
Decomposing its score by component on attacks it has and has not seen the style of:

    population                     embedding part    judge part
    own attacks (qwen + gemini)          +1.09          -1.22
    externally-authored attacks          -0.27          -1.51

The **embedding term carries almost the whole own-vs-external gap (1.36 logits); the judge
term differs by 0.29.** The component that reasons about what a note *does* transfers across
authorship; the component that encodes topical/lexical surface is what was tuned to this
project's house style. That is the mechanism behind the round-4 finding that B12's advantage
over published baselines is 2.80x on attacks we wrote and 1.03x on attacks we did not.

So B14 **drops the raw text embedding entirely** and fuses signals that each describe the
note's intent or effect, including three published detectors whose errors are measurably
complementary to B12's on external-dev:

    B12 ∪ plain-LLM prompt      125/266   (B12 alone 90, prompt alone 71)
    B12 ∪ all three baselines   147/266

Features (all per-text, all cached):
  0 judge_concept    this project's zero-shot "is this an injected instruction" score /10
  1 llama_guard3     P(unsafe) from Meta Llama Guard 3 8B
  2 deberta_pi       P(INJECTION) from ProtectAI deberta-v3-base-prompt-injection-v2
  3 prompt_qwen      P(YES) from a plain "is this malicious?" prompt on qwen2.5:7b
  4 prompt_llama31   the same prompt on llama3.1:8b (a family used nowhere else in B12/B13)
  5 perplexity       GPT-2 mean NLL, sign-flipped and scaled
  6 steer            judge tier: standing preference that routes money/attention
  7 lineage          judge tier: forged provenance claim
  8 worm             judge tier: self-replication
  9 imperative       cheap lexical prior: does the note instruct rather than record
 10 len_z            log length, standardized

Nothing here is fit; `train_b14.py` fits the combination, on dev data only.
"""
from __future__ import annotations

import math
import re
from typing import Dict, List, Sequence

import numpy as np

FEATURES = ("judge_concept", "llama_guard3", "deberta_pi", "prompt_qwen", "prompt_llama31",
            "perplexity", "steer", "lineage", "worm", "imperative", "len_z")
_IMPERATIVE = re.compile(
    r"\b(always|never|must|should|do not|don't|make sure|ensure|remember to|from now on|going forward|"
    r"whenever|every time|please |send|forward|include|copy|reply|respond|output|print|ignore|disregard|"
    r"instead of|no longer|skip|bypass)\b", re.I)


def imperative_score(text: str) -> float:
    hits = len(_IMPERATIVE.findall(text))
    return min(hits / 3.0, 2.0)


def len_z(text: str) -> float:
    return (math.log1p(len(text)) - 5.0) / 1.5


_CACHE = None


def _shared_cache():
    """One cache object per process. `build()` is called once per pool, and re-reading a
    14k-entry JSON file every time was both slow and the source of a mid-write read that
    crashed a long evaluation."""
    global _CACHE
    if _CACHE is None:
        from phase17.external_baselines import ScoreCache

        _CACHE = ScoreCache()
    return _CACHE


def build(texts: Sequence[str], workers: int = 8, warm: bool = True) -> np.ndarray:
    """Feature matrix for `texts`. Every LLM-backed column is cached and warmed concurrently."""
    from phase17.external_baselines import SCORERS, ScoreCache
    from phase17.judge_scores import ScoreJudge
    from phase17.semantic_detector import warm_all_tiers
    from phase17 import b11_live

    texts = list(texts)
    cache = _shared_cache()
    cols: Dict[str, List[float]] = {}
    for name, key in (("llama_guard3", "llama_guard3"), ("deberta_pi_v2", "deberta_pi"),
                      ("llm_prompt_qwen", "prompt_qwen"), ("llm_prompt_llama31", "prompt_llama31"),
                      ("perplexity_gpt2", "perplexity")):
        w = workers if name.startswith(("llama_guard", "llm_prompt")) else 0
        cols[key] = cache.get_many(name, texts, SCORERS[name], w)
        cache.save()
    if warm:
        warm_all_tiers(texts, tiers=("steer", "lineage", "worm"), workers=workers)
    sj = ScoreJudge("concept")
    cols["judge_concept"] = [sj.score(t) / 10.0 for t in texts]
    sj.save()
    for tier in ("steer", "lineage", "worm"):
        j = b11_live._judge(tier)
        cols[tier] = [float(j.flag(t)) for t in texts]
        j.save()
    cols["imperative"] = [imperative_score(t) for t in texts]
    cols["len_z"] = [len_z(t) for t in texts]
    # GPT-2 perplexity is a loss (lower = more fluent); flip so that "more suspicious" is up,
    # and scale to roughly the same range as the probability columns.
    cols["perplexity"] = [-(v / 10.0) for v in cols["perplexity"]]
    return np.column_stack([np.asarray(cols[f], dtype=float) for f in FEATURES])


__all__ = ["FEATURES", "build", "imperative_score", "len_z"]
