"""Phase 6.12 -- the Security-Utility Pareto relationship.

WHAT THIS DOES, AND WHY IT DOES NOT COLLAPSE THE TWO NUMBERS INTO ONE SCORE
--------------------------------------------------------------------------------
Section 19's own instruction is to evaluate the Pareto relationship between
security and utility, not to combine them into a single weighted score (which
would silently bake in a specific, arbitrary tradeoff preference no evidence
justifies). `pareto_frontier()` below returns which named configurations are
NON-DOMINATED (no other configuration is at least as good on both axes and
strictly better on one) -- the frontier itself, not a ranking.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple


@dataclass(frozen=True)
class ConfigurationPoint:
    """One named defense configuration's (security, utility) coordinates.
    Both axes are HIGHER-IS-BETTER by convention here -- callers must
    transform a lower-is-better security metric (e.g. PAR, FPR) into its
    complement (1 - PAR) before constructing this point, and this
    transformation must be stated explicitly wherever a point is built, never
    left implicit."""

    name: str
    security: float
    utility: float


def _dominates(a: ConfigurationPoint, b: ConfigurationPoint) -> bool:
    """True if `a` dominates `b`: at least as good on both axes, strictly
    better on at least one."""
    at_least_as_good = a.security >= b.security and a.utility >= b.utility
    strictly_better = a.security > b.security or a.utility > b.utility
    return at_least_as_good and strictly_better


def pareto_frontier(points: Sequence[ConfigurationPoint]) -> Tuple[ConfigurationPoint, ...]:
    """Returns the subset of `points` that is NOT dominated by any other
    point in the set -- the Pareto frontier. Order of the returned tuple
    matches the order configurations first appear in `points` (stable, not
    re-sorted by either axis, so a caller's own presentation order is
    preserved)."""
    if not points:
        raise ValueError("pareto_frontier: points must be non-empty.")
    frontier = []
    for candidate in points:
        if not any(_dominates(other, candidate) for other in points if other is not candidate):
            frontier.append(candidate)
    return tuple(frontier)
