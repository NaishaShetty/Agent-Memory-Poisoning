"""B12 -- stacked generalized live defense (Phase 17 fix round 4).

  1. language-safe B9 rule (G1);
  2. `StackedDetector` (embedding + judge logit, thresholds from leave-mechanism-out dev CV):
       score >= exclude threshold (0.5% dev FPR) -> QUARANTINE;
       score >= flag threshold (2% dev FPR) or `steer` -> ALLOW_WITH_RESTRICTION (never excluded);
  3. optional cross-memory conflict check (`conflict` = off | ordered | order_free), see b11_live.
Model = `phase17/data/stacked_model.json` (a few hundred numbers). Judge outputs are cached."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Sequence, Tuple

from phase6.defense.policy.states import ALLOW, ALLOW_WITH_RESTRICTION, QUARANTINE
from phase6.defense.risk.risk_score import GROUPED_GATED_ADMISSION_AND_RETRIEVAL_CORROBORATED

MODEL_PATH = Path(__file__).parent / "data" / "stacked_model.json"
_DET = None


def _detector():
    global _DET
    if _DET is None:
        from phase17.stacked_detector import StackedDetector

        _DET = StackedDetector.load(MODEL_PATH)
    return _DET


def b12_actions(items: Sequence[Tuple[str, str]], *, conflict: str = "off") -> Dict[str, str]:
    from phase14.defended_retrieval import _b9_actions
    from phase17 import b11_live

    actions = _b9_actions(items, GROUPED_GATED_ADMISSION_AND_RETRIEVAL_CORROBORATED)
    texts = [t for _, t in items]
    det = _detector()
    excl, flag = det.decide(texts, 0.005), det.decide(texts, 0.02)
    steer = b11_live._judge("steer")
    lineage = b11_live._judge("lineage")
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
    for (memory_id, text), e, f in zip(items, excl, flag):
        if actions[memory_id] in ("QUARANTINE", "BLOCK"):
            continue
        if e or lineage.flag(text) or conflicted.get(memory_id, False):
            actions[memory_id] = QUARANTINE
        elif (f or steer.flag(text) or contested.get(memory_id, False)) and actions[memory_id] == ALLOW:
            actions[memory_id] = ALLOW_WITH_RESTRICTION
    steer.save()
    lineage.save()
    return actions


__all__ = ["b12_actions"]
