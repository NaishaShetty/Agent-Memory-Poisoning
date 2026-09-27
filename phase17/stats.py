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
