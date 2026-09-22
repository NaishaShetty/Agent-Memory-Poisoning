"""Phase 13 -- correlating attribution/propagation-side confidence against
Phase 12's admission-signal detection confidence (2026-09-22, explicitly
authorized).

WHY THIS EXISTS
--------------------------------------------------------------------------------
Phase 12's own report recommended checking whether a real poison scenario that
was only weakly flagged at admission time also attributes/propagates less
"confidently." This was never directly tested. Closed here using two REAL,
ALREADY-BUILT, continuous per-scenario numbers -- no new signal or scoring
mechanism is invented for this:

- ADMISSION-SIDE: `phase6.defense.risk.risk_score.compute_memory_risk_score()`
  (Phase 10's own real, already-shipped arithmetic over Stage 6.5's five real
  admission signals), applied to each of the 15 real poison scenarios' own
  real `content_text`.
- ATTRIBUTION/PROPAGATION-SIDE: attribution has NO numeric confidence field,
  by explicit, documented design (`attribution/ATTRIBUTION_METHODOLOGY.md`
  Section 6 -- rejected as misleading; every attribution question reduces to a
  discrete status). The closest real, already-computed CONTINUOUS analog on
  this framework's attribution/lineage side is `phase12.propagation.
  propagation_rate.compute_pr()`'s own real, position-robust
  `propagated_fraction` per scenario -- how consistently a scenario's real
  poison content persists into a real downstream derived summary across 4
  real tested context positions.

Pearson correlation is computed directly over these 15 real, paired values
with no external dependency (pure Python). Whatever correlation comes out is
reported as-is: this module does not choose which scenarios to include after
seeing the numbers, and does not re-run with a different signal choice to
chase a particular result. A near-zero or even negative correlation is a
real, legitimate, reportable outcome, not a failure of this module.

UPDATE (2026-09-22, explicitly authorized): the FIRST version of this module
used `compute_memory_risk_score()`'s own banded `risk_score` (GROUPED_GATED,
capped per-group at 0.25 shares) and PR's `propagated_fraction` (a
threshold-then-count-positions fraction). Both are REAL but, by design,
low-resolution for a *correlation* question specifically: `risk_score` bands
Stage 6.5's five underlying [0,1]-continuous signals down to a handful of
discrete levels, and `propagated_fraction` saturates at 1.0 for any scenario
that clears the propagation threshold at all 4 positions, discarding how far
above threshold it was. Both are the RIGHT choice for their own operational
purpose (a governance action band; a pass/fail propagation count) but a poor
choice for measuring whether two continuous quantities move together.

This module now ALSO computes a second, higher-resolution pairing using the
SAME real underlying measurements, one step upstream of the banding/
thresholding: the RAW SUM of Stage 6.5's five individual admission signal
scores (`decision.signals_used.values()`, each already a real, continuous
[0,1] density score -- no new signal invented, just not yet banded into
`risk_score`) against PR's own real MEAN `poison_similarity` across the 4
real tested positions (continuous, not thresholded into propagated/not).
Both real correlations are reported, not just the more favorable one.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from phase11.data.real_corpus import real_poison_scenarios
from phase12.propagation.propagation_rate import compute_pr
from phase3.evaluation.llm.provider import GenerationConfig, LLMProvider
from phase6.defense.admission.reasoning_guard import evaluate_admission
from phase6.defense.policy.states import UNASSESSED
from phase6.defense.risk.risk_score import compute_memory_risk_score
from phase6.defense.signals.contract import build_signal_context

TS = "2026-09-22T00:15:00+00:00"


def _admission_signals(scenario_id: str, content_text: str) -> Dict[str, float]:
    context = build_signal_context(
        memory_id=scenario_id, content_text=content_text, content_type="CONVERSATIONAL_FACT",
        memory_type="foundation", parent_ids=(), lifecycle_state="ACTIVE", creation_timestamp=TS,
    )
    decision = evaluate_admission(
        context, current_security_state=UNASSESSED, run_id="phase13-confidence-correlation",
        episode_id="e1", timestamp=TS, evidence_refs=(f"EVT-{scenario_id}",),
    )
    return dict(decision.signals_used)


def _admission_risk_score(scenario_id: str, content_text: str) -> float:
    """Real Stage 6.5 admission signals -> real Phase 10 risk arithmetic,
    exactly as `phase6.defense.orchestration.pipeline.py::_to_signal_context()`/
    `evaluate_pool()` already wire it, just exposing the raw continuous
    `risk_score` (that pipeline only exposes the discrete `.action`)."""
    signals = _admission_signals(scenario_id, content_text)
    return compute_memory_risk_score(scenario_id, signals).risk_score


def _admission_raw_signal_sum(scenario_id: str, content_text: str) -> float:
    """Sum of Stage 6.5's five real, continuous [0,1] admission signal scores,
    BEFORE `compute_memory_risk_score()`'s own group-banding -- higher
    resolution than `risk_score` for a correlation question specifically (see
    module docstring's 2026-09-22 update)."""
    return sum(_admission_signals(scenario_id, content_text).values())


def _pearson(xs: Tuple[float, ...], ys: Tuple[float, ...]) -> Optional[float]:
    n = len(xs)
    if n < 2:
        return None
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x == 0.0 or var_y == 0.0:
        return None  # no variance on one side -- correlation is undefined, never reported as 0.0
    return cov / math.sqrt(var_x * var_y)


@dataclass(frozen=True)
class ConfidenceCorrelationResult:
    per_scenario_admission_risk: Dict[str, float]
    per_scenario_propagation_fraction: Dict[str, float]
    pearson_r: Optional[float]
    per_scenario_admission_raw_signal_sum: Dict[str, float]
    per_scenario_mean_poison_similarity: Dict[str, float]
    pearson_r_high_resolution: Optional[float]
    n_scenarios: int


def compute_confidence_correlation(
    *, provider: Optional[LLMProvider] = None, config: Optional[GenerationConfig] = None,
) -> ConfidenceCorrelationResult:
    pool = real_poison_scenarios()
    admission_risk = {m.scenario_id: _admission_risk_score(m.scenario_id, m.content_text) for m in pool.memories}
    admission_raw_sum = {m.scenario_id: _admission_raw_signal_sum(m.scenario_id, m.content_text) for m in pool.memories}

    pr_result = compute_pr(provider=provider, config=config)
    propagation_fraction = {s.scenario_id: s.propagated_fraction for s in pr_result.per_scenario}
    mean_poison_similarity = {
        s.scenario_id: sum(p.poison_similarity for p in s.positions) / len(s.positions)
        for s in pr_result.per_scenario
    }

    common = [sid for sid in admission_risk if sid in propagation_fraction]
    xs = tuple(admission_risk[sid] for sid in common)
    ys = tuple(propagation_fraction[sid] for sid in common)

    xs_hr = tuple(admission_raw_sum[sid] for sid in common)
    ys_hr = tuple(mean_poison_similarity[sid] for sid in common)

    return ConfidenceCorrelationResult(
        per_scenario_admission_risk=admission_risk,
        per_scenario_propagation_fraction=propagation_fraction,
        pearson_r=_pearson(xs, ys),
        per_scenario_admission_raw_signal_sum=admission_raw_sum,
        per_scenario_mean_poison_similarity=mean_poison_similarity,
        pearson_r_high_resolution=_pearson(xs_hr, ys_hr),
        n_scenarios=len(common),
    )


if __name__ == "__main__":
    result = compute_confidence_correlation()
    print(f"n_scenarios={result.n_scenarios} pearson_r (banded/thresholded)={result.pearson_r}")
    print(f"pearson_r_high_resolution (raw signal sum / mean similarity)={result.pearson_r_high_resolution}")
    for sid in sorted(result.per_scenario_admission_risk):
        print(
            f"  {sid}: admission_risk={result.per_scenario_admission_risk[sid]:.3f} "
            f"propagated_fraction={result.per_scenario_propagation_fraction.get(sid)} "
            f"raw_signal_sum={result.per_scenario_admission_raw_signal_sum[sid]:.3f} "
            f"mean_poison_similarity={result.per_scenario_mean_poison_similarity.get(sid):.3f}"
        )


__all__ = ["ConfidenceCorrelationResult", "compute_confidence_correlation"]
