"""Phase 6.11 -- Benjamini-Hochberg false discovery rate correction.

WHY THIS IS NEEDED, AND WHY BENJAMINI-HOCHBERG SPECIFICALLY
--------------------------------------------------------------------------------
Stage 6.10's per-attack integration and Stage 6.12's metrics protocol both
imply running the SAME statistical test (McNemar's) once per attack (up to
seven times) and, within Stage 6.9's ablation, once per configuration (up to
eight B0-B7 conditions). Running eight independent hypothesis tests at
alpha=0.05 each, uncorrected, inflates the real family-wise false-positive
rate well above 5% (Rule 3: do not claim statistical significance without
appropriate statistical evidence -- an uncorrected multi-test claim is exactly
the kind of overclaim this guards against).

Benjamini-Hochberg (1995) controls the FALSE DISCOVERY RATE (expected
proportion of false positives AMONG the tests called significant), a less
conservative choice than a strict Bonferroni family-wise-error correction --
appropriate here because Phase 6's comparisons (seven attacks, or eight
ablation configurations) are related, non-independent hypotheses about the
same underlying defense, where Bonferroni's full conservatism would make an
already-small-sample campaign (Stage 6.11's own protocol) even less likely to
detect a real effect. This is a disclosed methodological choice, not asserted
as the only valid one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple


@dataclass(frozen=True)
class BHResult:
    label: str
    raw_p_value: float
    adjusted_p_value: float
    significant: bool


def benjamini_hochberg(labeled_p_values: Sequence[Tuple[str, float]], alpha: float = 0.05) -> Tuple[BHResult, ...]:
    """Benjamini-Hochberg step-up procedure.

    Given m tests with raw p-values, sorted ascending as p_(1) <= ... <= p_(m):
    find the largest k such that p_(k) <= (k/m) * alpha; every test with
    rank <= k is called significant. Adjusted p-values are computed via the
    standard monotone-enforced formula: q_(i) = min_{j>=i} (m/j) * p_(j),
    capped at 1.0.

    Raises `ValueError` for an empty input or any p-value outside [0, 1].
    """
    if not labeled_p_values:
        raise ValueError("labeled_p_values must be non-empty.")
    for label, p in labeled_p_values:
        if not (0.0 <= p <= 1.0):
            raise ValueError(f"p-value for {label!r} is out of [0, 1]: {p}")

    m = len(labeled_p_values)
    ordered = sorted(labeled_p_values, key=lambda item: item[1])

    # Adjusted p-values: monotone from the largest rank downward.
    adjusted = [0.0] * m
    running_min = 1.0
    for i in range(m - 1, -1, -1):
        rank = i + 1  # 1-based rank
        _, p = ordered[i]
        candidate = min(1.0, (m / rank) * p)
        running_min = min(running_min, candidate)
        adjusted[i] = running_min

    # Largest rank k with p_(k) <= (k/m)*alpha determines the significance
    # cutoff for ALL ranks <= k (step-up procedure).
    largest_significant_rank = 0
    for i in range(m):
        rank = i + 1
        _, p = ordered[i]
        if p <= (rank / m) * alpha:
            largest_significant_rank = rank

    results = []
    for i, (label, p) in enumerate(ordered):
        rank = i + 1
        results.append(
            BHResult(
                label=label, raw_p_value=p, adjusted_p_value=adjusted[i],
                significant=rank <= largest_significant_rank,
            )
        )
    return tuple(results)
