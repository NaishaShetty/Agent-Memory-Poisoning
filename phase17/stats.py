"""Phase 17 -- small-n statistics, so ablation/generalization deltas are never
over-read (constraint (a)). Pure stdlib."""

from __future__ import annotations

import math
from typing import Sequence, Tuple


def wilson_interval(k: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def exact_mcnemar_p(b: int, c: int) -> float:
    """Two-sided exact McNemar test on discordant pair counts (b = detected
    only by A, c = detected only by B). p=1.0 when there are no discordant pairs."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def paired_delta(a: Sequence[bool], b: Sequence[bool]) -> dict:
    """Paired comparison of two per-record detection vectors (same records,
    same order): counts, discordant pairs, and the exact p-value."""
    assert len(a) == len(b)
    only_a = sum(1 for x, y in zip(a, b) if x and not y)
    only_b = sum(1 for x, y in zip(a, b) if y and not x)
    return {"n": len(a), "detected_a": sum(a), "detected_b": sum(b), "only_a": only_a, "only_b": only_b,
            "p_exact": exact_mcnemar_p(only_a, only_b)}


def cluster_bootstrap(outcomes: Sequence[bool], clusters: Sequence[str], n_boot: int = 5000, seed: int = 17) -> dict:
    """Cluster-robust rate and 95% interval: resample whole CLUSTERS (e.g.
    evasion variants grouped by parent record), so correlated variants of one
    parent are not counted as independent samples. Also returns the
    parent-level rate (fraction of clusters with at least one positive)."""
    import random

    groups: dict = {}
    for o, c in zip(outcomes, clusters):
        groups.setdefault(c, []).append(bool(o))
    keys = list(groups)
    rng = random.Random(seed)
    rates = []
    for _ in range(n_boot):
        sample = [groups[rng.choice(keys)] for _ in keys]
        flat = [x for g in sample for x in g]
        rates.append(sum(flat) / len(flat) if flat else 0.0)
    rates.sort()
    total = sum(len(g) for g in groups.values())
    return {
        "rate": sum(sum(g) for g in groups.values()) / total if total else 0.0, "n_records": total,
        "n_clusters": len(keys), "ci95_cluster": (rates[int(0.025 * n_boot)], rates[int(0.975 * n_boot) - 1]),
        "parents_with_any_positive": sum(1 for g in groups.values() if any(g)),
    }


def rate_with_ci(k: int, n: int) -> dict:
    lo, hi = wilson_interval(k, n)
    return {"k": k, "n": n, "rate": (k / n if n else 0.0), "ci95": (lo, hi)}


__all__ = ["wilson_interval", "exact_mcnemar_p", "paired_delta", "rate_with_ci", "cluster_bootstrap"]


class Underpowered(ValueError):
    pass


def min_achievable_p(m_discordant: int) -> float:
    """The smallest two-sided exact McNemar p obtainable from m discordant pairs (all one way)."""
    return exact_mcnemar_p(m_discordant, 0)


def require_power(n_at_risk: int, expected_event_rate: float, alpha: float = 0.05,
                  margin: float = 2.0) -> dict:
    """Refuse to run a paired test that cannot reach `alpha` even if the treatment works perfectly.

    WHY (round 7, unfavourable #9). The first pre-registered adaptive test drew seeds where the
    control arm produced ONE evasion event; with one discordant pair the smallest achievable
    p-value is 1.0, so the test was decided by its design before it ran and its falsification
    said nothing about the mechanism. Every pre-registered paired design now states its expected
    number of control events up front and calls this first. `margin` asks for that many times the
    bare minimum, because the realised count falls below its expectation about half the time.
    """
    need = 1
    while min_achievable_p(need) > alpha:
        need += 1
    expected = n_at_risk * expected_event_rate
    out = {"n_at_risk": n_at_risk, "expected_control_events": round(expected, 2),
           "min_events_for_alpha": need, "required_with_margin": need * margin, "alpha": alpha}
    if expected < need * margin:
        raise Underpowered(
            f"UNDERPOWERED DESIGN: {expected:.1f} expected control events; reaching p<{alpha} needs "
            f"at least {need} discordant pairs even with a perfect treatment, and this design asks "
            f"for {need * margin:.0f}. Pre-filter the seeds to the at-risk set or add seeds. "
            f"Detail: {out}")
    return out


# Noise floor for an n-item LLM-judged comparison: 5 points at n=120, scaled as 5*sqrt(120/n).
# (Relocated here 2026-10-12 so the formula's provenance cites a neutrally-named statistics module.)
NOISE_FLOOR_AT_120 = 5.0


def noise_floor_points(n: int) -> float:
    return NOISE_FLOOR_AT_120 * math.sqrt(120 / n)
