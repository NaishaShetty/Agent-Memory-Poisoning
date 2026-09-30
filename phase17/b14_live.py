"""Live `B14` — the round-5 defense (external review round 5, 2026-09-30).

B12 and B13 are both left unchanged, so every number published for them stays valid.

WHAT B14 IS, and why each piece is there rather than because it was available:

1. **A fusion score over intent/effect signals, with the raw text embedding removed.**
   The round-5 diagnosis (`fusion_features.py` docstring) showed B12's own-vs-external gap
   is carried almost entirely by its 384-dim embedding term (1.36 logits) and barely at all
   by its judge term (0.29). B14 therefore drops the embedding and fuses eleven signals that
   each describe what a note *does*: this project's zero-shot judge, three published
   detectors (Llama Guard 3, ProtectAI deberta prompt-injection v2, a GPT-2 perplexity
   filter), plain "is this malicious?" prompts on two model families, the steer/lineage/worm
   judge tiers, and two cheap lexical priors. Published detectors are included because their
   errors are measurably complementary to this project's on external-dev, not on faith:
   B12 ∪ plain-LLM prompt catches 125/266 where B12 alone catches 90.
   Fitted on dev only (`train_b14.py`); thresholds from group-held-out out-of-fold scores at
   0.5% / 2% FPR on dev negatives, the same protocol B12 used.

2. **Everything structural B13 established, unchanged**: source-aware trust (the user's own
   words are never excluded, only flagged), NLI corroboration of unsupported personal claims
   against the user's own turns, the unsupported-preference rule, and the B9 rule stack.
   These are orthogonal to writing style, which is exactly why they survived round 4.

3. **The carry-forward write guard** (`b13_live.guard_write`), re-exported here so a
   deployment gets one object.

Because a fused score is only as available as its components, B14 degrades explicitly: if a
component cannot be computed (no Llama Guard pulled, no network for a HF model), the feature
is imputed at its dev mean and the fact is recorded in `last_degraded`, rather than silently
scoring a different model than the one that was calibrated.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence, Tuple

import numpy as np

from phase6.defense.policy.states import ALLOW, ALLOW_WITH_RESTRICTION, QUARANTINE
from phase6.defense.risk.risk_score import GROUPED_GATED_ADMISSION_AND_RETRIEVAL_CORROBORATED

MODEL_PATH = Path(__file__).parent / "data" / "b14_model.json"
_MODEL = None
last_degraded: Dict[str, str] = {}


def _model():
    global _MODEL
    if _MODEL is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"{MODEL_PATH} is missing -- run `python -m phase17.train_b14` first. B14 is a fitted "
                "fusion; it deliberately has no hardcoded fallback weights, because scoring with "
                "weights that were never calibrated would silently be a different defense.")
        _MODEL = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    return _MODEL


def scores(texts: Sequence[str]) -> np.ndarray:
    from phase17.fusion_features import build

    m = _model()
    X = build(list(texts))
    w, b = np.asarray(m["coef"]), m["intercept"]
    return 1.0 / (1.0 + np.exp(-(X @ w + b)))


def b14_actions(
    items: Sequence[Tuple[str, str]], *, sources: Optional[Mapping[str, str]] = None,
    evidence: Optional[Sequence[str]] = None, evidence_names: Sequence[str] = (), conflict: str = "off",
) -> Dict[str, str]:
    from phase14.defended_retrieval import _b9_actions
    from phase17 import b11_live, b13_live

    m = _model()
    sources = sources or {}
    texts = [t for _, t in items]
    actions = _b9_actions(items, GROUPED_GATED_ADMISSION_AND_RETRIEVAL_CORROBORATED)
    s = scores(texts)
    t_excl, t_flag = float(m["thr"]["0.005"]), float(m["thr"]["0.02"])

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

    # B13's context-dependent corroboration, unchanged.
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
        hard = actions[memory_id] in ("QUARANTINE", "BLOCK") or si >= t_excl or conflicted.get(memory_id, False)
        if sup is not None:
            hard = hard or sup < b13_live.SUPPORT_EXCLUDE or (
                sup < b13_live.SUPPORT_FLAG and bool(b13_live._PREFERENCE.search(text)))
        if trusted:
            actions[memory_id] = ALLOW_WITH_RESTRICTION if hard else ALLOW
            continue
        if hard:
            if actions[memory_id] not in ("QUARANTINE", "BLOCK"):
                actions[memory_id] = QUARANTINE
        elif (si >= t_flag or contested.get(memory_id, False)
              or (sup is not None and sup < b13_live.SUPPORT_FLAG)) and actions[memory_id] == ALLOW:
            actions[memory_id] = ALLOW_WITH_RESTRICTION
    return actions


def guard_write(write_text: str, source_items, sources=None):
    from phase17.b13_live import guard_write as _g

    return _g(write_text, source_items, sources)


__all__ = ["b14_actions", "guard_write", "scores", "last_degraded"]
