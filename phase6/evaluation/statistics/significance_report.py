"""Phase 6 P2 fix (2026-09-14) -- the single, enforced path for reporting
statistical significance across more than one Phase 6 comparison (per-attack,
per-B0-B7-configuration, or any other family of related hypothesis tests).

WHY THIS MODULE EXISTS
--------------------------------------------------------------------------------
The audit finding this closes: `multiple_comparisons.py`'s own docstring
explains exactly why Benjamini-Hochberg correction is needed here (Stage
6.10's per-attack integration and Stage 6.12's metrics protocol both imply
running the same test up to seven or eight times) -- but at the time of that
audit, `benjamini_hochberg()` was implemented and unit-tested, yet called by
NOTHING else in the repository (`run_b0_b7.py` and every other Phase 6
evaluation script only ever printed raw detection/false-positive rates, never
a hypothesis-test p-value or a "significant" claim at all). There was
therefore no uncorrected-significance-claim BUG yet, but also no enforced
PATH that would prevent one from being introduced the first time a script
does start reporting per-attack/per-configuration significance -- exactly the
gap this module closes, ahead of that need rather than after a real overclaim
has already shipped.

`report_family_significance()` is the ONE function any current or future
Phase 6 script should call to turn a family of `McNemarResult`s (or any other
same-shaped labeled raw p-values) into a significance report. It ALWAYS
routes every p-value through `benjamini_hochberg()` -- there is no code path
in this module that reports "significant" from a raw, uncorrected p-value.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence, Tuple

from phase6.evaluation.statistics.multiple_comparisons import BHResult, benjamini_hochberg
from phase6.evaluation.statistics.tests import McNemarResult


@dataclass(frozen=True)
class SignificanceReport:
    """One family of related comparisons, corrected together. `results`
    carries the full `BHResult` per label (raw p-value, BH-adjusted p-value,
    and the corrected significance call) -- never just a bare significant/not
    boolean, so a caller always has the raw value available for honest
    disclosure alongside the corrected one."""

    alpha: float
    results: Tuple[BHResult, ...]

    def significant_labels(self) -> Tuple[str, ...]:
        """Labels the family-wise-corrected procedure actually calls
        significant -- i.e. what a caller should report as "significant,"
        never `results` filtered on `raw_p_value < alpha` directly."""
        return tuple(r.label for r in self.results if r.significant)

    def to_report_lines(self) -> Tuple[str, ...]:
        lines = [
            f"Benjamini-Hochberg correction (alpha={self.alpha}), n={len(self.results)} comparisons:",
        ]
        for r in self.results:
            marker = "SIGNIFICANT" if r.significant else "not significant"
            lines.append(f"  {r.label:30} raw_p={r.raw_p_value:.4f}  adjusted_p={r.adjusted_p_value:.4f}  {marker}")
        return tuple(lines)


def report_family_significance(
    labeled_mcnemar_results: Mapping[str, McNemarResult], alpha: float = 0.05
) -> SignificanceReport:
    """The enforced entry point: takes a family of `McNemarResult`s (e.g. one
    per attack, or one per B0-B7 configuration), extracts each `p_value`, and
    ALWAYS applies `benjamini_hochberg()` before returning anything a caller
    could report as "significant." A caller with raw p-values from a
    different test family (not McNemar's) should use `report_family_significance_from_p_values()`
    below instead of calling `benjamini_hochberg()` directly -- both exist
    specifically so there is no path to a "significant" claim in Phase 6 that
    bypasses correction.
    """
    return report_family_significance_from_p_values(
        {label: result.p_value for label, result in labeled_mcnemar_results.items()}, alpha=alpha
    )


def report_family_significance_from_p_values(
    labeled_p_values: Mapping[str, float], alpha: float = 0.05
) -> SignificanceReport:
    """Same enforced correction, for a family of raw p-values not already
    wrapped in `McNemarResult` (e.g. a future non-McNemar test family)."""
    results = benjamini_hochberg(tuple(labeled_p_values.items()), alpha=alpha)
    return SignificanceReport(alpha=alpha, results=results)


__all__ = [
    "SignificanceReport",
    "report_family_significance",
    "report_family_significance_from_p_values",
]
