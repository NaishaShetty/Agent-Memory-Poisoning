"""Live `B15` — cheap content backbone + the signals nothing else has (round 6).

WHAT ROUND 5 ACTUALLY SHOWED, and why B14 is the wrong shape:

| system | recall (frozen test) | FPR | sec/memory |
|---|---|---|---|
| B14 | 90.8% | 0.84% | 28.73 |
| ProtectAI deberta-v3 prompt-injection-v2 | 84.6% | **0.13%** | **~0.02** |
| B12 | 66.2% | 0.39% | 0.16 |

B14 spends **179x B12's cost** to add six points over a single local forward pass, and it pays
for them with **6x deberta's false-positive rate**. Its two most expensive features (plain
"is this malicious?" prompts on two 8B models, plus Llama Guard 3) are the whole of that cost
and most of that FPR. Meanwhile the signals that are genuinely this project's own — provenance
trust, NLI corroboration against the user's own words, the self-replication and forged-lineage
tiers — are nearly free and reach things no content classifier can:

  * additive fabrication: content-only 0/72, corroboration 43/72 (pre-registered, p=2.3e-13);
  * defense-aware rewrites: content-only 4/47 for every config since round 3, corroboration
    28/47 when the conversation is available (p=1.2e-7);
  * self-replicating notes: 29/29 at 0 false positives on 1,125 benign items.

So B15 inverts B14's balance:

  1. **deberta-v3 as the content backbone** — one local forward pass, no ollama, no model
     swapping. Its score is used directly with thresholds calibrated on dev negatives.
  2. **The zero-false-positive rules kept as rules**, not fusion features: `worm`, `lineage`.
     (Round 5 found a learned fusion drove `worm`'s weight to -0.15 because the dev pool has
     almost no positives of it, discarding precision B13 already had.)
  3. **Provenance trust + NLI corroboration**, unchanged from B13 — the user's own words are
     never excluded, and an unsupported personal claim from an untrusted channel is.
  4. **The pool-level coordination signal**, which escalates only within a near-duplicate
     clique and so cannot fire on an isolated benign memory.
  5. **GPT-2 perplexity**, kept because it is local and it is what catches AgentPoison-style
     nonsense triggers (2/6 -> 5/6 under leave-one-source-out).
  6. **No `imperative` lexical prior.** B14's +1.46 weight on it made B14 *worse than every
     baseline* on legitimate standing instructions without provenance (4/40 vs 0/40) — a
     standing instruction is imperative by definition. Dropped.
  7. **No plain-LLM prompts, no Llama Guard.** They cost ~28s/memory between them and Llama
     Guard had the worst benign behaviour of anything measured (2.00% FPR, 11/34 on AgentDojo
     tool output).

Expected effect, stated before measuring: recall between deberta's and B14's, FPR at or below
deberta's, cost within an order of magnitude of B12's, and the corroboration-dependent wins
(additive fabrication, evasion) retained in full because those paths are untouched.

B15's content threshold is fitted by `train_b15.py` on DEV ONLY. Its evaluation hold-out is
`holdout2_corpus.py` (Mosscap), frozen before this file was written.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence, Tuple

import numpy as np

from phase6.defense.policy.states import ALLOW, ALLOW_WITH_RESTRICTION, QUARANTINE
from phase6.defense.risk.risk_score import GROUPED_GATED_ADMISSION_AND_RETRIEVAL_CORROBORATED

MODEL_PATH = Path(__file__).parent / "data" / "b15_model.json"
# CORRECTED (round 6, after reading B15's first dev fit): the first version used deberta +
# perplexity ALONE and scored 10.7% out-of-fold dev recall against B14's 45.7% -- four times
# worse on exactly the subtle synthetic poisoning this benchmark exists to study. deberta's
# 84.6% on the frozen test comes from that set being overt prompt injection, which is what it
# was trained for.
#
# The mistake was dropping `judge_concept` along with the expensive features. It is B12/B13's
# strongest own-population signal AND it is cached per text, so it was never part of the 179x
# cost -- that was Llama Guard plus the two plain-LLM prompts. B15 keeps the cheap strong
# signals and drops only the expensive ones:
#
#   kept    judge_concept (cached), deberta_pi (local), perplexity (local), steer/lineage/worm
#   dropped llama_guard3, llm_prompt_qwen, llm_prompt_llama31  (~28s/memory between them)
#   dropped imperative  (B14's +1.46 on it made it worse than every baseline on legitimate
#                        standing instructions without provenance)
FEATURES = ("judge_concept", "deberta_pi", "perplexity", "steer", "lineage", "worm", "len_z")
_MODEL = None


def _model() -> dict:
    global _MODEL
    if _MODEL is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"{MODEL_PATH} is missing -- run `python -m phase17.train_b15` first. B15 has no "
                "hardcoded fallback weights on purpose: scoring with weights that were never "
                "calibrated would silently be a different defense.")
        _MODEL = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    return _MODEL


def content_features(texts: Sequence[str]) -> np.ndarray:
    """Two local models plus judge signals this project already computes and caches. No Llama
    Guard, no plain-LLM prompts -- those were the whole of B14's per-memory cost."""
    from phase17 import b11_live
    from phase17.external_baselines import SCORERS, ScoreCache
    from phase17.fusion_features import len_z
    from phase17.judge_scores import ScoreJudge

    texts = list(texts)
    cache = ScoreCache()
    deb = cache.get_many("deberta_pi_v2", texts, SCORERS["deberta_pi_v2"], 0)
    ppl = cache.get_many("perplexity_gpt2", texts, SCORERS["perplexity_gpt2"], 0)
    cache.save()
    sj = ScoreJudge("concept")
    concept = [sj.score(t) / 10.0 for t in texts]
    sj.save()
    tiers = {}
    for tier in ("steer", "lineage", "worm"):
        j = b11_live._judge(tier)
        tiers[tier] = [float(j.flag(t)) for t in texts]
        j.save()
    return np.column_stack([
        np.asarray(concept, float), np.asarray(deb, float), -(np.asarray(ppl, float) / 10.0),
        np.asarray(tiers["steer"], float), np.asarray(tiers["lineage"], float),
        np.asarray(tiers["worm"], float), np.asarray([len_z(t) for t in texts], float)])


def scores(texts: Sequence[str]) -> np.ndarray:
    m = _model()
    X = content_features(texts)
    return 1.0 / (1.0 + np.exp(-(X @ np.asarray(m["coef"]) + m["intercept"])))


def b15_actions(
    items: Sequence[Tuple[str, str]], *, sources: Optional[Mapping[str, str]] = None,
    evidence: Optional[Sequence[str]] = None, evidence_names: Sequence[str] = (), conflict: str = "off",
) -> Dict[str, str]:
    from phase14.defended_retrieval import _b9_actions
    from phase17 import b11_live, b13_live
    from phase17.coordination_signal import coordinated_members

    m = _model()
    sources = sources or {}
    texts = [t for _, t in items]
    actions = _b9_actions(items, GROUPED_GATED_ADMISSION_AND_RETRIEVAL_CORROBORATED)
    s = scores(texts)
    t_excl, t_flag = float(m["thr"]["0.005"]), float(m["thr"]["0.02"])
    lineage_j, worm_j = b11_live._judge("lineage"), b11_live._judge("worm")
    coordinated = coordinated_members(items)

    conflicted: Dict[str, bool] = {}
    contested: Dict[str, bool] = {}
    if conflict == "ordered":
        from phase17.conflict_check import exclusions

        conflicted = exclusions(items, b11_live.CONFLICT_THRESHOLD, b11_live.SUPERSEDE_THRESHOLD,
                                b11_live.APPEAL_THRESHOLD)
    elif conflict == "order_free":
        from phase17.conflict_check import contested_pairs

        contested = contested_pairs(items, b11_live.CONFLICT_THRESHOLD, b11_live.SUPERSEDE_THRESHOLD,
                                    b11_live.APPEAL_THRESHOLD)
    elif conflict != "off":
        raise ValueError(f"conflict must be off/ordered/order_free, got {conflict!r}")

    support: Dict[str, float] = {}
    if evidence:
        cand = [(mid, t) for mid, t in items
                if sources.get(mid) not in b13_live.TRUSTED_SOURCES
                and b13_live.is_personal_claim(t, evidence_names)]
        if cand:
            for (mid, _), sc in zip(cand, b13_live.support_scores([t for _, t in cand], evidence)):
                support[mid] = sc

    for (memory_id, text), si in zip(items, s):
        trusted = sources.get(memory_id) in b13_live.TRUSTED_SOURCES
        sup = support.get(memory_id)
        hard = (actions[memory_id] in ("QUARANTINE", "BLOCK") or si >= t_excl
                or conflicted.get(memory_id, False)
                or lineage_j.flag(text) or worm_j.flag(text))
        if memory_id in coordinated and si >= t_flag:
            hard = True
        if sup is not None:
            # B13's corroboration rule, restored in full. B14's extra "must also be
            # behaviour-changing" condition was added to cut B13's 1.1% benign-exclusion cost
            # and it cost 17 points of evasion recall (28/47 -> 11/47). B15 instead reduces
            # that false-positive cost at its source -- `support_scores` now searches more of
            # the conversation, see train_b15.py -- rather than by weakening the rule.
            hard = hard or sup < b13_live.SUPPORT_EXCLUDE
            hard = hard or (sup < b13_live.SUPPORT_FLAG and bool(b13_live._PREFERENCE.search(text)))
        if trusted:
            actions[memory_id] = ALLOW_WITH_RESTRICTION if hard else ALLOW
            continue
        if hard:
            if actions[memory_id] not in ("QUARANTINE", "BLOCK"):
                actions[memory_id] = QUARANTINE
        elif (si >= t_flag or contested.get(memory_id, False)
              or (sup is not None and sup < b13_live.SUPPORT_FLAG)) and actions[memory_id] == ALLOW:
            actions[memory_id] = ALLOW_WITH_RESTRICTION
    lineage_j.save()
    worm_j.save()
    return actions


def guard_write(write_text: str, source_items, sources=None):
    from phase17.b13_live import guard_write as _g

    return _g(write_text, source_items, sources)


__all__ = ["b15_actions", "guard_write", "scores", "content_features", "FEATURES"]
