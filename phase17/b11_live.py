"""B11 -- generalized live defense (Phase 17 generalization fix).

  1. the language-safe B9 rule (`GROUPED_GATED_ADMISSION_AND_RETRIEVAL_CORROBORATED`);
  2. a language-independent LLM judge, two tiers selected on DEV only:
       `concept` YES -> QUARANTINE (excluded); `broad` YES -> ALLOW_WITH_RESTRICTION
       (flagged, never excluded, so it costs no utility) unless already stronger.
Judge outputs are cached by text hash (`judge_cache.json`) so runs are reproducible.
"""

from __future__ import annotations

from typing import Dict, Sequence, Tuple

from phase6.defense.policy.states import ALLOW, ALLOW_WITH_RESTRICTION, QUARANTINE
from phase6.defense.risk.risk_score import GROUPED_GATED_ADMISSION_AND_RETRIEVAL_CORROBORATED

_JUDGES: dict = {}


def _judge(variant: str):
    if variant not in _JUDGES:
        from phase17.semantic_detector import LLMJudge

        _JUDGES[variant] = LLMJudge(variant)
    return _JUDGES[variant]


# Conflict-without-supersession thresholds, fixed on DEV pairs only
# (`phase17/data/conflict_results.json`; Youden on `conflict_sets.json` dev split).
CONFLICT_THRESHOLD = 4.442226241342723
SUPERSEDE_THRESHOLD = 6.277336254599504
APPEAL_THRESHOLD = -4.996318947989494


def b11_actions(items: Sequence[Tuple[str, str]], *, conflict: str = "off") -> Dict[str, str]:
    """conflict = "off" (default) | "ordered" | "order_free".
    "ordered": `items` are in ADMISSION order (oldest first); a LATER memory that contradicts an earlier one
    without a valid update (specific change, no appeal to prior authority) is QUARANTINEd.
    "order_free": order unknown; both members of an unsupported conflicting pair are only RESTRICTED
    (flag / step-up confirmation), never excluded. Live retrieval order is not admission order (Track B
    retrieves the poison first), hence "off" by default."""
    from phase14.defended_retrieval import _b9_actions

    actions = _b9_actions(items, GROUPED_GATED_ADMISSION_AND_RETRIEVAL_CORROBORATED)
    concept, broad, steer, lineage = _judge("concept"), _judge("broad"), _judge("steer"), _judge("lineage")
    conflicted: Dict[str, bool] = {}
    contested: Dict[str, bool] = {}
    if conflict == "ordered":
        from phase17.conflict_check import exclusions

        conflicted = exclusions(items, CONFLICT_THRESHOLD, SUPERSEDE_THRESHOLD, APPEAL_THRESHOLD)
    elif conflict == "order_free":
        from phase17.conflict_check import contested_pairs

        contested = contested_pairs(items, CONFLICT_THRESHOLD, SUPERSEDE_THRESHOLD, APPEAL_THRESHOLD)
    elif conflict != "off":
        raise ValueError(f"conflict must be off/ordered/order_free, got {conflict!r}")
    for memory_id, text in items:
        if actions[memory_id] in ("QUARANTINE", "BLOCK"):
            continue
        if concept.flag(text) or lineage.flag(text) or conflicted.get(memory_id, False):
            actions[memory_id] = QUARANTINE
        elif (broad.flag(text) or steer.flag(text) or contested.get(memory_id, False)) and actions[memory_id] == ALLOW:
            actions[memory_id] = ALLOW_WITH_RESTRICTION
    concept.save(); broad.save(); steer.save(); lineage.save()
    return actions


__all__ = ["b11_actions"]
