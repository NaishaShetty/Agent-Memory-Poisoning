"""Phase 6.11 -- Wilson score confidence intervals for a binomial proportion.

WHY WILSON, NOT THE NAIVE NORMAL-APPROXIMATION INTERVAL
--------------------------------------------------------------------------------
The Methodology Draft's own Figure 3 (Section 12.16) already uses "95% Wilson
confidence intervals" for exactly this reason: the naive interval
(p +/- z*sqrt(p(1-p)/n)) behaves badly (can extend below 0 or above 1, and has
poor coverage) for small n or p near 0 or 1 -- exactly the regime Stage 6.9's
own small pilot corpora (n=9 poison, n=11 benign) and any realistic Phase 6
campaign scale fall into. Reusing the SAME interval method this project's own
prior work already established, rather than picking a different one, keeps
Phase 6's statistical reporting consistent with the rest of the paper.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ConfidenceInterval:
    point_estimate: float
    lower: float
    upper: float
    confidence_level: float
    n: int
    successes: int


# Standard normal quantiles for the two confidence levels this project uses
# (95%, matching the Methodology's own Figure 3; 90% as a documented,
# less conservative alternative Stage 6.11's protocol may cite).
_Z_SCORES = {0.90: 1.6448536269514722, 0.95: 1.959963984540054, 0.99: 2.5758293035489004}


def wilson_score_interval(successes: int, n: int, confidence_level: float = 0.95) -> ConfidenceInterval:
    """The Wilson score interval for a binomial proportion `successes/n`.

    Formula (Wilson, 1927):
        center = (p_hat + z^2/(2n)) / (1 + z^2/n)
        half_width = z * sqrt(p_hat(1-p_hat)/n + z^2/(4n^2)) / (1 + z^2/n)
        interval = center +/- half_width

    Raises `ValueError` for `n <= 0`, `successes < 0`, or `successes > n` --
    a malformed input must fail loudly, never silently clamp.
    """
    if n <= 0:
        raise ValueError(f"n must be positive; got {n}")
    if successes < 0 or successes > n:
        raise ValueError(f"successes must be in [0, n]; got successes={successes}, n={n}")
    if confidence_level not in _Z_SCORES:
        raise ValueError(f"confidence_level must be one of {sorted(_Z_SCORES)}; got {confidence_level}")

    z = _Z_SCORES[confidence_level]
    p_hat = successes / n
    denominator = 1 + z**2 / n
    center = (p_hat + z**2 / (2 * n)) / denominator
    half_width = (z * math.sqrt(p_hat * (1 - p_hat) / n + z**2 / (4 * n**2))) / denominator

    return ConfidenceInterval(
        point_estimate=p_hat,
        lower=max(0.0, center - half_width),
        upper=min(1.0, center + half_width),
        confidence_level=confidence_level,
        n=n,
        successes=successes,
    )
