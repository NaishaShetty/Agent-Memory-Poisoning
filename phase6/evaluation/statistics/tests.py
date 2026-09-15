"""Phase 6.11 -- McNemar's exact test for paired binary outcomes.

WHY THIS TEST, MATCHING EXISTING PROJECT PRECEDENT
--------------------------------------------------------------------------------
The Methodology Draft (Section 12.16) already used "a paired McNemar's exact
test... computed directly from stored per-task LLM-judge outcomes" to compare
plain vs. verified generation on the SAME tasks. Phase 6's own natural
comparison (baseline vs. defended, on the SAME task/memory/attack instance) is
structurally identical: a paired, binary (poison mitigated: yes/no) outcome
comparison. Reusing the same test family is a deliberate consistency choice,
not a default picked without reason.

McNemar's test only uses the DISCORDANT pairs (b = baseline-fail/defended-pass,
c = baseline-pass/defended-fail) -- concordant pairs (both same outcome)
carry no information about which condition is better and are correctly
excluded, exactly as the Methodology's own description does ("94 no-diff, 22
both-incorrect" in its own worked example).

The EXACT version (binomial test on b vs b+c under p=0.5), not the
chi-squared approximation, is used -- appropriate for the small sample sizes
this project's own campaigns actually produce (the Methodology's own example
had b+c=4; a chi-squared approximation is unreliable at that scale).
"""

from __future__ import annotations

from dataclasses import dataclass

from scipy.stats import binomtest


@dataclass(frozen=True)
class McNemarResult:
    b: int  # baseline-fail, defended-pass (defense helped)
    c: int  # baseline-pass, defended-fail (defense hurt)
    n_discordant: int
    n_concordant: int
    p_value: float


def mcnemar_exact_test(b: int, c: int) -> McNemarResult:
    """Exact two-sided McNemar's test: binomial test of `b` successes out of
    `b + c` trials against p=0.5. `b` and `c` are the two discordant-pair
    counts (module docstring); `n_concordant` is not needed for the test
    itself but is reported for full transparency about how many pairs were
    excluded and why.

    Returns `p_value=1.0` for `b == c == 0` (no discordant pairs at all --
    zero evidence either way, correctly the least significant possible
    result, not an error)."""
    if b < 0 or c < 0:
        raise ValueError(f"b and c must be non-negative; got b={b}, c={c}")
    n_discordant = b + c
    if n_discordant == 0:
        p_value = 1.0
    else:
        p_value = binomtest(b, n_discordant, 0.5, alternative="two-sided").pvalue
    return McNemarResult(b=b, c=c, n_discordant=n_discordant, n_concordant=-1, p_value=p_value)


def mcnemar_from_paired_outcomes(baseline_outcomes, defended_outcomes) -> McNemarResult:
    """Convenience constructor: given two same-length sequences of booleans
    (per-task "was the poison mitigated" outcome under baseline vs. defended,
    same task/memory/attack instance at each index), compute `b`, `c`, and
    the concordant count directly, then run the exact test."""
    if len(baseline_outcomes) != len(defended_outcomes):
        raise ValueError("baseline_outcomes and defended_outcomes must be the same length (paired design).")
    b = 0  # baseline False, defended True -- defense helped
    c = 0  # baseline True, defended False -- defense hurt
    concordant = 0
    for baseline, defended in zip(baseline_outcomes, defended_outcomes):
        if baseline == defended:
            concordant += 1
        elif defended and not baseline:
            b += 1
        else:
            c += 1
    result = mcnemar_exact_test(b, c)
    return McNemarResult(b=b, c=c, n_discordant=result.n_discordant, n_concordant=concordant, p_value=result.p_value)
