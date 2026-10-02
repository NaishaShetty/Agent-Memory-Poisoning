"""Live `B13` -- B12 plus the fixes external review round 4 (2026-09-29) asked for.

B12 is left exactly as it was reviewed (`b12_live.py`, unchanged), so every published B12
number stays valid; everything new lives here. All thresholds below were set on DEV data
only (LoCoMo conversations 1-4, `dev_sets*.json`, the qwen-regenerated worm set, the even
half of the AgentDojo benign tool outputs) and frozen before the pre-registered test
(`docs/phase17/PREREGISTRATION_B13.md`).

What B13 adds, in the order the review listed them:

1. SOURCE-AWARE TRUST (the "single biggest structural improvement"). Each memory may carry
   the channel it arrived through (`provenance_sets.ALL_SOURCES`). The source comes from
   the system that wrote the memory, never from the memory's own text (text claiming to be
   from the user is exactly what `lineage` catches).
     - `user_turn` (the owner's own words): trusted. The soft flag tiers (stacked flag,
       `steer`) are skipped -- this is what "always CC my wife on invoices" needs -- and a
       hard hit is downgraded to ALLOW_WITH_RESTRICTION: the owner's words are never
       excluded, only flagged.
     - anything else, or unknown: untrusted. Full B12 checks, plus (2) and (3).
   A memory with NO recorded source is treated as untrusted, so B13 without provenance
   metadata degrades to "B12 + (3) + (4) + (5)", never to something weaker than B12.

2. CORROBORATION against the owner's own words (the Round-4 preference-corroboration idea,
   rebuilt on NLI because embedding similarity measures topic, not support: a contradiction
   is on-topic). For an untrusted memory that makes a PERSONAL claim about someone the
   owner's conversation is about, when owner turns are supplied as `evidence`: support =
   max NLI entailment probability from the owner's 5 most similar turns (and their top-3
   concatenation) to the memory. Below SUPPORT_EXCLUDE -> QUARANTINE; below SUPPORT_FLAG ->
   ALLOW_WITH_RESTRICTION, except an unsupported PREFERENCE claim, which is QUARANTINEd at
   SUPPORT_FLAG (preference hijack is where the measured harm is). This is the check that can reach additive fabrications
   (MPBench, 0/12 in the conflict check) and fabricated preferences: nothing contradicts
   them, but nothing the user said supports them either. External records (a calendar
   invite, an order confirmation) are not personal claims and are not subject to it.

3. `worm` judge tier (content): QUARANTINE a note that instructs the assistant to copy /
   re-insert itself into future memories or summaries.

4. CARRY-FORWARD GUARD (`guard_write`, behavioural): when the agent writes a summary or new
   memory, directive sentences derived from an untrusted source memory are dropped from the
   write, so an injected instruction cannot replicate through consolidation even if
   admission missed it. The reviewer's literal proposal (flag verbatim reappearance) was
   measured first and rejected on dev: the consolidator copies benign facts verbatim more
   often than worms (see `worm_replication.py`, `data/worm_replication_dev.json`).

5. Chinese: the union of the translate-then-score route and the multilingual-embedding
   route (measured, 0 benign exclusions on both native and machine-translated Chinese
   benign, `chinese_native_check.py`) replaces B12's translate-only route.
"""
from __future__ import annotations

import re
from typing import Dict, Mapping, Optional, Sequence, Tuple

import numpy as np

from phase6.defense.policy.states import ALLOW, ALLOW_WITH_RESTRICTION, QUARANTINE
from phase6.defense.risk.risk_score import GROUPED_GATED_ADMISSION_AND_RETRIEVAL_CORROBORATED

TRUSTED_SOURCES = ("user_turn",)
NLI_MODEL = "cross-encoder/nli-deberta-v3-xsmall"
# Frozen on DEV (LoCoMo conversations 1-4): the support scores at which 2% / 5% of the
# dataset's own benign observation memories fall below. See `b13_dev_calibration.py`.
SUPPORT_EXCLUDE = 0.0019
SUPPORT_FLAG = 0.0057
# An unsupported PREFERENCE claim is excluded at the (looser) flag threshold: on dev this
# took fabricated preferences from 9/32 to 25/32 excluded at 3/1026 benign observations
# (0.3%); `steer` alone reached only 4/32 because most planted preferences steer toward a
# brand or habit, not money.
_PREFERENCE = re.compile(
    r"\b(prefer|prefers|preferred|preference|favou?rite|loyal|always (?:uses?|goes|shops|orders|books|buys)|go-to|"
    r"recommends?|swears by|only (?:uses?|buys|trusts))\b", re.I)
CARRY_SIM = 0.6  # frozen on dev, worm_replication.py
# How much of the owner's conversation the corroboration check searches. Round 5's frozen
# evaluation found B13 excluding 17/1515 (1.1%) of LoCoMo's OWN benign derived memories --
# memories grounded in the conversation by construction -- because the turn that supports them
# was not among the 5 most similar. That is a retrieval miss, not a disagreement, so the fix is
# to search more of the conversation rather than to weaken the rule (which is what B14's
# two-signal condition did, at a cost of 17 points of evasion recall).
#
# Measured on dev (`train_b15.tune_support_retrieval()`, `data/b15_support_retrieval.json`) --
# an operating curve, not a single point, so a deployment can pick its own trade:
#
#   top_k   benign observations wrongly unsupported   dev fabrications caught
#       5                  21/1026  (2.05%)                   44/80
#      10                  12/1026  (1.17%)                   40/80
#      20                   5/1026  (0.49%)   <- default      36/80
#      40                   3/1026  (0.29%)                   33/80
#
# 20 is the default: it cuts the false-positive cost by 76% for 18% of the fabrication recall,
# which is the side the pre-registered failure condition cared about. The whole curve is
# published so the choice is visible rather than baked in.
SUPPORT_TOP_K = 20
_DIRECTIVE = re.compile(
    r"\b(should|must|always|never|make sure|remember to|be sure to|don't forget|do not forget|ensure|include|copy|"
    r"re-?insert|carry(?:ing)? forward|from now on|every time|whenever|going forward|preferred|prefers?|instead)\b",
    re.I)
_PERSONAL = re.compile(r"\b(the user|user's|i|i'm|i've|my|me|mine|he|she|his|her|they|their)\b", re.I)
_SENT = re.compile(r"(?<!\bDr)(?<!\bMr)(?<!\bMs)(?<!\bMrs)(?<=[.!?。])\s+")

_ML = None
_NLI = None


def _multilingual():
    global _ML
    if _ML is None:
        from phase17.multilingual_stacked import MultilingualDetector
        from phase17.tune_lomo import dev_pool

        pos, neg = dev_pool()
        _ML = MultilingualDetector()
        _ML.fit([x["text"] for x in pos + neg], [x["label"] for x in pos + neg], [x["group"] for x in pos + neg])
    return _ML


def _nli():
    global _NLI
    if _NLI is None:
        from sentence_transformers import CrossEncoder

        m = CrossEncoder(NLI_MODEL)
        ent = [i for i, lab in m.model.config.id2label.items() if lab.lower().startswith("entail")][0]
        _NLI = (m, ent)
    return _NLI


def is_personal_claim(text: str, names: Sequence[str] = ()) -> bool:
    """A claim about a person the owner's conversation is about (named) or about the user
    (first/third-person reference), as opposed to an external record."""
    low = text.lower()
    return any(n.lower() in low for n in names if n) or bool(_PERSONAL.search(text))


def support_scores(texts: Sequence[str], evidence: Sequence[str]) -> np.ndarray:
    """Max NLI entailment probability from the owner's own turns to each text."""
    from phase17.semantic_detector import _embed

    if not texts:
        return np.zeros(0)
    E, V = _embed(list(evidence)), _embed(list(texts))
    model, ent = _nli()
    out = []
    for t, v in zip(texts, V):
        top = np.argsort(-(E @ v))[:SUPPORT_TOP_K]
        prem = [evidence[i] for i in top] + [" ".join(evidence[i] for i in top[:3])]
        logits = model.predict([(p, t) for p in prem])
        pr = np.exp(logits - logits.max(1, keepdims=True))
        pr = pr / pr.sum(1, keepdims=True)
        out.append(float(pr[:, ent].max()))
    return np.asarray(out)


def b13_actions(
    items: Sequence[Tuple[str, str]], *, sources: Optional[Mapping[str, str]] = None,
    evidence: Optional[Sequence[str]] = None, evidence_names: Sequence[str] = (), conflict: str = "off",
) -> Dict[str, str]:
    from phase14.defended_retrieval import _b9_actions
    from phase17 import b11_live
    from phase17.b12_live import _detector
    from phase17.stacked_detector import is_cjk

    sources = sources or {}
    actions = _b9_actions(items, GROUPED_GATED_ADMISSION_AND_RETRIEVAL_CORROBORATED)
    texts = [t for _, t in items]
    det = _detector()
    excl, flag = det.decide(texts, 0.005), det.decide(texts, 0.02)
    cjk = [i for i, t in enumerate(texts) if is_cjk(t)]
    if cjk:
        ml = _multilingual()
        ml_x = ml.decide([texts[i] for i in cjk], 0.005)
        ml_f = ml.decide([texts[i] for i in cjk], 0.02)
        for i, x, f in zip(cjk, ml_x, ml_f):
            excl[i] = excl[i] or x
            flag[i] = flag[i] or f
    steer, lineage, worm = b11_live._judge("steer"), b11_live._judge("lineage"), b11_live._judge("worm")

    conflicted: Dict[str, bool] = {}
    contested: Dict[str, bool] = {}
    if conflict == "ordered":
        from phase17.conflict_check import exclusions

        conflicted = exclusions(items, b11_live.CONFLICT_THRESHOLD, b11_live.SUPERSEDE_THRESHOLD, b11_live.APPEAL_THRESHOLD)
    elif conflict == "order_free":
        from phase17.conflict_check import contested_pairs

        contested = contested_pairs(items, b11_live.CONFLICT_THRESHOLD, b11_live.SUPERSEDE_THRESHOLD, b11_live.APPEAL_THRESHOLD)
    elif conflict != "off":
        raise ValueError(f"conflict must be off/ordered/order_free, got {conflict!r}")

    support: Dict[str, float] = {}
    if evidence:
        cand = [(mid, t) for mid, t in items
                if sources.get(mid) not in TRUSTED_SOURCES and is_personal_claim(t, evidence_names)]
        for (mid, _), s in zip(cand, support_scores([t for _, t in cand], evidence)):
            support[mid] = s

    for (memory_id, text), e, f in zip(items, excl, flag):
        trusted = sources.get(memory_id) in TRUSTED_SOURCES
        hard = actions[memory_id] in ("QUARANTINE", "BLOCK")
        hard = hard or e or lineage.flag(text) or worm.flag(text) or conflicted.get(memory_id, False)
        s = support.get(memory_id)
        if trusted:
            # The owner's own words: never excluded, only flagged on a hard hit.
            actions[memory_id] = ALLOW_WITH_RESTRICTION if hard else ALLOW
            continue
        unsupported_pref = s is not None and s < SUPPORT_FLAG and bool(_PREFERENCE.search(text))
        if hard or (s is not None and s < SUPPORT_EXCLUDE) or unsupported_pref:
            if actions[memory_id] not in ("QUARANTINE", "BLOCK"):
                actions[memory_id] = QUARANTINE
        elif (f or steer.flag(text) or contested.get(memory_id, False) or (s is not None and s < SUPPORT_FLAG)) \
                and actions[memory_id] == ALLOW:
            actions[memory_id] = ALLOW_WITH_RESTRICTION
    steer.save(); lineage.save(); worm.save()
    return actions


def guard_write(write_text: str, source_items: Sequence[Tuple[str, str]],
                sources: Optional[Mapping[str, str]] = None) -> Tuple[str, Dict[str, float]]:
    """Carry-forward guard for summaries / new memories written by the agent. Drops every
    directive sentence of `write_text` whose closest untrusted source memory has embedding
    similarity >= CARRY_SIM; returns (guarded_text, {source_id: similarity} of what fired)."""
    from phase17.semantic_detector import _embed

    sources = sources or {}
    untrusted = [(mid, t) for mid, t in source_items if sources.get(mid) not in TRUSTED_SOURCES]
    sents = [s for s in _SENT.split(write_text) if s.strip()]
    if not sents or not untrusted:
        return write_text, {}
    S, U = _embed(sents), _embed([t for _, t in untrusted])
    sims = S @ U.T
    kept, fired = [], {}
    for i, sent in enumerate(sents):
        j = int(np.argmax(sims[i]))
        if sims[i, j] >= CARRY_SIM and _DIRECTIVE.search(sent):
            fired[untrusted[j][0]] = max(fired.get(untrusted[j][0], 0.0), float(sims[i, j]))
            continue
        kept.append(sent)
    return " ".join(kept), fired


__all__ = ["b13_actions", "guard_write", "support_scores", "is_personal_claim", "TRUSTED_SOURCES",
           "SUPPORT_EXCLUDE", "SUPPORT_FLAG", "CARRY_SIM"]
