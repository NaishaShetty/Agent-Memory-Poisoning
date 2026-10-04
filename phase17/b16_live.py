"""B16 = B15 + rejection memory (external review round 6, the adaptive-evasion item).

B15 and every config before it are STATELESS: each candidate memory is scored on its own text,
so the query-based adaptive attacker gets five independent attempts at a probabilistic detector
and needs one to land. Round 5/6 measured the result -- ~20% of the instances a config
initially excluded are recovered by the attacker within a budget of five rewrites, and B14's
170x cost barely moves that number, because per-item accuracy is not what is failing.

B16 adds the state: `phase17/rejection_memory.py`'s per-scope ledger of what was already
hard-mitigated. A candidate that is semantically within REJECT_SIM of a previous rejection in
the same scope is quarantined on that basis, whatever its own content score. The attacker's
constraint (the rewrite must still carry the claim) is what makes this work: a claim-preserving
paraphrase stays near what it paraphrases.

TWO DESIGN DECISIONS THAT KEEP THIS HONEST:

1. `ledger=None` means a FRESH, EMPTY ledger for that call. So on a first admission B16's
   decision is byte-identical to B15's, and B16's static recall equals B15's BY CONSTRUCTION --
   not as a claim I make, but as a property of the code. Only a caller that threads a
   persistent ledger (the adaptive attacker, or a real deployment) sees any difference. If a
   static evaluation ever shows B16 != B15, that is a bug, and
   `tests/test_working_set.py`-style guards in `test_rejection_memory.py` assert it.

2. The ledger records ONLY hard mitigations (QUARANTINE/BLOCK), never FLAG. A FLAG means the
   defense was unsure, and growing a blocking radius out of uncertainty is how a false-positive
   cascade starts.

The ledger is checked BEFORE the item is recorded, or every item would match itself.
"""
from __future__ import annotations

from typing import Dict, Mapping, Optional, Sequence, Tuple

LEDGER_REASON = "near_previous_rejection"


def b16_actions(
    items: Sequence[Tuple[str, str]], *, ledger=None, scope: str = "default",
    sources: Optional[Mapping[str, str]] = None, **kw,
) -> Dict[str, str]:
    from phase14.defended_retrieval import HARD_MITIGATION_ACTIONS
    from phase17.b15_live import b15_actions
    from phase17.rejection_memory import RejectionLedger, configured_reject_sim

    actions = dict(b15_actions(items, sources=sources, **kw))
    led = RejectionLedger(reject_sim=configured_reject_sim()) if ledger is None else ledger
    for mid, text in items:
        if actions.get(mid) not in HARD_MITIGATION_ACTIONS:
            near, _sim, _matched = led.check(text, scope)
            if near:
                actions[mid] = "QUARANTINE"
        led.observe(text, actions.get(mid, "ALLOW"), scope)
    return actions


def explain(items: Sequence[Tuple[str, str]], *, ledger=None, scope: str = "default", **kw) -> list:
    """Per-item diagnostics: what B15 said, what the ledger said, and which decided. Used by
    `eval_rejection_memory.py` so an improvement can be attributed rather than assumed."""
    from phase14.defended_retrieval import HARD_MITIGATION_ACTIONS
    from phase17.b15_live import b15_actions
    from phase17.rejection_memory import RejectionLedger, configured_reject_sim

    base = dict(b15_actions(items, **kw))
    led = RejectionLedger(reject_sim=configured_reject_sim()) if ledger is None else ledger
    rows = []
    for mid, text in items:
        b15 = base.get(mid, "ALLOW")
        near, sim, matched = led.check(text, scope)
        final = "QUARANTINE" if (b15 not in HARD_MITIGATION_ACTIONS and near) else b15
        rows.append({"id": mid, "b15_action": b15, "ledger_hit": bool(near),
                     "ledger_best_sim": round(sim, 4), "ledger_matched": matched[:120],
                     "final_action": final,
                     "decided_by": LEDGER_REASON if final != b15 else "b15",
                     "ledger_size": led.size(scope)})
        led.observe(text, final, scope)
    return rows
