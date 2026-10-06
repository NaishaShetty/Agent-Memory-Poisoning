"""B20/B21: the union configurations without the rule that pins their false-positive floor.

THE PROBLEM (unfavourable #8). B17 = B13 OR B14 and B18 = B17 OR deberta@oracle exclude whenever
B13 excludes, so on injection-shaped benign text their false-positive rate cannot go below B13's
own -- 33.5% on hold-out 3 -- at any threshold of their B14 component. The per-rule attribution
(32.36; a hold-out measurement, see R7-1) put most of B13's false positives in its stacked
CONTENT detector, whose threshold was calibrated on conversational-memory negatives and fires on
long instruction-shaped prose. But B13 was put into the union for its PROVENANCE-SPECIFIC rules --
corroboration against the owner's conversation and the mechanism judges -- which reach
note-shaped poisoning that B14 misses. Its content detector duplicates what B14 already does, and
does it with a threshold fitted to the wrong distribution.

THE CANDIDATE, PARAMETER-FREE. Keep from B13 only the rules whose purpose is memory-poisoning
mechanisms, and let B14 own content detection:

    B20 = B14  OR  B13's {corroboration, unsupported-preference, worm judge, lineage judge}
    B21 = B20  OR  deberta >= the round-5 frozen oracle threshold        (the B18 analogue)

No threshold, weight or score is introduced: every component keeps the constant B13 froze on dev
before any hold-out existed. What IS chosen is which components to keep, and that choice was
motivated by a diagnosis made on hold-out-3 items, so B20/B21 are labelled hold-out-informed in
design. They are developed on DEV (`dev_round7.py`) and tested once on hold-outs 4 and 5, which
neither the diagnosis nor the design has touched.

`b13_components` reproduces B13's decision rule by rule; `dev_round7` asserts on real data that
the OR of the components equals B13's own exclusion item for item, so the decomposition is B13's
logic rather than a re-implementation of it.
"""
from __future__ import annotations

from typing import Dict, Mapping, Optional, Sequence, Tuple

KEPT = ("corroboration", "worm", "lineage")
RANK = {"ALLOW": 0, "ALLOW_WITH_RESTRICTION": 1, "FLAG": 1, "QUARANTINE": 2, "BLOCK": 3}


def b13_components(items: Sequence[Tuple[str, str]], *, sources: Optional[Mapping[str, str]] = None,
                   evidence: Optional[Sequence[str]] = None,
                   evidence_names: Sequence[str] = ()) -> Dict[str, Dict[str, bool]]:
    """Which of B13's hard-exclusion rules fire for each item (untrusted channels only)."""
    from phase14.defended_retrieval import _b9_actions
    from phase17 import b11_live
    from phase17.b12_live import _detector
    from phase17.b13_live import (GROUPED_GATED_ADMISSION_AND_RETRIEVAL_CORROBORATED, SUPPORT_EXCLUDE,
                                  SUPPORT_FLAG, TRUSTED_SOURCES, _PREFERENCE, _multilingual,
                                  is_personal_claim, support_scores)
    from phase17.stacked_detector import is_cjk

    sources = sources or {}
    base = _b9_actions(items, GROUPED_GATED_ADMISSION_AND_RETRIEVAL_CORROBORATED)
    texts = [t for _, t in items]
    excl = list(_detector().decide(texts, 0.005))
    cjk = [i for i, t in enumerate(texts) if is_cjk(t)]
    if cjk:
        ml_x = _multilingual().decide([texts[i] for i in cjk], 0.005)
        for i, x in zip(cjk, ml_x):
            excl[i] = excl[i] or x
    lineage, worm = b11_live._judge("lineage"), b11_live._judge("worm")
    support: Dict[str, float] = {}
    if evidence:
        cand = [(mid, t) for mid, t in items
                if sources.get(mid) not in TRUSTED_SOURCES and is_personal_claim(t, evidence_names)]
        for (mid, _), s in zip(cand, support_scores([t for _, t in cand], evidence)):
            support[mid] = s
    out = {}
    for (mid, text), e in zip(items, excl):
        s = support.get(mid)
        out[mid] = {
            "trusted": sources.get(mid) in TRUSTED_SOURCES,
            "base": base[mid] in ("QUARANTINE", "BLOCK"),
            "content": bool(e),
            "lineage": bool(lineage.flag(text)),
            "worm": bool(worm.flag(text)),
            "corroboration": bool((s is not None and s < SUPPORT_EXCLUDE)
                                  or (s is not None and s < SUPPORT_FLAG
                                      and _PREFERENCE.search(text))),
        }
        out[mid] = {k: bool(v) for k, v in out[mid].items()}     # numpy bools do not serialise
    lineage.save(); worm.save()
    return out


def b13_excluded_from_components(c: Dict[str, bool]) -> bool:
    return (not c["trusted"]) and any(c[k] for k in ("base", "content", "lineage", "worm", "corroboration"))


def b13_provenance_excluded(c: Dict[str, bool]) -> bool:
    return (not c["trusted"]) and any(c[k] for k in KEPT)


def b20_actions(items: Sequence[Tuple[str, str]], *, sources: Optional[Mapping[str, str]] = None,
                **kw) -> Dict[str, str]:
    from phase17.b14_live import b14_actions

    comps = b13_components(items, sources=sources, evidence=kw.get("evidence"),
                           evidence_names=kw.get("evidence_names", ()))
    b = b14_actions(items, sources=sources, **kw)
    out = {}
    for mid, _ in items:
        a = b.get(mid, "ALLOW")
        out[mid] = "QUARANTINE" if b13_provenance_excluded(comps[mid]) and RANK.get(a, 0) < 2 else a
    return out


def b21_actions(items: Sequence[Tuple[str, str]], *, sources: Optional[Mapping[str, str]] = None,
                **kw) -> Dict[str, str]:
    from phase17.b18_live import _deberta_scores, deberta_threshold

    base = b20_actions(items, sources=sources, **kw)
    thr = deberta_threshold()
    scores = _deberta_scores([t for _, t in items])
    return {mid: (a if RANK.get(a, 0) >= 2 or scores.get(t, 0.0) < thr else "QUARANTINE")
            for (mid, t), a in ((it, base.get(it[0], "ALLOW")) for it in items)}
