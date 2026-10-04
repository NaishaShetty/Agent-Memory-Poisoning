"""B17 = B13 OR B14 -- the union, because they turned out to be complementary rather than ranked.

WHAT THE WORKING-ATTACK ANALYSIS SHOWED. Restricted to attacks that actually subvert an
undefended agent, B13 and B14 do not dominate one another; they fail on different things:

    own memory-poisoning attacks (482)   B13 46.7%   B14 39.4%   B13 wins, p=0.00013
    Mosscap, clean hold-out (64)         B13 12.5%   B14 62.5%   B14 STRICTLY dominates,
                                                                 +32 / -0, p=5e-10

B13's signals are provenance, NLI corroboration and the structural tiers -- they reach
fabricated preferences and invented standing policies, which is memory poisoning shaped like an
ordinary personal note. B14 fuses content classifiers trained on injection-shaped text. An
attack is usually one or the other, so the configs miss disjoint sets, and "which is better"
was the wrong question.

MEASURED FROM ALREADY-SAVED RAW DECISIONS, with no new model calls, because `eval_round6` now
persists per-item output (added for exactly this reason):

    working-attack recall    own     ext-dev   ext-test   Mosscap    ordinary-benign FPR
      B13                   46.7%     34.4%      61.6%     12.5%        1/1088  0.09%
      B14                   39.4%     49.4%      83.1%     62.5%        2/1088  0.18%
      B13 OR B14            51.5%     51.7%      83.4%     62.5%        2/1088  0.18%

Better than either on three groups, tied on the fourth, at B14's false-positive rate and not a
point worse. The union adds no new false positive at all: every benign item B13 excludes, B14
already excluded.

THE HONEST STATUS OF THESE NUMBERS, which matters more than the numbers. This union was chosen
AFTER reading hold-out results, so the figures above are DESCRIPTIVE, not a clean held-out
estimate -- the same status B15 carries on external_test, and for the same reason. Nothing was
refitted (both components are frozen and B17 adds no parameter, not even a threshold), so the
selection is of a combination rather than of a decision boundary, which is the mildest form of
this problem. It still needs a fresh hold-out before being reported as a generalisation claim.

COST IS THE REAL OBJECTION. B17 runs both, so it costs B14's ~26.4s per memory plus B13's
0.12s: ~155x B12. That buys +4.8 points over B13 on own attacks and +50 on Mosscap. For a
latency-sensitive admission path B13 alone remains the right choice; B17 is for deployments
where a missed poison costs more than 26 seconds.

B17 IS STATELESS, like everything except B16, so it does nothing about adaptive evasion.
Composing it with the rejection ledger is the obvious next step and is not done here.
"""
from __future__ import annotations

from typing import Dict, Mapping, Optional, Sequence, Tuple

COMPONENTS = ("B13", "B14")


def b17_actions(items: Sequence[Tuple[str, str]], *,
                sources: Optional[Mapping[str, str]] = None, **kw) -> Dict[str, str]:
    """Exclude if EITHER component excludes; otherwise take the stronger of the two actions.

    Deliberately not a new score to threshold: B17 introduces no parameter, so it cannot be
    accused of having been tuned on the hold-out that motivated it.
    """
    from phase17.b13_live import b13_actions
    from phase17.b14_live import b14_actions

    a = b13_actions(items, sources=sources, **kw)
    b = b14_actions(items, sources=sources, **kw)
    rank = {"ALLOW": 0, "FLAG": 1, "QUARANTINE": 2, "BLOCK": 3}
    # The stricter action of the two, which makes exclusion-if-either-excludes fall out
    # automatically, since QUARANTINE/BLOCK outrank ALLOW/FLAG.
    return {mid: max(a.get(mid, "ALLOW"), b.get(mid, "ALLOW"), key=lambda v: rank.get(v, 0))
            for mid, _ in items}
