"""Phase 6.11 -- sample-size / power calculation for McNemar's test, using
Connor's (1987) formula for the paired-sample design.

WHY THIS FORMULA, AND WHAT IT NEEDS AS INPUT
--------------------------------------------------------------------------------
Connor, R.J. (1987), "Sample size for testing differences in proportions for
the paired-sample design," Biometrics 43(1):207-211 -- the standard,
widely-cited closed-form sample-size formula for McNemar's test. It requires
two things Stage 6.9's real pilot data can actually estimate:

1. `p_discordant`: the expected PROPORTION OF PAIRS that will disagree
   between baseline and defended (i.e., the defense changes the outcome at
   all, in either direction).
2. `psi`: the odds ratio (b/c) among those discordant pairs -- how lopsided
   the disagreement is expected to be IN FAVOR of the defense. psi=1 means no
   real effect (as many pairs hurt as helped); larger psi means a stronger,
   easier-to-detect effect.

Formula:
    p_diff = p_discordant * (psi - 1) / (psi + 1)
    n = [ z_(1-alpha/2)*sqrt(p_discordant) + z_(1-beta)*sqrt(p_discordant - p_diff^2) ]^2 / p_diff^2

DO NOT GUESS p_discordant/psi FROM NOTHING -- Stage 6.11's protocol document
derives them from Stage 6.9's real pilot ablation numbers (disclosed as a
small-pilot-based estimate, not a firm prior), never invented arbitrarily.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from phase6.evaluation.statistics.intervals import _Z_SCORES


@dataclass(frozen=True)
class SampleSizeResult:
    p_discordant: float
    psi: float
    alpha: float
    power: float
    p_diff: float
    required_n: int


def mcnemar_sample_size(
    p_discordant: float, psi: float, *, alpha: float = 0.05, power: float = 0.8
) -> SampleSizeResult:
    """Connor's (1987) closed-form sample size for McNemar's test.

    Raises `ValueError` for `psi <= 1` (no directional effect to detect --
    the formula is undefined/degenerate there) or an out-of-range
    `p_discordant` (not in (0, 1]).
    """
    if not (0 < p_discordant <= 1):
        raise ValueError(f"p_discordant must be in (0, 1]; got {p_discordant}")
    if psi <= 1:
        raise ValueError(
            f"psi must be > 1 (an odds ratio of 1 or less has no directional "
            f"effect for this formula to size against); got {psi}"
        )
    confidence_level = 1 - alpha
    if confidence_level not in _Z_SCORES:
        raise ValueError(f"alpha must correspond to one of the supported confidence levels {sorted(_Z_SCORES)}; got alpha={alpha}")
    z_alpha = _Z_SCORES[confidence_level]

    # `power` is a one-sided concept (probability of correctly rejecting when
    # the effect is real) -- computed via the closed-form inverse normal CDF
    # rather than a second fixed lookup table, so this module can accept any
    # power value, not just a few pre-tabulated ones.
    z_beta = _inverse_normal_cdf(power)

    p_diff = p_discordant * (psi - 1) / (psi + 1)
    numerator = z_alpha * math.sqrt(p_discordant) + z_beta * math.sqrt(p_discordant - p_diff**2)
    n = (numerator**2) / (p_diff**2)

    return SampleSizeResult(
        p_discordant=p_discordant, psi=psi, alpha=alpha, power=power,
        p_diff=p_diff, required_n=math.ceil(n),
    )


def _inverse_normal_cdf(p: float) -> float:
    """Acklam's rational approximation to the inverse standard normal CDF
    (accurate to ~1.15e-9), used here only to convert a `power` fraction
    (e.g. 0.8, 0.9) into its corresponding one-sided z-score, since this
    module's callers specify power as a plain probability rather than
    picking from a small fixed table."""
    if not (0 < p < 1):
        raise ValueError(f"p must be in (0, 1); got {p}")
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00]
    p_low = 0.02425
    p_high = 1 - p_low
    if p < p_low:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
        )
    if p <= p_high:
        q = p - 0.5
        r = q * q
        return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (
            (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
        )
    q = math.sqrt(-2 * math.log(1 - p))
    return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
        (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
    )
