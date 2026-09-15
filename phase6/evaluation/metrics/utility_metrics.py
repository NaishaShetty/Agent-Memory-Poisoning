"""Phase 6.12 -- Utility Metrics: URS and the reused-not-reimplemented
Phase 3 correctness family.

WHY ANSWERABILITY/SEMANTIC/TEMPORAL/MULTI-HOP CORRECTNESS ARE NOT REBUILT HERE
--------------------------------------------------------------------------------
Phase 3 already implements eight additive correctness metrics (exact match,
normalized, content recall, date-normalized, number-word-normalized, NLI
entailment, multi-reference, LLM judge -- Methodology Section 12.13),
including the NLI-entailment classifier that recovers 63.2% of the gap
between string-matching and semantic judgment, validated on held-out data.
Phase 6 REUSES these verbatim by running them on defended vs. baseline
answers -- it does not reimplement "semantic correctness" or "temporal
correctness" as new Phase 6 metrics, which would duplicate already-validated
machinery and risk silently drifting from it. `utility_retention_score()`
below is the one genuinely NEW Phase 6 metric: a ratio over whichever of
Phase 3's existing metrics the caller supplies, computed identically
regardless of which underlying metric is chosen.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UtilityRetentionResult:
    task_success_rate_baseline: float
    task_success_rate_defended: float
    urs: float


def utility_retention_score(task_success_rate_defended: float, task_success_rate_baseline: float) -> UtilityRetentionResult:
    """URS = TSR_defended / TSR_baseline.

    `task_success_rate_*` must each be computed using ONE of Phase 3's
    existing, frozen correctness metrics (Methodology Section 12.13) applied
    identically to both the defended and baseline conditions on the SAME
    task set -- never two different metrics compared against each other, and
    never a Phase-6-invented substitute metric.

    URS=1.0 means no utility loss; URS<1.0 means the defense cost some
    benign task success; URS>1.0 (possible, though not expected as a design
    goal) would mean the defense somehow improved benign task success --
    reported honestly either way, not clamped to make the number look like a
    pure "cost" always <= 1.

    Raises `ValueError` if `task_success_rate_baseline` is 0 -- undefined
    (and, if it ever occurred, would indicate Phase 3's OWN baseline is
    broken, a problem far outside Phase 6's scope to paper over with a
    special-cased return value).
    """
    if not (0.0 <= task_success_rate_defended <= 1.0):
        raise ValueError(f"task_success_rate_defended must be in [0, 1]; got {task_success_rate_defended}")
    if not (0.0 <= task_success_rate_baseline <= 1.0):
        raise ValueError(f"task_success_rate_baseline must be in [0, 1]; got {task_success_rate_baseline}")
    if task_success_rate_baseline == 0.0:
        raise ValueError("task_success_rate_baseline is 0 -- URS is undefined; investigate the baseline, do not default.")
    return UtilityRetentionResult(
        task_success_rate_baseline=task_success_rate_baseline,
        task_success_rate_defended=task_success_rate_defended,
        urs=task_success_rate_defended / task_success_rate_baseline,
    )
