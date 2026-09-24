"""Phase 14 -- real, measured per-component latency, including the
previously-missing Consolidation Guard (2026-09-23, explicitly authorized).

WHY THIS EXISTS
--------------------------------------------------------------------------------
`phase6/evaluation/metrics/cost_metrics.py` real `ComponentCostProfile`
entries for the admission/retrieval/propagation/sleeper guards mostly carry
`measured_latency_seconds=None` (honestly disclosed as unmeasured, not
fabricated as 0). The Consolidation Guard (Phase 12's fifth component) has NO
entry there at all -- it did not exist when that module was last touched.
This module measures real wall-clock latency for: (a) `_b1_action()`'s real
`evaluate_admission()` call, (b) `_b9_actions()`'s real full risk-composed
per-candidate decision (both from `phase14/defended_retrieval.py`, unmodified
here), and (c) a real `evaluate_consolidation()` call -- on THIS SAME real
local machine already used throughout Phases 12-14, over `N_TRIALS` real
repetitions, reporting mean and stdev. This does not modify `cost_metrics.py`;
Phase 14's own report cites these real numbers directly and recommends a new
`ComponentCostProfile` entry for the Consolidation Guard as a real, disclosed
follow-on to that module.
"""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass
from typing import Tuple

from phase6.defense.consolidation.consolidation_guard import evaluate_consolidation
from phase14.defended_retrieval import _b1_action, _b9_actions

N_TRIALS = 20

_SAMPLE_CONTENT = "Melanie signed up for her pottery class on 14 August 2023."
_SAMPLE_DISTRACTORS = (
    "Jon lost his job as a banker on January 19, 2023.",
    "Gina lost her job at Door Dash in January 2023.",
    "Caroline is now leaning toward social work as a career.",
)


@dataclass(frozen=True)
class LatencyResult:
    component_name: str
    n_trials: int
    mean_seconds: float
    stdev_seconds: float
    min_seconds: float
    max_seconds: float


def _time_n(fn, n: int) -> LatencyResult:
    samples = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - t0)
    return samples


def measure_b1_latency(n_trials: int = N_TRIALS) -> LatencyResult:
    samples = _time_n(lambda: _b1_action("sample", _SAMPLE_CONTENT), n_trials)
    return LatencyResult(
        component_name="B1 (evaluate_admission, live, Phase 14)", n_trials=n_trials,
        mean_seconds=statistics.mean(samples), stdev_seconds=statistics.pstdev(samples),
        min_seconds=min(samples), max_seconds=max(samples),
    )


def measure_b9_latency(n_trials: int = N_TRIALS) -> LatencyResult:
    items = (("sample", _SAMPLE_CONTENT),) + tuple((f"d{i}", d) for i, d in enumerate(_SAMPLE_DISTRACTORS))
    samples = _time_n(lambda: _b9_actions(items), n_trials)
    return LatencyResult(
        component_name="B9 (risk-composed, live, per-pool-of-4, Phase 14)", n_trials=n_trials,
        mean_seconds=statistics.mean(samples), stdev_seconds=statistics.pstdev(samples),
        min_seconds=min(samples), max_seconds=max(samples),
    )


def measure_consolidation_guard_latency(n_trials: int = N_TRIALS) -> LatencyResult:
    samples = _time_n(
        lambda: evaluate_consolidation(
            _SAMPLE_CONTENT, list(_SAMPLE_DISTRACTORS), run_id="phase14-latency", episode_id="e1",
            timestamp="2026-09-23T00:00:00Z", evidence_refs=("EVT-sample",),
        ),
        n_trials,
    )
    return LatencyResult(
        component_name="Consolidation Guard (evaluate_consolidation, Phase 12, first real latency measurement)",
        n_trials=n_trials, mean_seconds=statistics.mean(samples), stdev_seconds=statistics.pstdev(samples),
        min_seconds=min(samples), max_seconds=max(samples),
    )


def measure_all(n_trials: int = N_TRIALS) -> Tuple[LatencyResult, ...]:
    return (
        measure_b1_latency(n_trials),
        measure_b9_latency(n_trials),
        measure_consolidation_guard_latency(n_trials),
    )


if __name__ == "__main__":
    for r in measure_all():
        print(f"{r.component_name}: mean={r.mean_seconds*1000:.3f}ms stdev={r.stdev_seconds*1000:.3f}ms "
              f"min={r.min_seconds*1000:.3f}ms max={r.max_seconds*1000:.3f}ms (n={r.n_trials})")


__all__ = ["LatencyResult", "measure_b1_latency", "measure_b9_latency", "measure_consolidation_guard_latency", "measure_all"]
