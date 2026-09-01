"""Phase 3.3-F -- formal statistical design for the A/B/C paired comparisons.

EXPERIMENTAL UNIT
--------------------------------------------------------------------------------
The unit of independent observation is the PAIRED TASK -- one real dataset task_id,
run once under each condition (A/B/C) with identical model/prompt/decoding
configuration, per `PHASE3_3_EXPERIMENTAL_SPEC.md`'s A/B/C control methodology
(unchanged, not modified by this stage). Repeated GENERATIONS of the SAME (task,
condition) pair are explicitly NOT counted as additional independent observations --
3.3-E's N=3 repeated run on one task produced IDENTICAL output all three times
(temperature=0, seed=42, fixed context), which is direct empirical evidence that, under
this fixed configuration, repeated generation is not a source of new information for the
purposes of a between-condition comparison (see `REPEATED_RUN_RATIONALE` below). Power
planning below is therefore expressed entirely in N_tasks, never in N_generations.

STATISTICAL DESIGN: McNemar's test (paired binary outcomes)
--------------------------------------------------------------------------------
Because the design is PAIRED (each task seen under multiple conditions, per
`PHASE3_3_EXPERIMENTAL_SPEC.md` Part 11), an independent-samples test (e.g. an
unpaired proportions z-test) would be a design error -- it would discard the pairing
structure and understate power. McNemar's test is the standard paired test for a binary
outcome (e.g. Strict TSR hit/miss, or canonical Answer Correctness) compared across two
conditions for the SAME tasks. This module implements ONLY the sample-size/power
calculation (a normal-approximation formula), not the test itself -- the actual
McNemar statistic on real campaign data is 3.3-G's job, once real N is collected.

WHY THIS STAGE CANNOT PRODUCE A SINGLE "RECOMMENDED N" WITHOUT CAVEATS
--------------------------------------------------------------------------------
3.3-E's pilot (n=5 tasks) is far too small to estimate the discordant-pair proportions
(p10, p01) McNemar's sample-size formula needs as INPUT -- attempting to estimate a
variance/effect size from 5 tasks and presenting it as a real estimate would be
manufacturing an effect size from insufficient data, which the mission explicitly
forbids. This module instead computes N across a SENSITIVITY TABLE of plausible
discordant-proportion scenarios (never a single fabricated point estimate), and
`recommend_n_tasks()` reports the recommendation AS a range with the scenario
assumptions stated alongside it, never as an unqualified single number.

FORMULA (Connor 1987 normal approximation for McNemar's test sample size):

    n = [ z_alpha/2 * sqrt(p10 + p01) + z_beta * sqrt(p10 + p01 - (p10 - p01)^2) ]^2
        / (p10 - p01)^2

where p10/p01 are the two discordant-pair proportions (condition-A-succeeds-B-fails and
vice versa) and (p10 - p01) is the effect size being detected. Standard z-values only
(alpha=0.05 two-sided, power=0.80/0.90) are supported -- this avoids implementing a
general inverse-normal-CDF from scratch for a one-off calculation; if a future stage
needs a different alpha/power, extend `Z_TABLE` explicitly rather than approximating.

MULTIPLE COMPARISONS
--------------------------------------------------------------------------------
Three pairwise comparisons are planned (A vs B, A vs C, B vs C) -- a Bonferroni
correction (dividing alpha by 3) is applied by default in `recommend_n_tasks()` to keep
the family-wise error rate at the nominal level, per the mission's explicit instruction
to consider multiple-comparison handling. This is the standard conservative choice, not
tuned to produce a convenient N.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Mapping, Tuple

# Two-sided alpha=0.05 and one-sided power values -- the only combinations supported
# without implementing a general inverse-normal-CDF (see module docstring).
Z_TABLE: Mapping[Tuple[float, float], Tuple[float, float]] = {
    # (alpha_two_sided, power): (z_alpha_over_2, z_power)
    (0.05, 0.80): (1.959964, 0.841621),
    (0.05, 0.90): (1.959964, 1.281552),
    (0.01, 0.80): (2.575829, 0.841621),
    (0.01, 0.90): (2.575829, 1.281552),
}

REPEATED_RUN_RATIONALE = (
    "3.3-E's N=3 repeated generation (task ecf5a096af5598393ce49c80, condition B, "
    "temperature=0/seed=42/fixed context) produced IDENTICAL answer text and IDENTICAL "
    "resolved failure_stage on all 3 runs -- direct empirical evidence that, under this "
    "fixed configuration, repeated generation of the SAME (task, condition) pair adds no "
    "new information for a between-condition comparison. Task replication (more distinct "
    "task_ids), not generation replication, is therefore the correct lever for "
    "statistical power in this design."
)


@dataclass(frozen=True)
class PowerScenario:
    label: str
    p10: float  # P(condition 1 succeeds, condition 2 fails)
    p01: float  # P(condition 1 fails, condition 2 succeeds)


def mcnemar_sample_size(
    p10: float, p01: float, alpha: float = 0.05, power: float = 0.80
) -> float:
    """Connor (1987) normal-approximation sample size for McNemar's test. Raises
    ValueError if p10 == p01 (zero effect size -- no finite sample size detects it) or
    if (alpha, power) is not in `Z_TABLE`."""
    if (alpha, power) not in Z_TABLE:
        raise ValueError(f"(alpha={alpha}, power={power}) not in Z_TABLE; extend it explicitly.")
    if p10 == p01:
        raise ValueError("p10 == p01 -- zero effect size, no finite N can detect it.")
    z_alpha, z_power = Z_TABLE[(alpha, power)]
    psum = p10 + p01
    d = p10 - p01
    numerator = (z_alpha * (psum ** 0.5) + z_power * ((psum - d ** 2) ** 0.5)) ** 2
    denominator = d ** 2
    return numerator / denominator


def sensitivity_table(
    scenarios: List[PowerScenario], alpha: float = 0.05, power: float = 0.80
) -> List[Mapping[str, object]]:
    rows = []
    for s in scenarios:
        n = mcnemar_sample_size(s.p10, s.p01, alpha=alpha, power=power)
        rows.append(
            {
                "scenario": s.label, "p10": s.p10, "p01": s.p01,
                "effect_size": abs(s.p10 - s.p01), "alpha": alpha, "power": power,
                "n_tasks_required": n,
            }
        )
    return rows


# Plausible discordant-proportion scenarios -- NOT estimated from the 5-task 3.3-E
# pilot (too small to estimate reliably; see module docstring). These are conventional,
# stated-as-assumptions planning scenarios spanning a small/medium/large paired effect,
# the standard approach when genuine pilot variance is unavailable.
DEFAULT_SCENARIOS: List[PowerScenario] = [
    PowerScenario("small effect (10pp), low discordance", p10=0.10, p01=0.00),
    PowerScenario("small effect (10pp), moderate discordance", p10=0.20, p01=0.10),
    PowerScenario("medium effect (20pp), moderate discordance", p10=0.30, p01=0.10),
    PowerScenario("medium effect (20pp), high discordance", p10=0.40, p01=0.20),
    PowerScenario("large effect (30pp), moderate discordance", p10=0.35, p01=0.05),
]


def recommend_n_tasks(
    scenarios: List[PowerScenario] = None, num_comparisons: int = 3, power: float = 0.80
) -> Mapping[str, object]:
    """Bonferroni-corrected (alpha/num_comparisons) sensitivity table across
    `scenarios` (default `DEFAULT_SCENARIOS`). Returns the FULL table plus the max
    (most conservative) and min (least conservative) N across scenarios -- never a
    single unqualified number.
    """
    scenarios = scenarios or DEFAULT_SCENARIOS
    corrected_alpha = 0.05 / num_comparisons
    # Only alpha=0.05 is in Z_TABLE pre-corrected; for num_comparisons=3 the corrected
    # alpha (~0.0167) is not itself in Z_TABLE, so this reports at the UNCORRECTED
    # alpha=0.01 entry (the closest available conservative bound) and states this
    # explicitly, rather than silently interpolating an unsupported z-value.
    used_alpha = 0.01 if num_comparisons > 1 else 0.05
    table = sensitivity_table(scenarios, alpha=used_alpha, power=power)
    ns = [row["n_tasks_required"] for row in table]
    return {
        "requested_bonferroni_alpha": corrected_alpha,
        "used_alpha_from_table": used_alpha,
        "note": (
            f"num_comparisons={num_comparisons} -> Bonferroni-corrected alpha would be "
            f"{corrected_alpha:.4f}; Z_TABLE only supports {{0.05, 0.01}} two-sided, so "
            f"the more conservative available entry (alpha=0.01) is used as an upper "
            f"bound on required N, not an exact match to {corrected_alpha:.4f}."
        ),
        "power": power,
        "table": table,
        "n_tasks_min_across_scenarios": min(ns),
        "n_tasks_max_across_scenarios": max(ns),
    }


__all__ = [
    "Z_TABLE",
    "REPEATED_RUN_RATIONALE",
    "PowerScenario",
    "mcnemar_sample_size",
    "sensitivity_table",
    "DEFAULT_SCENARIOS",
    "recommend_n_tasks",
]
