"""B18 = B13 OR B14 OR deberta@oracle -- adding back the signal B14's own fusion discards.

THE DIAGNOSTIC THAT MOTIVATED IT, and it is an unflattering one about B14. B14 fuses eleven
features, one of which IS ProtectAI's `deberta-v3-base-prompt-injection-v2`. On the clean
Mosscap hold-out, that single feature used on its own at an FPR-matched threshold scores 64.3%
while the whole eleven-feature fusion containing it scores 54.2%. **B14's learned weights
actively discard signal its own input provides**, which is what overfitting to the fitting
distribution looks like from the outside: the weights were fitted where deberta and the other
features agreed, so deberta's independent contribution was never worth much there, and
out-of-distribution it is worth a great deal.

So B18 restores it as a hard rule rather than a weighted feature. Measured per population from
already-saved raw decisions and cached baseline scores, with no new model calls:

    working on the FULL populations     own    ext-dev  ext-test  Mosscap   benign FPR
      B13                              46.1%   37.6%    71.5%    17.6%     1/1088
      B14                              41.2%   53.4%    90.8%    54.2%     2/1088
      B17 = B13 OR B14                 51.2%   56.0%    90.9%    54.2%     2/1088
      B18 = B17 OR deberta@oracle      51.4%   56.4%    93.0%    72.2%     3/1088

+18 points on the clean hold-out over B17, for one additional false positive in 1,088.

WHY THE ORACLE THRESHOLD AND NOT THE DEV ONE. deberta@dev scores higher still on Mosscap
(73.7%) but costs 9/1088 benign false positives against the oracle threshold's 1/1088. The
oracle threshold is the one matched to B12's false-positive rate, which is this project's
pre-existing convention for comparing a baseline against its own configs at equal cost -- so it
is chosen because it equalises FPR, which was decided before these numbers existed, NOT because
it scored better. Both are reported.

HONEST STATUS. Like B17, B18 was chosen after reading hold-out results, so the table above is
DESCRIPTIVE. Unlike B17, it is being validated: `holdout3_corpus.py` was built and frozen
before B18 was scored on anything, and `docs/phase17/PREREGISTRATION_HOLDOUT3.md` records the
prediction in advance. B18 introduces no fitted parameter of its own -- it reuses two frozen
configs and one frozen baseline threshold -- so what was selected is a combination, not a
decision boundary.

COST. B18 is B14's cost plus B13's plus one deberta forward pass: ~26.5s per memory, i.e. the
same order as B17 and ~155x B12. The deberta pass is the cheapest component of the three.

B18 IS STATELESS. For adaptive evasion it needs the rejection ledger, which
`rejection_memory.wrap_actions` now composes onto any config -- see `b16_live.py`.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence, Tuple

COMPONENTS = ("B13", "B14", "deberta_pi_v2@oracle")
_R5 = Path(__file__).parent / "data" / "eval_round5.json"
_SCORES = Path(__file__).parent / "data" / "external_baseline_scores.json"


def deberta_threshold() -> float:
    """The oracle threshold frozen in round 5, read rather than recomputed."""
    return float(json.loads(_R5.read_text(encoding="utf-8"))
                 ["baseline_thresholds"]["deberta_pi_v2"]["oracle"])


def _deberta_scores(texts: Sequence[str]) -> Dict[str, float]:
    """Cached where available, computed otherwise. One forward pass per uncached text."""
    cache = json.loads(_SCORES.read_text(encoding="utf-8")) if _SCORES.exists() else {}
    out, todo = {}, []
    for t in texts:
        k = "deberta_pi_v2:" + hashlib.sha256(t.encode("utf-8")).hexdigest()[:24]
        if k in cache:
            out[t] = cache[k]
        else:
            todo.append(t)
    if todo:
        from phase17.external_baselines import SCORERS

        fn = SCORERS["deberta_pi_v2"]
        for t in todo:
            out[t] = float(fn(t))
    return out


def b18_actions(items: Sequence[Tuple[str, str]], *,
                sources: Optional[Mapping[str, str]] = None, **kw) -> Dict[str, str]:
    from phase17.b17_live import b17_actions

    base = dict(b17_actions(items, sources=sources, **kw))
    thr = deberta_threshold()
    scores = _deberta_scores([t for _, t in items])
    rank = {"ALLOW": 0, "FLAG": 1, "QUARANTINE": 2, "BLOCK": 3}
    out: Dict[str, str] = {}
    for mid, text in items:
        a = base.get(mid, "ALLOW")
        hit = scores.get(text, 0.0) >= thr
        out[mid] = a if rank.get(a, 0) >= 2 or not hit else "QUARANTINE"
    return out
